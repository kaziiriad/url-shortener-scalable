from app.core.config import settings
from redis.asyncio import Redis

class RedisClient:
    def __init__(self) -> None:
        self.redis_client = Redis(
            host=settings.redis_host, 
            port=settings.redis_port, 
            password=settings.redis_password if settings.redis_password else None, 
            db=0,
            decode_responses=True
        )

    async def get(self, key: str) -> str:
        return await self.redis_client.get(key)

    async def set(self, key: str, value: str, expires_in: int = None) -> None:
        await self.redis_client.set(key, value, ex=expires_in)

    async def delete(self, key: str) -> None:
        await self.redis_client.delete(key)

    async def close(self) -> None:
        await self.redis_client.close()

        