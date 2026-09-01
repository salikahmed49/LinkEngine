# Link Analytics Platform

A production-ready, distributed URL shortener, caching, telemetry, and real-time stream analytics platform built with **FastAPI**, **PostgreSQL**, **Redis Streams**, **Nginx**, **Prometheus**, **Grafana**, and **React**.

---

## 🧭 Project Map & Documentation Guide

Every phase of this platform is documented with deep-dive architectural explanations, code references, and failure mode analysis in the [`docs/`](file:///c:/Users/salik/Documents/link-analytics-platform/docs) directory:

| Document | Description | Key Code References |
|---|---|---|
| **[Master Architecture & Deep Dive](file:///c:/Users/salik/Documents/link-analytics-platform/docs/architecture_and_deep_dive.md)** | Full system topology, read/write path separation, failure modes & resilience. | [`docker-compose.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/docker-compose.yml) |
| **[Phase 1: Core API & Database](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_1_core_api.md)** | Token generation, collision retry loops, custom aliases, and SQLAlchemy models. | [`app/models.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/models.py), [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py) |
| **[Phase 2: Redis Caching & Invalidation](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_2_redis_caching.md)** | Cache-Aside pattern, 24h TTL, active cache eviction on update/delete. | [`app/core/redis_client.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/redis_client.py), [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py) |
| **[Phase 3: Event Streaming (Redis Streams)](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_3_event_streaming.md)** | Async click logging, `ClickConsumer` batch worker, PEL crash recovery, deduplication. | [`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py) |
| **[Phase 4: Load Balancing & Rate Limiting](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_4_load_balancing.md)** | Nginx reverse proxy, 3-replica cluster, leaky bucket rate limiting, zero-downtime failover. | [`nginx/nginx.conf`](file:///c:/Users/salik/Documents/link-analytics-platform/nginx/nginx.conf), [`docker-compose.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/docker-compose.yml) |
| **[Phase 5: Observability & Telemetry](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_5_observability.md)** | Prometheus metrics (`/metrics`), latency percentiles (p50/p95/p99), Grafana dashboard. | [`app/core/metrics.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/metrics.py), [`prometheus/prometheus.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/prometheus/prometheus.yml) |
| **[Phase 6: CI/CD & Deployment](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_6_ci_cd.md)** | GitHub Actions automated test, build, and deploy pipeline to Fly.io/Railway. | [`.github/workflows/ci-cd.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/.github/workflows/ci-cd.yml), [`fly.toml`](file:///c:/Users/salik/Documents/link-analytics-platform/fly.toml) |
| **[Phase 7: Developer-Grade React Frontend](file:///c:/Users/salik/Documents/link-analytics-platform/docs/phase_7_react_frontend.md)** | React 18 + Vite frontend, asymmetric layout, live URL shortening, real-time event logs. | [`frontend/src/App.jsx`](file:///c:/Users/salik/Documents/link-analytics-platform/frontend/src/App.jsx), [`frontend/src/index.css`](file:///c:/Users/salik/Documents/link-analytics-platform/frontend/src/index.css) |

---

## 🗂️ Complete Codebase Directory Map

```text
link-analytics-platform/
│
├── app/                                # FastAPI Backend Application
│   ├── main.py                         # App instance, CORS, Prometheus middleware, router inclusion
│   ├── models.py                       # SQLAlchemy models: Link (links table), ClickEvent (click_events table)
│   ├── schemas.py                      # Pydantic schemas: LinkCreate, LinkUpdate, LinkResponse, LinkAnalyticsResponse
│   │
│   ├── core/                           # Infrastructure & Core Singletons
│   │   ├── config.py                   # Pydantic Settings (.env configuration)
│   │   ├── database.py                 # SQLAlchemy engine, session maker, get_db dependency
│   │   ├── logging.py                  # Structured logging
│   │   ├── metrics.py                  # Prometheus counters, histograms, and gauges
│   │   └── redis_client.py             # Shared Redis connection client
│   │
│   ├── routes/                         # API HTTP Route Handlers
│   │   └── links.py                    # POST /links, GET /{code}, GET /stats, GET /analytics, PATCH, DELETE
│   │
│   ├── services/                       # Core Business Logic
│   │   └── link_service.py             # Base62 generator, Cache-Aside read path, Redis Stream publisher
│   │
│   └── workers/                        # Background Microservices
│       └── click_consumer.py           # Redis Streams batch worker with PEL crash recovery & idempotency
│
├── frontend/                           # React 18 + Vite Single Page Application
│   ├── src/
│   │   ├── components/                 # UI Components (Header, CreateLinkForm, LinkResult, AnalyticsInspector)
│   │   ├── services/api.js             # API Client service with centralized error translation
│   │   ├── App.jsx                     # Asymmetric layout wrapper
│   │   ├── main.jsx                    # React root entrypoint
│   │   └── index.css                   # Custom engineer-grade dark theme design system
│   ├── Dockerfile                      # Multi-stage container build (Node -> Nginx)
│   ├── nginx.conf                      # SPA static server config
│   ├── package.json                    # Dependencies (React, Lucide icons, Vite)
│   └── vite.config.js                  # Vite bundler config
│
├── docs/                               # 📖 Dedicated In-Depth Phase Documentation
│   ├── architecture_and_deep_dive.md   # Master concepts: Read/write separation, failure modes, resilience
│   ├── phase_1_core_api.md             # Phase 1 deep dive
│   ├── phase_2_redis_caching.md        # Phase 2 deep dive
│   ├── phase_3_event_streaming.md      # Phase 3 deep dive
│   ├── phase_4_load_balancing.md       # Phase 4 deep dive
│   ├── phase_5_observability.md        # Phase 5 deep dive
│   ├── phase_6_ci_cd.md                # Phase 6 deep dive
│   └── phase_7_react_frontend.md       # Phase 7 deep dive
│
├── grafana/                            # Grafana Telemetry Dashboard Provisioning
│   ├── dashboards/                     # link_analytics_dashboard.json (Pre-built dashboard panels)
│   └── provisioning/                   # Datasource & dashboard auto-loaders
│
├── nginx/                              # Gateway Configuration
│   └── nginx.conf                      # 3-replica load balancing, leaky bucket rate limiting, failover
│
├── prometheus/                         # Metrics Collector Configuration
│   └── prometheus.yml                  # Scrape config for api_1, api_2, api_3
│
├── tests/                              # Automated Test Suite
│   └── test_links.py                   # 24 Unit & integration tests covering all features
│
├── .github/workflows/
│   └── ci-cd.yml                       # GitHub Actions pipeline (Pytest + Services, Docker Build, Deploy)
│
├── docker-compose.yml                  # 7-Microservice Docker Compose Stack
├── Dockerfile                          # Application Docker container
├── fly.toml                            # Fly.io deployment config
├── Procfile                            # PaaS process manager config
├── concurrency_test.py                 # Multi-threaded load test script
└── DOCUMENTATION.md                    # Master technical guide
```

---

## ⚡ Quick Start: Launch Entire Platform

Run the entire cluster with a single command:

```powershell
docker compose up --build -d
```

### Access Points
- **React Frontend**: [http://localhost:3001](http://localhost:3001)
- **API Gateway (Nginx)**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000) *(User: `admin`, Password: `admin`)*
- **Prometheus Telemetry**: [http://localhost:9090](http://localhost:9090)
- **Prometheus Metrics Raw Text**: [http://localhost:8000/metrics](http://localhost:8000/metrics)

---

## 🧪 Run Automated Tests

Run the full pytest suite (24 tests):

```powershell
.\.venv\Scripts\pytest -v
```
