import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import mongomock
import fakeredis.aioredis
import asyncio
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def anyio_backend():
    return 'asyncio'

# ============================================
# Test Configuration
# ============================================

@pytest.fixture(scope="session", autouse=True)
def test_config():
    """Configure test settings"""
    os.environ["TESTING"] = "true"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "WARNING"

# ============================================
# Database Fixtures
# ============================================

# --- Redis (fakeredis) ---

# Module-level shared Redis client for tests
_shared_fake_redis = None
_shared_redis_client = None


def get_shared_redis_client():
    """Get or create the shared Redis client for testing"""
    global _shared_fake_redis, _shared_redis_client

    if _shared_redis_client is None:
        from services_python.common.core.redis_client import RedisClient

        # Create the shared fake redis instance
        _shared_fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        class TestRedisClient:
            def __init__(self, fake_redis):
                self._fake_redis = fake_redis

            async def set(self, key: str, value: str, expires_in: int = None) -> None:
                await self._fake_redis.set(key, value, ex=expires_in)

            async def get(self, key: str) -> str | None:
                return await self._fake_redis.get(key)

            async def delete(self, key: str) -> None:
                await self._fake_redis.delete(key)

            async def close(self) -> None:
                pass

            async def ping(self) -> bool:
                return True

        _shared_redis_client = TestRedisClient(_shared_fake_redis)

    return _shared_redis_client


@pytest.fixture
def fake_redis():
    """Fake Redis client for testing (deprecated, use redis_client)"""
    return get_shared_redis_client()._fake_redis


@pytest.fixture
def redis_client():
    """RedisClient wrapper with fake redis backend - shared across tests"""
    return get_shared_redis_client()

# --- MongoDB (mongomock) ---

# Module-level shared MongoDB database for tests
_shared_mongo_db = None


def get_async_mongo_db():
    """Get or create the shared async MongoDB database"""
    global _shared_mongo_db

    if _shared_mongo_db is None:
        # Async wrapper for mongomock collections
        class AsyncCollection:
            def __init__(self, collection):
                self._collection = collection

            async def insert_one(self, doc):
                return self._collection.insert_one(doc)

            async def find_one(self, query, projection=None):
                """Find one document with optional projection."""
                if projection is not None:
                    return self._collection.find_one(query, projection)
                return self._collection.find_one(query)

            async def delete_one(self, query):
                return self._collection.delete_one(query)

            async def update_one(self, query, update, **kwargs):
                return self._collection.update_one(query, update, **kwargs)

            async def find(self, query=None):
                return self._collection.find(query)

        class AsyncDatabase:
            def __init__(self, db):
                self._db = db

            def __getattr__(self, name):
                return AsyncCollection(self._db[name])

        # Create mongomock client and wrap it
        client = mongomock.MongoClient()
        _shared_mongo_db = AsyncDatabase(client.test_db)

    return _shared_mongo_db


@pytest.fixture
def fake_mongo():
    """Fake MongoDB client with async wrappers for testing"""
    return get_async_mongo_db()

# --- PostgreSQL (or SQLite fallback) ---

def _get_test_database_url():
    """
    Get the test database URL.
    Uses PostgreSQL by default (production-like), with SQLite fallback via USE_TEST_SQLITE=true.
    """
    import os

    # Check if SQLite is explicitly requested
    if os.environ.get("USE_TEST_SQLITE") == "true":
        return "sqlite+aiosqlite:///:memory:"

    # Default: Use PostgreSQL (production-like testing)
    pg_host = os.environ.get("TEST_DB_HOST", "localhost")
    pg_port = os.environ.get("TEST_DB_PORT", "5432")
    pg_user = os.environ.get("TEST_DB_USER", "postgres")
    pg_password = os.environ.get("TEST_DB_PASSWORD", "pgpassword")
    pg_db = os.environ.get("TEST_DB_NAME", "url_shortener")

    return f"postgresql+asyncpg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"


@pytest_asyncio.fixture
async def test_db_session():
    """
    Database session for testing.
    Uses PostgreSQL if USE_TEST_POSTGRES=true, otherwise SQLite in-memory.
    """
    from services_python.common.db.sql.models import Base

    TEST_DATABASE_URL = _get_test_database_url()
    is_postgres = "postgresql" in TEST_DATABASE_URL

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    # Cleanup
    if is_postgres:
        # For PostgreSQL, truncate tables instead of dropping schema
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE urls CASCADE"))
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

# ============================================
# FastAPI Test Client
# ============================================

# Import for dependency overrides
from services_python.common.core.redis_client import RedisClient, get_redis_client

@pytest_asyncio.fixture
async def client(monkeypatch, redis_client):
    """Async HTTP test client with mocked databases"""
    from services_python.common.core.config import settings
    settings.testing = True

    from create_service.main import app as fastapi_app
    from services_python.common.db.sql.connection import get_db_async
    from services_python.common.db.sql.models import Base
    from services_python.common.db.nosql.connection import get_db
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Create test database
    TEST_DATABASE_URL = _get_test_database_url()
    is_postgres = "postgresql" in TEST_DATABASE_URL

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override PostgreSQL dependency
    async def override_get_db_async():
        async with TestingSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_async] = override_get_db_async

    # Use the shared MongoDB database (same as client_redirect)
    test_mongo_db = get_async_mongo_db()

    async def override_get_db():
        return test_mongo_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    async def override_redis_client():
        return redis_client

    fastapi_app.dependency_overrides[get_redis_client] = override_redis_client

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        yield c

    # Cleanup
    if is_postgres:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE urls CASCADE"))
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    # Clean up dependency overrides
    fastapi_app.dependency_overrides = {}


@pytest_asyncio.fixture
async def client_redirect(redis_client):
    """Async HTTP test client for redirect service with mocked databases"""
    from services_python.common.core.config import settings
    settings.testing = True

    from redirect_service.main import app as redirect_app
    from services_python.common.db.nosql.connection import get_db

    # Use the shared MongoDB database
    test_mongo_db = get_async_mongo_db()

    async def override_get_db():
        return test_mongo_db

    async def override_redis_client():
        return redis_client

    redirect_app.dependency_overrides[get_db] = override_get_db
    redirect_app.dependency_overrides[get_redis_client] = override_redis_client

    async with AsyncClient(transport=ASGITransport(app=redirect_app), base_url="http://test") as c:
        yield c

    # Clean up dependency overrides
    redirect_app.dependency_overrides = {}

# ============================================
# Test Data Fixtures
# ============================================

@pytest.fixture
def sample_long_urls():
    """Sample long URLs for testing"""
    return [
        "https://example.com/test1",
        "https://github.com/test2",
        "https://stackoverflow.com/questions/test3",
        "https://docs.python.org/test4"
    ]

@pytest.fixture
def sample_user():
    """Sample authenticated user"""
    return {
        "sub": "test_user_123",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User"
    }

@pytest.fixture
def expired_short_key():
    """Returns an expired short key for testing expiration logic"""
    return {
        "short_url_id": "expired123",
        "long_url": "https://example.com/expired",
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    }

@pytest.fixture
def malicious_urls():
    """Malicious or invalid URLs for testing security"""
    return [
        "http://localhost:8080/admin",  # Internal IP
        "javascript:alert('xss')",    # XSS attempt
        "file:///etc/passwd",           # Local file
        "http://192.168.1.1",          # Private IP
        "http://example.com.tk",        # Suspicious TLD
        "http://example.com/.git",      # Git repo exposure
    ]

@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset circuit breakers before each test to ensure clean state"""
    from services_python.common.utils.circuit_breaker import postgres_circuit_breaker, mongo_circuit_breaker

    # Reset PostgreSQL circuit breaker
    postgres_circuit_breaker.reset()

    # Reset MongoDB circuit breaker
    mongo_circuit_breaker.reset()

    yield

    # Reset after test as well
    postgres_circuit_breaker.reset()
    mongo_circuit_breaker.reset()

# ============================================
# Test Utilities
# ============================================

@pytest.fixture
def generate_short_key():
    """Generate a random short key for testing"""
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=7))

@pytest.fixture
def create_test_url(client, long_url: str) -> Dict[str, Any]:
    """Helper to create a test URL via the API"""
    async def _create(long_url: str):
        response = await client.post("/api/v1/create", json={"long_url": long_url})
        return response.json()
    return _create
