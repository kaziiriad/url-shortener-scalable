from datetime import datetime, timedelta, timezone
from app.db.nosql.connection import get_db
from app.models.schemas import URL, URLCreate, URLDelete
from app.db.sql.models import URL as URLModel
from app.db.sql.url_repository import URLKeyRepository
from fastapi import HTTPException
import logging
import json
from app.db.sql.connection import AsyncSessionLocal
from app.utils.circuit_breaker import with_retry, with_circuit_breaker, postgres_circuit_breaker, mongo_circuit_breaker
from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)

class URLService:

    @staticmethod
    @with_retry(max_retries=3, delay=0.5)
    @with_circuit_breaker(postgres_circuit_breaker)
    async def _get_unused_key(session: AsyncSessionLocal):
        """
        Retrieves an unused key from PostgreSQL, protected by a retry and circuit breaker.
        """
        return await URLKeyRepository.get_unused_key(session)

    @staticmethod
    @with_retry(max_retries=3, delay=0.5)
    @with_circuit_breaker(postgres_circuit_breaker)
    async def _populate_keys(session: AsyncSessionLocal, count: int):
        """
        Populates keys in PostgreSQL, protected by a retry and circuit breaker.
        """
        await URLKeyRepository.pre_populate_keys(session, count)

    @staticmethod
    @with_retry(max_retries=3, delay=0.5)
    @with_circuit_breaker(mongo_circuit_breaker)
    async def _insert_url_into_mongo(mongo_db, url_data: URL):
        """
        Inserts a URL into MongoDB, protected by a retry and circuit breaker.
        """
        await mongo_db.urls.insert_one(url_data.model_dump())

    @staticmethod
    @with_retry(max_retries=2, delay=0.2)
    @with_circuit_breaker(mongo_circuit_breaker)
    async def _find_url_in_mongo(mongo_db, short_url_id: str):
        """
        Finds a URL in MongoDB, protected by a retry and circuit breaker.
        """
        return await mongo_db.urls.find_one({"short_url_id": short_url_id})

    @staticmethod
    @with_retry(max_retries=3, delay=0.5)
    @with_circuit_breaker(mongo_circuit_breaker)
    async def _delete_url_from_mongo(mongo_db, short_url_id: str):
        """
        Deletes a URL from MongoDB, protected by a retry and circuit breaker.
        """
        await mongo_db.urls.delete_one({"short_url_id": short_url_id})


    @classmethod
    async def store_url(cls, session: AsyncSessionLocal, mongo_db, url: URLCreate):
        try:
            unused_url = await cls._get_unused_key(session)
            if unused_url is None:
                # If no keys, populate one and try again.
                await cls._populate_keys(session, 1)
                unused_url = await cls._get_unused_key(session)
                if unused_url is None:
                    logger.critical("Failed to retrieve an unused key even after populating.")
                    raise HTTPException(status_code=503, detail="Service is temporarily unable to generate new URLs.")

            short_url_id = unused_url.key
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=15)
            
            url_data = URL(
                short_url_id=short_url_id,
                long_url=url.long_url,
                user_id=url.user_id,
                expires_at=expires_at
            )
            
            await cls._insert_url_into_mongo(mongo_db, url_data)
            
            logger.info(f"URL stored successfully: {short_url_id}")
            return url_data
        except HTTPException as http_exc:
            # Re-raise HTTPException to avoid being caught by the generic exception handler
            raise http_exc
        except Exception as e:
            logger.error(f"Error storing URL: {e}")
            # This is a good place to use the handle_pool_exhaustion logic if you want to
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while storing the URL.")

    @classmethod
    async def get_url(cls, mongo_db, redis_client: RedisClient, short_url_id: str):
        try:
            # 1. Try Redis first
            redis_data = await redis_client.get(short_url_id)
            if redis_data:
                url_data = json.loads(redis_data)
                # Check expiration
                expired_at_str = url_data.get("expires_at")
                if expired_at_str:
                    # Assuming the timestamp is in ISO 8601 format with timezone
                    expires_at = datetime.fromisoformat(expired_at_str)
                    if expires_at < datetime.now(timezone.utc):
                        await redis_client.delete(short_url_id)
                        return None  # Expired
                return url_data  # Return data from cache

            # 2. If not in Redis, try MongoDB (with circuit breaker)
            url_data = await cls._find_url_in_mongo(mongo_db, short_url_id)
            if url_data:
                logger.info(f"URL retrieved from DB: {short_url_id}")
                # Convert ObjectId to string for JSON serialization
                url_data['_id'] = str(url_data['_id'])
                # 3. Cache the result in Redis for next time
                await redis_client.set(short_url_id, json.dumps(url_data, default=str), expires_in=1800)
                return url_data
            
            return None  # Not found in DB either

        except Exception as e:
            logger.error(f"Error getting URL: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while retrieving the URL.")

    @classmethod
    async def delete_url(cls, mongo_db, url_data: URLDelete):
        try:
            await cls._delete_url_from_mongo(mongo_db, url_data.short_url_id)
            logger.info(f"URL deleted successfully: {url_data.short_url_id}")
        except Exception as e:
            logger.error(f"Error deleting URL: {e}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while deleting the URL.")