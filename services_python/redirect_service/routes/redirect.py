from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from services_python.common.db.nosql.connection import get_db
from services_python.common.core.redis_client import RedisClient, get_redis_client
from opentelemetry import trace
from redirect_service.services.redirect_service import RedirectService
import logging
import traceback

redirect_router = APIRouter()
logger = logging.getLogger(__name__)

@redirect_router.get("/{short_key}")
async def handle_redirect(
    short_key: str,
    mongo_db=Depends(get_db),
    redis_client: RedisClient = Depends(get_redis_client)  # ← Singleton pattern
):
    """
    Redirects a short URL to its original long URL.
    """
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("handle_redirect") as span:
        span_ctx = span.get_span_context()
        span.set_attribute("short_key", short_key)

        try:
            span.add_event("redirect_service_called", attributes={"short_key": short_key})
            long_url = await RedirectService.get_long_url(short_key, mongo_db, redis_client)

            if not long_url:
                span.add_event("url_not_found", attributes={"short_key": short_key})
                span.set_status(trace.Status(trace.StatusCode.ERROR, "URL not found"))
                logger.warning(f"URL not found for key: {short_key}")
                raise HTTPException(status_code=404, detail="URL not found")

            span.add_event("redirect_success", attributes={"short_key": short_key, "long_url": long_url})
            span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info(f"Redirect successful: {short_key} -> {long_url}")
            return RedirectResponse(url=long_url)

        except HTTPException:
            raise
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.add_event("redirect_error", attributes={"short_key": short_key, "error": str(e)})
            # Comprehensive error logging with traceback
            logger.error(
                f"Unexpected error during redirect for key '{short_key}': {str(e)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="An unexpected error occurred")
