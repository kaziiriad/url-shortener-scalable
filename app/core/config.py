from pydantic_settings import BaseSettings
from typing import Optional, Any, List
from dotenv import load_dotenv
import os

load_dotenv("../../.env")

class Settings(BaseSettings):

    # Application
    host: str = os.getenv("HOST", "localhost")
    port: int = os.getenv("PORT", 8000)
    base_url: str = os.getenv("BASE_URL", f"http://{host}:{port}")
    testing: bool = os.getenv("TESTING", False)
    instance_id: Optional[str] = os.getenv("INSTANCE_ID", None)

    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "url_shortener")
    mongo_max_pool_size: int = os.getenv("MONGO_MAX_POOL_SIZE", 50)
    mongo_min_pool_size: int = os.getenv("MONGO_MIN_POOL_SIZE", 10)
    mongo_max_idle_time_ms: int = os.getenv("MONGO_MAX_IDLE_TIME_MS", 45000)
    
    
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = os.getenv("REDIS_PORT", 6379)
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_max_connections: int = os.getenv("REDIS_MAX_CONNECTIONS", 10) # Connection pool size for Redis
    redis_socket_keepalive: bool = os.getenv("REDIS_SOCKET_KEEPALIVE", True)
    redis_socket_timeout: int = os.getenv("REDIS_SOCKET_TIMEOUT", 5)
    

    db_name: str = os.getenv("DB_NAME", "url_shortener")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = os.getenv("DB_PORT", 5432)
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")

    # PostgreSQL Pool Configuration for FastAPI
    db_pool_size: int = os.getenv("DB_POOL_SIZE", 10) # Connections per FastAPI instance
    db_max_overflow: int = os.getenv("DB_MAX_OVERFLOW", 20) # Additional connections under load
    db_pool_timeout: int = os.getenv("DB_POOL_TIMEOUT", 30) # Wait time for connection from pool
    db_pool_recycle: int = os.getenv("DB_POOL_RECYCLE", 3600) # Recycle connections after 1 hour


    host: str = os.getenv("HOST", "localhost")
    port: int = os.getenv("PORT", 8000)
    base_url: str = os.getenv("BASE_URL", f"http://{host}:{port}")

    # Key management
    key_population_count: int = int(os.getenv("KEY_POPULATION_COUNT", "10"))
    key_population_schedule: int = int(os.getenv("KEY_POPULATION_SCHEDULE", "1800"))  # seconds
    key_minimum_threshold: int = os.getenv("KEY_MINIMUM_THRESHOLD", "1000") # Alert if below this

    # Celery task configuration
    task_retry_delay: int = int(os.getenv("TASK_RETRY_DELAY", "60"))  # seconds
    task_max_retries: int = int(os.getenv("TASK_MAX_RETRIES", "3"))
    cleanup_expired_schedule: int = int(os.getenv("CLEANUP_EXPIRED_SCHEDULE", "86400")) # Daily
    
    # Celery database connection pooling settings
    celery_db_pool_size: int = int(os.getenv("CELERY_DB_POOL_SIZE", "4"))
    celery_db_max_overflow: int = int(os.getenv("CELERY_DB_MAX_OVERFLOW", "8"))
    celery_concurrency: int = int(os.getenv("CELERY_CONCURRENCY", "4"))

    # Rate Limiting
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", True)
    create_url_rate_limit: str = os.getenv("CREATE_URL_RATE_LIMIT", "10/minute")
    redirect_rate_limit: str = os.getenv("REDIRECT_RATE_LIMIT", "10/minute")

    


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def calculate_connection_requirements():
    """
    Calculate total PostgreSQL connections needed.
    
    Formula:
    Total = (FastAPI instances * (pool_size + max_overflow)) + 
            (Celery workers * (celery_pool_size + celery_max_overflow))
    
    Example:
    - 3 FastAPI instances: 3 * (10 + 20) = 90 connections
    - 4 Celery workers: 4 * (20 + 10) = 120 connections
    - Total: 210 connections
    - Add 20% buffer: ~252 connections
    
    PostgreSQL max_connections should be set to at least this value.
    """
    num_fastapi_instances = int(os.getenv("NUM_FASTAPI_INSTANCES", 3))
    num_celery_workers = int(os.getenv("NUM_CELERY_WORKERS", 4))
    
    fastapi_connections = num_fastapi_instances * (
        settings.db_pool_size + settings.db_max_overflow
    )
    celery_connections = num_celery_workers * (
        settings.celery_db_pool_size + settings.celery_db_max_overflow
    )
    
    total = fastapi_connections + celery_connections
    with_buffer = int(total * 1.2)  # 20% buffer
    
    return {
        "fastapi_connections": fastapi_connections,
        "celery_connections": celery_connections,
        "total_minimum": total,
        "recommended_with_buffer": with_buffer,
        "current_max_connections": os.getenv("POSTGRES_MAX_CONNECTIONS", "100")
    }

# Validation
def validate_pool_configuration():
    """Validate that pool configuration is reasonable."""
    errors = []
    
    # Check if pools are too large
    if settings.db_pool_size > 50:
        errors.append("db_pool_size is very large (>50). Consider scaling horizontally instead.")
    
    if settings.celery_db_pool_size > 100:
        errors.append("celery_db_pool_size is very large (>100). May exceed PostgreSQL limits.")
    
    # Check if pools are too small
    if settings.db_pool_size < 5:
        errors.append("db_pool_size is too small (<5). May cause connection exhaustion.")
    
    # Check Celery pool vs concurrency
    if settings.celery_db_pool_size < settings.celery_concurrency:
        errors.append(
            f"celery_db_pool_size ({settings.celery_db_pool_size}) should be >= "
            f"celery_concurrency ({settings.celery_concurrency})"
        )
    
    if errors:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Pool configuration issues found:")
        for error in errors:
            logger.warning(f"  - {error}")
    
    return len(errors) == 0

# Run validation on import
if not settings.testing:
    validate_pool_configuration()