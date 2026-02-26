from datetime import datetime, timezone
from common.core.redis_client import RedisClient
from common.utils.circuit_breaker import with_circuit_breaker, mongo_circuit_breaker
from opentelemetry import trace
import logging
import json

logger = logging.getLogger(__name__)

class RedirectService:

    @staticmethod
    @with_circuit_breaker(mongo_circuit_breaker)
    async def _find_url_in_mongo(mongo_db, short_url_id: str):
        """
        Finds a URL in MongoDB with circuit breaker protection.
        Note: No retry logic for reads - fail fast for better redirect performance.
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("_find_url_in_mongo") as span:
            span.set_attribute("short_url_id", short_url_id)
            result = await mongo_db.urls.find_one({"short_url_id": short_url_id})
            span.set_attribute("found", result is not None)
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
                # 1. Try Redis first
                span.add_event("redis_get_called", attributes={"short_key": short_key})
                cached_data = await redis_client.get(short_key)

                if cached_data:
                    span.add_event("redis_cache_hit", attributes={"short_key": short_key})
                    url_data = json.loads(cached_data)

                    # Check expiration
                    expires_at_str = url_data.get("expires_at")
                    if expires_at_str:
                        span.add_event("expiration_check", attributes={"expires_at": expires_at_str})
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at < datetime.now(timezone.utc):
                            await redis_client.delete(short_key)
                            span.add_event("url_expired", attributes={"short_key": short_key})
                            logger.info(
                                "Expired URL removed from cache",
                                extra={"span_context": span_ctx, "short_key": short_key}
                            )
                            return None

                    span.add_event("returning_cached_url", attributes={"short_key": short_key})
                    logger.info(
                        "Cache hit",
                        extra={
                            "span_context": span_ctx,
                            "short_key": short_key,
                            "trace_id": f"{span_ctx.trace_id:032x}",
                            "span_id": f"{span_ctx.span_id:016x}"
                        }
                    )
                    return url_data.get("long_url")

                # 2. If not in Redis, try MongoDB
                span.add_event("mongo_find_called", attributes={"short_key": short_key})
                url_data = await cls._find_url_in_mongo(mongo_db, short_key)

                if url_data:
                    span.add_event("mongo_db_hit", attributes={"short_key": short_key})
                    long_url = url_data.get("long_url")

                    # Check expiration in DB
                    expires_at_str = url_data.get("expires_at")
                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at < datetime.now(timezone.utc):
                            span.add_event("url_expired_in_db", attributes={"short_key": short_key})
                            logger.info(
                                "URL found in DB but expired",
                                extra={"span_context": span_ctx, "short_key": short_key}
                            )
                            return None

                    # 3. Cache the result in Redis for next time
                    # Convert ObjectId to string for JSON serialization
                    url_data['_id'] = str(url_data['_id'])
                    span.add_event("redis_set_called", attributes={"short_key": short_key})
                    await redis_client.set(short_key, json.dumps(url_data, default=str), expires_in=1800)  # 30 min cache
                    span.add_event("redis_cache_updated", attributes={"short_key": short_key})

                    logger.info(
                        "DB hit - cached and returning",
                        extra={
                            "span_context": span_ctx,
                            "short_key": short_key,
                            "trace_id": f"{span_ctx.trace_id:032x}",
                            "span_id": f"{span_ctx.span_id:016x}"
                        }
                    )
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
