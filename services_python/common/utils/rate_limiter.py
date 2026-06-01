import re
import time
import uuid
from typing import Tuple
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
import logging

logger = logging.getLogger(__name__)

# Lua script for atomic sliding window rate limiting
# Returns: [allowed (0/1), current_count, reset_timestamp]
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

-- Remove entries outside the window
local window_start = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current entries
local current = redis.call('ZCARD', key)

-- Check if under limit
local allowed_val = 0
if current < limit then
    -- Add new entry
    redis.call('ZADD', key, now, unique_id)
    -- Set TTL to window size (with small buffer)
    redis.call('EXPIRE', key, window + 1)
    current = current + 1
    if current <= limit then
        allowed_val = 1
    end
end

-- Calculate reset time
local reset_at = now + window
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
if oldest and #oldest >= 2 then
    reset_at = tonumber(oldest[2]) + window
end

return {allowed_val, current, reset_at}
"""


class RateLimitParseError(ValueError):
    """Raised when rate limit string cannot be parsed."""
    pass


def parse_rate_limit(rate_limit_str: str) -> Tuple[int, int]:
    """
    Parse rate limit string like '10/minute' into (count, window_seconds).

    Formats supported:
    - "N/second", "N/minute", "N/hour", "N/day"
    - "N" (defaults to per minute)

    Returns:
        Tuple of (max_requests, window_seconds)
    """
    if not rate_limit_str:
        return 60, 1  # Default: 60 requests per second

    pattern = r'^(\d+)(?:/(second|minute|hour|day))?$'
    match = re.match(pattern, rate_limit_str.strip().lower())

    if not match:
        raise RateLimitParseError(
            f"Invalid rate limit format: '{rate_limit_str}'. "
            f"Expected format: 'N/unit' where unit is second/minute/hour/day"
        )

    count = int(match.group(1))
    unit = match.group(2) or 'minute'

    unit_to_seconds = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400,
    }

    window_seconds = unit_to_seconds[unit]
    return count, window_seconds


class SlidingWindowRateLimiter:
    """
    Redis-based sliding window rate limiter using sorted sets (ZSET).

    Algorithm:
    1. Store each request as a ZSET entry with score = timestamp
    2. Remove entries outside the sliding window on each check
    3. If count < limit, allow and add new entry
    4. All operations are atomic via Lua script
    """

    def __init__(
        self,
        redis_client: Redis,
        default_limit: str = "60/minute"
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client instance
            default_limit: Default rate limit (e.g., "60/minute")
        """
        self.redis = redis_client
        self.default_limit, self.default_window = parse_rate_limit(default_limit)
        self._script_sha: str | None = None

    async def _get_script_sha(self) -> str:
        """Load and cache Lua script SHA."""
        if self._script_sha is None:
            self._script_sha = await self.redis.script_load(SLIDING_WINDOW_LUA)
        return self._script_sha

    async def is_allowed(
        self,
        key_prefix: str,
        client_ip: str,
        rate_limit_str: str | None = None,
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            key_prefix: Prefix for rate limit key (e.g., "create_url", "redirect")
            client_ip: Client IP address
            rate_limit_str: Optional rate limit override (e.g., "10/minute")

        Returns:
            Tuple of (allowed: bool, remaining: int, reset_at: int)
            - allowed: True if request is allowed
            - remaining: Number of requests remaining in window
            - reset_at: Unix timestamp when window resets
        """
        if rate_limit_str:
            limit, window = parse_rate_limit(rate_limit_str)
        else:
            limit = self.default_limit
            window = self.default_window

        key = f"rate_limit:{key_prefix}:{client_ip}"
        now = time.time()
        unique_id = f"{uuid.uuid4().hex[:8]}-{int(now * 1000)}"

        try:
            sha = await self._get_script_sha()
            result = await self.redis.evalsha(
                sha,
                1,  # number of keys
                key,  # KEYS[1]
                str(now),  # ARGV[1]
                str(window),  # ARGV[2]
                str(limit),  # ARGV[3]
                unique_id,  # ARGV[4]
            )
        except Exception as e:
            # Fallback: if script not found, reload and retry
            logger.warning(f"Script error, reloading: {e}")
            self._script_sha = None
            sha = await self._get_script_sha()
            result = await self.redis.evalsha(
                sha, 1, key, str(now), str(window), str(limit), unique_id
            )

        allowed, current_count, reset_at = result
        remaining = max(0, limit - current_count)

        return (bool(allowed), remaining, int(reset_at))

    async def get_current_count(
        self,
        key_prefix: str,
        client_ip: str,
    ) -> int:
        """Get current request count for a client."""
        key = f"rate_limit:{key_prefix}:{client_ip}"
        now = time.time()
        window_start = now - self.default_window

        # Remove expired and count
        await self.redis.zremrangebyscore(key, '-inf', window_start)
        return await self.redis.zcard(key)

    async def reset(self, key_prefix: str, client_ip: str) -> None:
        """Reset rate limit for a specific client."""
        key = f"rate_limit:{key_prefix}:{client_ip}"
        await self.redis.delete(key)


# Global singleton instance
_rate_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter(redis_client: Redis | None = None) -> SlidingWindowRateLimiter:
    """
    Get singleton rate limiter instance.

    Args:
        redis_client: Optional Redis client. If not provided, creates one.

    Returns:
        SlidingWindowRateLimiter singleton
    """
    global _rate_limiter

    if _rate_limiter is None:
        if redis_client is None:
            # Create default Redis client
            from services_python.common.core.config import settings
            pool = ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_rate_limit_db,  # Use dedicated DB for rate limits
                max_connections=10,
                decode_responses=False,
            )
            redis_client = Redis(connection_pool=pool)

        _rate_limiter = SlidingWindowRateLimiter(
            redis_client=redis_client,
            default_limit="60/minute"
        )

    return _rate_limiter
