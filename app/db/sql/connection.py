from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DB_URL_ASYNC = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

engine = create_async_engine(DB_URL_ASYNC, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db_async():
    async with AsyncSessionLocal() as session:
        yield session

async def close_db_async(session: AsyncSession):
    await session.close()

# For Celery tasks - create fresh session without connection pooling issues
async def get_celery_db_session():
    """Create a fresh database session for Celery tasks to avoid connection conflicts."""
    # Create a new engine for each Celery task to avoid connection pooling issues
    fresh_engine = create_async_engine(DB_URL_ASYNC, future=True, echo=False, pool_size=5, max_overflow=10)
    fresh_session_local = sessionmaker(fresh_engine, expire_on_commit=False, class_=AsyncSession)
    
    async with fresh_session_local() as session:
        try:
            yield session
        finally:
            await session.close()
            await fresh_engine.dispose()
    