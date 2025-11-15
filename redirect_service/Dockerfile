# Base image
FROM python:3.12-slim-bookworm

# Install curl and certificates for uv installer
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv, a fast Python package installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set environment variables for uv
ENV PATH="/root/.local/bin:$PATH"
ENV UV_HTTP_TIMEOUT=120

# Set working directory
WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync

# Copy the common module and the service-specific code
COPY common/ ./common
COPY redirect_service/ ./redirect_service   

# Expose the port the app runs on
EXPOSE 8001

# Run the application
CMD ["uv", "run", "uvicorn", "redirect_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
