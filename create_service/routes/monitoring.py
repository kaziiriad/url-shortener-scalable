"""
Database health monitoring and connection pool tracking.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from common.db.sql.connection import get_db_async, get_pool_status, engine
from common.db.nosql.connection import check_mongo_health, MongoDBConnection
from common.db.sql.models import URL
from common.db.sql.url_repository import URLKeyRepository
from common.core.redis_client import RedisClient
import time
import logging
from opentelemetry import trace

logger = logging.getLogger(__name__)
monitoring_router = APIRouter(prefix='/monitoring', tags=["Monitoring"])

@monitoring_router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db_async)):
    """
    Comprehensive health check for load balancers and monitoring systems.
    Checks all database connections and connection pools.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("detailed_health_check") as span:
        span_ctx = span.get_span_context()
        start_time = time.time()
        health_status = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "checks": {}
        }
        span.add_event("Detailed health check started")
        # PostgreSQL health check
        try:
            span.add_event("PostgreSQL health check started")
            result = await db.execute(text("SELECT 1"))
            if result.scalar() != 1:
                raise Exception("Unexpected response from PostgreSQL")
            span.add_event("PostgreSQL health check completed")
            span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info(
                "PostgreSQL health check retrieved successfully",
                extra={
                    "trace_id": format(span_ctx.trace_id, "032x"),
                    "span_id": format(span_ctx.span_id, "016x"),
                    "span_name": span.name,
                    "span_kind": span.kind,
                    "span_status": span.status,
                }
            )
            health_status["checks"]["postgresql"] = {
                "status": "healthy",
                "response_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"PostgreSQL health check failed: {e}")
            health_status["checks"]["postgresql"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # MongoDB health check
        mongo_start = time.time()
        try:
            span.add_event("MongoDB health check started")
            is_healthy = await check_mongo_health()
            health_status["checks"]["mongodb"] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round((time.time() - mongo_start) * 1000, 2)
            }
            if not is_healthy:
                health_status["status"] = "degraded"
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"MongoDB health check failed: {e}")
            health_status["checks"]["mongodb"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Redis health check
        redis_start = time.time()
        try:
            span.add_event("Redis health check started")
            cache_service = RedisClient()
            await cache_service.ping()
            span.add_event("Redis health check completed")
            health_status["checks"]["redis"] = {
                "status": "healthy",
                "response_time_ms": round((time.time() - redis_start) * 1000, 2)
            }
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Redis health check failed: {e}")
            health_status["checks"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check available keys
        try:
            span.add_event("Key pool check started")
            available_keys = await URLKeyRepository.get_available_key_count(db)
            span.add_event("Key pool check completed")
            health_status["checks"]["key_pool"] = {
                "status": "healthy" if available_keys > 1000 else "warning",
                "available_keys": available_keys,
                "threshold": 1000
            }
            if available_keys < 100:
                health_status["status"] = "degraded"
                health_status["checks"]["key_pool"]["status"] = "critical"
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Key pool check failed: {e}")
            health_status["checks"]["key_pool"] = {
                "status": "unknown",
                "error": str(e)
            }
        
        try:
            span.add_event("Total key count check started")
            total_keys = await URLKeyRepository.get_total_key_count(db)
            span.add_event("Total key count check completed")
            health_status["checks"]["total_keys"] = {
                "total_keys": total_keys
            }
            if total_keys < 100000:
                health_status["status"] = "degraded"
                health_status["checks"]["total_keys"]["status"] = "critical"
            
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Total key count check failed: {e}")
            health_status["checks"]["total_keys"] = {
                "status": "unknown",
                "error": str(e)
            }

    health_status["total_response_time_ms"] = round((time.time() - start_time) * 1000, 2)
    span.set_status(trace.Status(trace.StatusCode.OK))
    logger.info(
        "Detailed health check completed",
        extra={
            "trace_id": format(span_ctx.trace_id, "032x"),
            "span_id": format(span_ctx.span_id, "016x"),
            "span_name": span.name,
            "span_kind": span.kind,
            "span_status": span.status,
        }
    )
    return health_status

@monitoring_router.get("/pool/status")
async def get_connection_pool_status():
    """
    Get connection pool statistics for PostgreSQL.
    Useful for capacity planning and troubleshooting.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_connection_pool_status") as span:
        span_ctx = span.get_span_context()
    try:
        span.add_event("Connection pool status check started")
        fastapi_pool = await get_pool_status("fastapi")
        span.add_event("Connection pool status check completed")
        
        # Calculate utilization percentages
        span.add_event("Connection pool status check started")
        if isinstance(fastapi_pool, dict) and "pool_size" in fastapi_pool:
            total_capacity = fastapi_pool["pool_size"] + fastapi_pool.get("overflow", 0)
            checked_out = fastapi_pool.get("checked_out", 0)
            utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0
            
            fastapi_pool["utilization_percent"] = round(utilization, 2)
            fastapi_pool["status"] = (
                "critical" if utilization > 90 else
                "warning" if utilization > 75 else
                "healthy"
            )
        span.add_event("Connection pool status check completed")        
        span.set_status(trace.Status(trace.StatusCode.OK))
        logger.info(
            "Connection pool status retrieved successfully",
            extra={
                "trace_id": format(span_ctx.trace_id, "032x"),
                "span_id": format(span_ctx.span_id, "016x"),
                "span_name": span.name,
                "span_kind": span.kind,
                "span_status": span.status,
            }
        )
        return {
            "fastapi_pool": fastapi_pool,
            "recommendations": get_pool_recommendations(fastapi_pool)
        }
    except Exception as e:
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        logger.error(f"Error getting pool status: {e}")
        return {"error": str(e)}

@monitoring_router.get("/mongodb/stats")
async def get_mongodb_stats():
    """
    Get MongoDB connection pool and database statistics.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_mongodb_stats") as span:
        span_ctx = span.get_span_context()
    try:
        span.add_event("MongoDB stats check started")
        pool_stats = MongoDBConnection.get_pool_stats()
        span.add_event("MongoDB stats check completed")
        
        # Get database stats
        span.add_event("MongoDB database stats check started")
        db = MongoDBConnection.get_database()
        db_stats = await db.command("dbStats")
        span.add_event("MongoDB database stats check completed")
        
        span.set_status(trace.Status(trace.StatusCode.OK))
        logger.info(
            "MongoDB stats retrieved successfully",
            extra={
                "trace_id": format(span_ctx.trace_id, "032x"),
                "span_id": format(span_ctx.span_id, "016x"),
                "span_name": span.name,
                "span_kind": span.kind,
                "span_status": span.status,
            }
        )
        
        return {
            "pool": pool_stats,
            "database": {
                "collections": db_stats.get("collections", 0),
                "objects": db_stats.get("objects", 0),
                "data_size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(db_stats.get("storageSize", 0) / (1024 * 1024), 2),
            }
        }
    except Exception as e:
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        logger.error(f"Error getting MongoDB stats: {e}")
        return {"error": str(e)}

def get_pool_recommendations(pool_stats: dict) -> list:
    """Generate recommendations based on pool statistics."""
    recommendations = []
    
    if isinstance(pool_stats, dict) and "utilization_percent" in pool_stats:
        utilization = pool_stats["utilization_percent"]
        
        if utilization > 90:
            recommendations.append({
                "severity": "critical",
                "message": "Connection pool is critically full. Consider increasing pool_size or max_overflow.",
                "action": "Scale up pool_size from current value"
            })
        elif utilization > 75:
            recommendations.append({
                "severity": "warning",
                "message": "Connection pool utilization is high. Monitor for potential exhaustion.",
                "action": "Review pool configuration and query patterns"
            })
        
        overflow = pool_stats.get("overflow", 0)
        if overflow > 0:
            recommendations.append({
                "severity": "info",
                "message": f"Using {overflow} overflow connections. This is normal under load.",
                "action": "Monitor if this becomes consistent"
            })
    
    return recommendations

@monitoring_router.get("/key/analytics")
async def get_key_analytics(db: AsyncSession = Depends(get_db_async)):
    """Get analytics about key usage and availability."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_key_analytics") as span:
        span_ctx = span.get_span_context()
    try:
        span.add_event("Key analytics check started")
        # Get total keys
        total_result = await db.execute(text("SELECT COUNT(*) FROM urls"))
        total_keys = total_result.scalar()
        span.add_event("Key analytics check completed")
        
        # Get used keys
        used_result = await db.execute(text("SELECT COUNT(*) FROM urls WHERE is_used = true"))
        used_keys = used_result.scalar()
        span.add_event("Key analytics check completed")
        
        # Get available keys
        available_keys = total_keys - used_keys
        span.add_event("Key analytics check completed")
        
        # Calculate usage percentage
        usage_percent = (used_keys / total_keys * 100) if total_keys > 0 else 0
        
        span.set_status(trace.Status(trace.StatusCode.OK))
        logger.info(
            "Key analytics retrieved successfully",
            extra={
                "trace_id": format(span_ctx.trace_id, "032x"),
                "span_id": format(span_ctx.span_id, "016x"),
                "span_name": span.name,
                "span_kind": span.kind,
                "span_status": span.status,
            }
        )
        return {
            "total_keys": total_keys,
            "used_keys": used_keys,
            "available_keys": available_keys,
            "usage_percent": round(usage_percent, 2),
            "status": (
                "critical" if usage_percent > 95 else
                "warning" if usage_percent > 85 else
                "healthy"
            ),
            "recommendation": (
                "Urgent: Trigger key pre-population immediately!" if usage_percent > 95 else
                "Consider scheduling key pre-population soon" if usage_percent > 85 else
                "Key pool is healthy"
            )
        }
    except Exception as e:
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        logger.error(f"Error getting key analytics: {e}")
        return {"error": str(e)}