import asyncio
import logging
from worker_service.celery_app import celery_app, AsyncTask
from common.db.sql.connection import get_celery_db_session
from common.db.sql.models import URL
from common.db.sql.url_repository import URLKeyRepository
from common.core.config import settings
from opentelemetry import trace

logger = logging.getLogger(__name__)

# @celery_app.task(bind=True, name="pre_populate_keys")
# def pre_populate_keys(self, count: int = None):
#     """Pre-populate database with unused short URL keys."""
#     if count is None:
#         count = settings.key_population_count
#
#     try:
#         logger.info(f"Starting key pre-population with {count} keys")
#
#         asyncio.run(_async_pre_populate_keys(count))
#
#         logger.info(f"Successfully pre-populated {count} keys")
#         return {"status": "success", "count": count}
#
#     except Exception as exc:
#         logger.error(f"Key pre-population failed: {exc}")
#         # Retry with exponential backoff
#         raise self.retry(
#             exc=exc,
#             countdown=settings.task_retry_delay,
#             max_retries=settings.task_max_retries
#         )

# async def _async_pre_populate_keys(count: int):
#     """Helper function to handle async DB operations."""
#     # Use fresh database session for each Celery task to avoid connection conflicts
#     session_gen = get_celery_db_session()
#     session = await session_gen.__anext__()
#     try:
#         await URL.pre_populate_keys(session, count)
#     finally:
#         await session_gen.aclose()

# # Periodic task configuration is now handled in celery_app.py

# if __name__ == "__main__":
#     # For testing - uses config default count
#     pre_populate_keys.delay()

@celery_app.task(
    name='pre_populate_keys',
    bind=True,
    base=AsyncTask,  # Use our custom AsyncTask base class
    max_retries=settings.task_max_retries,
    default_retry_delay=settings.task_retry_delay,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
async def pre_populate_keys(self, count: int = None):
    """Pre-populate database with unused short URL keys using optimized hybrid strategy."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("pre_populate_keys") as span:
        span_ctx = span.get_span_context()

        if count is None:
            count = settings.key_population_count

        span.set_attribute("key_count", count)
        logger.info(
            "Starting key pre-population with hybrid strategy",
            extra={"span_context": span_ctx, "count": count}
        )

        try:
            span.add_event("getting_db_session")
            async for session in get_celery_db_session():
                span.add_event("calling_repository_pre_populate_hybrid")
                # Use the optimized hybrid approach that auto-selects the best strategy
                inserted_count = await URLKeyRepository.pre_populate_keys_hybrid(session, count)

                span.set_attribute("inserted_count", inserted_count)
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info(
                    "Keys inserted successfully using hybrid strategy",
                    extra={
                        "span_context": span_ctx,
                        "inserted_count": inserted_count,
                        "trace_id": f"{span_ctx.trace_id:032x}",
                        "span_id": f"{span_ctx.span_id:016x}"
                    }
                )

                return {
                    "status": "success",
                    "count": inserted_count,
                }
        except Exception as exc:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            span.add_event("pre_population_failed", attributes={"error": str(exc)})
            logger.error(
                "Key pre-population failed",
                extra={"span_context": span_ctx, "error": str(exc)}
            )
            raise


