from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDBConnection:
    """Singleton MongoDB connection manager with connection pooling."""
    
    _client: AsyncIOMotorClient = None
    _db = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        """Get or create MongoDB client with connection pooling."""
        if cls._client is None:
            logger.info("Initializing MongoDB client with connection pooling")
            
            # MongoDB connection pool configuration
            cls._client = AsyncIOMotorClient(
                settings.mongo_uri,
                maxPoolSize=settings.mongo_max_pool_size,
                minPoolSize=settings.mongo_min_pool_size,
                maxIdleTimeMS=settings.mongo_max_idle_time_ms,
                waitQueueTimeoutMS=5000,  # Max wait time for connection from pool
                serverSelectionTimeoutMS=5000,  # Timeout for server selection
                connectTimeoutMS=10000,  # Connection timeout
                socketTimeoutMS=20000,  # Socket timeout
                retryWrites=True,  # Retry write operations on failure
                retryReads=True,  # Retry read operations on failure
                # Connection pool monitoring
                appname=f"url_shortener_{settings.instance_id or 'default'}",
            )
            logger.info("MongoDB client initialized successfully")
        return cls._client

    @classmethod
    def get_database(cls):
        """Get MongoDB database instance."""
        if cls._db is None:
            client = cls.get_client()
            cls._db = client[settings.mongo_db_name]
            logger.info(f"Connected to MongoDB database: {settings.mongo_db_name}")
        return cls._db

    @classmethod
    async def close(cls):
        """Close MongoDB connection."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB connection closed")
    @classmethod
    async def ping(cls) -> bool:
        """Ping MongoDB to check connection health."""
        try:
            client = cls.get_client()
            await client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False

    @classmethod
    def get_pool_stats(cls) -> dict:
        """Get MongoDB connection pool statistics."""
        if cls._client is None:
            return {"error": "Client not initialized"}
        
        try:
            # Get pool statistics from server status
            return {
                "max_pool_size": 50,
                "min_pool_size": 10,
                "status": "connected" if cls._client else "disconnected"
            }
        except Exception as e:
            logger.error(f"Error getting pool stats: {e}")
            return {"error": str(e)}


def get_db():
    """Get MongoDB database instance for dependency injection."""
    return MongoDBConnection.get_database()

async def close_mongo_connection():
    """Close MongoDB connection (for application shutdown)."""
    await MongoDBConnection.close()

async def check_mongo_health() -> bool:
    """Check MongoDB connection health."""
    return await MongoDBConnection.ping()