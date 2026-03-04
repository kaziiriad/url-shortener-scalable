#!/usr/bin/env python3
"""
Load Balancer Test Script for URL Shortener
Tests load distribution, performance, and functionality.
"""

import asyncio
import aiohttp
import json
import time
from collections import Counter
import sys

class LoadBalancerTester:
    def __init__(self, base_url="http://localhost"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_and_distribution(self, num_requests=20):
        """Test health endpoint and measure load distribution."""
        print("🔍 Testing Health Endpoint & Load Distribution")
        print("-" * 60)
        
        instance_responses = []
        response_times = []
        
        for i in range(num_requests):
            start_time = time.time()
            try:
                async with self.session.get(f"{self.base_url}/health") as response:
                    response_time = time.time() - start_time
                    response_times.append(response_time)
                    
                    if response.status == 200:
                        data = await response.json()
                        instance_id = data.get("instance_id", "unknown")
                        hostname = data.get("hostname", instance_id)
                        instance_responses.append(hostname)
                        status = "✅" if data.get("status") == "healthy" else "⚠️"
                        print(f"Request {i+1:2d}: {hostname} {status} ({response_time:.3f}s)")
                    else:
                        print(f"Request {i+1:2d}: HTTP {response.status} ({response_time:.3f}s)")
            except Exception as e:
                response_time = time.time() - start_time
                print(f"Request {i+1:2d}: Error - {e} ({response_time:.3f}s)")
            
            await asyncio.sleep(0.1)
        
        # Analyze results
        if instance_responses:
            distribution = Counter(instance_responses)
            avg_response_time = sum(response_times) / len(response_times)
            
            print(f"\n📊 Load Distribution Analysis:")
            print("-" * 40)
            for hostname, count in distribution.items():
                percentage = (count / len(instance_responses)) * 100
                print(f"Container {hostname}: {count:2d} requests ({percentage:5.1f}%)")
            
            print(f"\n⏱️  Performance Metrics:")
            print(f"Average response time: {avg_response_time:.3f}s")
            print(f"Min response time: {min(response_times):.3f}s")
            print(f"Max response time: {max(response_times):.3f}s")
            
            return len(set(instance_responses)) > 1  # True if load balancing works
        
        return False
    
    async def test_api_functionality(self):
        """Test core API functionality through load balancer."""
        print(f"\n🚀 Testing API Functionality")
        print("-" * 60)
        
        # Test root endpoint
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                data = await response.json()
                print(f"✅ Root endpoint: {response.status} - {data.get('message', 'N/A')}")
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
        
        # Test URL creation
        test_url = "https://www.example.com/test-page"
        try:
            payload = {"long_url": test_url}
            async with self.session.post(f"{self.base_url}/api/v1/create", json=payload) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    short_url = data.get("short_url", "")
                    print(f"✅ URL Creation: {response.status} - {short_url}")
                    
                    # Test redirect
                    if short_url:
                        short_key = short_url.split("/")[-1]
                        async with self.session.get(f"{self.base_url}/{short_key}", 
                                                  allow_redirects=False) as redirect_response:
                            location = redirect_response.headers.get('Location', '')
                            if redirect_response.status in [301, 302] and location == test_url:
                                print(f"✅ Redirect test: {redirect_response.status} -> {location}")
                            else:
                                print(f"⚠️  Redirect test: {redirect_response.status} -> {location}")
                else:
                    text = await response.text()
                    print(f"⚠️  URL Creation: {response.status} - {text}")
        except Exception as e:
            print(f"❌ API functionality error: {e}")
    
    async def test_performance_under_load(self, concurrent_requests=50):
        """Test performance under concurrent load."""
        print(f"\n⚡ Performance Test ({concurrent_requests} concurrent requests)")
        print("-" * 60)
        
        async def single_request():
            start_time = time.time()
            try:
                async with self.session.get(f"{self.base_url}/health") as response:
                    return {
                        'status': response.status,
                        'time': time.time() - start_time,
                        'success': response.status == 200
                    }
            except Exception as e:
                return {
                    'status': 'error',
                    'time': time.time() - start_time,
                    'success': False,
                    'error': str(e)
                }
        
        # Execute concurrent requests
        start_time = time.time()
        tasks = [single_request() for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        response_times = [r['time'] for r in results if r['success']]
        
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            requests_per_second = successful / total_time
            
            print(f"Total time: {total_time:.2f}s")
            print(f"Successful requests: {successful}/{concurrent_requests}")
            print(f"Failed requests: {failed}")
            print(f"Requests/second: {requests_per_second:.2f}")
            print(f"Average response time: {avg_time:.3f}s")
            print(f"95th percentile: {sorted(response_times)[int(len(response_times) * 0.95)]:.3f}s")
        else:
            print("❌ No successful requests during load test")
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        print(f"\n🚦 Testing Rate Limiting")
        print("-" * 60)
        
        # Send rapid requests to trigger rate limiting
        responses = []
        start_time = time.time()
        
        for i in range(20):
            try:
                async with self.session.get(f"{self.base_url}/health") as response:
                    responses.append(response.status)
                    if response.status == 429:
                        print(f"⚠️  Rate limiting triggered at request {i+1}")
                        break
            except Exception as e:
                responses.append('error')
            
            # No delay - send as fast as possible
        
        end_time = time.time()
        
        successful = sum(1 for status in responses if status == 200)
        rate_limited = sum(1 for status in responses if status == 429)
        errors = sum(1 for status in responses if status == 'error')
        
        print(f"Test duration: {end_time - start_time:.2f}s")
        print(f"Successful: {successful}")
        print(f"Rate limited (429): {rate_limited}")
        print(f"Errors: {errors}")
        print(f"Total requests: {len(responses)}")

async def main():
    """Main test runner."""
    print("🔧 URL Shortener Load Balancer Test Suite")
    print("=" * 70)
    
    # Check if custom URL provided
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"
    print(f"Testing URL: {base_url}")
    
    async with LoadBalancerTester(base_url) as tester:
        # Test 1: Health and Distribution
        load_balancing_works = await tester.test_health_and_distribution()
        
        if not load_balancing_works:
            print("\n⚠️  Warning: Load balancing may not be working properly")
            print("   Only one instance detected or no successful responses")
        
        # Test 2: API Functionality
        await tester.test_api_functionality()
        
        # Test 3: Performance under load
        await tester.test_performance_under_load()
        
        # Test 4: Rate limiting
        await tester.test_rate_limiting()
    
    print("\n" + "=" * 70)
    print("✅ Load Balancer Test Suite Completed")
    print("\nTo run with different URL: python test_load_balancer.py http://your-domain.com")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)