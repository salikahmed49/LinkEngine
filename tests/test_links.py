import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.redis_client import redis_client
from app.main import app
from app.models import ClickEvent, Link
from app.workers.click_consumer import ClickConsumer

settings = get_settings()

# In-memory SQLite database isolated for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database_and_redis():
    Base.metadata.create_all(bind=engine)
    redis_client.flushdb()
    yield
    Base.metadata.drop_all(bind=engine)
    redis_client.flushdb()


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data


def test_create_link_auto_generated(client):
    response = client.post("/links", json={"original_url": "https://example.com/some/long/path"})
    assert response.status_code == 201
    data = response.json()
    assert len(data["short_code"]) == 7
    assert data["original_url"] == "https://example.com/some/long/path"
    assert data["click_count"] == 0
    assert "created_at" in data


def test_create_link_custom_alias(client):
    response = client.post(
        "/links",
        json={"original_url": "https://example.com/docs", "custom_alias": "my-docs"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["short_code"] == "my-docs"
    assert data["original_url"] == "https://example.com/docs"
    assert data["click_count"] == 0


def test_create_duplicate_custom_alias_fails(client):
    payload = {"original_url": "https://example.com/1", "custom_alias": "duplicate"}
    res1 = client.post("/links", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/links", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_invalid_url_fails(client):
    response = client.post("/links", json={"original_url": "not-a-valid-url"})
    assert response.status_code == 422


def test_invalid_custom_alias_pattern(client):
    # Contains invalid character @
    response = client.post(
        "/links",
        json={"original_url": "https://example.com", "custom_alias": "bad@name"},
    )
    assert response.status_code == 422


def test_invalid_custom_alias_length(client):
    # Too short (< 3)
    response = client.post(
        "/links",
        json={"original_url": "https://example.com", "custom_alias": "ab"},
    )
    assert response.status_code == 422

    # Too long (> 10)
    response = client.post(
        "/links",
        json={"original_url": "https://example.com", "custom_alias": "verylongaliasname"},
    )
    assert response.status_code == 422


def test_redirect_and_event_publishing(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/target", "custom_alias": "target"},
    )
    assert create_res.status_code == 201

    # First redirect (Cache MISS -> publishes event to stream)
    redirect_res = client.get(
        "/target",
        headers={"User-Agent": "PytestClient/1.0", "Referer": "https://news.ycombinator.com"},
    )
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://example.com/target"

    # Second redirect (Cache HIT -> publishes event to stream)
    redirect_res2 = client.get(
        "/target",
        headers={"User-Agent": "PytestClient/2.0", "Referer": "https://google.com"},
    )
    assert redirect_res2.status_code == 307
    assert redirect_res2.headers["location"] == "https://example.com/target"

    # Verify 2 events are queued in Redis Stream
    stream_len = redis_client.xlen(settings.redis_stream_name)
    assert stream_len == 2

    # Process events with batch consumer worker
    consumer = ClickConsumer(block_ms=50)
    consumer.ensure_consumer_group()
    db = TestingSessionLocal()
    try:
        processed_count = consumer.consume_batch(db)
        assert processed_count == 2

        # Check aggregate stats
        stats_res = client.get("/links/target/stats")
        assert stats_res.status_code == 200
        assert stats_res.json()["click_count"] == 2

        # Check detailed analytics endpoint
        analytics_res = client.get("/links/target/analytics")
        assert analytics_res.status_code == 200
        analytics_data = analytics_res.json()
        assert analytics_data["total_clicks"] == 2
        assert len(analytics_data["recent_events"]) == 2
        assert len(analytics_data["top_referrers"]) == 2
    finally:
        db.close()


def test_consumer_idempotency(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/idempotent", "custom_alias": "idem"},
    )
    assert create_res.status_code == 201

    # Trigger a redirect to publish 1 stream event
    client.get("/idem")

    consumer = ClickConsumer(block_ms=50)
    consumer.ensure_consumer_group()
    db = TestingSessionLocal()
    try:
        # Read raw stream entries directly
        entries = redis_client.xrange(settings.redis_stream_name)
        assert len(entries) == 1

        # Process the entry first time
        count1 = consumer.process_entries(db, entries)
        assert count1 == 1

        # Process the EXACT same entry second time (simulating re-delivery)
        count2 = consumer.process_entries(db, entries)
        assert count2 == 0  # Deduplicated!

        # Total click_count in DB must remain 1, not 2
        link = db.query(Link).filter(Link.short_code == "idem").first()
        assert link.click_count == 1
    finally:
        db.close()


def test_consumer_crash_recovery_from_pel(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/pel-test", "custom_alias": "peltest"},
    )
    assert create_res.status_code == 201

    # Trigger redirect to publish event
    client.get("/peltest")

    consumer = ClickConsumer(consumer_name="worker-crash", block_ms=50)
    consumer.ensure_consumer_group()

    # Read message into PEL without acknowledging (simulating crash before processing)
    results = redis_client.xreadgroup(
        groupname=consumer.group_name,
        consumername=consumer.consumer_name,
        streams={consumer.stream_name: ">"},
        count=10,
    )
    assert len(results[0][1]) == 1

    # Verify message is in Pending Entries List
    pending_info = redis_client.xpending(consumer.stream_name, consumer.group_name)
    assert pending_info["pending"] == 1

    # Now recover using process_pending()
    db = TestingSessionLocal()
    try:
        recovered = consumer.process_pending(db)
        assert recovered == 1

        # Verify PEL is now empty after XACK
        pending_after = redis_client.xpending(consumer.stream_name, consumer.group_name)
        assert pending_after["pending"] == 0

        # Verify event was persisted and link click_count was updated
        link = db.query(Link).filter(Link.short_code == "peltest").first()
        assert link.click_count == 1
    finally:
        db.close()


def test_stats_does_not_increment_clicks(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/stats-test", "custom_alias": "statslink"},
    )
    assert create_res.status_code == 201

    # Query stats multiple times
    stats1 = client.get("/links/statslink/stats").json()
    stats2 = client.get("/links/statslink/stats").json()

    assert stats1["click_count"] == 0
    assert stats2["click_count"] == 0


def test_redirect_not_found(client):
    response = client.get("/nonexistent123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Short link not found"


def test_stats_not_found(client):
    response = client.get("/links/nonexistent123/stats")
    assert response.status_code == 404
    assert response.json()["detail"] == "Short link not found"


def test_analytics_not_found(client):
    response = client.get("/links/nonexistent123/analytics")
    assert response.status_code == 404
    assert response.json()["detail"] == "Short link not found"


def test_redirect_cache_ttl(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/ttl-test", "custom_alias": "ttltest"},
    )
    assert create_res.status_code == 201

    # Trigger cache miss and population
    res = client.get("/ttltest")
    assert res.status_code == 307

    # Check TTL on redis key
    ttl = redis_client.ttl("short_code:ttltest")
    assert ttl > 0
    assert ttl <= 86400


def test_cache_hit_skips_database_select(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/fast-redirect", "custom_alias": "fastlink"},
    )
    assert create_res.status_code == 201

    queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.strip().upper())

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        # First request -> Cache MISS: executes SELECT to fetch link
        queries.clear()
        res1 = client.get("/fastlink")
        assert res1.status_code == 307
        select_queries_miss = [q for q in queries if q.startswith("SELECT")]
        assert len(select_queries_miss) >= 1

        # Second request -> Cache HIT: executes ZERO queries on database (Read decoupled from DB)
        queries.clear()
        res2 = client.get("/fastlink")
        assert res2.status_code == 307
        select_queries_hit = [q for q in queries if q.startswith("SELECT")]
        assert len(select_queries_hit) == 0, f"Expected 0 SELECT queries on cache hit, got: {select_queries_hit}"
        assert len(queries) == 0, f"Expected 0 database queries on cache hit, got: {queries}"
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_update_link_invalidates_cache(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/original", "custom_alias": "updatelink"},
    )
    assert create_res.status_code == 201

    # Warm the cache
    client.get("/updatelink")
    assert redis_client.get("short_code:updatelink") == "https://example.com/original"

    # Update target URL
    update_res = client.patch(
        "/links/updatelink",
        json={"original_url": "https://example.com/new-destination"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["original_url"] == "https://example.com/new-destination"

    # Verify Redis cache was invalidated immediately
    assert redis_client.get("short_code:updatelink") is None

    # Next redirect points to new destination and repopulates cache
    redirect_res = client.get("/updatelink")
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://example.com/new-destination"
    assert redis_client.get("short_code:updatelink") == "https://example.com/new-destination"


def test_delete_link_invalidates_cache(client):
    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/to-delete", "custom_alias": "deletelink"},
    )
    assert create_res.status_code == 201

    # Warm the cache
    client.get("/deletelink")
    assert redis_client.get("short_code:deletelink") == "https://example.com/to-delete"

    # Delete link
    del_res = client.delete("/links/deletelink")
    assert del_res.status_code == 204

    # Verify Redis key deleted
    assert redis_client.get("short_code:deletelink") is None

    # Subsequent redirect returns 404
    get_res = client.get("/deletelink")
    assert get_res.status_code == 404


def test_stale_cache_self_healing(client):
    # Set a key directly in Redis that has no DB record
    redis_client.set("short_code:orphaned", "https://example.com/orphan")
    assert redis_client.get("short_code:orphaned") == "https://example.com/orphan"

    # Fast redirect succeeds via cache
    res = client.get("/orphaned")
    assert res.status_code == 307

    # When consumer worker runs and detects missing DB link, it cleans up the stale Redis entry
    consumer = ClickConsumer(block_ms=50)
    consumer.ensure_consumer_group()
    db = TestingSessionLocal()
    try:
        consumer.consume_batch(db)
        assert redis_client.get("short_code:orphaned") is None

        # Next redirect is a cache MISS and returns 404
        res2 = client.get("/orphaned")
        assert res2.status_code == 404
    finally:
        db.close()


def test_update_nonexistent_link(client):
    res = client.patch(
        "/links/nonexistent",
        json={"original_url": "https://example.com/new"},
    )
    assert res.status_code == 404


def test_delete_nonexistent_link(client):
    res = client.delete("/links/nonexistent")
    assert res.status_code == 404


def test_redis_failure_fallback(client, monkeypatch):
    from unittest.mock import MagicMock
    from redis.exceptions import ConnectionError as RedisConnectionError

    create_res = client.post(
        "/links",
        json={"original_url": "https://example.com/fallback", "custom_alias": "fallback"},
    )
    assert create_res.status_code == 201

    # Simulate Redis connection failure
    mock_redis = MagicMock()
    mock_redis.get.side_effect = RedisConnectionError("Redis connection refused")
    mock_redis.set.side_effect = RedisConnectionError("Redis connection refused")
    mock_redis.delete.side_effect = RedisConnectionError("Redis connection refused")
    mock_redis.xadd.side_effect = RedisConnectionError("Redis connection refused")

    monkeypatch.setattr("app.services.link_service.redis_client", mock_redis)

    # Redirect should still succeed via database fallback
    res = client.get("/fallback")
    assert res.status_code == 307
    assert res.headers["location"] == "https://example.com/fallback"


def test_prometheus_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "link_cache_hits_total" in response.text
    assert "link_cache_misses_total" in response.text
    assert "click_events_published_total" in response.text

