from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

DB_URL_ASYNC = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

# Connection Pool Sizing Strategy:
# Rule of thumb: pool_size = (number of CPUs * 2) + effective_spindle_count
# For web apps: pool_size = expected concurrent requests / instances
# Total connections = (FastAPI instances * pool_size) + (Celery workers * celery_pool_size)

# Engine and session for FastAPI application
engine = create_async_engine(
    DB_URL_ASYNC,
    future=True,
    echo=False,
    pool_size=10,  # Base pool size per FastAPI instance
    max_overflow=20,  # Additional connections under load
    pool_pre_ping=True,  # Verify connections before use (prevents stale connections)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents timeout issues)
    pool_timeout=30,  # Wait max 30s for connection from pool
    echo_pool=False,  # Set to True for debugging connection pool
    connect_args={
        "server_settings": {
            "application_name": f"url_shortener_fastapi_{settings.instance_id or 'default'}",
        },
        "command_timeout": 60,  # Query timeout
        "timeout": 10,  # Connection timeout
    }
)
AsyncSessionLocal = sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession,
    autoflush=False  # Manual control for better performance
)
Base = declarative_base()

async def get_db_async():
    """Dependency for FastAPI routes - ensures proper connection lifecycle."""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()

async def close_db_async(session: AsyncSession):
    await session.close()

# --- Celery specific database connection pooling ---
celery_engine = None
CeleryAsyncSessionLocal = None

async def init_celery_db():
    """
    Initialize a single, shared database engine for Celery tasks.
    
    Connection Pool Sizing for Celery:
    - pool_size should be >= celery worker concurrency
    - If you have 4 workers with concurrency=4 each, you need at least 16 connections
    - Add max_overflow for burst capacity
    """
    global celery_engine, CeleryAsyncSessionLocal
    if celery_engine is None:
        # Configure pool_size and max_overflow based on expected Celery concurrency
        # These values should be tuned based on your PostgreSQL server's max_connections
        # and Celery worker's concurrency settings.
        celery_concurrency = settings.celery_concurrency or 4
        celery_pool_size = settings.celery_db_pool_size or (celery_concurrency * 2)
        celery_max_overflow = settings.celery_db_max_overflow or celery_concurrency
        
        logger.info(f"Initializing Celery DB pool: size={celery_pool_size}, max_overflow={celery_max_overflow}")

        celery_engine = create_async_engine(
            DB_URL_ASYNC,
            future=True,
            echo=False,
            pool_size=celery_pool_size,
            max_overflow=celery_max_overflow,
            pool_pre_ping=True,  # Verify connections (important for long-running workers)
            pool_recycle=1800,  # Recycle after 30 mins (workers run longer)
            pool_timeout=30,
            echo_pool=False,
            connect_args={
                "server_settings": {
                    "application_name": "url_shortener_celery_worker",
                },
                "command_timeout": 120,  # Longer timeout for background tasks
                "timeout": 15,
            }
        )
        CeleryAsyncSessionLocal = sessionmaker(
            celery_engine, 
            expire_on_commit=False, 
            class_=AsyncSession,
            autoflush=False
        )
        logger.info("Celery database engine initialized")

async def close_celery_db():
    """Dispose of the Celery database engine on worker shutdown."""
    global celery_engine, CeleryAsyncSessionLocal
    if celery_engine:
        await celery_engine.dispose()
        celery_engine = None
        CeleryAsyncSessionLocal = None
        logger.info("Celery database engine disposed")

async def get_celery_db_session():
    """Provide a database session from the shared pool for Celery tasks."""
    if celery_engine is None:
        logger.warning("Celery DB engine not initialized, initializing now...")
        await init_celery_db()
    
    session = CeleryAsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        logger.error(f"Celery database session error: {e}")
        raise
    finally:
        await session.close()
    

# --- Connection Pool Monitoring ---
async def get_pool_status(engine_name: str = "fastapi"):
    """Get current connection pool status for monitoring."""
    try:
        target_engine = engine if engine_name == "fastapi" else celery_engine
        if target_engine is None:
            return {"error": f"{engine_name} engine not initialized"}
        
        pool = target_engine.pool
        return {
            "engine": engine_name,
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return {"error": str(e)}