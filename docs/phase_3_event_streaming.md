# Phase 3: Event-Driven Analytics & Redis Streams

---

## 1. Concepts & Objectives

### Why Synchronous Database Writes Don't Scale
In a naive URL shortener, every redirect request executes:
```sql
UPDATE links SET click_count = click_count + 1 WHERE short_code = 'xyz';
INSERT INTO click_events (short_code, clicked_at, user_agent, ...) VALUES (...);
```
Under high concurrent traffic (e.g. 10,000 req/sec to a trending viral link):
- **Row-Level Lock Contention**: Thousands of simultaneous connections queue up trying to acquire the exclusive row write-lock on the same `links` row.
- **Write-Ahead Log (WAL) Bottleneck**: Heavy disk I/O on every click slows down redirects from $<1\text{ms}$ to $>200\text{ms}$, leading to database connection pool exhaustion.

### The Solution: Read Path / Write Path Decoupling
1. **Read Path (Ultra-Fast & Synchronous)**:
   FastAPI receives the request, publishes an immutable event payload to the Redis Stream `clicks:stream` via `XADD`, and immediately returns an HTTP 307 redirect ($<1\text{ms}$, non-blocking).
2. **Write Path (Asynchronous & Batched)**:
   A dedicated background worker service (`ClickConsumer`) reads batches of events from the stream, deduplicates them, and writes them to PostgreSQL in a single bulk transaction.
3. **Eventual Consistency**:
   The user gets their redirect instantly. Analytics tables catch up milliseconds later in the background.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Click Event Model** | [`app/models.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/models.py#L21-L34) (`ClickEvent`) | Defines `click_events` table: `id`, `event_id` (UUID unique index), `short_code`, `clicked_at`, `user_agent`, `referrer`, `ip_address`. |
| **Stream Event Publisher** | [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L93-L120) (`publish_click_event`) | Constructs an event payload with UUID4 and pushes to Redis stream `clicks:stream` via `redis_client.xadd()`. |
| **Consumer Group & Offset Management** | [`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py#L82-L108) (`ensure_consumer_group`) | Creates the Redis consumer group (`analytics_group`) with `MKSTREAM` starting from stream beginning (`0`). |
| **Idempotent Batch Processor** | [`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py#L110-L188) (`process_entries`) | Deduplicates stream messages against existing `event_id`s in PostgreSQL, bulk-inserts `ClickEvent` records, batch-increments `Link.click_count`, and acknowledges messages via `XACK`. |
| **Crash Recovery & PEL Draining** | [`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py#L190-L225) (`process_pending`) | On worker startup, drains the Pending Entries List (PEL, reading ID `0`) to process and acknowledge uncommitted messages left from any prior worker crash. |
| **Analytics Query Route** | [`app/routes/links.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/routes/links.py#L88-L103) (`get_analytics`)<br>[`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L250-L310) (`get_link_analytics`) | Aggregates total clicks, top 5 referrers, top 5 user-agents, and the 10 most recent click events. |

---

## 3. Code Deep Dive

### 3.1 What Happens When the Consumer Worker Crashes?
Redis Streams tracks assigned messages in the **Pending Entries List (PEL)**. When a message is delivered to a consumer via `XREADGROUP`, it enters the PEL. It is only removed when the consumer explicitly issues an `XACK`.

If the worker process crashes after reading 50 messages but before committing to PostgreSQL:
1. The 50 messages remain safe in the stream and in the PEL.
2. When the worker restarts, `process_pending()` runs:
   ```python
   def process_pending(self, db: Session) -> int:
       # ID "0" reads unacknowledged messages assigned to this group
       results = redis_client.xreadgroup(
           groupname=self.group_name,
           consumername=self.consumer_name,
           streams={self.stream_name: "0"},
           count=self.batch_size,
       )
       # Processes the batch, commits to DB, and issues XACK
       return self.process_entries(db, stream_entries)
   ```
3. Because each message carries a unique `event_id`, the database query `SELECT event_id FROM click_events WHERE event_id IN (...)` guarantees that no event is inserted twice (**At-Least-Once Delivery with Idempotence = Exactly-Once Semantics**).
