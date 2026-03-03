import http from 'k6/http';
import { check, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const redirectRate = new Rate('redirect_success');
const cacheHitRate = new Rate('cache_hit');
const redirectTime = new Trend('redirect_latency');
const httpRedirects = new Counter('http_redirects');
const httpErrors = new Counter('redirect_errors');

// Test configuration
export const options = {
  scenarios: {
    // Simulate real-world traffic pattern: mostly cache hits
    normal_traffic: {
      executor: 'constant-arrival-rate',
      rate: 1000, // 1000 requests per second
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
    // Stress test: high load to find breaking point
    stress_test: {
      executor: 'ramping-arrival-rate',
      startRate: 100,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 1000,
      stages: [
        { duration: '1m', target: 100 },   // Warm up
        { duration: '2m', target: 1000 },  // Ramp to 1000 RPS
        { duration: '3m', target: 5000 },  // Spike to 5000 RPS
        { duration: '2m', target: 100 },   // Cool down
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<50', 'p(99)<100'], // 95% under 50ms, 99% under 100ms
    http_req_failed: ['rate<0.01'], // Less than 1% errors
    redirect_success: ['rate>0.99'], // 99%+ success rate
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8001';

// Pre-populated keys to test (mix of popular and long-tail)
const KEYS = __ENV.TEST_KEYS
  ? __ENV.TEST_KEYS.split(',')
  : Array.from({ length: 1000 }, (_, i) => `test${i}`);

export function setup() {
  // Verify service is healthy
  const healthCheck = http.get(`${BASE_URL}/health`);
  if (healthCheck.status !== 200) {
    throw new Error('Service is not healthy');
  }

  // Pre-warm cache by hitting each key once
  console.log('Warming up cache...');
  const warmupCount = Math.min(100, KEYS.length);
  for (let i = 0; i < warmupCount; i++) {
    http.get(`${BASE_URL}/${KEYS[i]}`, {
      redirects: 0, // Don't follow redirects to get faster responses
    });
  }
  console.log(`Cache warmup complete with ${warmupCount} requests`);

  return { totalKeys: KEYS.length };
}

export default function(data) {
  group('Redirect Load Test', function() {
    // Simulate realistic access patterns: 80% popular keys, 20% long-tail
    let key;
    if (Math.random() < 0.8) {
      // Popular keys (first 20%)
      key = KEYS[Math.floor(Math.random() * Math.floor(KEYS.length * 0.2))];
    } else {
      // Long-tail keys (remaining 80%)
      key = KEYS[Math.floor(Math.random() * KEYS.length)];
    }

    const startTime = Date.now();
    const response = http.get(`${BASE_URL}/${key}`, {
      redirects: 0, // Don't follow redirects for performance testing
      tags: { name: 'redirect_request' },
    });
    const duration = Date.now() - startTime;

    // Record custom metrics
    redirectTime.add(duration);

    // Check response
    const isSuccess = check(response, {
      'status is 301/302/307 or 200': (r) => r.status === 301 || r.status === 302 || r.status === 307 || r.status === 200,
      'response time < 50ms': (r) => r.timings.duration < 50,
      'has location header or body': (r) =>
        r.headers['Location'] !== undefined ||
        (r.status === 200 && r.body.length > 0),
    });

    if (isSuccess) {
      redirectRate.add(1);
      httpRedirects.add(1);

      // Estimate cache hit based on response time (Redis ~0.9ms, MongoDB ~1ms)
      // In production, you'd use actual cache metrics
      if (duration < 10) {
        cacheHitRate.add(1);
      } else {
        cacheHitRate.add(0);
      }
    } else {
      redirectRate.add(0);
      httpErrors.add(1);
    }
  });
}

export function teardown(data) {
  console.log(`Test completed. Total keys tested: ${data.totalKeys}`);
}