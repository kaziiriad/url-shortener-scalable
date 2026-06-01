import hashlib
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from services_python.common.core.config import settings
from services_python.common.utils.rate_limiter import get_rate_limiter, SlidingWindowRateLimiter
import logging

logger = logging.getLogger(__name__)

RATE_LIMIT_ID_COOKIE = "rl_id"
RATE_LIMIT_ID_HEADER = "X-RateLimit-Id"


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request.

    Checks headers in order:
    1. X-Forwarded-For (first IP, comma-separated)
    2. X-Real-IP
    3. request.client.host (fallback)
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """Extract User-Agent header."""
    return request.headers.get("user-agent", "unknown")


def generate_client_identifier(
    request: Request,
    session_user_id: str | None = None,
) -> str:
    """
    Generate stable client identifier for rate limiting.

    Strategy (in order of preference):
    1. Authenticated user: IP + session token (most stable for logged-in users)
    2. Has X-RateLimit-Id cookie: Use cookie value (stabile per-browser on shared IP)
    3. Has X-RateLimit-Id header: Use header value (client-specified identity)
    4. Fallback: IP + hash(User-Agent) (distinguishes browsers on shared IP)

    Args:
        request: FastAPI request
        session_user_id: User ID from session/token (if authenticated)

    Returns:
        Stable identifier string for rate limiting
    """
    # 1. Authenticated user: IP + session token
    if session_user_id:
        ip = get_client_ip(request)
        return f"auth:{ip}:{session_user_id}"

    # 2. Client-specified identifier via header
    rate_limit_id = request.headers.get(RATE_LIMIT_ID_HEADER)
    if rate_limit_id:
        return f"header:{rate_limit_id}"

    # 3. Client-specified identifier via cookie
    rate_limit_cookie = request.cookies.get(RATE_LIMIT_ID_COOKIE)
    if rate_limit_cookie:
        return f"cookie:{rate_limit_cookie}"

    # 4. Fallback: IP + User-Agent hash (distinguishes browsers on shared IP)
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    ua_hash = hashlib.md5(ua.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"ipua:{ip}:{ua_hash}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for Redis-based sliding window rate limiting.

    Applies rate limiting to requests matching the configured path prefix.
    Returns 429 Too Many Requests when limit is exceeded.

    Usage:
        app.add_middleware(
            RateLimitMiddleware,
            path_prefix="/api/v1/create",
            rate_limit_key="create_url"
        )
    """

    def __init__(
        self,
        app,
        path_prefix: str = "/",
        rate_limit_key: str = "default",
        rate_limit_str: str | None = None,
        get_session_user_id: Callable[[Request], str | None] | None = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            path_prefix: Apply to paths starting with this prefix
            rate_limit_key: Key prefix for Redis rate limit storage
            rate_limit_str: Optional override (e.g., "100/minute")
            get_session_user_id: Callable to extract user ID from request (for auth)
        """
        super().__init__(app)
        self.path_prefix = path_prefix
        self.rate_limit_key = rate_limit_key
        self.rate_limit_str = rate_limit_str
        self.get_session_user_id = get_session_user_id
        self.rate_limiter: SlidingWindowRateLimiter | None = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazy initialization of rate limiter."""
        if not self._initialized:
            self.rate_limiter = get_rate_limiter()
            self._initialized = True

    def _should_apply(self, request: Request) -> bool:
        """Check if rate limiting should apply to this request."""
        if not settings.rate_limit_enabled:
            return False
        return request.url.path.startswith(self.path_prefix)

    def _get_session_user_id(self, request: Request) -> str | None:
        """Extract session user ID if authenticator is configured."""
        if self.get_session_user_id:
            try:
                return self.get_session_user_id(request)
            except Exception as e:
                logger.warning(f"Failed to get session user ID: {e}")
        return None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with rate limiting."""
        # Check if this path should be rate limited
        if not self._should_apply(request):
            return await call_next(request)

        # Initialize rate limiter on first request
        await self._ensure_initialized()

        # Get session user ID (if auth is configured)
        session_user_id = self._get_session_user_id(request)

        # Generate stable client identifier
        client_id = generate_client_identifier(request, session_user_id)

        now = time.time()

        # Determine rate limit string to use
        rate_str = self.rate_limit_str
        if rate_str is None:
            if self.rate_limit_key == "create_url":
                rate_str = settings.create_url_rate_limit
            elif self.rate_limit_key == "redirect":
                rate_str = settings.redirect_rate_limit
            else:
                rate_str = "60/minute"  # Default fallback

        # Check rate limit
        allowed, remaining, reset_at = await self.rate_limiter.is_allowed(
            key_prefix=self.rate_limit_key,
            client_ip=client_id,
            rate_limit_str=rate_str,
        )

        # Log the check
        logger.debug(
            f"Rate limit check: key={self.rate_limit_key}, id={client_id[:30]}, "
            f"allowed={allowed}, remaining={remaining}, reset_at={reset_at}"
        )

        if not allowed:
            retry_after = max(1, int(reset_at - now))
            logger.warning(
                f"Rate limit exceeded: key={self.rate_limit_key}, id={client_id[:30]}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "X-RateLimit-Limit": rate_str,
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        response.headers["X-RateLimit-Limit"] = rate_str

        return response
