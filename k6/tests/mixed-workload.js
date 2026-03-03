import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const createTime = new Trend('create_latency');
const redirectTime = new Trend('redirect_latency');
const createCount = new Counter('operations_create');
const redirectCount = new Counter('operations_redirect');

// Test configuration
export const options = {
  scenarios: {
    // Simulate production traffic pattern
    production_like: {
      executor: 'constant-arrival-rate',
      rate: 500, // 500 requests per second total
      timeUnit: '1s',
      duration: '10m',
      preAllocatedVUs: 100,
      maxVUs: 500,
      gracefulStop: '30s',
    },
    // Load test: sustained high traffic
    sustained_load: {
      executor: 'constant-arrival-rate',
      startTime: '10m',
      rate: 2000,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 200,
      maxVUs: 1000,
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<200'], // 95% under 200ms
    http_req_failed: ['rate<0.02'], // Less than 2% errors
    errors: ['rate<0.02'],
  },
};

const CREATE_BASE_URL = __ENV.CREATE_BASE_URL || 'http://localhost:8000';
const REDIRECT_BASE_URL = __ENV.REDIRECT_BASE_URL || 'http://localhost:8001';

// Traffic split: 10% create, 90% redirect (typical URL shortener pattern)
const TRAFFIC_SPLIT = { create: 0.1, redirect: 0.9 };

// Pool of keys for redirect testing
const KEY_POOL = __ENV.TEST_KEYS
  ? __ENV.TEST_KEYS.split(',')
  : Array.from({ length: 5000 }, (_, i) => `test${i}`);

let createdKeys = []; // Store newly created keys for redirect testing

function generateRandomURL() {
  const domains = ['example.com', 'test.com', 'demo.org', 'sample.net', 'api.example.com'];
  const paths = [
    'page1',
    'test',
    'demo',
    'api/v1/users',
    'products/123',
    'blog/post-1',
    'docs/reference',
    'search?q=test',
  ];
  const domain = domains[Math.floor(Math.random() * domains.length)];
  const path = paths[Math.floor(Math.random() * paths.length)];
  return `https://${domain}/${path}`;
}

function generateExpirationDate() {
  const now = new Date();
  now.setDate(now.getDate() + Math.floor(Math.random() * 30) + 1);
  return now.toISOString();
}

function createURL() {
  const payload = JSON.stringify({
    long_url: generateRandomURL(),
    expires_at: generateExpirationDate(),
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'create_url' },
  };

  const startTime = Date.now();
  const response = http.post(`${CREATE_BASE_URL}/api/v1/create`, payload, params);
  const duration = Date.now() - startTime;

  createTime.add(duration);
  createCount.add(1);

  const isSuccess = check(response, {
    'create status is 201 or 200': (r) => r.status === 201 || r.status === 200,
    'has short_url': (r) => r.json('short_url') !== undefined,
    'create time < 500ms': (r) => r.timings.duration < 500,
  });

  if (isSuccess) {
    errorRate.add(0);
    // Extract key for redirect testing
    try {
      const shortUrl = response.json('short_url');
      const key = shortUrl.split('/').pop();
      if (key) {
        createdKeys.push(key);
        // Keep only recent keys to manage memory
        if (createdKeys.length > 1000) {
          createdKeys = createdKeys.slice(-500);
        }
      }
    } catch (e) {
      // Ignore parsing errors
    }
  } else {
    errorRate.add(1);
  }

  return { success: isSuccess, duration };
}

function redirectURL(key) {
  const startTime = Date.now();
  const response = http.get(`${REDIRECT_BASE_URL}/${key}`, {
    redirects: 0,
    tags: { name: 'redirect_url' },
  });
  const duration = Date.now() - startTime;

  redirectTime.add(duration);
  redirectCount.add(1);

  const isSuccess = check(response, {
    'redirect status is 301/302/307/200': (r) =>
      r.status === 301 || r.status === 302 || r.status === 307 || r.status === 200,
    'redirect time < 50ms': (r) => r.timings.duration < 50,
  });

  if (isSuccess) {
    errorRate.add(0);
  } else {
    errorRate.add(1);
  }

  return { success: isSuccess, duration };
}

export function setup() {
  // Health check
  const createHealth = http.get(`${CREATE_BASE_URL}/health`);
  const redirectHealth = http.get(`${REDIRECT_BASE_URL}/health`);

  if (createHealth.status !== 200 || redirectHealth.status !== 200) {
    throw new Error('Services are not healthy');
  }

  console.log('Services are healthy. Starting mixed workload test...');
  return { startTime: new Date().toISOString() };
}

export default function(data) {
  // Decide operation type based on traffic split
  const operationType = Math.random();

  if (operationType < TRAFFIC_SPLIT.create) {
    // Create operation
    createURL();
  } else {
    // Redirect operation
    let key;

    // 30% chance to use a recently created key
    if (createdKeys.length > 0 && Math.random() < 0.3) {
      key = createdKeys[Math.floor(Math.random() * createdKeys.length)];
    } else {
      // Use pre-populated keys with zipf distribution (prefer popular keys)
      const zipfIndex = Math.floor(Math.random() * Math.random() * KEY_POOL.length);
      key = KEY_POOL[Math.min(zipfIndex, KEY_POOL.length - 1)];
    }

    redirectURL(key);
  }

  // Minimal think time (realistic automated traffic)
  sleep(Math.random() * 0.1);
}

export function teardown(data) {
  console.log(`Test completed. Started at: ${data.startTime}`);
  console.log(`Created ${createdKeys.length} new URLs during test`);
}