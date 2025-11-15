"""Task to remove expired keys from MongoDB and reset PostgreSQL keys to unused."""
import asyncio
import logging
from datetime import datetime, timezone
from create_service.core.celery_app import celery_app
from common.core.config import settings
from common.db.nosql.connection import get_db
from common.db.sql.models import URL
from common.db.sql.connection import get_celery_db_session
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="remove_expired_keys")
def remove_expired_keys(self):
    """Remove expired keys from MongoDB and reset PostgreSQL keys to unused."""
    try:
        logger.info("Starting expired keys cleanup task")
        
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_async_cleanup_expired_keys())
            logger.info(f"Expired keys cleanup completed: {result}")
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Expired keys cleanup failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(
            exc=exc, 
            countdown=settings.task_retry_delay, 
            max_retries=settings.task_max_retries
        )

async def _async_cleanup_expired_keys():
    """Helper function to handle async cleanup operations."""
    # Create fresh connections for this task
    # DB_URL_ASYNC = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    
    # engine = create_async_engine(DB_URL_ASYNC, future=True, echo=False)
    # AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    mongo_db = get_db()
    
    try:
        # Get current UTC time
        now = datetime.now(timezone.utc)
        
        # Find expired URLs in MongoDB
        expired_urls_cursor = mongo_db.urls.find({
            "expires_at": {"$lt": now},
            "is_deleted": {"$ne": True}
        })
        
        expired_urls = await expired_urls_cursor.to_list(length=None)
        expired_count = len(expired_urls)
        
        if expired_count == 0:
            logger.info("No expired URLs found")
            return {"status": "success", "expired_removed": 0, "keys_reset": 0}
        
        logger.info(f"Found {expired_count} expired URLs to clean up")
        
        # Extract short_url_ids for PostgreSQL update
        expired_keys = [url["short_url_id"] for url in expired_urls if "short_url_id" in url]
        
        # Remove expired URLs from MongoDB
        delete_result = await mongo_db.urls.delete_many({
            "expires_at": {"$lt": now},
            "is_deleted": {"$ne": True}
        })
        
        logger.info(f"Removed {delete_result.deleted_count} expired URLs from MongoDB")
        
        # Reset PostgreSQL keys to unused
        keys_reset = 0
        if expired_keys:
            session_gen = get_celery_db_session()
            session = await session_gen.__anext__()
            try:
                # Update keys back to unused status
                stmt = update(URL).where(
                    URL.key.in_(expired_keys),
                    URL.is_used == True
                ).values(is_used=False)
                
                result = await session.execute(stmt)
                keys_reset = result.rowcount  # type: ignore[attr-defined]
                await session.commit()
                
                logger.info(f"Reset {keys_reset} keys to unused status in PostgreSQL")
            finally:
                await session_gen.aclose()
        
        return {
            "status": "success", 
            "expired_removed": delete_result.deleted_count,
            "keys_reset": keys_reset,
            "cleanup_time": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise e
    # No cleanup needed - AsyncSessionLocal handles it automatically
