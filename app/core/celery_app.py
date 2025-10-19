import asyncio
import logging
from celery import Celery, Task
from celery.signals import worker_init, worker_shutdown, worker_process_init
from app.core.config import settings
from app.db.sql.connection import init_celery_db, close_celery_db # Import new functions

logger = logging.getLogger(__name__)

# Build Redis URL with auth if password exists
redis_password = f":{settings.redis_password}@{settings.redis_host}" if settings.redis_password else settings.redis_host
redis_url = f"redis://{redis_password}:{settings.redis_port}/1"

# Create Celery application
celery_app = Celery(
    "url_shortener_tasks",
    broker=redis_url,
    backend=redis_url,
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_pool='solo',
    task_routes={
        'app.tasks.prepopulate_db.pre_populate_keys': {'queue': 'db_tasks'},
    },
    # Auto-discover tasks from all registered task modules
    include=[
        'app.tasks.prepopulate_db',
    ],
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Important for async tasks

)

# Periodic task configuration from settings
celery_app.conf.beat_schedule = {
    'populate-keys-periodic': {
        'task': 'pre_populate_keys',
        'schedule': float(settings.key_population_schedule),
        'args': ()  # Uses default count from config
    }
    # 'remove-expired-keys-periodic': {
    #     'task': 'remove_expired_keys',
    #     'schedule': float(settings.cleanup_expired_schedule),
    #     'args': ()  # Uses default count from config
    # },
}

# Set default timezone
celery_app.conf.timezone = 'UTC'


class AsyncTask(Task):
    """
    Base task class that properly handles async functions.
    Creates a new event loop for each task execution.
    """
    
    _loop = None
    
    def __call__(self, *args, **kwargs):
        """
        Override __call__ to properly handle async execution.
        Creates a fresh event loop for each task.
        """
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
        except RuntimeError:
            # Create new event loop if none exists or if closed
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            # Run the async task
            return loop.run_until_complete(self.run_async(*args, **kwargs))
        finally:
            # Don't close the loop - reuse it for next task
            pass
    
    async def run_async(self, *args, **kwargs):
        """
        Override this in subclasses instead of run().
        This is the actual async implementation.
        """
        raise NotImplementedError("Subclasses must implement run_async()")


# --- Worker Lifecycle Hooks ---
# @worker_init.connect
# def configure_celery_worker_db(sender=None, conf=None, **kwargs):
#     """Initialize database engine for Celery worker on startup."""
#     import asyncio
#     # Celery worker_init runs in a separate thread/process, so we need to manage event loop
#     loop = asyncio.get_event_loop()
#     if loop.is_running():
#         loop.create_task(init_celery_db())
#     else:
#         loop.run_until_complete(init_celery_db())

# @worker_shutdown.connect
# def cleanup_celery_worker_db(sender=None, conf=None, **kwargs):
#     """Dispose of database engine for Celery worker on shutdown."""
#     import asyncio
#     loop = asyncio.get_event_loop()
#     if loop.is_running():
#         loop.create_task(close_celery_db())
#     else:
#         loop.run_until_complete(close_celery_db())

@worker_process_init.connect
def init_worker_process(**kwargs):

    logger.info("Celery worker process initialized")

    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()
    except RuntimeError:
        pass
    
    # Create fresh event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize database connections
    loop.run_until_complete(init_celery_db())
    
    logger.info("Worker process initialized with fresh event loop")

@worker_init.connect
def configure_celery_worker_db(sender=None, conf=None, **kwargs):

    logger.info("Configuring Celery worker database...")

    # For solo/threads pool, we handle this in worker_process_init
    # This is here for compatibility
    if sender and hasattr(sender, 'pool') and sender.pool.__class__.__name__ not in ['Solo', 'ThreadPool']:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(init_celery_db())
            else:
                loop.run_until_complete(init_celery_db())
        except RuntimeError:
            logger.warning("Could not initialize DB in worker_init - will initialize in tasks")

@worker_shutdown.connect
def cleanup_celery_worker_db(sender=None, conf=None, **kwargs):

    logger.info("Cleaning up Celery worker database...")

    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.run_until_complete(close_celery_db())
            loop.close()
    except RuntimeError:

        logger.warning("Could not close DB in worker_shutdown - will close in tasks")
    
    logger.info("Celery worker database cleanup complete")

def run_async_task(coro):

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)