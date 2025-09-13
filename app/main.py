from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.routes.urls import url_router
from app.db.sql.init_db import init_database
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

# Include redirect route at root level (without prefix) - must be last
from app.routes.urls import get_url
app.add_api_route("/{key}", get_url, methods=["GET"], tags=["Redirect"])

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host or "0.0.0.0", port=settings.port)