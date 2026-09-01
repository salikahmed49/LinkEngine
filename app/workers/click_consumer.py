import logging
import signal
import sys
import time
from collections import Counter
from datetime import datetime

from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import get_logger, setup_logging
from app.core.metrics import STREAM_EVENTS_CONSUMED, STREAM_PENDING_GAUGE
from app.core.redis_client import redis_client
from app.models import ClickEvent, Link

setup_logging()
logger = get_logger("click_consumer")
settings = get_settings()

_running = True


def _signal_handler(sig, frame):
    global _running
    logger.info("Shutdown signal received. Finishing current batch and exiting...")
    _running = False


class ClickConsumer:
    """
    Asynchronous event batch consumer for Redis Streams click analytics.

    Features:
    - Consumer group management with offset tracking
    - Batch consumption with configurable batch sizes and polling block timeouts
    - Crash recovery via Pending Entries List (PEL) processing on startup
    - Idempotent bulk inserts (deduplication by unique event_id)
    - Batch aggregate click_count incrementing in PostgreSQL/SQLite
    - Explicit XACK message acknowledgment
    """

    def __init__(
        self,
        stream_name: str | None = None,
        group_name: str | None = None,
        consumer_name: str = "worker-1",
        batch_size: int | None = None,
        block_ms: int | None = None,
    ):
        self.stream_name = stream_name or settings.redis_stream_name
        self.group_name = group_name or settings.redis_consumer_group
        self.consumer_name = consumer_name
        self.batch_size = batch_size or settings.consumer_batch_size
        self.block_ms = block_ms or settings.consumer_block_ms

    def ensure_consumer_group(self) -> None:
        """Creates the Redis stream consumer group if it does not already exist."""
        try:
            redis_client.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )
            logger.info(
                f"Created consumer group '{self.group_name}' on stream '{self.stream_name}'"
            )
        except RedisError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(
                    f"Consumer group '{self.group_name}' already exists on '{self.stream_name}'"
                )
            else:
                logger.error(f"Error creating consumer group: {e}")
                raise

    def process_entries(
        self, db: Session, raw_entries: list[tuple[str, dict[str, str]]]
    ) -> int:
        """
        Idempotently processes and bulk inserts a list of (message_id, data_dict) stream entries.
        """
        if not raw_entries:
            return 0

        msg_ids: list[str] = []
        parsed_events: list[dict] = []
        event_ids: set[str] = set()

        for msg_id, data in raw_entries:
            msg_ids.append(msg_id)
            event_id = data.get("event_id")
            short_code = data.get("short_code")
            clicked_at_str = data.get("clicked_at")

            if not event_id or not short_code or not clicked_at_str:
                logger.warning(f"Skipping malformed stream entry {msg_id}: {data}")
                continue

            try:
                clicked_at = datetime.fromisoformat(clicked_at_str)
            except ValueError:
                clicked_at = datetime.utcnow()

            parsed_events.append(
                {
                    "msg_id": msg_id,
                    "event_id": event_id,
                    "short_code": short_code,
                    "clicked_at": clicked_at,
                    "user_agent": data.get("user_agent") or None,
                    "referrer": data.get("referrer") or None,
                    "ip_address": data.get("ip_address") or None,
                }
            )
            event_ids.add(event_id)

        if not parsed_events:
            # Acknowledge all malformed messages so they aren't stuck in PEL
            if msg_ids:
                redis_client.xack(self.stream_name, self.group_name, *msg_ids)
            return 0

        # Deduplication check: filter out event_ids already persisted in the database
        existing_event_rows = (
            db.query(ClickEvent.event_id)
            .filter(ClickEvent.event_id.in_(list(event_ids)))
            .all()
        )
        existing_event_ids = {row[0] for row in existing_event_rows}

        new_events: list[ClickEvent] = []
        clicks_per_code: Counter[str] = Counter()

        for ev in parsed_events:
            if ev["event_id"] in existing_event_ids:
                logger.debug(
                    f"Duplicate event {ev['event_id']} detected; skipping DB insert"
                )
                continue

            new_events.append(
                ClickEvent(
                    event_id=ev["event_id"],
                    short_code=ev["short_code"],
                    clicked_at=ev["clicked_at"],
                    user_agent=ev["user_agent"],
                    referrer=ev["referrer"],
                    ip_address=ev["ip_address"],
                )
            )
            clicks_per_code[ev["short_code"]] += 1
            existing_event_ids.add(ev["event_id"])

        # Bulk insert new ClickEvent records
        if new_events:
            db.add_all(new_events)

            # Batch increment aggregate link click_counts
            for code, count in clicks_per_code.items():
                updated = (
                    db.query(Link)
                    .filter(Link.short_code == code)
                    .update(
                        {Link.click_count: Link.click_count + count},
                        synchronize_session=False,
                    )
                )
                if updated == 0:
                    from app.services.link_service import invalidate_link_cache

                    invalidate_link_cache(code)
                    logger.warning(
                        f"Orphaned link '{code}' detected in stream; removed stale Redis cache"
                    )

            db.commit()
            STREAM_EVENTS_CONSUMED.inc(len(new_events))
            logger.info(
                f"Persisted batch of {len(new_events)} click events across {len(clicks_per_code)} short codes"
            )

        # Acknowledge processed stream entries in Redis
        if msg_ids:
            redis_client.xack(self.stream_name, self.group_name, *msg_ids)

        return len(new_events)

    def process_pending(self, db: Session) -> int:
        """
        Drains unacknowledged pending messages from previous crashes or restarts (PEL).
        """
        total_recovered = 0
        try:
            pending_info = redis_client.xpending(self.stream_name, self.group_name)
            STREAM_PENDING_GAUGE.set(pending_info.get("pending", 0))
        except RedisError:
            pass

        while True:
            try:
                # ID "0" reads pending messages assigned to this consumer group
                results = redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: "0"},
                    count=self.batch_size,
                )
            except RedisError as e:
                logger.error(f"Failed to read pending messages from Redis: {e}")
                break

            if not results or not results[0][1]:
                break

            stream_entries = results[0][1]
            processed = self.process_entries(db, stream_entries)
            total_recovered += processed
            logger.info(
                f"Recovered and processed {len(stream_entries)} pending entries from PEL"
            )

            # If we received fewer than batch size, PEL is drained
            if len(stream_entries) < self.batch_size:
                break

        return total_recovered

    def consume_batch(self, db: Session) -> int:
        """
        Polls for new unread messages (ID '>') and processes them.
        """
        try:
            results = redis_client.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},
                count=self.batch_size,
                block=self.block_ms,
            )
        except RedisError as e:
            logger.warning(f"Error reading from Redis Stream: {e}")
            time.sleep(1)
            return 0

        if not results or not results[0][1]:
            return 0

        stream_entries = results[0][1]
        return self.process_entries(db, stream_entries)

    def run(self) -> None:
        """
        Main worker execution loop with crash recovery and graceful shutdown.
        """
        global _running
        self.ensure_consumer_group()
        logger.info(
            f"ClickConsumer '{self.consumer_name}' started. Listening on stream '{self.stream_name}' (group: '{self.group_name}')..."
        )

        # Initial crash recovery pass
        db = SessionLocal()
        try:
            recovered = self.process_pending(db)
            if recovered > 0:
                logger.info(f"Crash recovery complete. Recovered {recovered} events.")
        finally:
            db.close()

        while _running:
            db = SessionLocal()
            try:
                self.consume_batch(db)
            except Exception as e:
                logger.exception(f"Unexpected error during batch consumption: {e}")
                time.sleep(1)
            finally:
                db.close()

        logger.info("ClickConsumer stopped cleanly.")


def main():
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    consumer = ClickConsumer()
    consumer.run()


if __name__ == "__main__":
    main()
