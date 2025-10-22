import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import mongomock
import fakeredis.aioredis

@pytest.fixture
def anyio_backend():
    return 'asyncio'

# --- Redis (fakeredis) ---
@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)

@pytest_asyncio.fixture
async def client(monkeypatch, fake_redis):
    from ..app.core.config import settings
    settings.testing = True

    from ..app.main import app as fastapi_app
    from ..app.db.sql.connection import get_db_async, Base
    from ..app.db.nosql.connection import get_db

    # --- PostgreSQL (SQLite in-memory) ---
    TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

    async def override_get_db_async():
        async with TestingSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_async] = override_get_db_async

    # --- MongoDB (mongomock) ---
    mongo_client = mongomock.MongoClient()
    test_mongo_db = mongo_client.test_db

    async def override_get_db():
        return test_mongo_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr("app.core.redis_client.RedisClient", lambda: fake_redis)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        yield c

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
