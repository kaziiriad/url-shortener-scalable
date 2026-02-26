# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a **microservice URL shortener** built with FastAPI, designed for high scalability. The architecture separates write operations (create service) from read operations (redirect service) for independent scaling.

### Services

- **create_service** (port 8000): Handles URL creation via POST `/api/v1/create`. Uses PostgreSQL (via PgBouncer) to fetch pre-populated keys and stores URL mappings in MongoDB.
- **redirect_service** (port 8001): Read-only service for URL redirects. Checks Redis cache first, falls back to MongoDB.
- **worker_service**: Celery workers for background tasks - key pre-population and expired URL cleanup.

### Data Layer

- **PostgreSQL**: Stores pre-populated short URL keys. Keys are bulk-inserted using raw SQL with `unnest()` for efficiency.
- **MongoDB**: Stores URL mappings and metadata (long_url, expires_at, created_at).
- **Redis**: Cache layer for sub-millisecond redirects, plus Celery message broker.
- **PgBouncer**: Connection pooler between services and PostgreSQL (port 6432).

### Load Balancing

Nginx routes traffic:
- `/api/*` → create_service
- `/*` → redirect_service
- `/flower/*` → Celery Flower monitoring dashboard

## Common Commands

### Docker Development

```bash
# Start all services
docker-compose -f docker-compose-decoupled.yml up -d

# Start only databases (for local dev)
docker-compose -f docker-compose-decoupled.yml up -d redis postgres mongo_db pgbouncer

# View logs
docker-compose -f docker-compose-decoupled.yml logs -f [service_name]

# Stop all services
docker-compose -f docker-compose-decoupled.yml down
```

### Local Development (without Docker for services)

Requires uv package manager. Run in separate terminals:

```bash
# Terminal 1: Create service
uv run create_service.main:app --port 8000 --reload

# Terminal 2: Redirect service
uv run redirect_service.main:app --port 8001 --reload

# Terminal 3: Celery worker
uv run celery -A worker_service.celery_app:celery_app worker --loglevel=info

# Terminal 4: Celery beat (optional, for scheduled tasks)
uv run celery -A worker_service.celery_app:celery_app beat --loglevel=info
```

### Testing

```bash
# Install test dependencies
uv sync --with test

# Run all tests
pytest

# Run specific test file
pytest tests/test_specific_file.py

# Run with coverage
pytest --cov=.

# Run async tests specifically
pytest -q tests/ --asyncio-mode=auto
```

### AWS Deployment

```bash
cd infra
pulumi up

# After provisioning, deploy with Ansible
cd ../ansible
ansible-playbook -i inventory/hosts.yml playbook.yml
```

## Key Architectural Patterns

### Key Pre-population System
- Short URL keys are pre-generated in PostgreSQL to ensure instant URL creation
- Celery task runs periodically to maintain a pool of available keys
- Create service marks keys as "used" atomically

### Repository Pattern
- `common/db/sql/url_repository.py`: PostgreSQL operations (key management)
- `common/db/mongo/url_repository.py`: MongoDB operations (URL CRUD)
- Each service has its own service layer that uses these repositories

### Connection Pooling
- All database connections use SQLAlchemy async engine with pooling
- PgBouncer provides transaction-level pooling for PostgreSQL
- Pool configuration in `common/core/config.py` with validation logic

### Testing Strategy
- Uses `mongomock` for MongoDB tests (no real DB needed)
- Uses `fakeredis` for Redis tests
- Uses in-memory SQLite (`sqlite+aiosqlite:///:memory:`) for PostgreSQL tests
- Tests use `pytest-asyncio` with auto mode

## Important File Locations

- `common/core/config.py`: All environment variable configuration with validation
- `common/core/tracing.py`: OpenTelemetry tracing setup
- `common/utils/logger.py`: Structured logging with service context
- `common/db/sql/`: PostgreSQL repository and models
- `common/db/mongo/`: MongoDB repository
- `worker_service/tasks/`: Celery task definitions
- `docker-compose-decoupled.yml`: Full stack orchestration
- `nginx-decoupled.conf`: Load balancer configuration

## Environment Configuration

Key environment variables are defined in `common/core/config.py`. For local development, services typically need:
- `DB_HOST=pgbouncer`, `DB_PORT=6432` (not direct postgres)
- `MONGO_URI=mongodb://mongo_db:27017`
- `REDIS_HOST=redis`
- `TRACING_ENABLED=true` for OpenTelemetry
- `SERVICE_NAME` set appropriately for each service

## OpenTelemetry Tracing

The system uses OpenTelemetry with OTLP exporter. Traces are sent to `otel-collector:4317` (or configured via `OTLP_ENDPOINT`). Instrumentation covers:
- FastAPI endpoints
- SQLAlchemy queries
- Redis operations
- Celery tasks
- HTTP client requests

Tracing is initialized in each service's `main.py` via `common/core/tracing.py`.