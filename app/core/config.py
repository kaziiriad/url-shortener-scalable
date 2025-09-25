from pydantic_settings import BaseSettings
from typing import Optional, Any, List
from dotenv import load_dotenv
import os

load_dotenv("../../.env")

class Settings(BaseSettings):
    TESTING: bool = False
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = os.getenv("REDIS_PORT", 6379)
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    db_name: str = os.getenv("DB_NAME", "url_shortener")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = os.getenv("DB_PORT", 5432)
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")

    host: str = os.getenv("HOST", "localhost")
    port: int = os.getenv("PORT", 8000)
    base_url: str = os.getenv("BASE_URL", f"http://{host}:{port}")

    # Celery task configuration
    key_population_count: int = int(os.getenv("KEY_POPULATION_COUNT", "10"))
    key_population_schedule: int = int(os.getenv("KEY_POPULATION_SCHEDULE", "1800"))  # seconds
    task_retry_delay: int = int(os.getenv("TASK_RETRY_DELAY", "60"))  # seconds
    task_max_retries: int = int(os.getenv("TASK_MAX_RETRIES", "3"))
    
    # Cleanup task configuration
    cleanup_expired_schedule: int = int(os.getenv("CLEANUP_EXPIRED_SCHEDULE", "86400"))  # daily

    # Celery database connection pooling settings
    celery_db_pool_size: int = int(os.getenv("CELERY_DB_POOL_SIZE", "4"))
    celery_db_max_overflow: int = int(os.getenv("CELERY_DB_MAX_OVERFLOW", "8"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()