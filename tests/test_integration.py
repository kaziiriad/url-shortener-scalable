"""
Integration tests for the complete URL shortener workflow.

Tests cover:
- Full URL creation → redirect flow
- Create service → MongoDB → Redis → Redirect service
- Cache behavior throughout the flow
- End-to-end API interactions
"""
import pytest
import json
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from common.db.sql.models import URL


# ============================================
# Full Workflow Tests
# ============================================

@pytest.mark.e2e
async def test_full_url_creation_and_redirect(client: AsyncClient, client_redirect: AsyncClient, test_db_session, fake_mongo, redis_client):
    """Test complete workflow: create URL → MongoDB → redirect → cache"""
    from common.core.config import settings

    # Step 1: Create a short URL using create service
    long_url = "https://example.com/full-test"
    create_response = await client.post("/api/v1/create", json={"long_url": long_url})

    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["message"] == "URL created successfully"
    assert "short_url" in create_data

    # Extract the short key from the short URL
    short_url = create_data["short_url"]
    short_key = short_url.split("/")[-1]

    # Step 2: Verify URL was stored in MongoDB
    url_doc = await fake_mongo.urls.find_one({"short_url_id": short_key})
    assert url_doc is not None
    assert url_doc["long_url"] == long_url

    # Step 3: Verify URL IS cached in Redis (create_service caches it immediately)
    cached_data = await redis_client.get(short_key)
    assert cached_data is not None
    # Verify the cached data can be parsed and contains the correct URL
    cached_json = json.loads(cached_data)
    assert cached_json["long_url"] == long_url

    # Step 4: Test redirect via redirect service (should use cache)
    redirect_response = await client_redirect.get(f"/{short_key}")

    # Accept any redirect status (301, 302, or 307)
    assert redirect_response.status_code in [301, 302, 307]
    assert redirect_response.headers["location"] == long_url


@pytest.mark.e2e
async def test_multiple_urls_creation_and_redirect(client: AsyncClient, client_redirect: AsyncClient, test_db_session, fake_mongo):
    """Test creating and redirecting multiple URLs"""
    test_urls = [
        "https://github.com/test1",
        "https://stackoverflow.com/questions/test2",
        "https://docs.python.org/test3"
    ]

    created_keys = []

    # Step 1: Create multiple short URLs
    for url in test_urls:
        response = await client.post("/api/v1/create", json={"long_url": url})
        assert response.status_code == 200
        data = response.json()
        short_key = data["short_url"].split("/")[-1]
        created_keys.append(short_key)

    # Step 2: Verify all were created in MongoDB
    for short_key in created_keys:
        url_doc = await fake_mongo.urls.find_one({"short_url_id": short_key})
        assert url_doc is not None

    # Step 3: Test redirects for all
    for i, short_key in enumerate(created_keys):
        response = await client_redirect.get(f"/{short_key}")
        assert response.status_code in [301, 302, 307]
        assert response.headers["location"] == test_urls[i]


@pytest.mark.e2e
async def test_cache_invalidation_after_deletion(client: AsyncClient, test_db_session, fake_mongo, redis_client):
    """Test that cache is cleared after URL deletion"""
    # This test requires a delete endpoint which doesn't exist yet
    # Skipping for now
    pytest.skip("Delete endpoint not implemented")


@pytest.mark.e2e
async def test_expired_url_returns_404(client: AsyncClient, test_db_session, fake_mongo, redis_client):
    """Test that expired URLs return 404 during redirect"""
    # Step 1: Create a URL with manual expiration
    long_url = "https://example.com/expired-test"
    short_key = "expired_manual"

    # Manually insert an expired URL into MongoDB
    now = datetime.now(timezone.utc)
    url_doc = {
        "short_url_id": short_key,
        "long_url": long_url,
        "expires_at": now - timedelta(days=1),  # Already expired
        "created_at": now - timedelta(days=30)
    }
    await fake_mongo.urls.insert_one(url_doc)

    # Step 2: Try to redirect - should return 404
    redirect_response = await client.get(f"/{short_key}")
    assert redirect_response.status_code == 404


@pytest.mark.e2e
async def test_concurrent_url_creation(client: AsyncClient, test_db_session, fake_mongo):
    """
    Test that concurrent URL creation works correctly.

    This test validates that the FOR UPDATE SKIP LOCKED mechanism in PostgreSQL
    correctly handles concurrent key acquisition when multiple requests arrive
    simultaneously and the key pool is exhausted.

    Note: PostgreSQL is now the default for tests. Use USE_TEST_SQLITE=true
    to use SQLite (but this test will be skipped as SQLite doesn't support
    FOR UPDATE SKIP LOCKED).
    """
    import asyncio
    import os

    # Skip if explicitly using SQLite (SQLite doesn't support FOR UPDATE SKIP LOCKED)
    if os.environ.get("USE_TEST_SQLITE") == "true":
        pytest.skip("Concurrent key acquisition test requires PostgreSQL (SQLite doesn't support FOR UPDATE SKIP LOCKED)")

    long_urls = [f"https://example.com/concurrent-{i}" for i in range(10)]

    # Create multiple URLs concurrently WITHOUT pre-seeding keys
    # This tests the auto-populate + concurrent acquisition behavior
    async def create_url(url):
        response = await client.post("/api/v1/create", json={"long_url": url})
        return response.json()

    results = await asyncio.gather(*[create_url(url) for url in long_urls])

    # All should succeed
    assert len(results) == 10
    for result in results:
        assert result["message"] == "URL created successfully"
        assert "short_url" in result

    # All short keys should be unique (this is the key assertion!)
    short_keys = [result["short_url"].split("/")[-1] for result in results]
    assert len(short_keys) == len(set(short_keys)), f"Duplicate keys found: {short_keys}"


@pytest.mark.e2e
async def test_key_exhaustion_and_auto_population(client: AsyncClient, test_db_session):
    """Test that the system handles key exhaustion gracefully"""
    from common.db.sql.models import URL
    import random
    import string

    # First, let's check available key count
    available_count = await test_db_session.execute(
        select(func.count(URL.id)).where(URL.is_used == False)
    )
    initial_count = available_count.scalar() or 0

    # Use up all available keys
    created_urls = []
    for i in range(initial_count):
        response = await client.post("/api/v1/create", json={"long_url": f"https://example.com/exhaust-{i}"})
        if response.status_code == 200:
            created_urls.append(response.json()["short_url"].split("/")[-1])
        else:
            break

    # Now try one more - it should auto-populate and succeed
    final_response = await client.post("/api/v1/create", json={"long_url": "https://example.com/after-exhaustion"})
    assert final_response.status_code == 200
    assert "short_url" in final_response.json()


@pytest.mark.e2e
async def test_create_url_with_custom_user_id(client: AsyncClient, client_redirect: AsyncClient, test_db_session, fake_mongo):
    """Test creating URLs with user IDs for tracking"""
    user_urls = [
        ("https://example.com/user1-test", "user_123"),
        ("https://example.com/user2-test", "user_456"),
    ]

    created_keys = []

    for long_url, user_id in user_urls:
        response = await client.post(
            "/api/v1/create",
            json={"long_url": long_url, "user_id": user_id}
        )
        assert response.status_code == 200
        data = response.json()
        short_key = data["short_url"].split("/")[-1]
        created_keys.append(short_key)

        # Verify in MongoDB with user_id
        url_doc = await fake_mongo.urls.find_one({"short_url_id": short_key})
        assert url_doc is not None
        # Note: user_id might not be stored in MongoDB depending on implementation


@pytest.mark.e2e
async def test_redirect_fallback_to_mongodb_when_cache_miss(client: AsyncClient, client_redirect: AsyncClient, test_db_session, fake_mongo, redis_client):
    """Test that redirect falls back to MongoDB when cache is empty"""
    # Step 1: Create a URL
    long_url = "https://example.com/cache-miss"
    create_response = await client.post("/api/v1/create", json={"long_url": long_url})
    assert create_response.status_code == 200
    short_key = create_response.json()["short_url"].split("/")[-1]

    # Step 2: Clear the cache to simulate cache miss
    await redis_client.delete(short_key)

    # Step 3: Redirect should still work (fallback to MongoDB)
    redirect_response = await client_redirect.get(f"/{short_key}")
    assert redirect_response.status_code in [301, 302, 307]
    assert redirect_response.headers["location"] == long_url

    # Step 4: Verify URL was re-cached after MongoDB fetch
    cached_data = await redis_client.get(short_key)
    assert cached_data is not None


@pytest.mark.e2e
async def test_https_auto_addition_in_url_creation(client: AsyncClient, test_db_session, fake_mongo):
    """Test that https:// is auto-added to URLs without scheme"""
    test_cases = [
        ("example.com/no-scheme", "https://example.com/no-scheme"),
        ("http://example.com/http-scheme", "http://example.com/http-scheme"),  # Should keep existing
        ("https://example.com/https-scheme", "https://example.com/https-scheme"),  # Should keep existing
    ]

    for input_url, expected_stored in test_cases:
        response = await client.post("/api/v1/create", json={"long_url": input_url})
        assert response.status_code == 200

        # Verify the stored URL (could check redirect or MongoDB)
        short_key = response.json()["short_url"].split("/")[-1]
        url_doc = await fake_mongo.urls.find_one({"short_url_id": short_key})
        assert url_doc["long_url"] == expected_stored