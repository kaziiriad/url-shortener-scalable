"""
Retry mechanisms and circuit breaker for database operations.
Handles transient failures in distributed systems.
"""
import asyncio
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Callable, Any
from sqlalchemy.exc import OperationalError, DBAPIError
from pymongo.errors import AutoReconnect, NetworkTimeout
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit breaker pattern implementation for database operations.
    Prevents cascade failures by stopping requests when failure rate is high.
    """
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        
    def record_success(self):
        """Record a successful operation."""
        self.failures = 0
        self.state = "closed"
        
    def record_failure(self):
        """Record a failed operation."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker opened after {self.failures} failures")
            
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
            
        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = "half_open"
                logger.info("Circuit breaker entering half-open state")
                return True
            return False
            
        # half_open state - allow one request to test
        return True

# Global circuit breakers for different services
postgres_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
mongo_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (OperationalError, DBAPIError, AutoReconnect, NetworkTimeout)
):
    """
    Decorator to retry database operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay (exponential backoff)
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record success if this was a retry
                    if attempt > 0:
                        logger.info(f"Operation succeeded after {attempt} retries")
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Operation failed after {max_retries + 1} attempts: {e}"
                        )
                        raise
                        
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(f"Unexpected error (not retrying): {e}")
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """
    Decorator to apply circuit breaker pattern to database operations.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not circuit_breaker.can_execute():
                raise Exception(
                    f"Circuit breaker is open. Service temporarily unavailable. "
                    f"Try again in {circuit_breaker.timeout}s"
                )
            
            try:
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
            except Exception as e:
                circuit_breaker.record_failure()
                raise
                
        return wrapper
    return decorator

# Example usage in URLService
@with_retry(max_retries=3, delay=1.0, backoff=2.0)
@with_circuit_breaker(postgres_circuit_breaker)
async def get_unused_key_with_retry(session):
    """Get unused key with retry and circuit breaker."""
    from common.db.sql.models import URL
    return await URL.get_unused_key(session)

@with_retry(max_retries=3, delay=1.0, backoff=2.0)
@with_circuit_breaker(mongo_circuit_breaker)
async def store_url_with_retry(db, url_data):
    """Store URL in MongoDB with retry and circuit breaker."""
    return await db.urls.insert_one(url_data.model_dump())

# Connection pool exhaustion handler
async def handle_pool_exhaustion(func: Callable, *args, **kwargs):
    """
    Handle connection pool exhaustion gracefully.
    Returns a degraded service response instead of failing completely.
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        error_msg = str(e).lower()
        
        if "timeout" in error_msg or "pool" in error_msg:
            logger.critical(
                f"Connection pool exhaustion detected: {e}. "
                "Consider scaling up connection pool or adding more instances."
            )
            # Return graceful degradation
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable due to high load. Please retry."
            )
        raise

# Database query timeout wrapper
async def with_timeout(func: Callable, timeout_seconds: int = 30):
    """
    Execute database operation with timeout.
    Prevents hanging connections from exhausting the pool.
    """
    try:
        return await asyncio.wait_for(
            func(),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(f"Database operation timed out after {timeout_seconds}s")
        raise HTTPException(
            status_code=504,
            detail="Database operation timed out"
        )