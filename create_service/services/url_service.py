from datetime import datetime, timedelta, timezone
from common.models.schemas import URL, URLCreate, URLDelete
from common.db.sql.url_repository import URLKeyRepository
from fastapi import HTTPException
import logging
import json
import asyncio
from common.db.sql.connection import AsyncSessionLocal
from common.utils.circuit_breaker import with_retry, with_circuit_breaker, postgres_circuit_breaker, mongo_circuit_breaker
from common.core.redis_client import RedisClient
from opentelemetry import trace
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Advisory lock key for key pre-population (prevents thundering herd)
_KEY_POPULATE_LOCK_ID = 54321  # Arbitrary unique ID for this lock

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

    @staticmethod
    async def _try_advisory_lock(session: AsyncSessionLocal) -> bool:
        """
        Attempt to acquire a PostgreSQL advisory lock for key pre-population.

        Only one transaction will acquire the lock, preventing the thundering herd
        problem where multiple concurrent requests all trigger pre-population.

        Returns:
            bool: True if lock was acquired, False otherwise
            For SQLite (which doesn't support advisory locks), returns True
            to allow normal operation without the lock optimization.
        """
        try:
            result = await session.execute(
                text(f"SELECT pg_try_advisory_xact_lock({_KEY_POPULATE_LOCK_ID})")
            )
            lock_acquired = result.scalar()
            return lock_acquired
        except Exception as e:
            # SQLite doesn't support advisory locks - that's okay for tests
            # Return True to proceed without the lock optimization
            logger.debug(f"Advisory lock not supported (likely SQLite): {e}")
            return True


    @classmethod
    async def store_url(cls, session: AsyncSessionLocal, mongo_db, url: URLCreate):
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("store_url") as span:
            span_ctx = span.get_span_context()
            span.set_attribute("url", url)
            try:
                span.add_event("unused_key_repository_called")
                unused_url = await cls._get_unused_key(session)
                span.add_event("unused_key_repository_response", attributes={"unused_url": unused_url})

                if unused_url is None:
                    # No keys available - need to populate more
                    # Use advisory lock to prevent thundering herd: only one thread does the populate
                    lock_acquired = await cls._try_advisory_lock(session)

                    if lock_acquired:
                        # This thread acquired the lock - do the populate
                        # Populate a larger batch (1000 keys) to handle concurrent load
                        populate_count = 1000
                        span.add_event("populate_keys_with_lock", attributes={"count": populate_count})
                        logger.info(f"Acquired advisory lock, populating {populate_count} keys")
                        await cls._populate_keys(session, populate_count)
                    else:
                        # Another thread is populating - wait briefly and retry
                        span.add_event("waiting_for_other_thread_populate")
                        logger.info("Another thread is populating keys, waiting...")
                        await asyncio.sleep(0.1)  # Brief wait for other thread to finish

                    # Try to get a key again (may have been populated by this or another thread)
                    span.add_event("unused_key_repository_called_after_populate")
                    unused_url = await cls._get_unused_key(session)
                    span.add_event("unused_key_repository_response_after_populate", attributes={"unused_url": unused_url})

                    if unused_url is None:
                        # Still no keys after populate - service is truly unavailable
                        span.add_event("unused_key_validation_failed")
                        span.set_status(trace.Status(trace.StatusCode.ERROR, "Service is temporarily unable to generate new URLs."))
                        raise HTTPException(status_code=503, detail="Service is temporarily unable to generate new URLs.")
                
                span.add_event("unused_key_validation_success", attributes={"unused_url": unused_url})
                short_url_id = unused_url.key
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(days=15)
                
                url_data = URL(
                    short_url_id=short_url_id,
                    long_url=url.long_url,
                    user_id=url.user_id,
                    expires_at=expires_at
                )
                span.add_event("url_data_created", attributes={"url_data": url_data})
                
                await cls._insert_url_into_mongo(mongo_db, url_data)
                span.add_event("url_inserted_into_mongo", attributes={"url_data": url_data})
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info(
                    "URL stored successfully",
                    extra={
                        "span_context": span_ctx,
                        "url_data": url_data
                    }
                )
                return url_data
            except HTTPException as http_exc:
                # Re-raise HTTPException to avoid being caught by the generic exception handler
                span.set_status(trace.Status(trace.StatusCode.ERROR, "HTTPException occurred while storing URL."))
                logger.error(
                    "HTTPException occurred while storing URL",
                    extra={
                        "span_context": span_ctx,
                        "http_exc": str(http_exc)
                    }
                )
                raise http_exc
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, "Exception occurred while storing URL."))
                logger.error(
                    "Exception occurred while storing URL",
                    extra={
                        "span_context": span_ctx,
                        "e": str(e)
                    }
                )

                raise HTTPException(status_code=500, detail="An unexpected error occurred while storing the URL.")

    @classmethod
    async def get_url(cls, mongo_db, redis_client: RedisClient, short_url_id: str):
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("get_url") as span:
            span_ctx = span.get_span_context()
            span.set_attribute("short_url_id", short_url_id)
            try:
                # 1. Try Redis first
                span.add_event("redis_get_called", attributes={"short_url_id": short_url_id})
                redis_data = await redis_client.get(short_url_id)

                if redis_data:
                    span.add_event("redis_get_success", attributes={"short_url_id": short_url_id})
                    url_data = json.loads(redis_data)
                    span.add_event("url_data_retrieved_from_redis", attributes={"url_data": url_data})

                    # Check expiration
                    expired_at_str = url_data.get("expires_at")
                    if expired_at_str:
                        span.add_event("url_data_expiration_check", attributes={"expires_at": expired_at_str})
                        # Assuming the timestamp is in ISO 8601 format with timezone
                        expires_at = datetime.fromisoformat(expired_at_str)
                        if expires_at < datetime.now(timezone.utc):
                            await redis_client.delete(short_url_id)
                            span.add_event("url_data_expired", attributes={"short_url_id": short_url_id})
                            return None  # Expired

                    return url_data  # Return data from cache

                # 2. If not in Redis, try MongoDB (with circuit breaker)
                span.add_event("mongo_find_called", attributes={"short_url_id": short_url_id})
                url_data = await cls._find_url_in_mongo(mongo_db, short_url_id)
                if url_data:
                    span.add_event("mongo_find_success", attributes={"short_url_id": short_url_id})
                    logger.info(f"URL retrieved from DB: {short_url_id}")
                    span.add_event("url_data_retrieved_from_mongo", attributes={"url_data": url_data})
                    # Convert ObjectId to string for JSON serialization
                    url_data['_id'] = str(url_data['_id'])
                    # 3. Cache the result in Redis for next time
                    await redis_client.set(short_url_id, json.dumps(url_data, default=str), expires_in=1800)
                    span.add_event("url_data_cached_in_redis", attributes={"short_url_id": short_url_id})
                    return url_data

                return None  # Not found in DB either

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(f"Error getting URL: {e}", extra={"span_context": span_ctx})
                raise HTTPException(status_code=500, detail="An unexpected error occurred while retrieving the URL.")

    @classmethod
    async def delete_url(cls, mongo_db, url_data: URLDelete):
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("delete_url") as span:
            span_ctx = span.get_span_context()
            span.set_attribute("short_url_id", url_data.short_url_id)
            try:
                span.add_event("delete_url_called", attributes={"short_url_id": url_data.short_url_id})
                await cls._delete_url_from_mongo(mongo_db, url_data.short_url_id)
                span.add_event("url_deleted_from_mongo", attributes={"short_url_id": url_data.short_url_id})
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info(f"URL deleted successfully: {url_data.short_url_id}")
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(f"Error deleting URL: {e}", extra={"span_context": span_ctx})
                raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the URL.")