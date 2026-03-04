"""
Service-level tests for URL redirect service.

Tests cover:
- Cache hits (Redis)
- Cache misses with MongoDB fallback
- Expired URLs (both in cache and MongoDB)
- URL not found scenarios
- API endpoint behavior
- MongoDB query projection optimization
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from redirect_service.services.redirect_service import RedirectService
from common.core.redis_client import RedisClient
import json


# ============================================
# Service Layer Tests (RedirectService)
# ============================================

@pytest.mark.unit
async def test_get_long_url_cache_hit(redis_client, fake_mongo):
    """Test successful URL retrieval from Redis cache"""
    short_key = "test123"
    url_data = {
        "short_url_id": short_key,
        "long_url": "https://example.com/cached",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    }

    # Pre-populate cache
    await redis_client.set(short_key, json.dumps(url_data))

    # Get URL
    result = await RedirectService.get_long_url(short_key, fake_mongo, redis_client)

    assert result == "https://example.com/cached"


@pytest.mark.unit
async def test_get_long_url_cache_miss_mongo_hit(redis_client, fake_mongo):
    """Test URL retrieval falls back to MongoDB when not in cache"""
    short_key = "mongo123"
    # Store expires_at as ISO string for fromisoformat compatibility
    url_doc = {
        "short_url_id": short_key,
        "long_url": "https://example.com/from-mongo",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await fake_mongo.urls.insert_one(url_doc)

    # Get URL - should fetch from MongoDB and cache it
    result = await RedirectService.get_long_url(short_key, fake_mongo, redis_client)

    assert result == "https://example.com/from-mongo"

    # Verify it's now cached
    cached = await redis_client.get(short_key)
    assert cached is not None
    cached_data = json.loads(cached)
    assert cached_data["long_url"] == "https://example.com/from-mongo"


@pytest.mark.unit
async def test_get_long_url_expired_in_cache(redis_client, fake_mongo):
    """Test expired URL in cache returns None and is removed"""
    short_key = "expired123"
    url_data = {
        "short_url_id": short_key,
        "long_url": "https://example.com/expired",
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    }

    await redis_client.set(short_key, json.dumps(url_data))

    # Get URL - should return None for expired URL
    result = await RedirectService.get_long_url(short_key, fake_mongo, redis_client)

    assert result is None

    # Key should be deleted from cache
    cached = await redis_client.get(short_key)
    assert cached is None


@pytest.mark.unit
async def test_get_long_url_expired_in_mongodb(redis_client, fake_mongo):
    """Test expired URL in MongoDB returns None"""
    short_key = "expired_mongo123"
    url_doc = {
        "short_url_id": short_key,
        "long_url": "https://example.com/expired-mongo",
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await fake_mongo.urls.insert_one(url_doc)

    # Get URL - should return None for expired URL
    result = await RedirectService.get_long_url(short_key, fake_mongo, redis_client)

    assert result is None


@pytest.mark.unit
async def test_get_long_url_not_found(redis_client, fake_mongo):
    """Test URL not found in cache or MongoDB returns None"""
    short_key = "nonexistent123"

    # Get URL - should return None
    result = await RedirectService.get_long_url(short_key, fake_mongo, redis_client)

    assert result is None


@pytest.mark.unit
async def test_find_url_in_mongo_success(fake_mongo):
    """Test MongoDB URL lookup succeeds with projection optimization"""
    short_key = "lookup123"
    url_doc = {
        "short_url_id": short_key,
        "long_url": "https://example.com/lookup",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await fake_mongo.urls.insert_one(url_doc)

    # Call the internal method directly
    result = await RedirectService._find_url_in_mongo(fake_mongo, short_key)

    assert result is not None
    assert result["long_url"] == "https://example.com/lookup"
    # Note: After optimization with projection, only long_url and expires_at are returned
    assert "short_url_id" not in result  # Projection optimization excludes this field
    assert "_id" not in result  # Projection optimization excludes this field


@pytest.mark.unit
async def test_find_url_in_mongo_not_found(fake_mongo):
    """Test MongoDB URL lookup returns None when not found"""
    short_key = "nonexistent_lookup"

    # Call the internal method directly
    result = await RedirectService._find_url_in_mongo(fake_mongo, short_key)

    assert result is None


# ============================================
# API Endpoint Tests
# ============================================

@pytest.mark.integration
async def test_handle_redirect_success(client_redirect: AsyncClient, fake_mongo):
    """Test successful redirect returns redirect status"""
    short_key = "redirect123"
    url_doc = {
        "short_url_id": short_key,
        "long_url": "https://example.com/target",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await fake_mongo.urls.insert_one(url_doc)

    response = await client_redirect.get(f"/{short_key}")

    # FastAPI RedirectResponse defaults to 307 (Temporary Redirect)
    assert response.status_code in [301, 302, 307]  # Accept any redirect status
    assert response.headers["location"] == "https://example.com/target"


@pytest.mark.integration
async def test_handle_redirect_not_found(client_redirect: AsyncClient):
    """Test redirect to non-existent URL returns 404"""
    short_key = "nonexistent_redirect"

    response = await client_redirect.get(f"/{short_key}")

    assert response.status_code == 404
    assert response.json()["detail"] == "URL not found"


@pytest.mark.integration
async def test_handle_redirect_expired_url(client_redirect: AsyncClient, fake_mongo):
    """Test redirect to expired URL returns 404"""
    short_key = "expired_redirect"
    url_doc = {
        "short_url_id": short_key,
        "long_url": "https://example.com/expired-target",
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await fake_mongo.urls.insert_one(url_doc)

    response = await client_redirect.get(f"/{short_key}")

    assert response.status_code == 404


@pytest.mark.integration
async def test_handle_redirect_from_cache(client_redirect: AsyncClient, redis_client):
    """Test redirect works when URL is in cache"""
    short_key = "cached_redirect"
    url_data = {
        "short_url_id": short_key,
        "long_url": "https://example.com/cached-target",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    }
    # Use the redis_client which is the same wrapper used by client_redirect
    await redis_client.set(short_key, json.dumps(url_data))

    response = await client_redirect.get(f"/{short_key}")

    # FastAPI RedirectResponse defaults to 307 (Temporary Redirect)
    assert response.status_code in [301, 302, 307]  # Accept any redirect status
    assert response.headers["location"] == "https://example.com/cached-target"