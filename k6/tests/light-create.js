import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const creationTime = new Trend('creation_time');

// Lightweight test configuration
export const options = {
  scenarios: {
    light_load: {
      executor: 'constant-arrival-rate',
      rate: 10, // 10 requests per second
      timeUnit: '1s',
      duration: '1m',
      preAllocatedVUs: 5,
      maxVUs: 20,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_ENDPOINT = `${BASE_URL}/api/v1/create`;

function generateRandomURL() {
  const domains = ['example.com', 'test.com', 'demo.org'];
  const path = Math.random().toString(36).substring(7);
  return `https://${domains[Math.floor(Math.random() * domains.length)]}/${path}`;
}

function generateExpirationDate() {
  const now = new Date();
  now.setDate(now.getDate() + Math.floor(Math.random() * 30) + 1);
  return now.toISOString();
}

export default function() {
  const payload = JSON.stringify({
    long_url: generateRandomURL(),
    expires_at: generateExpirationDate(),
  });

  const response = http.post(API_ENDPOINT, payload, {
    headers: { 'Content-Type': 'application/json' },
  });

  const isSuccess = check(response, {
    'status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'has short_url': (r) => {
      try {
        return r.json('short_url') !== undefined;
      } catch {
        return false;
      }
    },
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  if (isSuccess) {
    errorRate.add(0);
    creationTime.add(response.timings.duration);
  } else {
    errorRate.add(1);
  }

  sleep(Math.random());
}

export function teardown() {
  console.log('Light load test completed');
}