from contextlib import asynccontextmanager
import os
import socket
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

import app.models  # noqa: F401 - ensure models are registered with Base metadata
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import get_logger, setup_logging
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.routes.links import router as links_router

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

INSTANCE_ID = os.getenv("INSTANCE_NAME", os.getenv("HOSTNAME", socket.gethostname()))


import threading
from app.workers.click_consumer import ClickConsumer

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Initializing database tables (Instance: {INSTANCE_ID})...")
    Base.metadata.create_all(bind=engine)

    # In single-service or free-tier deployments, run ClickConsumer as an embedded daemon thread
    if os.getenv("EMBEDDED_WORKER", "true").lower() == "true":
        logger.info("Starting embedded background ClickConsumer worker thread...")
        try:
            consumer = ClickConsumer(consumer_name=f"embedded-{INSTANCE_ID}")
            worker_thread = threading.Thread(target=consumer.start, daemon=True)
            worker_thread.start()
        except Exception as e:
            logger.warning(f"Could not start embedded worker thread: {e}")

    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.app_name,
    description="Scalable URL shortener with real-time click analytics",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def telemetry_and_instance_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Add instance header
    response.headers["X-Instance-ID"] = INSTANCE_ID

    # Record Prometheus metrics (normalize path to avoid high cardinality for short codes)
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path
    REQUEST_COUNT.labels(
        method=request.method, endpoint=endpoint, status_code=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)

    return response


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
        "instance_id": INSTANCE_ID,
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus metrics scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(links_router)