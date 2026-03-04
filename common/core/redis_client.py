from common.core.config import settings
from redis.asyncio import Redis, ConnectionPool
import logging

logger = logging.getLogger(__name__)

# Global singleton instances
_redis_pool: ConnectionPool = None
_redis_client_singleton: Redis = None

class RedisClient:
    def __init__(self) -> None:
        """
        Initialize Redis client with connection pooling (singleton pattern).
        All requests share the same connection pool for optimal performance.
        """
        global _redis_pool, _redis_client_singleton

        if _redis_client_singleton is None:
            logger.info("Initializing Redis connection pool for redirect service")

            # Create connection pool (shared across all instances)
            _redis_pool = ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password if settings.redis_password else None,
                db=0,
                max_connections=50,  # Connection pool size
                socket_keepalive=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                decode_responses=False  # Return bytes, decode only when needed (faster)
            )

            # Create singleton Redis client
            _redis_client_singleton = Redis(connection_pool=_redis_pool)
            logger.info(f"Redis connection pool created: max_connections=50")

        self.redis_client = _redis_client_singleton

    async def get(self, key: str) -> str | None:
        """Get value from Redis, decoding bytes to string."""
        val = await self.redis_client.get(key)
        if val is None:
            return None
        # Handle both bytes (new code) and str (old cached data)
        if isinstance(val, bytes):
            return val.decode('utf-8')
        return str(val)  # Already a string (from old cached data)

    async def set(self, key: str, value: str, expires_in: int = None) -> None:
        """Set value in Redis, encoding string to bytes."""
        # Store as bytes for consistency with decode_responses=False
        await self.redis_client.set(key, value.encode('utf-8') if isinstance(value, str) else value, ex=expires_in)

    async def delete(self, key: str) -> None:
        """Delete key from Redis."""
        await self.redis_client.delete(key)

    async def close(self) -> None:
        await self.redis_client.close()

    async def ping(self) -> bool:
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            print(f"Redis ping failed: {e}")
            return False


# Dependency function for FastAPI - returns singleton instance
def get_redis_client() -> RedisClient:
    """
    FastAPI dependency function that returns the singleton RedisClient.
    Use this instead of Depends(RedisClient) to avoid creating new instances.

    Usage:
        @app.get("/")
        async def endpoint(redis_client: RedisClient = Depends(get_redis_client)):
            ...
    """
    return RedisClient()