# Master Architecture Deep Dive: Everything You Need to Understand

This guide explains the foundational distributed systems concepts, architectural decisions, and failure modes implemented throughout the **Link Analytics Platform**.

---

## 1. High-Level Architecture & Lifecycle

```text
[ Client Request ] ────► [ Nginx Gateway:8000 ] (Per-IP Rate Limiting: 10r/s)
                                │
                                ▼ (Round-Robin Load Balancing)
                       [ FastAPI Replicas: api_1, api_2, api_3 ]
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[ Cache-Aside Read Path: <1ms ]               [ Async Write Path: Stream ]
Check Redis: short_code:{code}                XADD clicks:stream payload
  ├─ HIT: return original_url                   │
  └─ MISS: SELECT Postgres -> SET Redis         ▼
                                         [ ClickConsumer Worker ]
                                         XREADGROUP analytics_group
                                                │ (Deduplication by UUID)
                                                ▼
                                         [ PostgreSQL Database ]
                                         Bulk INSERT click_events
                                         Batch UPDATE links.click_count
                                                │
                                                ▼
                                         XACK clicks:stream (Remove from PEL)
```

---

## 2. The 7 Core Architectural Principles

### 1. Read Path vs. Write Path Decoupling
- **The Problem**: A URL shortener is a read-heavy system (e.g. 95% reads, 5% writes). If you write to the database synchronously on every redirect, thousands of concurrent users hitting the same link will trigger row-level lock contention on `links.click_count` and disk I/O bottlenecks.
- **The Solution**: The redirect endpoint never touches the database on a cache hit. It pushes an event to an in-memory stream (`XADD`) in microseconds and immediately redirects the user (`HTTP 307`). The database write happens in batches in the background.

---

### 2. Cache-Aside Pattern & Active Invalidation
- **Cache-Aside (Lazy Loading)**: Data is only loaded into Redis when requested. This saves memory by ensuring unvisited links don't consume RAM.
- **TTL (Time-To-Live)**: Every cached key expires after 24 hours (`ex=86400`), automatically reclaiming memory from inactive links.
- **Active Invalidation**: When a link is updated (`PATCH`) or deleted (`DELETE`), the application explicitly deletes the cached Redis key (`invalidate_link_cache`) so stale destinations are never served.

---

### 3. Redis Streams vs. Pub/Sub vs. Kafka
- **Why Not Redis Pub/Sub?**: Pub/sub is "fire-and-forget" with no persistence. If the consumer worker is restarting or offline when a click happens, that click event is permanently lost.
- **Why Redis Streams?**: Redis Streams provides durable event logs, consumer group offset tracking, and acknowledgment tracking (`XACK`).
- **Why Not Kafka?**: Redis Streams gives us the required streaming and consumer group capabilities without the heavy infrastructure overhead of running Apache Kafka and ZooKeeper/KRaft.

---

### 4. At-Least-Once Delivery & Idempotency
- **The Challenge**: Network glitches or worker restarts can cause a message to be re-delivered from the stream.
- **The Solution**: Every click event is generated with a unique `event_id` (UUID4). Before inserting a batch, `ClickConsumer` queries:
  ```python
  existing_ids = db.query(ClickEvent.event_id).filter(ClickEvent.event_id.in_(batch_ids)).all()
  ```
  Any event already in PostgreSQL is skipped, ensuring that even if a message is delivered multiple times, it is only recorded once (**Idempotent Processing**).

---

### 5. Crash Recovery with the Pending Entries List (PEL)
- When a worker reads a message via `XREADGROUP`, Redis marks it as "pending" in the PEL.
- If the worker crashes before calling `XACK`, the message remains in the PEL.
- When the worker restarts, `process_pending()` reads from stream ID `0` to drain all unacknowledged messages first before reading new events (`>`).

---

### 6. Leaky Bucket Rate Limiting (Nginx)
- Configured using `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;`.
- Tracks IP addresses in a memory-efficient 4-byte binary format.
- `burst=20 nodelay`: Allows users to open several links at once without throttling, while rejecting sustained traffic over 10 requests/second with `HTTP 429 Too Many Requests`.

---

### 7. Observability via the RED Method
- **Rate**: Request throughput (RPS) broken down by status code.
- **Errors**: Number of 4xx and 5xx responses.
- **Duration**: Latency percentiles ($p50, p95, p99$) tracked via Prometheus histograms.
- **Cache Hit Rate %**: Gauge monitoring the ratio of cache hits vs misses.

---

## 3. Failure Mode & Resilience Matrix

| Failure Scenario | What Happens | How the System Handles It |
|---|---|---|
| **Redis Goes Offline** | Cache lookup & stream publish fail. | All Redis calls are wrapped in `try...except RedisError`. The redirect endpoint automatically falls back to direct PostgreSQL queries. |
| **FastAPI Replica Crashes** | A container terminates unexpectedly. | Nginx detects the connection drop via `proxy_next_upstream` and seamlessly routes the client's request to a healthy replica. |
| **ClickConsumer Worker Crashes** | Unacknowledged messages remain in memory. | Redis keeps unacknowledged messages in the PEL. Upon restart, `process_pending()` reads ID `0` and processes them with zero data loss. |
| **Auto-Generated Code Collision** | Random 7-character string matches existing key. | `create_link()` catches `IntegrityError`, rolls back the transaction, and retries with a new token up to 5 times. |
| **Abusive Traffic Spike** | Client sends 100 requests/second. | Nginx absorbs the first 20 in the burst buffer and immediately drops the remainder with `HTTP 429`. |

---

## 4. Master File Navigation Index

- **Phase 1 (Core API & DB)**: [`docs/phase_1_core_api.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_1_core_api.md)
- **Phase 2 (Redis Caching)**: [`docs/phase_2_redis_caching.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_2_redis_caching.md)
- **Phase 3 (Event Streaming)**: [`docs/phase_3_event_streaming.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_3_event_streaming.md)
- **Phase 4 (Load Balancing)**: [`docs/phase_4_load_balancing.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_4_load_balancing.md)
- **Phase 5 (Observability)**: [`docs/phase_5_observability.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_5_observability.md)
- **Phase 6 (CI/CD)**: [`docs/phase_6_ci_cd.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_6_ci_cd.md)
- **Phase 7 (React Frontend)**: [`docs/phase_7_react_frontend.md`](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_7_react_frontend.md)
