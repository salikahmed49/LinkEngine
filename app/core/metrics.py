"""
Prometheus metrics registry and telemetry definitions for the Link Analytics Platform.
"""

from prometheus_client import Counter, Gauge, Histogram

# HTTP metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received by FastAPI",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Caching metrics
CACHE_HITS = Counter(
    "link_cache_hits_total",
    "Total Redis cache hits for short links",
)

CACHE_MISSES = Counter(
    "link_cache_misses_total",
    "Total Redis cache misses for short links",
)

# Event streaming & consumer metrics
STREAM_EVENTS_PUBLISHED = Counter(
    "click_events_published_total",
    "Total click events published to Redis Stream",
)

STREAM_EVENTS_CONSUMED = Counter(
    "click_events_consumed_total",
    "Total click events successfully consumed and persisted to PostgreSQL",
)

STREAM_PENDING_GAUGE = Gauge(
    "click_events_pending_count",
    "Number of unacknowledged events currently in the Redis Stream Pending Entries List (PEL)",
)
