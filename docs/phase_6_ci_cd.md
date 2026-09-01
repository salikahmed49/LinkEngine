# Phase 6: CI/CD Pipeline & Zero-Downtime Deployment

---

## 1. Concepts & Objectives

Modern cloud platforms require automated verification before code reaches production:
1. **Continuous Integration (CI)**: Automatically spins up test databases and Redis brokers to execute the full unit/integration test suite against pull requests and commits.
2. **Container Build Verification**: Builds and validates Docker images to ensure all dependencies and runtime configurations compile.
3. **Continuous Deployment (CD)**: Automatically deploys approved changes to hosting platforms (e.g. Fly.io or Railway) on merges to `main`.
4. **Zero-Downtime Rolling Deploys**: Ensures health checks pass on new application machines before shutting down old machines.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Automated CI/CD Workflow** | [`.github/workflows/ci-cd.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/.github/workflows/ci-cd.yml) | GitHub Actions workflow orchestrating `test`, `docker-build`, and `deploy` jobs. |
| **Production Dockerfile** | [`Dockerfile`](file:///c:/Users/salik/Documents/link-analytics-platform/Dockerfile) | Multi-stage / clean Python 3.13 slim image with optimized layer caching and bytecode suppression. |
| **Fly.io Deployment Config** | [`fly.toml`](file:///c:/Users/salik/Documents/link-analytics-platform/fly.toml) | Defines primary region, HTTP concurrency limits, and `/health` rolling deployment checks. |
| **PaaS Deployment Config** | [`Procfile`](file:///c:/Users/salik/Documents/link-analytics-platform/Procfile) | Declares the `web` process (Uvicorn) and `worker` process (ClickConsumer) for platforms like Railway or Render. |
| **Docker Build Exclusion** | [`.dockerignore`](file:///c:/Users/salik/Documents/link-analytics-platform/.dockerignore) | Excludes `node_modules`, `.venv`, `.pytest_cache`, and `.env` from Docker build context to ensure fast builds. |

---

## 3. The CI/CD Pipeline Flow

```text
[ Git Push to main / PR ]
           │
           ▼
┌────────────────────────────────────────┐
│  Job 1: Run Automated Tests            │
│  • Spawns ephemeral PostgreSQL 16      │
│  • Spawns ephemeral Redis 7            │
│  • Installs requirements.txt           │
│  • Runs: pytest -v (24 tests pass)     │
└──────────────────┬─────────────────────┘
                   │ (Requires Pass)
                   ▼
┌────────────────────────────────────────┐
│  Job 2: Build & Verify Docker Image    │
│  • Uses Docker Buildx with GHA cache   │
│  • Validates image compilation         │
└──────────────────┬─────────────────────┘
                   │ (On Merge to main)
                   ▼
┌────────────────────────────────────────┐
│  Job 3: Deploy to Production (Fly.io)  │
│  • Deploys new machines                │
│  • Verifies GET /health returns 200 OK │
│  • Switches traffic & shuts old nodes  │
└────────────────────────────────────────┘
```
