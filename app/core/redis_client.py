import redis

from app.core.config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=1.0,
    socket_connect_timeout=1.0,
)