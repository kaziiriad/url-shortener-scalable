FROM python:3.12-slim AS build-deps

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv system-wide, so all users can access it
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/


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
COPY create_service/ ./create_service   

# Create a non-root user and change ownership
# RUN chown -R appuser:appuser /app && \
#     mkdir -p /home/appuser/.cache && \
#     chown -R appuser:appuser /home/appuser/.cache

# # Switch to non-root user
# USER appuser

# Set up virtual environment as appuser
# ENV VIRTUAL_ENV="/app/.venv"
# RUN uv venv --relocatable
# ENV PATH="/app/.venv/bin:$PATH"

# Set a longer timeout for UV package downloads

# Install dependencies as appuser
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "create_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
