from datetime import datetime, timezone
from services_python.common.core.redis_client import RedisClient
from opentelemetry import trace
import logging
import json

logger = logging.getLogger(__name__)

class RedirectService:

    @staticmethod
    async def _find_url_in_mongo(mongo_db, short_url_id: str):
        """
        Finds a URL in MongoDB - optimized for read performance.
        No circuit breaker for reads - redirects should fail fast.
        Uses projection to fetch only needed fields.
        """
        # Only fetch the fields we need (reduces data transfer)
        projection = {"long_url": 1, "expires_at": 1, "_id": 0}
        result = await mongo_db.urls.find_one(
            {"short_url_id": short_url_id},
            projection
        )
        return result

    @classmethod
    async def get_long_url(cls, short_key: str, mongo_db, redis_client: RedisClient) -> str | None:
        """
        Retrieves the long URL associated with a short key.
        1. Check Redis cache.
        2. If not in cache, check MongoDB.
        3. If in MongoDB, cache the result in Redis.
        """
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("get_long_url") as span:
            span_ctx = span.get_span_context()
            span.set_attribute("short_key", short_key)

            try:
                # 1. Try Redis first (with error handling for cache failures)
                span.add_event("redis_get_called", attributes={"short_key": short_key})
                try:
                    cached_data = await redis_client.get(short_key)
                except Exception as redis_error:
                    # Redis unavailable - fall back to MongoDB
                    span.add_event("redis_get_failed", attributes={"error": str(redis_error)})
                    cached_data = None

                if cached_data:
                    span.add_event("redis_cache_hit", attributes={"short_key": short_key})
                    try:
                        url_data = json.loads(cached_data)
                    except Exception:
                        # Invalid cache data - delete and fall through to MongoDB
                        try:
                            await redis_client.delete(short_key)
                        except Exception:
                            pass
                        cached_data = None

                    if url_data:
                        # Check expiration
                        expires_at_str = url_data.get("expires_at")
                        if expires_at_str:
                            span.add_event("expiration_check", attributes={"expires_at": expires_at_str})
                            expires_at = datetime.fromisoformat(expires_at_str)
                            # Handle both naive and aware datetimes from cache
                            if expires_at.tzinfo is None:
                                expires_at = expires_at.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            if expires_at < now:
                                try:
                                    await redis_client.delete(short_key)
                                except Exception as redis_error:
                                    span.add_event("redis_delete_failed", attributes={"error": str(redis_error)})
                                    logger.warning(f"Failed to delete expired URL from Redis: {redis_error}")
                                span.add_event("url_expired", attributes={"short_key": short_key})
                                logger.info(f"Expired URL removed from cache: {short_key}")
                                return None

                        span.add_event("returning_cached_url", attributes={"short_key": short_key})
                        long_url = url_data.get("long_url")
                        logger.debug(f"Returning cached URL for {short_key}: {long_url}")
                        return long_url

                # 2. If not in Redis, try MongoDB
                span.add_event("mongo_find_called", attributes={"short_key": short_key})
                url_data = await cls._find_url_in_mongo(mongo_db, short_key)

                if url_data:
                    span.add_event("mongo_db_hit", attributes={"short_key": short_key})
                    long_url = url_data.get("long_url")

                    # Check expiration in DB
                    expires_at = url_data.get("expires_at")
                    if expires_at:
                        # Handle both datetime objects and ISO strings
                        if isinstance(expires_at, str):
                            expires_at = datetime.fromisoformat(expires_at)
                        # Ensure datetime has timezone info
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        if expires_at < datetime.now(timezone.utc):
                            span.add_event("url_expired_in_db", attributes={"short_key": short_key})
                            logger.info(
                                "URL found in DB but expired",
                                extra={"span_context": span_ctx, "short_key": short_key}
                            )
                            return None

                    # 3. Cache the result in Redis for next time (optimized)
                    # Only cache what we need - don't store _id
                    cache_data = {
                        "long_url": long_url,
                        "expires_at": expires_at.isoformat() if expires_at else None
                    }
                    span.add_event("redis_set_called", attributes={"short_key": short_key})
                    try:
                        await redis_client.set(short_key, json.dumps(cache_data), expires_in=1800)  # 30 min cache
                        span.add_event("redis_cache_updated", attributes={"short_key": short_key})
                    except Exception as redis_error:
                        # Redis unavailable - log warning but don't fail the request
                        span.add_event("redis_set_failed", attributes={"error": str(redis_error)})
                        logger.warning(
                            f"Failed to cache URL in Redis: {redis_error}"
                        )

                    logger.info(f"DB hit - cached and returning: {short_key}")
                    return long_url

                span.add_event("url_not_found", attributes={"short_key": short_key})
                span.set_status(trace.Status(trace.StatusCode.ERROR, "URL not found"))
                logger.warning(
                    "URL not found in cache or DB",
                    extra={"span_context": span_ctx, "short_key": short_key}
                )
                return None

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.add_event("error_retrieving_url", attributes={"short_key": short_key, "error": str(e)})
                logger.error(
                    "Error retrieving URL",
                    extra={
                        "span_context": span_ctx,
                        "short_key": short_key,
                        "error": str(e)
                    }
                )
                raise
