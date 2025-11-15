from fastapi import FastAPI
from contextlib import asynccontextmanager
from common.core.config import settings
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Redirect service...")
    yield
    # Shutdown
    logger.info("🛑 Shutting down Redirect service...")

app = FastAPI(
    title="Redirect Service API",
    description="A service to handle URL shortener redirects.",
    version="1.0.0",
    lifespan=lifespan
)

# Will be created later
from redirect_service.routes.redirect import redirect_router

@app.get("/")
async def root():
    return {"message": "Redirect Service", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

app.include_router(redirect_router)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host or "0.0.0.0", port=settings.port or 8001)
