"""Task to remove expired keys from MongoDB and reset PostgreSQL keys to unused."""
import asyncio
import logging
from datetime import datetime, timezone
from worker_service.celery_app import celery_app, AsyncTask
from common.core.config import settings
from common.db.nosql.connection import get_db
from common.db.sql.models import URL
from common.db.sql.connection import get_celery_db_session
from sqlalchemy import select, update
from opentelemetry import trace

logger = logging.getLogger(__name__)


@celery_app.task(
    name='remove_expired_keys',
    bind=True,
    base=AsyncTask,
    max_retries=settings.task_max_retries,
    default_retry_delay=settings.task_retry_delay,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
async def remove_expired_keys(self):
    """Remove expired keys from MongoDB and reset PostgreSQL keys to unused."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("remove_expired_keys") as span:
        span_ctx = span.get_span_context()

        logger.info(
            "Starting expired keys cleanup task",
            extra={"span_context": span_ctx}
        )

        try:
            # Get current UTC time
            now = datetime.now(timezone.utc)
            span.set_attribute("cleanup_time", now.isoformat())

            # Get MongoDB connection
            span.add_event("getting_mongodb_connection")
            mongo_db = get_db()

            # Find expired URLs in MongoDB
            span.add_event("finding_expired_urls")
            expired_urls_cursor = mongo_db.urls.find({
                "expires_at": {"$lt": now},
                "is_deleted": {"$ne": True}
            })

            expired_urls = await expired_urls_cursor.to_list(length=None)
            expired_count = len(expired_urls)
            span.set_attribute("expired_count", expired_count)

            if expired_count == 0:
                span.add_event("no_expired_urls_found")
                logger.info(
                    "No expired URLs found",
                    extra={"span_context": span_ctx}
                )
                return {"status": "success", "expired_removed": 0, "keys_reset": 0}

            logger.info(
                "Found expired URLs to clean up",
                extra={"span_context": span_ctx, "expired_count": expired_count}
            )

            # Extract short_url_ids for PostgreSQL update
            expired_keys = [url["short_url_id"] for url in expired_urls if "short_url_id" in url]
            span.set_attribute("expired_keys", expired_keys)

            # Remove expired URLs from MongoDB
            span.add_event("deleting_from_mongodb")
            delete_result = await mongo_db.urls.delete_many({
                "expires_at": {"$lt": now},
                "is_deleted": {"$ne": True}
            })
            span.set_attribute("deleted_from_mongodb", delete_result.deleted_count)

            logger.info(
                "Removed expired URLs from MongoDB",
                extra={"span_context": span_ctx, "deleted_count": delete_result.deleted_count}
            )

            # Reset PostgreSQL keys to unused
            keys_reset = 0
            if expired_keys:
                span.add_event("resetting_postgresql_keys")
                async for session in get_celery_db_session():
                    # Update keys back to unused status
                    stmt = update(URL).where(
                        URL.key.in_(expired_keys),
                        URL.is_used == True
                    ).values(is_used=False)

                    result = await session.execute(stmt)
                    keys_reset = result.rowcount  # type: ignore[attr-defined]
                    await session.commit()

                    span.set_attribute("keys_reset", keys_reset)
                    logger.info(
                        "Reset keys to unused status",
                        extra={"span_context": span_ctx, "keys_reset": keys_reset}
                    )
                    break

            span.set_status(trace.Status(trace.StatusCode.OK))

            return {
                "status": "success",
                "expired_removed": delete_result.deleted_count,
                "keys_reset": keys_reset,
                "cleanup_time": now.isoformat()
            }

        except Exception as exc:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            span.add_event("cleanup_failed", attributes={"error": str(exc)})
            logger.error(
                "Expired keys cleanup failed",
                extra={"span_context": span_ctx, "error": str(exc)}
            )
            raise
