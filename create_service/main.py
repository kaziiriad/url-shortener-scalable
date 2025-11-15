from fastapi import FastAPI
from contextlib import asynccontextmanager
from common.core.config import settings
from create_service.routes.urls import url_router
from create_service.routes.monitoring import monitoring_router
from common.db.sql.init_db import init_database
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting URL Shortener application...")
    if not settings.testing:
        try:
            await init_database()
            logger.info("✅ Database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down URL Shortener application...")

app = FastAPI(
    title="URL Shortener API",
    description="A scalable URL shortener service",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routes with prefix
app.include_router(url_router, prefix="/api/v1", tags=["API"])
app.include_router(monitoring_router)

@app.get("/")
async def root():
    return {"message": "URL Shortener API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint for load balancer monitoring."""
    import os
    import time
    import socket
    
    # Get container/instance identifier
    hostname = socket.gethostname()
    instance_id = os.getenv("INSTANCE_ID", hostname)
    
    health_data = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "instance_id": instance_id,
        "hostname": hostname,
        "version": "1.0.0"
    }
    
    return health_data

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host or "0.0.0.0", port=settings.port)