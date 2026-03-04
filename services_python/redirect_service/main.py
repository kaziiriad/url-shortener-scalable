from fastapi import FastAPI
from contextlib import asynccontextmanager
from services_python.common.core.config import settings
import uvicorn
from opentelemetry import trace
from services_python.common.core.tracing import setup_tracing
from services_python.common.utils.logger import initialize_logger

# Initialize structured logger with OpenTelemetry integration
logger = initialize_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Redirect service...")
    setup_tracing(app)
    yield
    # Shutdown
    logger.info("Shutting down Redirect service...")

app = FastAPI(
    title="Redirect Service API",
    description="A service to handle URL shortener redirects.",
    version="1.0.0",
    lifespan=lifespan
)

# Will be created later
from redirect_service.routes.redirect import redirect_router  # noqa: E402

@app.get("/")
async def root():
    return {"message": "Redirect Service", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("service", "redirect_service")
        span.set_attribute("status", "healthy")
        return {"status": "healthy", "service": "redirect_service"}

app.include_router(redirect_router)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host or "0.0.0.0", port=settings.port or 8001)
