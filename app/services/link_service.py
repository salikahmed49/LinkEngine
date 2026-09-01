import secrets
import string
import uuid
from datetime import datetime, timezone

from redis.exceptions import RedisError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CACHE_HITS, CACHE_MISSES, STREAM_EVENTS_PUBLISHED
from app.core.redis_client import redis_client
from app.models import ClickEvent, Link
from app.schemas import ClickEventResponse, ItemCount, LinkAnalyticsResponse, LinkCreate, LinkUpdate

logger = get_logger(__name__)
settings = get_settings()

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_GENERATION_RETRIES = 5
CACHE_PREFIX = "short_code:"


def invalidate_link_cache(short_code: str) -> None:
    """Removes the cached entry for a short code from Redis."""
    cache_key = f"{CACHE_PREFIX}{short_code}"
    try:
        redis_client.delete(cache_key)
        logger.debug(f"Invalidated cache for '{short_code}'")
    except RedisError as e:
        logger.warning(f"Failed to invalidate cache for '{short_code}': {e}")


def generate_short_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def create_link(db: Session, link_data: LinkCreate) -> Link:
    if link_data.custom_alias:
        # User specified custom alias
        code = link_data.custom_alias
        new_link = Link(
            short_code=code,
            original_url=str(link_data.original_url),
        )
        db.add(new_link)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError(f"short_code '{code}' already exists")

        db.refresh(new_link)
        logger.info(
            f"Created link with custom alias '{code}' -> {link_data.original_url}"
        )
        return new_link

    # Auto-generate with collision retries
    for attempt in range(1, MAX_GENERATION_RETRIES + 1):
        code = generate_short_code()
        new_link = Link(
            short_code=code,
            original_url=str(link_data.original_url),
        )
        db.add(new_link)

        try:
            db.commit()
            db.refresh(new_link)
            logger.info(
                f"Created link '{code}' on attempt {attempt} -> "
                f"{link_data.original_url}"
            )
            return new_link

        except IntegrityError:
            db.rollback()
            logger.warning(
                f"Short code collision on '{code}' "
                f"(attempt {attempt}/{MAX_GENERATION_RETRIES})"
            )

    raise RuntimeError(
        "Failed to generate a unique short code after multiple attempts. "
        "Please try again."
    )


def publish_click_event(
    short_code: str,
    user_agent: str | None = None,
    referrer: str | None = None,
    ip_address: str | None = None,
) -> str | None:
    """
    Publishes an immutable click event to the Redis Stream.
    Returns the generated Redis Stream entry ID, or None if publishing fails.
    """
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "short_code": short_code,
        "clicked_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": user_agent or "",
        "referrer": referrer or "",
        "ip_address": ip_address or "",
    }
    try:
        msg_id = redis_client.xadd(settings.redis_stream_name, event_payload)
        STREAM_EVENTS_PUBLISHED.inc()
        logger.debug(
            f"Published click event {event_payload['event_id']} for '{short_code}' to stream '{settings.redis_stream_name}' (ID: {msg_id})"
        )
        return msg_id
    except RedisError as e:
        logger.warning(f"Failed to publish click event to Redis Stream '{settings.redis_stream_name}': {e}")
        return None


def get_and_track_link(
    db: Session,
    short_code: str,
    user_agent: str | None = None,
    referrer: str | None = None,
    ip_address: str | None = None,
) -> str | None:
    """
    Decoupled Cache-aside redirect lookup + asynchronous event streaming.

    Cache HIT:
        Skip database read entirely. Publish click event to Redis Stream.
        Return cached original_url immediately.

    Cache MISS:
        SELECT from database, write-back to Redis cache with TTL,
        publish click event to Redis Stream, and return original_url.

    Returns the original_url string, or None if the short_code doesn't exist.
    """
    cache_key = f"{CACHE_PREFIX}{short_code}"

    # 1. Try Redis cache first
    try:
        cached_url = redis_client.get(cache_key)
    except RedisError as e:
        logger.warning(f"Redis get failed ({e}); falling back to database")
        cached_url = None

    if cached_url is not None:
        CACHE_HITS.inc()
        logger.debug(f"Cache HIT for '{short_code}'")
        # Publish click event asynchronously to stream (non-blocking)
        publish_click_event(short_code, user_agent, referrer, ip_address)
        return cached_url

    # 2. Cache MISS — lookup from database
    CACHE_MISSES.inc()
    logger.debug(f"Cache MISS for '{short_code}'")
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        return None

    # Write-back to Redis cache for subsequent hits
    try:
        redis_client.set(
            cache_key,
            link.original_url,
            ex=settings.redis_cache_ttl,
        )
        logger.debug(
            f"Cached '{short_code}' -> {link.original_url} (TTL: {settings.redis_cache_ttl}s)"
        )
    except RedisError as e:
        logger.warning(f"Failed to cache '{short_code}' in Redis: {e}")

    # Publish click event to stream (with graceful DB fallback if Redis is offline)
    msg_id = publish_click_event(short_code, user_agent, referrer, ip_address)
    if not msg_id:
        try:
            event = ClickEvent(
                event_id=str(uuid.uuid4()),
                short_code=short_code,
                clicked_at=datetime.now(timezone.utc),
                user_agent=user_agent,
                referrer=referrer,
                ip_address=ip_address,
            )
            db.add(event)
            link.click_count += 1
            db.commit()
            logger.debug(f"Direct DB fallback recorded click for '{short_code}'")
        except Exception as e:
            db.rollback()
            logger.warning(f"Direct DB fallback click record failed: {e}")

    return link.original_url


def get_link_stats(db: Session, short_code: str) -> Link | None:
    """Retrieves link analytics and metadata without incrementing the click counter."""
    return db.query(Link).filter(
        Link.short_code == short_code
    ).first()


def get_link_analytics(db: Session, short_code: str, limit: int = 50) -> LinkAnalyticsResponse | None:
    """Retrieves detailed click analytics including recent events, top referrers, and user agents."""
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        return None

    # Recent click events
    recent_db_events = (
        db.query(ClickEvent)
        .filter(ClickEvent.short_code == short_code)
        .order_by(ClickEvent.clicked_at.desc())
        .limit(limit)
        .all()
    )

    # Top referrers aggregation
    top_referrers_raw = (
        db.query(ClickEvent.referrer, func.count(ClickEvent.id))
        .filter(
            ClickEvent.short_code == short_code,
            ClickEvent.referrer.isnot(None),
            ClickEvent.referrer != "",
        )
        .group_by(ClickEvent.referrer)
        .order_by(func.count(ClickEvent.id).desc())
        .limit(5)
        .all()
    )
    top_referrers = [ItemCount(name=ref or "direct", count=cnt) for ref, cnt in top_referrers_raw]

    # Top user agents aggregation
    top_ua_raw = (
        db.query(ClickEvent.user_agent, func.count(ClickEvent.id))
        .filter(
            ClickEvent.short_code == short_code,
            ClickEvent.user_agent.isnot(None),
            ClickEvent.user_agent != "",
        )
        .group_by(ClickEvent.user_agent)
        .order_by(func.count(ClickEvent.id).desc())
        .limit(5)
        .all()
    )
    top_user_agents = [ItemCount(name=ua or "unknown", count=cnt) for ua, cnt in top_ua_raw]

    recent_events = [
        ClickEventResponse(
            event_id=ev.event_id,
            short_code=ev.short_code,
            clicked_at=ev.clicked_at,
            user_agent=ev.user_agent,
            referrer=ev.referrer,
            ip_address=ev.ip_address,
        )
        for ev in recent_db_events
    ]

    return LinkAnalyticsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        total_clicks=link.click_count,
        created_at=link.created_at,
        top_referrers=top_referrers,
        top_user_agents=top_user_agents,
        recent_events=recent_events,
    )


def update_link(
    db: Session,
    short_code: str,
    link_update: LinkUpdate,
) -> Link | None:
    """Updates target URL for an existing short code and invalidates the cache."""
    link = db.query(Link).filter(
        Link.short_code == short_code
    ).first()

    if not link:
        return None

    link.original_url = str(link_update.original_url)

    db.commit()
    db.refresh(link)

    invalidate_link_cache(short_code)

    logger.info(
        f"Updated link '{short_code}' -> {link.original_url} "
        f"and invalidated cache"
    )

    return link


def delete_link(db: Session, short_code: str) -> bool:
    """Deletes a short link and invalidates any cached redirect in Redis."""
    link = db.query(Link).filter(
        Link.short_code == short_code
    ).first()

    if not link:
        return False

    db.delete(link)
    db.commit()

    invalidate_link_cache(short_code)

    logger.info(
        f"Deleted link '{short_code}' and invalidated cache"
    )

    return True
