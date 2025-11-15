import logging
import json
from datetime import datetime, timezone
from common.core.redis_client import RedisClient
from common.utils.circuit_breaker import with_retry, with_circuit_breaker, mongo_circuit_breaker

logger = logging.getLogger(__name__)

class RedirectService:

    @staticmethod
    @with_retry(max_retries=2, delay=0.2)
    @with_circuit_breaker(mongo_circuit_breaker)
    async def _find_url_in_mongo(mongo_db, short_url_id: str):
        """
        Finds a URL in MongoDB, protected by a retry and circuit breaker.
        """
        return await mongo_db.urls.find_one({"short_url_id": short_url_id})

    @classmethod
    async def get_long_url(cls, short_key: str, mongo_db, redis_client: RedisClient) -> str | None:
        """
        Retrieves the long URL associated with a short key.
        1. Check Redis cache.
        2. If not in cache, check MongoDB.
        3. If in MongoDB, cache the result in Redis.
        """
        try:
            # 1. Try Redis first
            cached_data = await redis_client.get(short_key)
            if cached_data:
                url_data = json.loads(cached_data)
                # expires_at_str = url_data.get("expires_at")
                # if expires_at_str:
                #     expires_at = datetime.fromisoformat(expires_at_str)
                #     if expires_at < datetime.now(timezone.utc):
                #         await redis_client.delete(short_key)
                #         logger.info(f"Removed expired URL from cache: {short_key}")
                #         return None  # Expired
                logger.info(f"Cache hit for {short_key}")
                return url_data.get("long_url")

            # 2. If not in Redis, try MongoDB
            url_data = await cls._find_url_in_mongo(mongo_db, short_key)
            if url_data:
                logger.info(f"DB hit for {short_key}")
                long_url = url_data.get("long_url")
                
                # 3. Cache the result in Redis for next time
                # Convert ObjectId to string for JSON serialization
                url_data['_id'] = str(url_data['_id'])
                await redis_client.set(short_key, json.dumps(url_data, default=str), expires_in=1800) # 30 min cache
                
                return long_url
            
            logger.warning(f"URL not found for key: {short_key}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving URL for {short_key}: {e}")
            # In a production system, you might want to handle this more gracefully
            # For now, we'll just return None
            return None
