import asyncio
import logging
from app.db.sql.models import URL
from app.db.sql.connection import get_celery_db_session
from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="pre_populate_keys")
def pre_populate_keys(self, count: int = None):
    """Pre-populate database with unused short URL keys."""
    if count is None:
        count = settings.key_population_count
        
    try:
        logger.info(f"Starting key pre-population with {count} keys")
        
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_async_pre_populate_keys(count))
            logger.info(f"Successfully pre-populated {count} keys")
            return {"status": "success", "count": count}
        finally:
            loop.close()
        
    except Exception as exc:
        logger.error(f"Key pre-population failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(
            exc=exc, 
            countdown=settings.task_retry_delay, 
            max_retries=settings.task_max_retries
        )

async def _async_pre_populate_keys(count: int):
    """Helper function to handle async DB operations."""
    # Use fresh database session for each Celery task to avoid connection conflicts
    session_gen = get_celery_db_session()
    session = await session_gen.__anext__()
    try:
        await URL.pre_populate_keys(session, count)
        
    finally:
        await session_gen.aclose()

# Periodic task configuration is now handled in celery_app.py

if __name__ == "__main__":
    # For testing - uses config default count
    pre_populate_keys.delay()