"""Celery application configuration."""
import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

# Build Redis URL with auth if password exists
redis_password = f":{settings.redis_password}@" if settings.redis_password else ""
redis_url = f"redis://{redis_password}{settings.redis_host}:{settings.redis_port}/1"

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
    task_routes={
        'app.tasks.prepopulate_db.pre_populate_keys': {'queue': 'db_tasks'},
        'app.tasks.remove_expired_keys.remove_expired_keys': {'queue': 'cleanup_tasks'},
    },
    # Auto-discover tasks from all registered task modules
    include=[
        'app.tasks.prepopulate_db',
        'app.tasks.remove_expired_keys',
    ]
)

# Periodic task configuration from settings
celery_app.conf.beat_schedule = {
    'populate-keys-periodic': {
        'task': 'pre_populate_keys',
        'schedule': float(settings.key_population_schedule),
        'args': ()  # Uses default count from config
    },
    'remove-expired-keys-periodic': {
        'task': 'remove_expired_keys',
        'schedule': float(settings.cleanup_expired_schedule),
        'args': ()  # Uses default count from config
    },
}

# Set default timezone
celery_app.conf.timezone = 'UTC'
