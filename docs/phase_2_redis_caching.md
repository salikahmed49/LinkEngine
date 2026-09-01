# Phase 2: Redis Caching Layer & Invalidation

---

## 1. Concepts & Objectives

In high-throughput URL shorteners, the redirect endpoint (`GET /{short_code}`) experiences 95%+ read traffic. Querying PostgreSQL on every redirect introduces disk I/O, database connection pool contention, and high latency (~10–50ms).

Phase 2 introduces **In-Memory Caching with Redis 7** using the **Cache-Aside Pattern**:
1. **Cache Read**: Inspect Redis first.
2. **Cache HIT**: Return the cached target URL directly from memory in $<1\text{ms}$ with **0 database SELECT queries**.
3. **Cache MISS**: Read from PostgreSQL, write-back to Redis with a 24-hour TTL (`ex=86400`), and return.
4. **Active Cache Invalidation**: Purge cached keys immediately when a link is edited (`PATCH`) or deleted (`DELETE`) to prevent serving stale destinations.
5. **Graceful Degradation**: Fall back to direct database lookups if Redis is offline or unreachable.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Redis Connection Pool** | [`app/core/redis_client.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/redis_client.py) (`redis_client`) | Instantiates a shared `redis.Redis` client with `decode_responses=True` and connection pooling. |
| **Cache Configuration & TTL** | [`app/core/config.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/config.py#L17) (`redis_cache_ttl`) | Reads `REDIS_CACHE_TTL` from `.env` (defaulting to 86,400 seconds / 24 hours). |
| **Cache-Aside Lookup Logic** | [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L122-L180) (`get_and_track_link`) | Performs Redis `GET short_code:{code}`. On hit, bypasses SQL; on miss, queries SQL and issues `redis_client.set(..., ex=ttl)`. |
| **Active Cache Invalidation** | [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L22-L30) (`invalidate_link_cache`)<br>[`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L210-L245) (`update_link`, `delete_link`) | Calls `redis_client.delete(f"short_code:{short_code}")` immediately after committing SQL updates or deletes. |

---

## 3. Code Deep Dive

### 3.1 Cache-Aside Read Path
In [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L122-L180):

```python
def get_and_track_link(db: Session, short_code: str, ...) -> str | None:
    cache_key = f"short_code:{short_code}"

    # 1. Inspect Redis Cache First
    try:
        cached_url = redis_client.get(cache_key)
    except RedisError as e:
        logger.warning(f"Redis get failed ({e}); falling back to database")
        cached_url = None

    # Cache HIT: Zero DB queries executed
    if cached_url is not None:
        publish_click_event(short_code, ...)  # Non-blocking async stream
        return cached_url

    # 2. Cache MISS: Query PostgreSQL
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link:
        return None

    # Write-back to Redis for subsequent hits
    try:
        redis_client.set(cache_key, link.original_url, ex=settings.redis_cache_ttl)
    except RedisError as e:
        logger.warning(f"Failed to cache '{short_code}' in Redis: {e}")

    publish_click_event(short_code, ...)
    return link.original_url
```

---

## 4. Key Architectural Takeaways

1. **Why Cache-Aside instead of Write-Through**:
   - Write-Through caches every created link immediately, caching URLs that might never be visited.
   - Cache-Aside is lazy: only links that are actively requested get loaded into memory, maximizing RAM efficiency.
2. **Why TTL is Crucial**:
   - Setting `ex=86400` ensures that dormant links naturally expire out of Redis, preventing memory exhaustion on platforms with millions of shortened links.
3. **Resilience to Cache Failures**:
   - Wrapping all Redis operations in `try...except RedisError` guarantees that if Redis crashes or is restarted, the application continues to serve redirects via PostgreSQL without failing requests.
