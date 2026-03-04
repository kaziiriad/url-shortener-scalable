# K6 Performance Testing - Quick Start Guide

## Prerequisites

Ensure services are running:
```bash
docker-compose -f docker/compose/docker-compose-decoupled.yml up -d
```

## Run Your First Test

### Option 1: Using Docker Compose (Recommended)

```bash
cd k6

# 1. Run smoke test (30 seconds) - verifies services are working
docker-compose -f docker-compose-k6.yml --profile smoke up k6-smoke

# 2. Run URL creation load test (4 minutes) - tests create endpoint
docker-compose -f docker-compose-k6.yml --profile create up k6-create

# 3. Run redirect load test (8 minutes) - tests redirect performance
docker-compose -f docker-compose-k6.yml --profile redirect up k6-redirect

# 4. Run mixed workload (15 minutes) - realistic traffic pattern
docker-compose -f docker-compose-k6.yml --profile mixed up k6-mixed
```

### Option 2: Using k6 Directly

```bash
# Install k6 first (if not installed)
brew install k6  # macOS

cd k6

# Run smoke test
k6 run tests/smoke-test.js

# Run URL creation test
k6 run tests/create-url.js

# Run redirect test
k6 run tests/redirect.js

# Run mixed workload
k6 run tests/mixed-workload.js
```

### Option 3: Using Docker with Custom Parameters

```bash
# Run with custom base URL
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "$(pwd)/k6:/tests" \
  grafana/k6:latest run /tests/tests/create-url.js \
  --env BASE_URL=http://localhost:8000

# Run with custom test keys (for redirect tests)
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "$(pwd)/k6:/tests" \
  grafana/k6:latest run /tests/tests/redirect.js \
  --env BASE_URL=http://localhost:8001 \
  --env TEST_KEYS=key1,key2,key3
```

## Understanding Test Output

### Success Example
```
✓ status is 201 or 200
✓ has short_url in response
✓ response time < 500ms

checks.........................: 100.0% ✓ 6000  ✗ 0
http_req_duration..............: avg=150ms  min=10ms  med=120ms  max=800ms
http_req_failed................: 0.00%  ✓ 0   ✗ 6000
```

### Failure Example
```
✗ status is 201 or 200

checks.........................: 85.0% ✓ 5100  ✗ 900
http_req_duration..............: avg=2.5s   min=10ms  med=1.8s   max=5s
http_req_failed................: 15.00% ✓ 900  ✗ 5100
```

## Common Issues

### "Connection refused"
**Solution**: Services are not running. Start them with:
```bash
docker-compose -f docker/compose/docker-compose-decoupled.yml up -d
```

### "Cannot connect to service"
**Solution**: Check if services are healthy:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### High failure rates
**Possible causes**:
1. Database connection issues - check logs: `docker-compose logs -f mongo_db redis`
2. Circuit breaker open - wait 60 seconds or restart create_service
3. Out of URL keys - run key population task

## Next Steps

1. **Run smoke test** to verify basic functionality
2. **Run individual tests** to establish performance baselines
3. **Run mixed workload** to simulate realistic traffic
4. **Monitor Grafana** at http://localhost:3000 during tests
5. **Adjust test parameters** in test files to match your requirements

## Test Duration Guide

| Test | Duration | Load Level |
|------|----------|------------|
| Smoke Test | ~30s | 1 VU |
| Create URL | 4 min | 100-500 req/s |
| Redirect | 8 min | 100-5000 req/s |
| Mixed Workload | 15 min | 500-2000 req/s |

## Need Help?

See [README.md](./README.md) for detailed documentation and JavaScript explanations.