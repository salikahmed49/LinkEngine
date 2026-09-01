# Link Analytics Platform — Project Overview & Architecture Guide

## 1. Project Overview

The **Link Analytics Platform** is a high-performance URL shortening and click-tracking microservice built with **FastAPI**, **SQLAlchemy**, and **Pydantic v2**.

The platform is designed to provide:
1. **URL Shortening**: Shorten long URLs into compact, collision-resistant 7-character base62 tokens or user-defined custom aliases.
2. **Fast Redirection**: Resolve short codes to target URLs with HTTP 307/302 redirects.
3. **Click Analytics & Tracking**: Track link engagement with click counters and metadata timestamps.

---

## 2. Tech Stack

- **Framework**: FastAPI (v0.115+)
- **ASGI Server**: Uvicorn
- **ORM & Database**: SQLAlchemy 2.0 with SQLite / PostgreSQL (configurable via `DATABASE_URL`)
- **Data Validation & Settings**: Pydantic v2 & Pydantic-Settings
- **Caching Layer**: Redis 7 (Cache-Aside with TTL & active invalidation)
- **Event Streaming & Messaging**: Redis Streams (`XADD`, `XREADGROUP`, Consumer Groups, PEL recovery)
- **Background Workers**: Python batch consumer worker (`app/workers/click_consumer.py`)
- **Reverse Proxy & Load Balancer**: Nginx with 3-replica upstream & per-IP rate limiting
- **Observability**: Prometheus metrics (`/metrics`) & Grafana telemetry dashboards
- **CI/CD**: GitHub Actions workflow (`.github/workflows/ci-cd.yml`)
- **Frontend**: React 18 + Vite with engineer-grade UI & live telemetry
- **Testing**: Pytest & HTTPX (FastAPI TestClient) — 24 tests
- **Python Version**: Python 3.13+

---

## 3. Project Structure

```text
link-analytics-platform/
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application instance, CORS, Prometheus middleware, routes
│   ├── models.py               # SQLAlchemy ORM models (Link, ClickEvent)
│   ├── schemas.py              # Pydantic v2 schemas for request validation, responses, & analytics
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Application settings using Pydantic BaseSettings (.env support)
│   │   ├── database.py         # SQLAlchemy engine, session maker, get_db dependency
│   │   ├── logging.py          # Structured logging setup
│   │   ├── metrics.py          # Prometheus counters, histograms, and gauges
│   │   └── redis_client.py     # Shared Redis client instance
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── links.py            # API routes: POST /links, GET /{short_code}, GET /stats, GET /analytics, PATCH, DELETE
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── link_service.py     # Business logic: short code generation, cache-aside read path, stream event publishing
│   │
│   └── workers/
│       ├── __init__.py
│       └── click_consumer.py   # Event batch consumer: pulls from Redis Streams, deduplicates, writes to PostgreSQL
│
├── frontend/                   # React + Vite frontend application
│   ├── src/
│   │   ├── components/         # Header, CreateLinkForm, LinkResult, AnalyticsInspector
│   │   ├── services/           # api.js API client service
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css           # Technical design system
│   ├── Dockerfile              # Multi-stage container build for React
│   ├── nginx.conf              # SPA static server config
│   ├── package.json
│   └── vite.config.js
│
├── grafana/                    # Grafana telemetry provisioning & dashboards
│   ├── dashboards/             # link_analytics_dashboard.json
│   └── provisioning/           # Datasource & dashboard providers
│
├── nginx/
│   └── nginx.conf              # Upstream load balancing, rate limiting, failover
│
├── prometheus/
│   └── prometheus.yml          # Scrape configuration for FastAPI replicas
│
├── tests/
│   ├── __init__.py
│   └── test_links.py           # Comprehensive unit & integration tests (24 tests)
│
├── .github/workflows/
│   └── ci-cd.yml               # Automated test, build, and deploy GitHub Actions pipeline
│
├── docker-compose.yml          # 7-microservice composition (Postgres, Redis, 3 APIs, Worker, Nginx, Prometheus, Grafana, Frontend)
├── Dockerfile                  # Application Docker container
├── fly.toml                    # Fly.io deployment config
├── Procfile                    # PaaS deployment config
├── concurrency_test.py         # Concurrent load testing script
├── requirements.txt            # Project dependencies
├── DOCUMENTATION.md            # Comprehensive master technical documentation
└── PROJECT_OVERVIEW.md         # Architecture overview
```

---

## 4. Phase Completion Status

| Phase | Description | Status | Verification |
|---|---|---|---|
| **Phase 1** | Core URL shortener API (FastAPI, SQLite/Postgres, Pydantic v2) | ✅ Complete | Automated unit tests |
| **Phase 2** | Redis Caching (Cache-Aside, TTL, active invalidation, graceful fallback) | ✅ Complete | Query bypass tests (0 DB queries on cache hits) |
| **Phase 3** | Event-Driven Analytics (Redis Streams, ClickConsumer worker, PEL recovery, idempotency) | ✅ Complete | Stream publishing & consumer deduplication tests |
| **Phase 4** | Load Balancing & Rate Limiting (Nginx, 3 FastAPI replicas, per-IP rate limits) | ✅ Complete | Docker Compose cluster & failover tests |
| **Phase 5** | Observability (Prometheus metrics `/metrics` & Grafana telemetry dashboard) | ✅ Complete | Endpoint tests & pre-provisioned Grafana panels |
| **Phase 6** | CI/CD Pipeline (GitHub Actions automated test, build, deploy workflows) | ✅ Complete | `.github/workflows/ci-cd.yml` |
| **Phase 7** | Frontend (Polished React + Vite dev-tool UI, real-time analytics inspector) | ✅ Complete | Vite production build (`dist/`) & Docker container |

