FROM python:3.12-slim AS build-deps

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv system-wide, so all users can access it
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/


ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    # Install dependencies based on the locked file, but not the project code itself yet
    uv sync --locked --no-install-project

# Copy project files first (excluding .venv via .dockerignore)
COPY pyproject.toml uv.lock ./
# COPY .env .
COPY services_python/common/ ./common/
COPY services_python/worker_service/ ./worker_service/

FROM python:3.12-slim

WORKDIR /app

# Copy uv from the build stage
COPY --from=build-deps /usr/local/bin/uv /usr/local/bin/uv

# Copy the virtual environment from the build stage
COPY --from=build-deps /app/.venv /app/.venv

# Copy the application source code (same as stage 1)
COPY pyproject.toml uv.lock ./
COPY services_python/common/ ./common/
COPY services_python/worker_service/ ./worker_service/

ENV PATH="/app/.venv/bin:$PATH"


