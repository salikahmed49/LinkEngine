# Phase 4: Load Balancing, Rate Limiting & Failover (Nginx)

---

## 1. Concepts & Objectives

A single FastAPI instance cannot utilize multi-core CPU capacity fully due to the Python Global Interpreter Lock (GIL) and constitutes a single point of failure (SPOF).

Phase 4 introduces **Nginx as an API Gateway and Reverse Proxy** orchestrating 3 stateless FastAPI application replicas (`api_1`, `api_2`, `api_3`):
1. **Horizontal Scaling**: Distributes incoming HTTP requests across all 3 replicas using **Round-Robin** load balancing.
2. **Per-IP Rate Limiting**: Protects downstream services from DoS attacks, scrapers, and abuse using the **Leaky Bucket** algorithm (`10 req/s` with `burst=20 nodelay`).
3. **Automatic Failover (`proxy_next_upstream`)**: If a replica process crashes mid-request, Nginx automatically reroutes that in-flight request to a healthy replica with zero user-facing errors.
4. **Passive Health Checks**: Marks unhealthy replicas as unavailable after consecutive failures (`max_fails=3 fail_timeout=10s`) and automatically probes for recovery.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Upstream Load Balancing Cluster** | [`nginx/nginx.conf`](file:///c:/Users/salik/Documents/link-analytics-platform/nginx/nginx.conf#L20-L26) (`upstream fastapi_cluster`) | Declares the cluster containing `api_1:8000`, `api_2:8000`, `api_3:8000` with `max_fails=3 fail_timeout=10s`. |
| **Leaky Bucket Rate Limiting** | [`nginx/nginx.conf`](file:///c:/Users/salik/Documents/link-analytics-platform/nginx/nginx.conf#L16-L18)<br>[`nginx/nginx.conf`](file:///c:/Users/salik/Documents/link-analytics-platform/nginx/nginx.conf#L40-L41) | Configures `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s` and applies `limit_req zone=api_limit burst=20 nodelay; limit_req_status 429;`. |
| **Zero-Downtime Failover** | [`nginx/nginx.conf`](file:///c:/Users/salik/Documents/link-analytics-platform/nginx/nginx.conf#L49-L52) | Configures `proxy_next_upstream error timeout http_502 http_503 http_504;` and short connection timeouts. |
| **Cluster Topology & Networks** | [`docker-compose.yml`](file:///c:/Users/salik/Documents/link-analytics-platform/docker-compose.yml#L34-L112) | Defines the 3 FastAPI replica containers, PostgreSQL, Redis, Worker, and Nginx proxy listening on port 8000. |
| **Instance Tracking Header** | [`app/main.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/main.py#L43-L57) | Injects `X-Instance-ID` HTTP response header and returns `instance_id` in `/health` to verify round-robin routing. |

---

## 3. Code Deep Dive

### 3.1 How Nginx Rate Limiting Works
```nginx
# 1. Allocate 10MB shared memory zone tracking binary IP addresses
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_status 429;

server {
    location / {
        # Allow sudden spikes up to 20 requests without artificial throttling delays
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://fastapi_cluster;
        proxy_next_upstream error timeout http_502 http_503 http_504;
    }
}
```

- **`$binary_remote_addr`**: Uses 4 bytes per IPv4 address instead of a string (15 bytes), enabling a 10MB zone to track ~160,000 distinct IP addresses concurrently.
- **`burst=20 nodelay`**: Legitimate users opening multiple links simultaneously won't get blocked as long as their burst does not exceed 20 requests. If an abusive client sends 30 rapid requests, requests 1–20 succeed immediately and requests 21–30 receive `HTTP 429 Too Many Requests`.
