import http from 'k6/http';
import { check, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const redirectRate = new Rate('redirect_success');
const redirectLatency = new Trend('redirect_latency');
const cacheHitRate = new Rate('cache_hit');

// Test configuration
export const options = {
  scenarios: {
    // Warm-up phase (low traffic to populate cache)
    warmup: {
      executor: 'constant-arrival-rate',
      rate: 10,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 10,
      maxVUs: 10,
      gracefulStop: '5s',
      startTime: '0s',
    },
    // Steady traffic (simulates normal load)
    steady_traffic: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 50,
      maxVUs: 50,
      gracefulStop: '5s',
      startTime: '30s',
    },
    // Stress test (find breaking point)
    stress_test: {
      executor: 'ramping-arrival-rate',
      startRate: 100,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: '30s', target: 500 },   // Ramp to 500 RPS
        { duration: '30s', target: 1000 },  // Spike to 1000 RPS
        { duration: '30s', target: 100 },   // Cool down
      ],
      gracefulStop: '5s',
      startTime: '150s',  // 2m30s
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<50', 'p(99)<100'], // 95% under 50ms, 99% under 100ms
    http_req_failed: ['rate<0.01'], // Less than 1% errors
    redirect_success: ['rate>0.99'], // 99%+ success rate
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8001';

let nextKeyIndex = 0;

export function setup() {
  // Try to discover existing keys by making a few requests
  console.log('Discovering available keys for redirect testing...');

  const testKeys = [
    // Valid keys from MongoDB (existing URLs) - 30 keys for variety
    'N3WjnOp', 'C7HS67o', 'xQ07M1D', '2E6XS48', 'DpTNrDq',
    'dz5F3SS', 'XtysJZR', 'YA0OQmC', 'Ov76fki', 'DGwpgUs',
    '9AbQB90', 'wNpp6Aq', 'qRowlX2', 'YXxzSXF', 'H3H3pFn',
    'VBwN8QG', '3rjCnbh', 'qAdWG1Z', '6GIA12W', 'g1tHVn1',
    'TJxWcgA', '2X0rDDb', 'uMNC9Ft', 'remSwKV', 'A8BUIY0',
    'VHxD2oY', 'HUB0KjK', 'w7fLqLK', 'zajQCov', '88CmTcJ'
  ];

  // Try each key and see which ones work
  const workingKeys = [];
  for (const key of testKeys) {
    const response = http.get(`${BASE_URL}/${key}`, {
      redirects: 0,
      tags: { name: 'discovery' },
    });

    if (response.status === 301 || response.status === 302 || response.status === 307 || response.status === 200) {
      workingKeys.push(key);
      console.log(`Working key found: ${key} (status: ${response.status})`);
    }
  }

  if (workingKeys.length > 0) {
    console.log(`Found ${workingKeys.length} working keys for testing`);
    return { keys: workingKeys, totalKeys: workingKeys.length };
  } else {
    console.log('No working keys found, will use dynamic key generation');
    // Generate keys dynamically and test them
    return { keys: [], totalKeys: 0 };
  }
}

function getTestKey(data) {
  // Use pre-discovered keys if available
  if (data.keys.length > 0) {
    const key = data.keys[nextKeyIndex % data.keys.length];
    nextKeyIndex++;
    return key;
  }

  // Fallback: generate sequential keys
  return 'test' + (__VU % 1000).toString().padStart(4, '0');
}

export default function(data) {
  group('Redirect Load Test', function() {
    const key = getTestKey(data);
    const startTime = Date.now();

    const response = http.get(`${BASE_URL}/${key}`, {
      redirects: 0, // Don't follow redirects
      tags: { name: 'redirect_request' },
    });

    const duration = Date.now() - startTime;
    redirectLatency.add(duration);

    // Estimate cache hit based on response time
    // < 10ms = likely cache hit (Redis)
    // >= 10ms = likely cache miss (MongoDB)
    if (duration < 10) {
      cacheHitRate.add(1);
    } else {
      cacheHitRate.add(0);
    }

    const isSuccess = check(response, {
      'redirect status (301/302/307/200)': (r) =>
        r.status === 301 || r.status === 302 || r.status === 307 || r.status === 200,
      'response time < 50ms': (r) => r.timings.duration < 50,
      'has location or body': (r) =>
        r.headers['Location'] !== undefined ||
        (r.status === 200 && r.body.length > 0),
    });

    if (isSuccess) {
      redirectRate.add(1);
    } else {
      redirectRate.add(0);
    }
  });
}

export function teardown(data) {
  console.log(`\n=== Redirect Test Summary ===`);
  console.log(`Total keys tested: ${data.totalKeys}`);
  // Note: Custom metrics are available in k6 summary, not via .value in teardown
}