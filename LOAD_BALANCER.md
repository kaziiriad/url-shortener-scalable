# Nginx Load Balancer for URL Shortener

This document explains the nginx load balancer configuration specifically designed for the URL shortener application.

## 🏗️ Architecture Overview

The load balancer setup includes:
- **Nginx**: Reverse proxy and load balancer
- **3 Application Instances**: Horizontal scaling for high availability
- **Shared Backend Services**: Redis, PostgreSQL, MongoDB, Celery
- **Health Monitoring**: Comprehensive health checks and monitoring

```
Internet → Nginx Load Balancer → App Instance 1
                               → App Instance 2  → Shared Redis
                               → App Instance 3  → Shared PostgreSQL
                                                → Shared MongoDB
```

## 🚀 Quick Start

### Using the Load Balancer Setup (Recommended)

1. **Start with load balancer (3 replicas)**:
   ```bash
   docker-compose -f docker-compose-lb.yml up -d
   ```

2. **Verify all services are healthy**:
   ```bash
   docker-compose -f docker-compose-lb.yml ps
   ```

3. **Test the load balancer**:
   ```bash
   python test_load_balancer.py
   ```

4. **Scale dynamically if needed**:
   ```bash
   docker-compose -f docker-compose-lb.yml up -d --scale web_app=5
   ```

5. **Access the application**:
   - Main application: http://localhost
   - Celery monitoring: http://localhost:5555
   - Nginx health: http://localhost/nginx-health

### Advantages of Using Replicas

- ✅ **Cleaner configuration**: Single service definition instead of multiple
- ✅ **Easy scaling**: Change replica count or use `--scale` flag
- ✅ **Automatic service discovery**: Docker handles load balancing internally
- ✅ **Consistent configuration**: All instances have identical settings
- ✅ **Simplified maintenance**: Update once, apply to all replicas

### Using Original Setup (Single Instance)

```bash
docker-compose up -d
```

## 📊 Load Balancer Features

### 1. **Optimized for URL Shortener Traffic Patterns**

- **High-volume redirects**: Cached and optimized for sub-second response times
- **API rate limiting**: Stricter limits on URL creation, generous on redirects
- **Connection pooling**: Efficient connection reuse between nginx and app instances

### 2. **Intelligent Traffic Distribution**

```nginx
upstream url_shortener_backend {
    least_conn;  # Routes to instance with fewest active connections
    
    # Docker Compose automatically load balances across all replicas
    server web_app:8000 max_fails=3 fail_timeout=30s;
    
    keepalive 32;  # Connection pooling
}
```

With `deploy.replicas: 3` in docker-compose, Docker automatically creates 3 instances and handles service discovery.

### 3. **Performance Optimizations**

#### Redirect Caching
```nginx
# Cache successful redirects for 5 minutes
proxy_cache_valid 200 302 5m;
proxy_cache_valid 404 1m;
```

#### Rate Limiting Zones
- **URL Creation**: 10 requests/minute per IP
- **General API**: 60 requests/minute per IP  
- **Redirects**: 100 requests/second per IP
- **Health checks**: 10 requests/second per IP

#### Timeouts Optimized by Endpoint
- **Redirects**: 2-3 second timeouts (should be very fast)
- **API calls**: 5-15 second timeouts
- **Health checks**: 2-3 second timeouts

### 4. **Monitoring and Observability**

#### Custom Log Format
```nginx
log_format url_shortener '$remote_addr - $remote_user [$time_local] '
                        '"$request" $status $body_bytes_sent '
                        '"$http_referer" "$http_user_agent" '
                        '$request_time $upstream_response_time '
                        '$upstream_addr "$request_id"';
```

#### Health Check Endpoints
- `/nginx-health`: Nginx status
- `/health`: Application health (with instance identification)

## 🔧 Configuration Details

### Rate Limiting Configuration

| Endpoint | Rate Limit | Burst | Purpose |
|----------|------------|-------|---------|
| `/api/v1/create` | 10/min | 3 | Prevent abuse of URL creation |
| `/api/*` | 60/min | 10 | General API protection |
| `/[a-zA-Z0-9]{6,8}` | 100/sec | 20 | High-volume redirects |
| `/health` | 10/sec | 5 | Health check monitoring |

### Caching Strategy

1. **Redirect Cache**: 5-minute cache for successful redirects
2. **404 Cache**: 1-minute cache for not-found URLs
3. **Background Updates**: Cache refreshed in background
4. **Stale While Revalidate**: Serve stale content during backend issues

### Security Headers

```nginx
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

## 🔍 Testing and Monitoring

### Load Balancer Test Script

The included `test_load_balancer.py` script tests:

1. **Load Distribution**: Verifies requests are distributed across instances
2. **API Functionality**: Tests URL creation and redirection
3. **Performance**: Measures response times under concurrent load
4. **Rate Limiting**: Validates rate limiting is working

```bash
# Basic test
python test_load_balancer.py

# Test against different URL
python test_load_balancer.py http://your-domain.com
```

### Health Check Monitoring

Each application instance provides detailed health information:

```json
{
  "status": "healthy",
  "timestamp": 1694123456,
  "instance_id": "1",
  "version": "1.0.0",
  "services": {
    "redis": "healthy",
    "postgres": "healthy"
  }
}
```

### Docker Health Checks

All services include comprehensive health checks:
- **App instances**: HTTP health endpoint checks
- **Nginx**: Internal health endpoint
- **Redis**: Redis ping command
- **PostgreSQL**: pg_isready check
- **MongoDB**: MongoDB ping command

## 📈 Scaling Considerations

### Horizontal Scaling

To scale the application instances, simply change the replica count:

```yaml
# In docker-compose-lb.yml
web_app:
  # ... existing configuration
  deploy:
    replicas: 5  # Scale from 3 to 5 instances
```

Or scale dynamically:
```bash
docker-compose -f docker-compose-lb.yml up -d --scale web_app=5
```

No nginx configuration changes needed - Docker Compose handles service discovery automatically!

### Resource Allocation

Current setup allocates:
- **Nginx**: Minimal resources (Alpine Linux)
- **App instances**: Standard FastAPI resource usage
- **Redis**: 256MB memory limit with LRU eviction
- **PostgreSQL**: Standard configuration
- **MongoDB**: Standard configuration

### Performance Tuning

For high-traffic scenarios:

1. **Increase worker processes**:
   ```yaml
   nginx_lb:
     environment:
       - NGINX_WORKER_PROCESSES=auto
       - NGINX_WORKER_CONNECTIONS=2048
   ```

2. **Tune cache sizes**:
   ```nginx
   proxy_cache_path /var/cache/nginx/redirects levels=1:2 keys_zone=redirect_cache:50m max_size=500m;
   ```

3. **Adjust rate limits**:
   ```nginx
   limit_req_zone $binary_remote_addr zone=redirects:10m rate=500r/s;
   ```

## 🚨 Production Considerations

### HTTPS Configuration

For production, uncomment and configure the HTTPS server block in `nginx-lb.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.pem;
    ssl_certificate_key /path/to/private-key.pem;
    # ... SSL configuration
}
```

### Security Enhancements

1. **Basic Authentication for Flower**:
   ```nginx
   location /flower/ {
       auth_basic "Celery Flower";
       auth_basic_user_file /etc/nginx/.htpasswd;
       # ... proxy configuration
   }
   ```

2. **IP Whitelisting**:
   ```nginx
   location /api/admin/ {
       allow 192.168.1.0/24;
       deny all;
       # ... proxy configuration
   }
   ```

3. **DDoS Protection**:
   ```nginx
   limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
   limit_conn conn_limit_per_ip 10;
   ```

### Monitoring Integration

Consider integrating with:
- **Prometheus**: For metrics collection
- **Grafana**: For visualization
- **ELK Stack**: For log analysis
- **Sentry**: For error tracking

## 🛠️ Troubleshooting

### Common Issues

1. **503 Service Unavailable**:
   - Check if application instances are healthy
   - Verify network connectivity between nginx and apps
   - Check docker-compose logs

2. **High Response Times**:
   - Monitor cache hit rates
   - Check database connection pool settings
   - Verify resource allocation

3. **Rate Limiting Too Aggressive**:
   - Adjust rate limits in nginx-lb.conf
   - Monitor nginx error logs for 429 responses

### Debugging Commands

```bash
# Check service status
docker-compose -f docker-compose-lb.yml ps

# View nginx logs
docker-compose -f docker-compose-lb.yml logs nginx_lb

# Check individual app instance
docker-compose -f docker-compose-lb.yml logs web_app_1

# Test specific instance directly
curl http://localhost:8001/health  # If you expose individual ports

# Monitor nginx cache
docker exec -it <nginx_container> ls -la /var/cache/nginx/
```

## 📚 Additional Resources

- [Nginx Load Balancing Documentation](https://nginx.org/en/docs/http/load_balancing.html)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [Redis Caching Strategies](https://redis.io/docs/manual/config/)

---

This load balancer configuration is specifically optimized for URL shortener traffic patterns with high redirect volumes and moderate API usage. Adjust the configuration based on your specific traffic patterns and performance requirements.
