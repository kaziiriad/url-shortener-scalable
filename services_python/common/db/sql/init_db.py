"""Database initialization module."""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncEngine
from services_python.common.db.sql.connection import engine, Base
from services_python.common.db.sql.models import URL  # Import all models to register them

logger = logging.getLogger(__name__)

async def create_tables(engine: AsyncEngine):
    """Create all database tables."""
    try:
        async with engine.begin() as conn:
            # Drop all tables (for development - remove in production)
            # await conn.run_sync(Base.metadata.drop_all)
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise

async def init_database():
    """Initialize the database by creating tables."""
    logger.info("🔄 Initializing database...")
    await create_tables(engine)
    logger.info("✅ Database initialization completed")

if __name__ == "__main__":
    # Run initialization directly
    print("🔄 Initializing database tables...")
    try:
        asyncio.run(init_database())
        print("✅ Database initialization completed successfully!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import sys
        sys.exit(1)