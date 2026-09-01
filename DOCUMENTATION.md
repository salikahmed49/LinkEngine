# Link Analytics Platform — Master Technical Documentation & Architecture Guide

A production-grade, event-driven URL shortening, caching, telemetry, and analytics engine built with **FastAPI**, **PostgreSQL**, **Redis Streams**, **Nginx**, **Prometheus**, **Grafana**, and **React**.

### 📖 Dedicated Phase Guides & Deep Dives
- **[System Architecture & Everything You Need to Know](file:///c:/Users/salik/Documents/link-analytics-platform/docs/architecture_and_deep_dive.md)**
- **[Phase 1: Core API & Relational Data Layer](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_1_core_api.md)**
- **[Phase 2: Redis Caching & Invalidation](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_2_redis_caching.md)**
- **[Phase 3: Event-Driven Analytics & Streaming](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_3_event_streaming.md)**
- **[Phase 4: Load Balancing, Rate Limiting & Nginx](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_4_load_balancing.md)**
- **[Phase 5: Observability, Prometheus & Grafana](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_5_observability.md)**
- **[Phase 6: CI/CD Pipeline & Deployment](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_6_ci_cd.md)**
- **[Phase 7: Developer-Grade React Frontend](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_7_react_frontend.md)**

---

## 1. System Architecture Overview

```text
                                  [ Internet / Clients ]
                                             │
                                             ▼
                        ┌──────────────────────────────────────────┐
                        │        Nginx Reverse Proxy & Gateway     │
                        │    • Port 8000 (Public Entrypoint)       │
                        │    • Per-IP Rate Limiting (10 r/s)       │
                        │    • Failover (proxy_next_upstream)      │
                        └────────────────────┬─────────────────────┘
                                             │
                       Round-Robin Load Balancing (3 Replicas)
                                             │
            ┌────────────────────────────────┼────────────────────────────────┐
            ▼                                ▼                                ▼
   ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
   │  FastAPI: api_1 │              │  FastAPI: api_2 │              │  FastAPI: api_3 │
   └────────┬────────┘              └────────┬────────┘              └────────┬────────┘
            │                                │                                │
            └────────────────────────────────┼────────────────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
             (Fast Read Path: <1ms)                       (Async Fire-and-Forget)
                     │                                               │
                     ▼                                               ▼
         ┌────────────────────────┐                      ┌────────────────────────┐
         │  Redis 7: Cache Layer  │                      │ Redis 7: Stream Buffer │
         │  • Cache-Aside Lookup  │                      │ • XADD clicks:stream   │
         │  • 24-hour TTL Expiry  │                      │ • Immutable Event Log  │
         │  • Active Invalidation │                      └───────────┬────────────┘
         └────────────────────────┘                                  │
                                                                     │ (Batch Ingestion)
                                                                     ▼
                                                         ┌────────────────────────┐
                                                         │ ClickConsumer Worker   │
                                                         │ • Consumer Group       │
                                                         │ • Deduplication (UUID) │
                                                         │ • Crash Recovery (PEL) │
                                                         │ • XACK Acknowledgment  │
                                                         └───────────┬────────────┘
                                                                     │
                                                                     ▼ (Bulk Inserts)
                                                         ┌────────────────────────┐
                                                         │ PostgreSQL Database    │
                                                         │ • links table          │
                                                         │ • click_events table   │
                                                         └────────────────────────┘
```

---

## 2. Phase-by-Phase Technical Breakdown

### Phase 1 — Core API & Relational Data Layer
- **Framework & Models**: FastAPI with SQLAlchemy 2.0.
- **Link Model**:
  - `id`: Auto-incrementing primary key.
  - `short_code`: 7-character base62 collision-resistant token or custom alias (`^[a-zA-Z0-9_-]{3,10}$`).
  - `original_url`: Target URL up to 2048 characters.
  - `click_count`: Total clicks aggregated.
  - `created_at`: Timezone-aware server timestamp.
- **Service Layer**:
  - `create_link()`: Handles collision retries transparently on duplicate tokens and throws a `409 Conflict` on duplicate custom aliases.
  - `get_link_stats()`: Inspects link metadata without incrementing click counters.

---

### Phase 2 — Redis Caching Layer (Cache-Aside)
- **Problem Solved**: Direct database lookups for every redirect create high read latency and connection pool exhaustion.
- **Cache-Aside Pattern**:
  1. On redirect request (`GET /{short_code}`), check Redis key `short_code:{short_code}`.
  2. **Cache HIT**: Retrieve target URL directly from memory ($<1\text{ms}$).
  3. **Cache MISS**: Query PostgreSQL once, write target URL into Redis with TTL (`ex=86400`), and return.
- **Active Invalidation**:
  - When target URLs are updated (`PATCH /links/{short_code}`) or deleted (`DELETE /links/{short_code}`), `invalidate_link_cache(short_code)` evicts the stale Redis key immediately.
- **Fault-Tolerant Fallback**: If Redis crashes or experiences network partitions, all queries fall back to PostgreSQL automatically without throwing 500 errors.

---

### Phase 3 — Event-Driven Analytics & Streaming (Redis Streams)
- **Problem Solved**: Synchronous database updates on every click (`UPDATE links SET click_count = click_count + 1`) introduce row-level lock contention, WAL write overhead, and high redirect latency.
- **Decoupled Architecture**:
  - **Read Path (Immediate)**: FastAPI extracts request context (`user_agent`, `referer`, `client.host`) and publishes an immutable click event to the Redis Stream (`clicks:stream`) using `XADD`. The user receives a `307 Temporary Redirect` in $<1\text{ms}$.
  - **Write Path (Asynchronous)**: A standalone `ClickConsumer` background worker pulls batches of events via consumer group `analytics_group` using `XREADGROUP`.
- **Idempotency & Deduplication**:
  - Each event has a unique `event_id` (UUID4).
  - The worker checks existing database IDs to guarantee that message re-deliveries do not double-count clicks.
- **Crash Recovery**:
  - On worker startup, `process_pending()` reads unacknowledged entries from the Pending Entries List (`PEL`, ID `0`) to drain and finish interrupted batches before consuming new events (`>`).
  - Successfully written batches send `XACK` to remove items from the PEL.

---

### Phase 4 — Reverse Proxy, Load Balancing & Rate Limiting (Nginx)
- **Multi-Replica Scaling**:
  - Nginx acts as the front gateway on port `8000`, distributing traffic across 3 stateless FastAPI replicas (`api_1`, `api_2`, `api_3`) via Round-Robin.
- **Per-IP Rate Limiting**:
  - Configured with `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;`.
  - Accommodates bursts up to 20 requests with `burst=20 nodelay`.
  - Rejects abusive traffic with `HTTP 429 Too Many Requests`.
- **Passive Health Checking & Failover**:
  - Configured with `max_fails=3 fail_timeout=10s` and `proxy_next_upstream error timeout http_502 http_503 http_504`.
  - If a replica crashes, Nginx transparently re-routes in-flight requests to healthy replicas with zero downtime.

---

### Phase 5 — Observability & Telemetry (Prometheus & Grafana)
- **Prometheus Metrics Endpoint (`/metrics`)**:
  - `http_requests_total`: Request counts labeled by HTTP method, route, and status code.
  - `http_request_duration_seconds`: Request latency histogram across configurable percentile buckets.
  - `link_cache_hits_total` & `link_cache_misses_total`: Real-time cache efficiency counters.
  - `click_events_published_total` & `click_events_consumed_total`: Streaming pipeline throughput.
  - `click_events_pending_count`: Gauge tracking unacknowledged messages in the Redis PEL.
- **Grafana Dashboard (`http://localhost:3000`)**:
  - Pre-provisioned datasource and dashboard visualizing RPS, p50/p95/p99 latency, Cache Hit Rate %, and stream ingestion velocity.

---

### Phase 6 — CI/CD Pipeline & Deployment
- **GitHub Actions Workflow (`.github/workflows/ci-cd.yml`)**:
  - Automatically spins up PostgreSQL and Redis service containers in CI.
  - Executes full test suite (`pytest -v`).
  - Builds and verifies Docker container image with layer caching.
  - Triggers automated deployment to production (Fly.io / Railway) on merges to `main`.
- **Deployment Configs**: `fly.toml`, `Procfile`, `.dockerignore`.

---

### Phase 7 — Developer-Grade React Frontend
- **Tech Stack**: React 18, Vite 5, Vanilla CSS design system, Google Fonts (`JetBrains Mono`, `Plus Jakarta Sans`).
- **Design Philosophy**: Minimalist, dense, engineer-grade technical aesthetic with high typographic hierarchy, status indicators, and no generic SaaS tropes.
- **Key Features**:
  1. **URL Shortener Console**: Immediate URL shortening, custom alias support, and one-click copy button.
  2. **Live Analytics Inspector**: Lookup any short link to inspect real-time click volume, created dates, top referrers, top client user agents, and recent event logs.
  3. **Cluster Health Telemetry**: Live polling of backend health, response latency, and active replica ID.

---

## 3. End-to-End Quick Start Guide

### Prerequisites
- Docker & Docker Compose
- Python 3.13+ (for local development)
- Node.js 20+ (for local frontend development)

### Launch Full Microservices Stack (Docker Compose)
Run the entire cluster with a single command:
```powershell
docker compose up --build -d
```

### Access Points
| Service | URL | Credentials / Notes |
|---|---|---|
| **Frontend Application** | `http://localhost:3001` | React Single-Page Application |
| **API Gateway / Nginx** | `http://localhost:8000` | Reverse proxy & Rate Limiter |
| **Interactive API Docs** | `http://localhost:8000/docs` | Swagger UI |
| **Prometheus Telemetry** | `http://localhost:9090` | Metrics scraper & PromQL |
| **Grafana Dashboard** | `http://localhost:3000` | User: `admin`, Password: `admin` |
| **Prometheus Scrape Endpoint** | `http://localhost:8000/metrics` | Telemetry raw text |

---

## 4. Operational & Verification Cheatsheet

### 1. Run Automated Test Suite
```powershell
.\.venv\Scripts\pytest -v
```
*(All 24 unit & integration tests run against isolated in-memory SQLite and Redis)*.

### 2. Test Round-Robin Load Balancing
```powershell
1..6 | ForEach-Object { curl.exe -i http://localhost:8000/health | Select-String "X-Instance-ID" }
```

### 3. Test Per-IP Rate Limiting
```powershell
1..30 | ForEach-Object { (curl.exe -s -o /dev/null -w "%{http_code}`n" http://localhost:8000/) }
```

### 4. Test Concurrency & Stream Processing
```powershell
.\.venv\Scripts\python concurrency_test.py
```

### 5. Inspect Redis Streams Directly
```powershell
docker exec -it link-analytics-redis redis-cli XLEN clicks:stream
docker exec -it link-analytics-redis redis-cli XINFO GROUPS clicks:stream
```

### 6. Inspect PostgreSQL Event Table
```powershell
docker exec -it link-analytics-postgres psql -U linkuser -d linkanalytics -c "SELECT * FROM click_events ORDER BY clicked_at DESC LIMIT 5;"
```
