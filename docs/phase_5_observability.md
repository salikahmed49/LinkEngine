# Phase 5: Observability, Metrics & Telemetry (Prometheus & Grafana)

---

## 1. Concepts & Objectives

### Metrics vs. Logs
- **Logs**: High-cardinality text events (`[2026-09-02 01:00:00] User clicked link abc from 192.168.1.1`). Essential for forensic debugging of individual requests.
- **Metrics**: Aggregated numerical timeseries data (`rate(http_requests_total[1m])`). Lightweight, low overhead, and ideal for alerting, capacity planning, and real-time dashboarding.

### The RED Method & Key Telemetry
Phase 5 instruments the platform following the industry-standard **RED Method**:
1. **Rate**: Requests per second handled by the API cluster (`sum(rate(http_requests_total[1m]))`).
2. **Errors**: Failed requests categorized by HTTP status code (`4xx`, `5xx`).
3. **Duration**: Request latency percentiles ($p50$, $p95$, $p99$) calculated via histogram buckets.
4. **Cache Efficiency**: Real-time Redis cache hit ratio percentage (`Hit Rate % = Hits / (Hits + Misses) * 100`).
5. **Streaming Ingestion Velocity**: Rate of events published to Redis Streams vs. rate consumed and persisted by the worker.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Prometheus Metrics Registry** | [`app/core/metrics.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/metrics.py) (`REQUEST_COUNT`, `REQUEST_LATENCY`, `CACHE_HITS`, `CACHE_MISSES`, `STREAM_EVENTS_PUBLISHED`, `STREAM_EVENTS_CONSUMED`, `STREAM_PENDING_GAUGE`) | Defines all Prometheus metrics, histogram buckets, and gauge definitions. |
| **Telemetry Middleware & Scrape Endpoint** | [`app/main.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/main.py#L43-L65)<br>[`app/main.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/main.py#L82-L86) (`/metrics`) | Tracks execution duration of every HTTP request, increments counters, and serves raw Prometheus formatted metrics at `GET /metrics`. |
| **Cache & Event Instrumentation** | [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L112)<br>[`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L150-L157) | Increments `STREAM_EVENTS_PUBLISHED`, `CACHE_HITS`, and `CACHE_MISSES`. |
| **Worker Ingestion Instrumentation** | [`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py#L180)<br>[`app/workers/click_consumer.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/workers/click_consumer.py#L194-L198) | Increments `STREAM_EVENTS_CONSUMED` and tracks unacknowledged items in `STREAM_PENDING_GAUGE`. |
| **Prometheus Scraper Config** | [`prometheus/prometheus.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/prometheus/prometheus.yml) | Configures Prometheus to pull `/metrics` from all 3 FastAPI replicas every 5 seconds. |
| **Pre-Provisioned Grafana Dashboard** | [`grafana/dashboards/link_analytics_dashboard.json`](file:///c:/Users/salik/Documents/link-analytics-platform/grafana/dashboards/link_analytics_dashboard.json)<br>[`grafana/provisioning/`](file:///c:/Users/salik/Documents/link-analytics-platform/grafana/provisioning/) | Automatically loads Prometheus as a datasource and renders real-time panels upon Docker startup. |

---

## 3. Key PromQL Queries Used in Grafana

| Panel | PromQL Expression | Explanation |
|---|---|---|
| **Request Throughput (RPS)** | `sum(rate(http_requests_total[1m])) by (status_code)` | Visualizes traffic volume segmented by HTTP status (200, 307, 404, 429). |
| **Cache Hit Rate (%)** | `(sum(rate(link_cache_hits_total[1m])) or vector(0)) / ((sum(rate(link_cache_hits_total[1m])) or vector(0)) + (sum(rate(link_cache_misses_total[1m])) or vector(0))) * 100` | Displays memory efficiency gauge (Green > 85%, Yellow 50–85%, Red < 50%). |
| **95th Percentile Latency (p95)** | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le)) * 1000` | Calculates the maximum latency experienced by 95% of users in milliseconds. |
| **Stream Flow (Publish vs Consume)** | `sum(rate(click_events_published_total[1m]))` vs `sum(rate(click_events_consumed_total[1m]))` | Confirms that worker consumption matches event publishing velocity. |
