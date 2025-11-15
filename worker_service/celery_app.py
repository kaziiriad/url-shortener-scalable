import asyncio
import logging
from celery import Celery, Task
from celery.signals import worker_init, worker_shutdown, worker_process_init
from common.core.config import settings

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
        'create_service.tasks.prepopulate_db.pre_populate_keys': {'queue': 'db_tasks'},
    },
    # Auto-discover tasks from all registered task modules
    include=[
        'worker_service.tasks.prepopulate_db',
    ],
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # Important for async tasks
        broker_heartbeat = 60,
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
   
    def __call__(self, *args, **kwargs):
        """
        Override __call__ to properly handle async execution.
        Detects if the task's run method is a coroutine and handles it.
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
        
        # Call the actual task function
        result = self.run(*args, **kwargs)
        
        # If it's a coroutine, run it in the event loop
        if asyncio.iscoroutine(result):
            return loop.run_until_complete(result)
        
        # Otherwise, return the result directly (for sync tasks)
        return result
    


# --- Worker Lifecycle Hooks ---
@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize each worker process with a fresh event loop.
    This runs BEFORE any tasks execute in the worker.
    """
    logger.info("Initializing worker process...")
    
    # Close any existing event loop
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()
    except RuntimeError:
        pass
    
    # Create fresh event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logger.info("Worker process initialized with fresh event loop")

@worker_init.connect
def configure_celery_worker_db(sender=None, conf=None, **kwargs):
    """
    Initialize database engine for Celery worker on startup.
    This runs once per worker (not per task).
    """
    logger.info("Configuring Celery worker database...")
    
@worker_shutdown.connect
def cleanup_celery_worker_db(sender=None, conf=None, **kwargs):
    """
    Cleanup database connections on worker shutdown.
    """
    logger.info("Cleaning up Celery worker database...")
    
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            # Now we can close the loop
            loop.close()
    except RuntimeError as e:
        logger.warning(f"Error during cleanup: {e}")
    
    logger.info("Worker cleanup completed")

def run_async_task(coro):
    """
    Helper function to run async coroutines in Celery tasks.
    Creates a fresh event loop if needed.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)