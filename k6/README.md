# K6 Performance Testing Suite

This directory contains performance and load testing scripts using [k6](https://k6.io/) for the URL shortener service.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Test Scripts Overview](#test-scripts-overview)
- [Running Tests](#running-tests)
- [Understanding Test Results](#understanding-test-results)
- [Customization](#customization)

---

## Prerequisites

- Docker and Docker Compose (for containerized testing)
- Or k6 installed locally: `brew install k6` (macOS) or see [k6 installation guide](https://k6.io/docs/getting-started/installation/)

---

## Installation

### Quick Start with Docker

```bash
# From project root - start all services first
docker-compose -f docker/compose/docker-compose-decoupled.yml up -d

# Start monitoring stack (optional, for Grafana dashboards)
cd monitoring && docker-compose -f docker-compose-monitoring.yml up -d && cd ..

# Run k6 tests using Docker Compose profiles
cd k6

# Run smoke test (quick health check)
docker-compose -f docker-compose-k6.yml --profile smoke up k6-smoke

# Run URL creation load test
docker-compose -f docker-compose-k6.yml --profile create up k6-create

# Run redirect load test
docker-compose -f docker-compose-k6.yml --profile redirect up k6-redirect

# Run mixed workload test (most realistic)
docker-compose -f docker-compose-k6.yml --profile mixed up k6-mixed

# Run all tests
docker-compose -f docker-compose-k6.yml --profile all up
```

### Local Installation

```bash
# Install k6
brew install k6  # macOS
# Or: go install go.k6.io/k6/cmd/k6@latest

# Run tests
k6 run tests/create-url.js
```

---

## Test Scripts Overview

### 1. `create-url.js` - URL Creation Load Test

**Purpose**: Tests the URL creation endpoint under various load conditions.

**Test Scenarios**:
- **constant_load**: Steady 100 requests/second for 2 minutes
- **spike_test**: Sudden spike to 500 requests/second for 30 seconds (starts at 2 min)
- **recovery**: Returns to normal load (100 req/s) for 1.5 minutes

**What it Tests**:
- Can the service handle sustained load?
- How does it respond to sudden traffic spikes?
- Does it recover properly after overload?

**Metrics Collected**:
- `creation_time`: How long each URL creation takes
- `creations_success`: Count of successful creations
- `creations_failed`: Count of failed creations
- `errors`: Error rate

**Key JavaScript Concepts**:
```javascript
// Generate random data for each request
function generateRandomURL() {
  const domains = ['example.com', 'test.com', 'demo.org', 'sample.net'];
  const domain = domains[Math.floor(Math.random() * domains.length)];
  return `https://${domain}/page`;
}

// Send POST request with JSON payload
const response = http.post(API_ENDPOINT, JSON.stringify(payload), {
  headers: { 'Content-Type': 'application/json' }
});

// Check if response is valid
const isSuccess = check(response, {
  'status is 201 or 200': (r) => r.status === 201 || r.status === 200,
  'has short_url': (r) => r.json('short_url') !== undefined,
});
```

---

### 2. `redirect.js` - Redirect Performance Test

**Purpose**: Tests the redirect endpoint with focus on cache performance and latency.

**Test Scenarios**:
- **normal_traffic**: Sustained 1000 requests/second for 5 minutes (simulates production)
- **stress_test**: Ramps from 100 to 5000 requests/second to find breaking point

**What it Tests**:
- Cache hit rate (Redis performance)
- Redirect latency (target: <50ms for 95% of requests)
- How system behaves under extreme stress

**Traffic Pattern Simulation**:
```javascript
// Simulates real-world access: 80% popular URLs, 20% long-tail
if (Math.random() < 0.8) {
  // Popular keys (first 20% get 80% of traffic)
  key = KEYS[Math.floor(Math.random() * (KEYS.length * 0.2))];
} else {
  // Long-tail keys (remaining 80% get 20% of traffic)
  key = KEYS[Math.floor(Math.random() * KEYS.length)];
}
```

**Metrics Collected**:
- `redirect_latency`: Time to complete redirect
- `redirect_success`: Success rate
- `cache_hit`: Estimated cache hit rate (based on response time)
- `http_redirects`: Total successful redirects
- `redirect_errors`: Total failed redirects

---

### 3. `mixed-workload.js` - Realistic Traffic Simulation

**Purpose**: Simulates production-like traffic with both URL creation and redirects.

**Traffic Split**:
- 10% URL creation
- 90% redirects (typical for URL shorteners)

**Test Scenarios**:
- **production_like**: 500 requests/second for 10 minutes
- **sustained_load**: 2000 requests/second for 5 minutes (starts at 10 min)

**What it Tests**:
- Can the system handle mixed operations simultaneously?
- Do creates and redirects interfere with each other?
- Performance under sustained realistic load

**Key Logic**:
```javascript
// Decide which operation to perform
const operationType = Math.random();

if (operationType < 0.1) {
  // 10% chance: Create new URL
  createURL();
} else {
  // 90% chance: Redirect existing URL
  redirectURL(getRandomKey());
}
```

---

## Running Tests

### Basic Commands

```bash
# Run URL creation test
k6 run tests/create-url.js

# Run redirect test with custom base URL
k6 run tests/redirect.js --env BASE_URL=http://localhost:8001

# Run mixed workload test
k6 run tests/mixed-workload.js

# Run with specific test keys (for redirect tests)
k6 run tests/redirect.js --env TEST_KEYS=test1,test2,test3
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BASE_URL` | Base URL for API requests | `http://localhost:8000` |
| `CREATE_BASE_URL` | URL creation service | `http://localhost:8000` |
| `REDIRECT_BASE_URL` | Redirect service | `http://localhost:8001` |
| `TEST_KEYS` | Comma-separated keys for testing | Auto-generated 1000 keys |

### Running with Docker

```bash
# Services must be running first
docker-compose -f docker/compose/docker-compose-decoupled.yml up -d

# Run tests against Docker services using the project network
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "$(pwd)/k6:/tests" \
  grafana/k6:latest run /tests/tests/mixed-workload.js \
  --env CREATE_BASE_URL=http://create_service:8000 \
  --env REDIRECT_BASE_URL=http://redirect_service:8001
```

---

## Understanding Test Results

### Console Output

```
✓ status is 201 or 200
✓ has short_url in response
✓ response time < 500ms
✗ status is 201 or 200

checks.........................: 95.0% ✓ 2850  ✗ 150
data_received..................: 12 MB 200 kB/s
data_sent......................: 15 MB 250 kB/s
http_req_blocked...............: avg=1.2ms    min=0.5µs   med=2µs     max=150ms
http_req_connecting............: avg=800µs    min=0s      med=0s      max=100ms
http_req_duration..............: avg=250ms    min=10ms    med=180ms   max=2s
  { expected_response:true }...: avg=250ms    min=10ms    med=180ms   max=2s
http_req_failed................: 5.0%  ✓ 150   ✗ 2850
http_req_receiving.............: avg=5ms      min=10µs    med=2ms     max=200ms
http_req_sending...............: avg=10ms     min=5µs     med=100µs   max=150ms
http_req_tls_handshaking.......: avg=0s       min=0s      med=0s      max=0s
http_req_waiting...............: avg=235ms    min=10ms    med=175ms   max=1.9s
http_reqs......................: 3000  50/s
iteration_duration.............: avg=1.5s     min=105ms   med=1s      max=5s
iterations.....................: 3000  50/s
vus............................: 50    min=50  max=200
vus_max........................: 200   min=200 max=200
```

### Key Metrics Explained

| Metric | What It Means | Good Value |
|--------|---------------|------------|
| `http_req_duration` | Total request time | <500ms for creates, <50ms for redirects |
| `http_req_failed` | Failed request rate | <5% |
| `checks` | Custom check pass rate | >95% |
| `vus` | Active virtual users | Varies by test |
| `p(95)` | 95th percentile latency | 95% of requests complete under this time |

### Thresholds

Each test defines performance thresholds. If not met, the test exits with non-zero status:

```javascript
thresholds: {
  'http_req_duration': ['p(95)<500'],  // 95% under 500ms
  'http_req_failed': ['rate<0.05'],     // Less than 5% errors
}
```

---

## Customization

### Changing Load Parameters

Edit the `options` object in each test file:

```javascript
export const options = {
  scenarios: {
    my_test: {
      executor: 'constant-arrival-rate',
      rate: 100,        // Change: requests per second
      timeUnit: '1s',   // Time unit for rate
      duration: '5m',   // Change: test duration
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
};
```

### Adding New Test Scenarios

```javascript
export const options = {
  scenarios: {
    // Add your custom scenario
    custom_test: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 100,
      stages: [
        { duration: '1m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '1m', target: 0 },
      ],
    },
  },
};
```

### Custom Metrics

```javascript
import { Rate, Trend, Counter } from 'k6/metrics';

const myCustomRate = new Rate('my_custom_rate');
const myCustomTrend = new Trend('my_custom_trend');

// In your test
myCustomRate.add(1);  // Add success
myCustomTrend.add(duration);  // Record timing
```

---

## Integration with Grafana

To send k6 metrics to Prometheus/Grafana, use the k6-prometheus extension:

```bash
# Install xk6 with Prometheus extension
xk6 build --with github.com/grafana/xk6-output-prometheus-push

# Run with Prometheus output
k6 run --out push=http://localhost:9091 tests/mixed-workload.js
```

---

## Troubleshooting

### Connection Refused

Ensure services are running:
```bash
docker-compose -f docker/compose/docker-compose-decoupled.yml ps
```

### High Failure Rates

- Check service health: `curl http://localhost:8000/health`
- Review service logs: `docker-compose logs -f create_service`
- Increase `maxVUs` in test configuration

### Slow Response Times

- Check if Redis is caching: should see <10ms for cached redirects
- Review MongoDB query performance in logs
- Check circuit breaker state (may be blocking requests)

---

## Best Practices

1. **Start Small**: Begin with low RPS and gradually increase
2. **Monitor Services**: Watch Grafana dashboards during tests
3. **Test in Staging**: Run load tests against staging environment before production
4. **Use Realistic Data**: Configure traffic patterns to match production
5. **Run Regularly**: Schedule performance tests in CI/CD pipeline

---

## JavaScript Quick Reference for k6

### Making Requests

```javascript
// GET request
const response = http.get('https://example.com');

// POST request
http.post('https://api.example.com', JSON.stringify({key: 'value'}), {
  headers: {'Content-Type': 'application/json'}
});

// PUT request
http.put('https://api.example.com/123', body, params);
```

### Assertions (Checks)

```javascript
check(response, {
  'status is 200': (r) => r.status === 200,
  'body contains text': (r) => r.body.includes('expected'),
  'JSON has field': (r) => r.json('field') !== undefined,
});
```

### Randomness

```javascript
// Random number
Math.random()  // 0 to 1
Math.floor(Math.random() * 10)  // 0 to 9

// Random array element
const items = ['a', 'b', 'c'];
items[Math.floor(Math.random() * items.length)]
```

### Loops and Sleep

```javascript
// Sleep for random time
sleep(Math.random() * 3);  // 0-3 seconds

// Fixed sleep
sleep(1);  // 1 second
```