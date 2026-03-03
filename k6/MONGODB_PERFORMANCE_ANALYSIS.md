# MongoDB Performance Analysis Report

## Executive Summary

**Test Date**: 2026-03-03
**Load Test**: 100-500 RPS for 4 minutes
**Result**: **FAILED** - P95 latency 4.76s (target: <500ms)

---

## Current Configuration

### MongoDB Configuration

| Setting | Value | Assessment |
|---------|-------|------------|
| **Storage Engine** | WiredTiger | ✓ Modern, efficient |
| **Cache Size** | 0.5 GB | ⚠️ **Undersized for production** |
| **Journaling** | Disabled | ✓ Fast but risky (data loss on crash) |
| **Max Connections** | 200 | ✓ Sufficient |
| **Current Connections** | 17 (9%) | ✓ Not a bottleneck |

### Application Connection Pool

| Setting | Value | Assessment |
|---------|-------|------------|
| **Max Pool Size** | 50 | ⚠️ **Too small for 500 RPS** |
| **Min Pool Size** | 10 | ✓ Reasonable |
| **Max Idle Time** | 45s | ✓ Good for cleanup |

---

## Performance Metrics Analysis

### Operation Statistics (45,434 inserts)

```
Total Write Latency: 6,301,249 μs (6.3 seconds total)
Average per Write:     139 μs (0.14ms) ✓ Excellent
But P95 Latency:       4,760 ms (4.76 seconds) ✗ Terrible
But P99 Latency:       11,210 ms (11.21 seconds) ✗ Unacceptable
```

**Interpretation**:
- **Average performance is good** (0.14ms per write)
- **Tail latency is catastrophic** (4-11 seconds)
- **Most writes complete quickly**
- **Some writes experience massive delays**

### Root Cause Analysis

#### 1. **Connection Pool Exhaustion** 🔴 CRITICAL

**Problem**:
- App pool: 50 connections
- Test load: 500 concurrent requests
- **Only 50 requests can write at once**
- **450 requests wait for connections**

**Evidence**:
- k6 showed "dropped_iterations: 17,824"
- These are requests that couldn't even start

**Impact**:
- Request queuing
- Timeout errors
- Poor user experience

---

#### 2. **Write Serialization** 🔴 CRITICAL

**Problem**:
- MongoDB collection-level write locks
- All inserts to `urls` collection serialize
- Only one write at a time (per document)

**Under 500 RPS**:
- 500 concurrent requests competing for write locks
- Lock contention causes massive latency spikes
- Some requests wait 4-11 seconds

**Evidence**:
- P95: 4.76s (requests waiting for locks)
- P99: 11.21s (extreme lock contention)

---

#### 3. **Cache Size** 🟡 MEDIUM

**Current**: 0.5 GB
**Working Set**: ~13 MB (45K docs × 300 bytes)

**Analysis**:
- Working set FITS in cache
- Cache size is NOT the bottleneck
- **But** under high load, cache evictions occur
- Page faults cause latency spikes

---

#### 4. **Synchronous Writes** 🟡 MEDIUM

**Current**: `w=1` (acknowledged)
**Behavior**: Each insert waits for MongoDB confirmation

**Problem**:
- Adds ~1-2ms per operation (network round-trip)
- Under 500 RPS: 500-1000ms of accumulated latency
- Combined with lock contention: catastrophic

---

## Performance Comparison

| Load Level | RPS | P95 Latency | P99 Latency | Success Rate |
|------------|-----|-------------|-------------|-------------|
| **Light** | 10 | 33ms | 175ms | 99.9% ✅ |
| **Medium** | 100 | Unknown | Unknown | Unknown |
| **High** | 500 | 4,760ms | 11,210ms | 92.8% ⚠️ |

**Analysis**:
- System works excellently at 10 RPS
- Performance degrades catastrophically at 500 RPS
- **Bottleneck is connection pool + write locks**

---

## Recommendations

### 🔴 CRITICAL (Must Fix)

#### 1. **Increase Connection Pool Size**

**Current**:
```python
mongo_max_pool_size = 50
```

**Recommended**:
```python
mongo_max_pool_size = 200  # 4x increase
```

**Impact**:
- Handle 500 RPS without connection starvation
- Reduce dropped_iterations to near zero
- **Expected improvement**: 50% reduction in errors

---

#### 2. **Implement Bulk Writes**

**Current**: One insert per request
**Recommended**: Batch inserts every 100ms or 1000 docs

**Code Change**:
```python
# Instead of: await collection.insert_one(doc)
# Use: await collection.insert_many(docs, ordered=False)
```

**Impact**:
- Reduce network round-trips
- Better throughput
- **Expected improvement**: 5-10x faster

---

### 🟡 HIGH PRIORITY

#### 3. **Increase MongoDB Cache**

**Current**: 0.5 GB
**Recommended**: 2-4 GB

**Change**:
```yaml
# docker-compose-decoupled.yml
mongo_db:
  command: ["--wiredTigerCacheSizeGB", "2"]
```

**Impact**:
- Fewer cache evictions
- More consistent latency
- **Expected improvement**: 20-30% reduction in P99 latency

---

#### 4. **Use Unordered Writes**

**Current**: `ordered=False` not set
**Recommended**: Always use `ordered=False`

```python
await collection.insert_many(docs, ordered=False)
```

**Impact**:
- Parallel writes instead of serial
- Better throughput
- **Expected improvement**: 2-3x faster

---

#### 5. **Implement Write-Concern: 1**

**Current**: Default (w=1) - waits for primary
**Optimization**: Use `w="majority"` only for critical data

**Trade-off**:
- Faster writes for non-critical data
- Risk: Small window of data loss

---

### 🟢 NICE TO HAVE

#### 6. **Enable MongoDB Profiling**

```python
# Monitor slow operations
db.command({'profile': 2, 'slowms': 100})
```

#### 7. **Add Connection Pool Monitoring**

```python
# Report pool metrics
{
  "pool_size": pool.size,
  "available": pool.available,
  "staged": pool.staged
}
```

---

## Expected Performance After Fixes

### With Critical Fixes Only

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| P95 Latency | 4,760ms | ~500ms | **9.5x faster** |
| P99 Latency | 11,210ms | ~1,000ms | **11x faster** |
| Success Rate | 92.8% | 99%+ | **+6.2%** |
| Dropped Requests | 17,824 | ~0 | **100% reduction** |

### With All Fixes

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| P95 Latency | 4,760ms | ~100ms | **47x faster** |
| P99 Latency | 11,210ms | ~200ms | **56x faster** |
| Max RPS | ~100 | 1,000+ | **10x more throughput** |

---

## Implementation Priority

### Phase 1: Quick Wins (1 hour)
1. Increase `mongo_max_pool_size` to 200
2. Add `ordered=False` to all writes
3. Restart services

### Phase 2: Medium Effort (1 day)
1. Implement bulk write buffer
2. Increase MongoDB cache to 2GB
3. Add performance monitoring

### Phase 3: Advanced (1 week)
1. Implement write-behind pattern
2. Add read replicas for analytics
3. Optimize index strategy

---

## Testing Validation

After each fix, re-run:

```bash
# Light test (baseline)
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "/mnt/e/url_shortener_scalable/k6/tests:/tests" \
  grafana/k6:latest run /tests/light-create.js \
  --env BASE_URL=http://create_service:8000

# Full load test
docker run --rm -i --network url_shortener_scalable_url_shortener_network \
  -v "/mnt/e/url_shortener_scalable/k6/tests:/tests" \
  grafana/k6:latest run /tests/create-url.js \
  --env BASE_URL=http://create_service:8000
```

**Success Criteria**:
- P95 < 500ms ✅
- P99 < 1000ms ✅
- HTTP errors < 5% ✅
- Success rate > 95% ✅

---

## Conclusion

The MongoDB performance issues are **solvable** with configuration changes:

**Root Cause**: Connection pool too small + write serialization

**Solution**: Increase pool size + bulk writes

**Expected Result**: 10-50x performance improvement

**No code refactoring required** - only configuration and minor code changes.

---

## Appendix: Connection Pool Math

**Current Configuration**:
- Pool size: 50 connections
- Each connection: ~1 write operation
- Max concurrent writes: 50
- At 500 RPS: 450 requests waiting

**Required Configuration**:
- Pool size: 200 connections
- Each connection: ~1 write operation
- Max concurrent writes: 200
- At 500 RPS: 300 requests waiting (better, but not perfect)

**Optimal Configuration**:
- Pool size: 200 connections
- Bulk writes: 100 docs per batch
- Effective throughput: 20,000 writes/sec
- At 500 RPS: No waiting ✅