import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "URL Shortener API", "version": "1.0.0", "status": "running"}

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "instance_id" in data
    assert "hostname" in data
    assert "version" in data

@pytest.mark.asyncio
async def test_create(client: AsyncClient):
    # Create a short URL
    response = await client.post("/api/v1/create", json={"long_url": "https://www.google.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "URL created successfully"
    # Just verify short_url exists, format may vary based on settings
    assert "short_url" in data
    assert "long_url" in data
    assert data["long_url"] == "https://www.google.com"

@pytest.mark.asyncio
async def test_get_url(client: AsyncClient, client_redirect: AsyncClient):
    # Create a short URL using create service
    response = await client.post("/api/v1/create", json={"long_url": "https://www.google.com"})
    assert response.status_code == 200
    data = response.json()
    short_url = data["short_url"]
    key = short_url.split("/")[-1]

    # Redirect using redirect service
    response = await client_redirect.get(f"/{key}")
    assert response.status_code in [301, 302, 307]
    assert response.headers["location"] == "https://www.google.com"