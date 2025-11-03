import asyncio
import logging
from app.core.celery_app import celery_app, AsyncTask
from app.db.sql.connection import get_celery_db_session
from app.db.sql.models import URL
from app.db.sql.url_repository import URLKeyRepository
from app.core.config import settings

logger = logging.getLogger(__name__)

# @celery_app.task(bind=True, name="pre_populate_keys")
# def pre_populate_keys(self, count: int = None):
#     """Pre-populate database with unused short URL keys."""
#     if count is None:
#         count = settings.key_population_count
        
#     try:
#         logger.info(f"Starting key pre-population with {count} keys")
        
#         asyncio.run(_async_pre_populate_keys(count))
        
#         logger.info(f"Successfully pre-populated {count} keys")
#         return {"status": "success", "count": count}
        
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
async def pre_populate_keys(self, count: int = 0):
    """Pre-populate database with unused short URL keys."""
    if count is None:
        count = settings.key_population_count

    logger.info(f"Starting key pre-population with {count} keys")

    try:
        async for session in get_celery_db_session():
            inserted_count = await URLKeyRepository.pre_populate_keys(session, count)

            logger.info(f"Inserted {inserted_count} keys into the database")

            return {
                "status": "success",
                "count": inserted_count,
            }
    except Exception as exc:
        logger.error(f"Key pre-population failed: {exc}")
        raise



