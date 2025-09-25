from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DB_URL_ASYNC = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

# Engine and session for FastAPI application
engine = create_async_engine(DB_URL_ASYNC, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db_async():
    async with AsyncSessionLocal() as session:
        yield session

async def close_db_async(session: AsyncSession):
    await session.close()

# --- Celery specific database connection pooling ---
celery_engine = None
CeleryAsyncSessionLocal = None

async def init_celery_db():
    """Initialize a single, shared database engine for Celery tasks."""
    global celery_engine, CeleryAsyncSessionLocal
    if celery_engine is None:
        # Configure pool_size and max_overflow based on expected Celery concurrency
        # These values should be tuned based on your PostgreSQL server's max_connections
        # and Celery worker's concurrency settings.
        celery_engine = create_async_engine(
            DB_URL_ASYNC,
            future=True,
            echo=False,
            pool_size=settings.celery_db_pool_size,
            max_overflow=settings.celery_db_max_overflow
        )
        CeleryAsyncSessionLocal = sessionmaker(celery_engine, expire_on_commit=False, class_=AsyncSession)

async def close_celery_db():
    """Dispose of the Celery database engine on worker shutdown."""
    global celery_engine
    if celery_engine:
        await celery_engine.dispose()
        celery_engine = None

async def get_celery_db_session():
    """Provide a database session from the shared pool for Celery tasks."""
    if celery_engine is None:
        # This should ideally not happen if init_celery_db is called on startup
        await init_celery_db()
    
    async with CeleryAsyncSessionLocal() as session:
        yield session

    