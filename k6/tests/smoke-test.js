import http from 'k6/http';
import { check } from 'k6';

// Simple smoke test to verify services are working
// Run this before any load tests to ensure basic functionality

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ['rate==1.0'], // All checks must pass
  },
};

const CREATE_BASE_URL = __ENV.CREATE_BASE_URL || 'http://localhost:8000';
const REDIRECT_BASE_URL = __ENV.REDIRECT_BASE_URL || 'http://localhost:8001';

export default function() {
  console.log('Running smoke test...');

  // Test 1: Create service health
  const createHealth = http.get(`${CREATE_BASE_URL}/health`);
  check(createHealth, {
    'create_service health check passes': (r) => r.status === 200,
  });
  console.log(`Create service health: ${createHealth.status}`);

  // Test 2: Redirect service health
  const redirectHealth = http.get(`${REDIRECT_BASE_URL}/health`);
  check(redirectHealth, {
    'redirect_service health check passes': (r) => r.status === 200,
  });
  console.log(`Redirect service health: ${redirectHealth.status}`);

  // Test 3: Create a short URL
  const testPayload = JSON.stringify({
    long_url: 'https://example.com/smoke-test',
    expires_at: new Date(Date.now() + 86400000).toISOString(), // 24 hours from now
  });

  const createResponse = http.post(
    `${CREATE_BASE_URL}/api/v1/create`,
    testPayload,
    { headers: { 'Content-Type': 'application/json' } }
  );

  const createSuccess = check(createResponse, {
    'create URL returns 201 or 200': (r) => r.status === 201 || r.status === 200,
    'response has short_url': (r) => {
      try {
        return r.json('short_url') !== undefined;
      } catch {
        return false;
      }
    },
  });

  console.log(`Create URL status: ${createResponse.status}`);

  if (createSuccess) {
    // Test 4: Redirect using the created URL
    try {
      const shortUrl = createResponse.json('short_url');
      const shortKey = shortUrl.split('/').pop();

      const redirectResponse = http.get(`${REDIRECT_BASE_URL}/${shortKey}`, {
        redirects: 0,
      });

      check(redirectResponse, {
        'redirect returns valid redirect status': (r) =>
          r.status === 301 || r.status === 302 || r.status === 307 || r.status === 200,
      });

      console.log(`Redirect status for ${shortKey}: ${redirectResponse.status}`);
    } catch (e) {
      console.log(`Could not test redirect: ${e.message}`);
    }
  }

  console.log('Smoke test completed!');
}