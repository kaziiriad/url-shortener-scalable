"""
Test utilities and helper functions for URL shortener E2E tests.
"""
import asyncio
from typing import Dict, Any, Optional
from httpx import AsyncClient, Response
import time


class TestHelper:
    """Helper class for common test operations"""

    @staticmethod
    async def create_short_url(
        client: AsyncClient,
        long_url: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a short URL via API"""
        payload = {"long_url": long_url}
        if user_id:
            payload["user_id"] = user_id

        response = await client.post("/api/v1/create", json=payload)
        assert response.status_code == 200, f"Failed to create URL: {response.text}"
        return response.json()

    @staticmethod
    async def get_redirect_url(
        client: AsyncClient,
        short_key: str
    ) -> Response:
        """Get redirect response"""
        return await client.get(f"/{short_key}", follow_redirects=False)

    @staticmethod
    def assert_redirect(response: Response, expected_url: str, status_code: int = 302):
        """Assert redirect response"""
        assert response.status_code == status_code
        assert response.headers["location"] == expected_url

    @staticmethod
    def assert_error_response(response: Response, status_code: int, detail_contains: str = None):
        """Assert error response"""
        assert response.status_code == status_code
        if detail_contains:
            assert detail_contains in response.text.lower()

    @staticmethod
    async def wait_for_condition(
        condition: callable,
        timeout: float = 5.0,
        poll_interval: float = 0.1
    ):
        """Wait for a condition to be true"""
        start = time.time()
        while time.time() - start < timeout:
            if await condition():
                return
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Condition not met within {timeout}s")

    @staticmethod
    def generate_test_url_data(index: int = 0) -> str:
        """Generate test URL data"""
        return f"https://example.com/test-{index}.com"

    @staticmethod
    def extract_short_key(short_url: str) -> str:
        """Extract short key from short URL"""
        return short_url.split("/")[-1]


class DatabaseHelper:
    """Helper for database test operations"""

    @staticmethod
    async def seed_test_keys(session, count: int = 100):
        """Seed test keys in PostgreSQL for testing"""
        from services_python.common.db.sql.url_repository import URLKeyRepository

        seeded = await URLKeyRepository.pre_populate_keys_postgres_native(
            session=session,
            count=count
        )
        return seeded

    @staticmethod
    async def cleanup_test_data(session):
        """Clean up test data after tests"""
        # Clean up MongoDB
        from services_python.common.db.nosql.connection import get_db
        mongo_db = get_db()
        await mongo_db.urls.delete_many({})

        # Clean up PostgreSQL
        await session.execute("DELETE FROM urls WHERE is_used = false LIMIT 1000")
        await session.commit()


class PerformanceMetrics:
    """Helper for measuring and tracking performance metrics"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.metrics = {}

    def start(self):
        """Start performance measurement"""
        self.start_time = time.time()

    def end(self):
        """End performance measurement and calculate metrics"""
        self.end_time = time.time()
        if self.start_time:
            self.metrics["duration"] = self.end_time - self.start_time

    def get_duration(self) -> float:
        """Get the measured duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def assert_under_threshold(self, threshold_ms: float, operation_name: str):
        """Assert operation completed under threshold"""
        duration_ms = self.get_duration() * 1000
        assert duration_ms < threshold_ms, \
            f"{operation_name} took {duration_ms:.2f}ms, exceeds threshold of {threshold_ms}ms"

    @staticmethod
    def get_p95_latency(latencies: list[float]) -> float:
        """Calculate P95 latency from a list of latencies"""
        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index] if sorted_latencies else 0.0