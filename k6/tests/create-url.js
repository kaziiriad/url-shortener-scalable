import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const creationTime = new Trend('creation_time');
const successCount = new Counter('creations_success');
const failureCount = new Counter('creations_failed');

// Test configuration
export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-arrival-rate',
      rate: 100, // 100 requests per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
    spike_test: {
      executor: 'constant-arrival-rate',
      startTime: '2m',
      rate: 500, // Spike to 500 RPS
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
    recovery: {
      executor: 'constant-arrival-rate',
      startTime: '2m30s',
      rate: 100, // Return to normal
      timeUnit: '1s',
      duration: '1m30s',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% under 500ms, 99% under 1s
    http_req_failed: ['rate<0.05'], // Less than 5% errors
    errors: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_ENDPOINT = `${BASE_URL}/api/v1/create`;

export function setup() {
  // Pre-warm the connection
  http.get(`${BASE_URL}/health`);
  return { startTime: new Date().toISOString() };
}

function generateRandomURL() {
  const domains = ['example.com', 'test.com', 'demo.org', 'sample.net'];
  const paths = ['page1', 'test', 'demo', 'api/v1/users', 'products/123'];
  const domain = domains[Math.floor(Math.random() * domains.length)];
  const path = paths[Math.floor(Math.random() * paths.length)];
  return `https://${domain}/${path}`;
}

function generateExpirationDate() {
  const now = new Date();
  now.setDate(now.getDate() + Math.floor(Math.random() * 30) + 1); // 1-30 days from now
  return now.toISOString();
}

export default function(data) {
  const payload = JSON.stringify({
    long_url: generateRandomURL(),
    expires_at: generateExpirationDate(),
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const startTime = Date.now();
  const response = http.post(API_ENDPOINT, payload, params);
  const duration = Date.now() - startTime;

  // Record custom metrics
  creationTime.add(duration);

  const isSuccess = check(response, {
    'status is 201 or 200': (r) => r.status === 201 || r.status === 200,
    'has short_url in response': (r) => r.json('short_url') !== undefined,
    'has long_url in response': (r) => r.json('long_url') !== undefined,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  if (isSuccess) {
    successCount.add(1);
    errorRate.add(0);
  } else {
    failureCount.add(1);
    errorRate.add(1);
  }

  sleep(Math.random() * 2); // Random think time 0-2s
}

export function teardown(data) {
  console.log(`Test completed. Started at: ${data.startTime}`);
}
