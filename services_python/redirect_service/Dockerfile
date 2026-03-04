# Base image
FROM python:3.12-slim AS build-deps

# Install curl and certificates for uv installer
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv, a fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Use Docker build cache mounts to speed up repeated builds
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    # Install dependencies based on the locked file, but not the project code itself yet
    uv sync --locked --no-install-project

# Stage 2: Final image (often a smaller base)
FROM python:3.12-slim

WORKDIR /app

# Copy uv from the build stage
COPY --from=build-deps /usr/local/bin/uv /usr/local/bin/uv

# Copy the virtual environment from the build stage
COPY --from=build-deps /app/.venv /app/.venv

# Copy the application source code (same as stage 1)
COPY pyproject.toml uv.lock ./
COPY common/ ./common
COPY redirect_service/ ./redirect_service   


# Expose the port the app runs on
EXPOSE 8001

# Run the application
CMD ["uv", "run", "uvicorn", "redirect_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
