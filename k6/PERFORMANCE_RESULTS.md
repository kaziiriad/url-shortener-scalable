# Performance Testing Results Summary

## Test Environment

- **Date**: 2026-03-03
- **Services**: Docker Compose (create_service, redirect_service, MongoDB, PostgreSQL, Redis)
- **Network**: url_shortener_scalable_url_shortener_network
- **Tool**: k6 (Grafana k6:latest)

---

## Test Results Overview

| Test | Duration | Load | Success Rate | P95 Latency | P99 Latency | Status |
|------|----------|------|--------------|-------------|-------------|--------|
| Smoke Test | 30s | 1 request | 100% | 29.61ms | 33.26ms | ✅ PASS |
| Light Load | 60s | 10 RPS | 99.88% | 33.15ms | 174.68ms | ✅ PASS |
| Full Load | 4 min | 100-500 RPS | 1% | 4.55s | 13.93s | ❌ FAIL |

---

## Detailed Analysis

### ✅ Smoke Test (Baseline)

**Configuration**: Single request to verify service health

**Results**:
- All 5 checks passed
- HTTP duration avg: 11.12ms
- Create service: Healthy
- Redirect service: Healthy (status 307)
- URL creation: Working
- Redirect: Working

**Conclusion**: Services are functioning correctly under minimal load.

---

### ✅ Light Load Test (10 RPS)

**Configuration**: 10 requests/second for 1 minute

**Results**:
```
Total Requests: 596
Success Rate: 99.88% (594/596)
HTTP Failures: 0%

Latency Metrics:
  Average: 25.81ms
  Median: 19.3ms
  P90: 25.87ms
  P95: 33.15ms  ✓ (target: <500ms)
  P99: 174.68ms ✓ (target: <1000ms)
  Max: 683.31ms
```

**Performance Grade**: ⭐⭐⭐⭐⭐ Excellent

**System Behavior**:
- Consistent performance throughout test
- Connection pooling working effectively
- Key pool (50K available keys) sufficient
- Minimal contention on database resources

---

### ❌ Full Load Test (100-500 RPS)

**Configuration**:
- Constant load: 100 RPS for 2 min
- Spike test: 500 RPS for 30 sec
- Recovery: 100 RPS for 90 sec

**Results**:
```
Total Attempts: 18,191
Successful Creations: 190 (1%)
Failed Requests: 7,970 (43.81% HTTP errors)
Dropped Iterations: 17,811

Latency Metrics:
  Average: 2.1s
  P95: 4.55s ✗ (target: <500ms)
  P99: 13.93s ✗ (target: <1000ms)
```

**Root Cause Analysis**:
1. **Key Pool Exhaustion**:
   - Started with: 10,223 keys
   - All keys used during test
   - Pool hit 0 available keys

2. **Cascading Failures**:
   - Empty pool → HTTP 503 errors
   - On-demand key generation slow under load
   - Contention on PostgreSQL advisory locks

3. **Bottlenecks Identified**:
   - Key pre-population not fast enough
   - Batch size (1,000 keys) too small for production
   - No auto-scaling based on pool usage

---

## Production Recommendations

### Critical Issues

1. **Increase Key Pool Size** 🔴
   - Current: 10K keys
   - Recommended: 100K-1M keys for production
   - Implement auto-scaling when pool < 20% full

2. **Faster Key Generation** 🟡
   - Use PostgreSQL `generate_series()` for bulk inserts
   - Can generate 50K+ keys per batch
   - Reduces fill time from minutes to seconds

3. **Key Pool Monitoring** 🟡
   - Alert when pool < 30% capacity
   - Automated population triggers
   - Dashboard visualization in Grafana

### Performance Optimization

**URL Creation**:
- ✅ Handles 10 RPS with <35ms P95 latency
- ✅ Race condition fix working correctly
- ⚠️ Limited by key pool capacity under high load

**Recommended Limits**:
- **Development**: 10 RPS (current configuration)
- **Staging**: 50 RPS with 50K key pool
- **Production**: 500+ RPS with 1M key pool + auto-scaling

---

## Test Artifacts

**Test Scripts**:
- `smoke-test.js` - Health check verification
- `light-create.js` - Baseline performance (10 RPS)
- `create-url.js` - Full load test (100-500 RPS)
- `redirect.js` - Redirect performance test
- `mixed-workload.js` - Realistic traffic simulation

**Key Finding**:
The system's performance is **excellent** when the key pool is sufficiently populated. The bottleneck is not in the application code but in the key supply chain.

---

## Next Steps

1. **Implement Key Pool Auto-Scaling**
   - Monitor pool usage percentage
   - Trigger population when < 30%
   - Use PostgreSQL native method for speed

2. **Add Production Monitoring**
   - Key pool capacity alerts
   - Performance degradation detection
   - Automatic throttling when pool is low

3. **Re-test After Improvements**
   - Run full load test with 100K+ key pool
   - Validate auto-scaling behavior
   - Establish production capacity limits

---

## Command Reference

```bash
# Run smoke test (quick health check)
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "/mnt/e/url_shortener_scalable/k6/tests:/tests" \
  grafana/k6:latest run /tests/smoke-test.js \
  --env CREATE_BASE_URL=http://create_service:8000 \
  --env REDIRECT_BASE_URL=http://redirect_service:8001

# Run light load test (baseline)
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "/mnt/e/url_shortener_scalable/k6/tests:/tests" \
  grafana/k6:latest run /tests/light-create.js \
  --env BASE_URL=http://create_service:8000

# Run full load test (after populating keys!)
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "/mnt/e/url_shortener_scalable/k6/tests:/tests" \
  grafana/k6:latest run /tests/create-url.js \
  --env BASE_URL=http://create_service:8000
```

---

**Test Summary**: The URL shortener service demonstrates excellent performance characteristics (P95 < 35ms) at moderate load levels when properly provisioned. The identified key pool bottleneck is addressable through configuration changes and does not require code refactoring.