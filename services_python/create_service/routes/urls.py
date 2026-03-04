from services_python.common.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from services_python.common.db.nosql.connection import get_db
from services_python.common.db.sql.connection import get_db_async
from services_python.common.core.redis_client import RedisClient, get_redis_client
from create_service.services.url_service import URLService
from services_python.common.models.schemas import URLCreate
from opentelemetry import trace
import logging

logger = logging.getLogger(__name__)
url_router = APIRouter()

@url_router.post("/create")
async def create_url(
    url: URLCreate,
    session: AsyncSession = Depends(get_db_async),
    mongo_db = Depends(get_db),
    redis_client: RedisClient = Depends(get_redis_client)  # ← Singleton pattern
):

    tracer = trace.get_tracer(__name__)
    span_name = "create_url_api"
    with tracer.start_as_current_span(span_name) as span:
        span_ctx = span.get_span_context()
        try:
            # Use the URLService classmethod directly
            span.add_event("URL service called")
            url_data = await URLService.store_url(session=session, mongo_db=mongo_db, url=url)
            span.add_event("URL service returned")

            # Store URL mapping in Redis for fast retrieval
            span.add_event("Redis set called")
            await redis_client.set(url_data.short_url_id, url_data.model_dump_json(), expires_in=1800)
            span.add_event("Redis client set completed")

            span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info(
                "URL created successfully",
                extra={
                    "trace_id": format(span_ctx.trace_id, "032x"),
                    "span_id": format(span_ctx.span_id, "016x"),
                    "span_name": span_name,
                    "span_kind": getattr(span, "kind", "INTERNAL"),
                    "span_status": getattr(span, "status", None),
                }
            )
            return {
                "message": "URL created successfully",
                "short_url": f"{settings.base_url}/{url_data.short_url_id}",
                "long_url": url_data.long_url,
                "expires_at": url_data.expires_at
            }
        except HTTPException as http_exc:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(http_exc)))
            logger.error(
                "HTTP Exception",
                extra={
                    "trace_id": format(span_ctx.trace_id, "032x"),
                    "span_id": format(span_ctx.span_id, "016x"),
                    "span_name": span_name,
                    "span_kind": getattr(span, "kind", "INTERNAL"),
                    "span_status": getattr(span, "status", None),
                }
            )
            raise http_exc
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(
                "Exception",
                extra={
                    "trace_id": format(span_ctx.trace_id, "032x"),
                    "span_id": format(span_ctx.span_id, "016x"),
                    "span_name": span_name,
                    "span_kind": getattr(span, "kind", "INTERNAL"),
                    "span_status": getattr(span, "status", None),
                }
            )
            raise HTTPException(status_code=500, detail=f"Error creating URL via API: {str(e)}")