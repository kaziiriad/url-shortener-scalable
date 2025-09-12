# URL Shortener - Scalable Microservice

A high-performance, scalable URL shortener service built with FastAPI, featuring Redis caching, PostgreSQL storage, MongoDB for analytics, and Celery for background tasks.

## 🚀 Features

- **Fast URL Shortening**: Generate short URLs with pre-populated keys for instant response
- **Redis Caching**: Lightning-fast redirects with Redis-first lookup
- **Dual Database**: PostgreSQL for URL management, MongoDB for analytics
- **Background Tasks**: Celery workers for key pre-population and cleanup
- **Monitoring**: Celery Flower dashboard for task monitoring
- **Containerized**: Full Docker setup with docker-compose
- **Scalable Architecture**: Microservice design ready for horizontal scaling

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│   Redis Cache   │    │   PostgreSQL    │
│   (Port 8000)   │    │   (Port 6379)   │    │   (Port 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         ├──────────────────────────────────────────────┘
         │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     MongoDB     │    │ Celery Worker   │    │ Celery Flower   │
│   (Port 27017)  │    │  (Background)   │    │   (Port 5555)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Git

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd url_shortener_scalable
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

3. **Verify services are running**
   ```bash
   docker-compose ps
   ```

4. **Access the application**
   - API: http://localhost:8000
   - Flower Dashboard: http://localhost:5555
   - API Documentation: http://localhost:8000/docs

### Local Development

1. **Create virtual environment**
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start external services**
   ```bash
   docker-compose up -d redis postgres mongo_db
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

## 🔧 Configuration

Key environment variables in `.env`:

```env
# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=pgpassword
DB_NAME=url_shortener

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=

# MongoDB
MONGO_URI=mongodb://mongo_db:27017

# Application
BASE_URL=http://localhost:8000
HOST=0.0.0.0
PORT=8000

# Celery Tasks
KEY_POPULATION_COUNT=50
KEY_POPULATION_SCHEDULE=300
```

## 📚 API Usage

### Create Short URL

```bash
curl -X POST "http://localhost:8000/api/v1/create" \
  -H "Content-Type: application/json" \
  -d '{
    "long_url": "https://www.example.com",
    "expires_at": "2025-12-31T23:59:59"
  }'
```

**Response:**
```json
{
  "message": "URL created successfully",
  "short_url": "http://localhost:8000/abc123",
  "long_url": "https://www.example.com",
  "expires_at": "2025-12-31T23:59:59"
}
```

### Access Short URL

Simply visit the short URL in your browser or use curl:

```bash
curl -L "http://localhost:8000/abc123"
```

This will redirect you to the original long URL.

### Health Check

```bash
curl "http://localhost:8000/health"
```

## 🛠️ Services

| Service | Port | Description |
|---------|------|-------------|
| **web_app** | 8000 | Main FastAPI application |
| **redis** | 6379 | Cache for fast URL lookups |
| **postgres** | 5432 | Primary database for URL storage |
| **mongo_db** | 27017 | Analytics and logging database |
| **celery_worker** | - | Background task processor |
| **celery_beat** | - | Periodic task scheduler |
| **celery_flower** | 5555 | Task monitoring dashboard |

## 🔄 Background Tasks

The system uses Celery for background processing:

- **Key Pre-population**: Automatically generates unused short URL keys
- **Cleanup Tasks**: Removes expired URLs and maintains database health
- **Analytics**: Processes usage statistics and metrics

Monitor tasks at: http://localhost:5555

## 🗂️ Project Structure

```
url_shortener_scalable/
├── app/
│   ├── core/              # Core configuration and utilities
│   ├── db/                # Database connections and models
│   │   ├── sql/           # PostgreSQL models and operations
│   │   └── nosql/         # MongoDB connections
│   ├── models/            # Pydantic schemas
│   ├── routes/            # API route handlers
│   ├── services/          # Business logic services
│   ├── tasks/             # Celery background tasks
│   └── main.py            # FastAPI application entry point
├── docker-compose.yml     # Multi-service Docker setup
├── Dockerfile            # Container image definition
├── pyproject.toml        # Python dependencies and project config
└── README.md             # This file
```

## 🧪 Testing

### Manual Testing

1. **Create a short URL**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/create" \
     -H "Content-Type: application/json" \
     -d '{"long_url": "https://github.com", "expires_at": "2025-12-31T23:59:59"}'
   ```

2. **Test the redirect**
   ```bash
   curl -I "http://localhost:8000/<short_key>"
   ```

3. **Check background tasks**
   - Visit http://localhost:5555 to see Celery tasks
   - Monitor logs: `docker-compose logs celery_worker`

### Load Testing

The system is designed to handle high loads through:
- Redis caching for sub-millisecond redirects
- Pre-populated URL keys for instant creation
- Horizontal scaling capabilities
- Efficient database indexing

## 🔧 Development

### Adding New Features

1. **API Endpoints**: Add routes in `app/routes/`
2. **Background Tasks**: Create tasks in `app/tasks/`
3. **Database Models**: Update models in `app/db/sql/models.py`
4. **Services**: Add business logic in `app/services/`

### Database Migrations

The application automatically initializes databases on startup. For schema changes:

1. Update models in `app/db/sql/models.py`
2. Restart the application to apply changes

### Monitoring

- **Application Logs**: `docker-compose logs web_app`
- **Task Monitoring**: http://localhost:5555
- **Database Health**: Check via health endpoint

## 🚀 Deployment

### Production Considerations

1. **Environment Variables**: Use secure values in production
2. **SSL/TLS**: Configure HTTPS for production domains
3. **Database**: Use managed database services
4. **Caching**: Consider Redis Cluster for high availability
5. **Monitoring**: Add application performance monitoring
6. **Scaling**: Use container orchestration (Kubernetes, Docker Swarm)

### Docker Production

```bash
# Build production image
docker-compose -f docker-compose.prod.yml build

# Deploy with production config
docker-compose -f docker-compose.prod.yml up -d
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Task processing by [Celery](https://celeryproject.org/)
- Caching powered by [Redis](https://redis.io/)
- Database management with [PostgreSQL](https://postgresql.org/) and [MongoDB](https://mongodb.com/)
- Package management by [uv](https://github.com/astral-sh/uv)

---

## 📞 Support

For questions and support:
- Create an issue in the repository
- Check the API documentation at http://localhost:8000/docs
- Monitor system health at http://localhost:8000/health
