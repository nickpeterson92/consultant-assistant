# Circuit Breaker and Resilience Patterns Documentation

> **Important Note**: In this system, circuit breakers are used **only for network calls** (A2A protocol communication between agents). They are **not used for local database operations** like SQLite access, as local operations don't have the same failure patterns as network calls.

## Table of Contents
1. [Introduction for Junior Engineers](#introduction-for-junior-engineers)
2. [What is a Circuit Breaker?](#what-is-a-circuit-breaker)
3. [Real-World Analogy](#real-world-analogy)
4. [Why Circuit Breakers are Crucial](#why-circuit-breakers-are-crucial)
5. [Circuit Breaker Pattern](#circuit-breaker-pattern)
6. [Step-by-Step Implementation Guide](#step-by-step-implementation-guide)
7. [Common Mistakes and How to Avoid Them](#common-mistakes-and-how-to-avoid-them)
8. [Testing Circuit Breakers](#testing-circuit-breakers)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Practical Examples](#practical-examples)
11. [Advanced Topics](#advanced-topics)

## Introduction for Junior Engineers

Welcome! This guide will teach you about one of the most important patterns in distributed systems: the Circuit Breaker. If you're new to building systems that talk to other services over the network, this pattern will save you from many production nightmares.

### Prerequisites
- Basic understanding of async/await in Python
- Familiarity with try/except error handling
- Knowledge of HTTP requests and responses

## What is a Circuit Breaker?

A circuit breaker is a design pattern that prevents a network or service failure from constantly recurring. Think of it as a smart wrapper around your external service calls that can automatically "turn off" requests when things go wrong.

### The Problem It Solves

Imagine you have a service that calls another service:

```python
# Without circuit breaker - BAD!
async def get_user_data(user_id):
    try:
        response = await external_api.get(f"/users/{user_id}")
        return response.json()
    except Exception as e:
        # This will keep trying and failing!
        logger.error(f"Failed to get user: {e}")
        raise
```

If `external_api` is down, every request will:
1. Wait for a timeout (maybe 30 seconds)
2. Fail
3. Make your users wait
4. Potentially crash your service with too many hanging connections

## Real-World Analogy

### The Electrical Circuit Breaker

Think about the circuit breaker in your home's electrical panel:

1. **Normal Operation (CLOSED)**: Electricity flows normally from the power company to your appliances
2. **Detecting Problems**: If too much current flows (like a short circuit), it detects danger
3. **Breaking the Circuit (OPEN)**: It "trips" and cuts off electricity to prevent fires
4. **Manual Reset (HALF-OPEN)**: After fixing the problem, you manually flip the switch to test if it's safe
5. **Back to Normal**: If the test succeeds, power flows again

Our software circuit breaker works the same way:
- **CLOSED**: Requests flow to the external service
- **OPEN**: Requests are blocked when too many failures occur
- **HALF-OPEN**: We test with a few requests to see if the service recovered

### Visual Representation

```
Your Service          Circuit Breaker          External Service
     |                      |                         |
     |---Request #1------>[CLOSED]-------Success----->|
     |<--Response---------[CLOSED]<-------200 OK------|
     |                      |                         |
     |---Request #2------>[CLOSED]-------Success----->|
     |<--Response---------[CLOSED]<-------200 OK------|
     |                      |                         |
     |---Request #3------>[CLOSED]-------Timeout----->| (Service Down!)
     |<--Error-----------[CLOSED]<-------Timeout------|
     |                      |                         |
     |---Request #4------>[CLOSED]-------Timeout----->|
     |<--Error-----------[CLOSED]<-------Timeout------|
     |                      |                         |
     |---Request #5------>[CLOSED]-------Timeout----->|
     |<--Error-----------[OPEN!]<--------Timeout------| (Circuit Opens!)
     |                      |                         |
     |---Request #6------>[OPEN]                      |
     |<--Fast Fail!------[OPEN]                       | (No network call!)
     |                      |                         |
     |  ... time passes ... |                         |
     |                      |                         |
     |---Request #N----->[HALF-OPEN]-----Test-------->| (Testing recovery)
     |<--Response-------[CLOSED]<--------200 OK-------| (Service is back!)
```

## Why Circuit Breakers are Crucial

### 1. Prevents Cascading Failures
Without circuit breakers, one failing service can bring down your entire system:
```
Service A → Service B → Service C
           ↘         ↗
            Service D

If Service C fails, B waits, A waits, D waits... everything grinds to a halt!
```

### 2. Fail Fast
Users prefer quick errors over long waits:
- ❌ Without CB: 30-second timeout, user gives up
- ✅ With CB: Instant error, user can retry or do something else

### 3. Gives Services Time to Recover
Bombarding a struggling service with requests prevents recovery:
- ❌ Without CB: Failing service gets 1000 requests/second
- ✅ With CB: Failing service gets 0 requests, can restart peacefully

### 4. Resource Protection
Your service has limited resources:
- ❌ Without CB: All threads/connections tied up waiting for timeouts
- ✅ With CB: Resources available for other operations

## Overview

The resilience patterns in this system protect against cascading failures, network issues, and service degradation in the distributed multi-agent architecture. The implementation centers around the Circuit Breaker pattern, complemented by retry logic, timeouts, and graceful degradation strategies.

### Where Circuit Breakers Are Used in This System

Circuit breakers are applied **selectively** based on the type of operation:

✅ **Used for Network Operations:**
- A2A protocol calls between agents
- Health check endpoints
- External API calls

❌ **NOT Used for Local Operations:**
- SQLite database access (local file system)
- Memory operations
- Configuration loading
- Local file I/O

This selective application follows the principle that circuit breakers are meant for unreliable network operations, not reliable local operations.

## Circuit Breaker Pattern

### The Three States Explained

A circuit breaker has three states, just like a traffic light system:

1. **CLOSED (Green Light)** - Normal operation
   - All requests pass through
   - We're counting failures
   - Like normal traffic flow

2. **OPEN (Red Light)** - Circuit is broken
   - All requests fail immediately
   - No requests reach the external service
   - Like a road closure

3. **HALF-OPEN (Yellow Light)** - Testing phase
   - Limited requests allowed through
   - Testing if the service recovered
   - Like a cautious merge

### State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    Circuit Breaker States                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────┐     failures >= threshold     ┌────────────┐    │
│  │            │──────────────────────────────>│            │    │
│  │   CLOSED   │                               │    OPEN    │    │
│  │  (Normal)  │<──────────────────────────────│   (Fail)   │    │
│  └─────┬──────┘        success                └──────┬─────┘    │
│        │ ^                                           │          │
│        │ │                                           │          │
│        │ │ success           timeout elapsed         │          │
│        │ └───────────────┐                           │          │
│        │                 │                           ▼          │
│        │                 │                   ┌──────────────┐   │
│        │ failure         │                   │  HALF_OPEN   │   │
│        └─────────────────┴───────────────────│   (Test)     │   │
│                                              └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5          # Failures before opening
    timeout: float = 60.0              # Seconds to stay open
    half_open_max_calls: int = 3       # Test calls in half-open
    
class CircuitBreaker:
    """Thread-safe circuit breaker implementation"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitOpenError("Circuit breaker is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError("Half-open call limit reached")
                self.half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
```

## Step-by-Step Implementation Guide

Let's build a circuit breaker from scratch to understand how it works!

### Step 1: Basic Structure

First, let's create a simple circuit breaker class:

```python
import time
import asyncio
from enum import Enum
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class SimpleCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        """
        Args:
            failure_threshold: How many failures before opening circuit
            timeout: How long to wait before trying again (seconds)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        
        # Start in CLOSED state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        
    def call(self, func: Callable) -> Any:
        """Wrap a function call with circuit breaker logic"""
        # We'll implement this next!
        pass
```

### Step 2: Implementing State Checks

Now let's add the logic to check if we should allow a request:

```python
def should_allow_request(self) -> bool:
    """Check if we should allow the request based on current state"""
    
    if self.state == CircuitState.CLOSED:
        # Circuit is closed, allow all requests
        return True
        
    elif self.state == CircuitState.OPEN:
        # Check if enough time has passed to try again
        if self.last_failure_time and \
           time.time() - self.last_failure_time > self.timeout:
            # Move to HALF_OPEN state to test
            self.state = CircuitState.HALF_OPEN
            print("Circuit breaker moving to HALF_OPEN state")
            return True
        else:
            # Still in timeout period
            return False
            
    elif self.state == CircuitState.HALF_OPEN:
        # In test mode, allow the request
        return True
```

### Step 3: Handling Success and Failure

Add methods to handle what happens when calls succeed or fail:

```python
def on_success(self):
    """Called when a request succeeds"""
    if self.state == CircuitState.HALF_OPEN:
        # Test succeeded, close the circuit
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        print("Circuit breaker is now CLOSED (recovered)")
    elif self.state == CircuitState.CLOSED:
        # Reset failure count on success
        self.failure_count = 0

def on_failure(self):
    """Called when a request fails"""
    self.failure_count += 1
    self.last_failure_time = time.time()
    
    if self.state == CircuitState.HALF_OPEN:
        # Test failed, reopen the circuit
        self.state = CircuitState.OPEN
        print("Circuit breaker reopened due to test failure")
    elif self.state == CircuitState.CLOSED:
        # Check if we've hit the failure threshold
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"Circuit breaker OPENED after {self.failure_count} failures")
```

### Step 4: Implementing the Call Method

Now let's put it all together:

```python
def call(self, func: Callable, *args, **kwargs) -> Any:
    """Execute function with circuit breaker protection"""
    
    # Check if we should allow the request
    if not self.should_allow_request():
        raise Exception("Circuit breaker is OPEN - request blocked")
    
    try:
        # Try to execute the function
        result = func(*args, **kwargs)
        self.on_success()
        return result
    except Exception as e:
        self.on_failure()
        raise
```

### Step 5: Making it Async

For modern Python applications, we need async support:

```python
class AsyncCircuitBreaker(SimpleCircuitBreaker):
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        super().__init__(failure_threshold, timeout)
        # Add a lock for thread safety
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""
        
        # Thread-safe state check
        async with self._lock:
            if not self.should_allow_request():
                raise Exception("Circuit breaker is OPEN - request blocked")
        
        try:
            # Execute the async function
            result = await func(*args, **kwargs)
            
            async with self._lock:
                self.on_success()
            
            return result
        except Exception as e:
            async with self._lock:
                self.on_failure()
            raise
```

### Step 6: Complete Working Example

Here's a full example showing how to use the circuit breaker:

```python
import aiohttp
import asyncio
from datetime import datetime

# Create a circuit breaker instance
circuit_breaker = AsyncCircuitBreaker(
    failure_threshold=3,  # Open after 3 failures
    timeout=30.0         # Try again after 30 seconds
)

async def call_external_api(user_id: int):
    """Simulate calling an external API"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.example.com/users/{user_id}",
            timeout=aiohttp.ClientTimeout(total=5)
        ) as response:
            return await response.json()

async def get_user_with_circuit_breaker(user_id: int):
    """Get user data with circuit breaker protection"""
    try:
        # Wrap the API call with circuit breaker
        result = await circuit_breaker.call(call_external_api, user_id)
        return result
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        # Return fallback data or handle gracefully
        return {"id": user_id, "name": "Unknown", "cached": True}

# Example usage
async def main():
    # Simulate multiple requests
    for i in range(10):
        print(f"\n--- Request {i+1} ---")
        user_data = await get_user_with_circuit_breaker(123)
        print(f"Got user data: {user_data}")
        await asyncio.sleep(5)  # Wait between requests

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 7: Adding Configuration

Make your circuit breaker configurable:

```python
from dataclasses import dataclass

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5          # Failures before opening
    timeout: float = 60.0              # Seconds to stay open
    half_open_max_calls: int = 3       # Test calls in half-open
    
    # Advanced configuration
    success_threshold: int = 1         # Successes needed to close
    excluded_exceptions: tuple = ()    # Exceptions that don't count as failures
    
class ConfigurableCircuitBreaker(AsyncCircuitBreaker):
    def __init__(self, config: CircuitBreakerConfig):
        super().__init__(config.failure_threshold, config.timeout)
        self.config = config
        self.half_open_calls = 0
        self.success_count = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Enhanced call with configuration support"""
        
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self.should_allow_request():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise Exception("Half-open call limit reached")
                self.half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.config.success_threshold:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                        self.success_count = 0
                        print("Circuit breaker closed after successful tests")
                else:
                    self.on_success()
            
            return result
            
        except Exception as e:
            # Check if this exception should trigger the circuit breaker
            if not isinstance(e, self.config.excluded_exceptions):
                async with self._lock:
                    self.on_failure()
            raise
```

### Step 8: Integration with Your Application

Here's how to integrate circuit breakers into a real application:

```python
# circuit_breakers.py
from typing import Dict

class CircuitBreakerRegistry:
    """Manage circuit breakers for different services"""
    
    def __init__(self):
        self._breakers: Dict[str, ConfigurableCircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
    
    def get_breaker(self, service_name: str) -> ConfigurableCircuitBreaker:
        """Get or create a circuit breaker for a service"""
        if service_name not in self._breakers:
            # Create service-specific configuration
            config = self._get_config_for_service(service_name)
            self._breakers[service_name] = ConfigurableCircuitBreaker(config)
        
        return self._breakers[service_name]
    
    def _get_config_for_service(self, service_name: str) -> CircuitBreakerConfig:
        """Get configuration for specific service"""
        # You can load from config file or environment
        configs = {
            "payment-api": CircuitBreakerConfig(
                failure_threshold=3,
                timeout=30,
                half_open_max_calls=2
            ),
            "user-service": CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60,
                half_open_max_calls=3
            ),
            "email-service": CircuitBreakerConfig(
                failure_threshold=10,  # Less critical, allow more failures
                timeout=120,
                half_open_max_calls=5
            )
        }
        return configs.get(service_name, self._default_config)

# Usage in your application
registry = CircuitBreakerRegistry()

async def call_payment_api(payment_data):
    breaker = registry.get_breaker("payment-api")
    
    async def make_payment():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://payment-api.example.com/charge",
                json=payment_data
            ) as response:
                return await response.json()
    
    return await breaker.call(make_payment)
```

### State Transitions

**CLOSED → OPEN**
```python
async def _on_failure(self):
    """Handle failure in circuit breaker"""
    async with self._lock:
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
```

**OPEN → HALF_OPEN**
```python
def _should_attempt_reset(self) -> bool:
    """Check if enough time has passed to test recovery"""
    return (
        self.last_failure_time and
        time.time() - self.last_failure_time > self.config.timeout
    )
```

**HALF_OPEN → CLOSED/OPEN**
```python
async def _on_success(self):
    """Handle success - potentially close circuit"""
    async with self._lock:
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful test")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
```

## Retry Logic

### Exponential Backoff with Jitter

```python
@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0            # Initial delay in seconds
    max_delay: float = 30.0            # Maximum delay
    exponential_base: float = 2.0      # Backoff multiplier
    jitter: bool = True                # Add randomization

class RetryStrategy:
    """Implements intelligent retry logic"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        # Exponential backoff
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            delay *= (0.5 + random.random())
        
        return delay
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    raise
                
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Retry attempt {attempt + 1}/{self.config.max_attempts} "
                    f"after {delay:.2f}s delay. Error: {e}"
                )
                await asyncio.sleep(delay)
        
        raise last_exception
```

### Selective Retry

Not all errors should trigger retries:

```python
def _should_retry(self, exception: Exception, attempt: int) -> bool:
    """Determine if error is retryable"""
    # Don't retry on final attempt
    if attempt >= self.config.max_attempts - 1:
        return False
    
    # Retry on network errors
    if isinstance(exception, (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ConnectionError
    )):
        return True
    
    # Don't retry on client errors (4xx)
    if isinstance(exception, aiohttp.ClientResponseError):
        if 400 <= exception.status < 500:
            return False
    
    # Retry on server errors (5xx)
    if hasattr(exception, 'status') and exception.status >= 500:
        return True
    
    # Default: retry
    return True
```

## Resilient Call Pattern

### Combining Circuit Breaker and Retry

```python
async def resilient_call(
    func: Callable,
    *args,
    circuit_breaker: Optional[CircuitBreaker] = None,
    retry_config: Optional[RetryConfig] = None,
    timeout: Optional[float] = None,
    **kwargs
) -> Any:
    """
    Execute function with full resilience stack:
    1. Circuit breaker check
    2. Timeout enforcement
    3. Retry on failure
    4. Graceful degradation
    """
    
    # Default configurations
    if circuit_breaker is None:
        circuit_breaker = get_default_circuit_breaker()
    if retry_config is None:
        retry_config = RetryConfig()
    
    retry_strategy = RetryStrategy(retry_config)
    
    async def wrapped_call():
        # Apply timeout if specified
        if timeout:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout
            )
        else:
            return await func(*args, **kwargs)
    
    # Execute with circuit breaker
    try:
        return await circuit_breaker.call(
            retry_strategy.execute_with_retry,
            wrapped_call
        )
    except CircuitOpenError:
        # Circuit is open - fail fast
        logger.error(f"Circuit breaker open for {func.__name__}")
        raise
    except Exception as e:
        logger.error(f"Resilient call failed for {func.__name__}: {e}")
        raise
```

## Connection Pool Resilience

### Pool Configuration

```python
class ResilientConnectionPool:
    """Connection pool with resilience features"""
    
    def __init__(self, config: PoolConfig):
        self.config = config
        self.pools: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()
    
    async def get_session(
        self,
        base_url: str,
        timeout: int = 30
    ) -> aiohttp.ClientSession:
        """Get or create session with proper configuration"""
        
        # Include timeout in pool key to prevent mismatches
        pool_key = f"{base_url}_timeout_{timeout}"
        
        async with self._lock:
            if pool_key not in self.pools:
                connector = aiohttp.TCPConnector(
                    limit=self.config.total_connections,
                    limit_per_host=self.config.per_host_connections,
                    ttl_dns_cache=self.config.dns_cache_ttl,
                    keepalive_timeout=self.config.keepalive_timeout,
                    enable_cleanup_closed=True,
                    force_close=True
                )
                
                timeout_config = aiohttp.ClientTimeout(
                    total=timeout,
                    connect=min(timeout / 3, 10),  # Connection timeout
                    sock_read=timeout
                )
                
                self.pools[pool_key] = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout_config
                )
            
            return self.pools[pool_key]
```

### Connection Recovery

```python
async def _ensure_pool_health(self):
    """Monitor and recover unhealthy connections"""
    while True:
        try:
            async with self._lock:
                for pool_key, session in list(self.pools.items()):
                    if session.closed:
                        # Remove closed sessions
                        del self.pools[pool_key]
                        logger.info(f"Removed closed session: {pool_key}")
                    elif hasattr(session.connector, 'closed_connections'):
                        # Clean up closed connections
                        closed = session.connector.closed_connections
                        if closed > self.config.cleanup_threshold:
                            await session.connector.close()
                            del self.pools[pool_key]
                            logger.info(
                                f"Recycled session with {closed} "
                                f"closed connections: {pool_key}"
                            )
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Pool health check error: {e}")
            await asyncio.sleep(60)
```

## Timeout Management

### Hierarchical Timeouts

```python
class TimeoutManager:
    """Manage timeouts at different levels"""
    
    def __init__(self):
        self.default_timeouts = {
            "health_check": 10,
            "standard_request": 30,
            "long_operation": 120,
            "batch_operation": 300
        }
    
    def get_timeout(
        self,
        operation_type: str,
        custom_timeout: Optional[float] = None
    ) -> float:
        """Get appropriate timeout for operation"""
        
        if custom_timeout:
            return custom_timeout
        
        return self.default_timeouts.get(
            operation_type,
            self.default_timeouts["standard_request"]
        )
    
    @contextmanager
    async def timeout_context(
        self,
        operation: str,
        timeout: Optional[float] = None
    ):
        """Context manager for operation timeouts"""
        
        actual_timeout = self.get_timeout(operation, timeout)
        
        try:
            async with asyncio.timeout(actual_timeout):
                yield
        except asyncio.TimeoutError:
            logger.error(
                f"Operation '{operation}' timed out after {actual_timeout}s"
            )
            raise
```

## Graceful Degradation

### Fallback Strategies

```python
class DegradationStrategy:
    """Implement graceful degradation patterns"""
    
    async def with_fallback(
        self,
        primary_func: Callable,
        fallback_func: Callable,
        *args,
        **kwargs
    ):
        """Try primary function, fall back on failure"""
        try:
            return await primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"Primary function failed, using fallback: {e}"
            )
            return await fallback_func(*args, **kwargs)
    
    async def with_cache_fallback(
        self,
        func: Callable,
        cache_key: str,
        *args,
        **kwargs
    ):
        """Use cached result if fresh call fails"""
        try:
            result = await func(*args, **kwargs)
            # Update cache with fresh result
            await self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"Using cached result due to error: {e}")
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
            raise
    
    async def with_partial_result(
        self,
        tasks: List[Callable],
        min_success_ratio: float = 0.5
    ):
        """Accept partial results if enough succeed"""
        results = []
        errors = []
        
        # Execute all tasks concurrently
        futures = [asyncio.create_task(task()) for task in tasks]
        
        for future in asyncio.as_completed(futures):
            try:
                result = await future
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        success_ratio = len(results) / len(tasks)
        
        if success_ratio >= min_success_ratio:
            logger.warning(
                f"Partial success: {len(results)}/{len(tasks)} succeeded"
            )
            return results
        else:
            raise Exception(
                f"Too many failures: {len(errors)}/{len(tasks)} failed"
            )
```

## Health Checks

### Agent Health Monitoring

```python
class HealthChecker:
    """Monitor agent health with circuit breaker integration"""
    
    def __init__(self):
        self.health_status = {}
        self.circuit_breakers = {}
    
    async def check_agent_health(
        self,
        agent_name: str,
        agent_url: str
    ) -> HealthStatus:
        """Check agent health with resilience"""
        
        # Get or create circuit breaker for agent
        if agent_name not in self.circuit_breakers:
            self.circuit_breakers[agent_name] = CircuitBreaker(
                CircuitBreakerConfig(
                    failure_threshold=3,  # More sensitive for health
                    timeout=30
                )
            )
        
        circuit_breaker = self.circuit_breakers[agent_name]
        
        try:
            # Health check with shorter timeout
            async with A2AClient(timeout=10) as client:
                await circuit_breaker.call(
                    client.get_agent_card,
                    f"{agent_url}/a2a"
                )
            
            self.health_status[agent_name] = HealthStatus.HEALTHY
            return HealthStatus.HEALTHY
            
        except CircuitOpenError:
            self.health_status[agent_name] = HealthStatus.CIRCUIT_OPEN
            return HealthStatus.CIRCUIT_OPEN
            
        except Exception as e:
            logger.error(f"Health check failed for {agent_name}: {e}")
            self.health_status[agent_name] = HealthStatus.UNHEALTHY
            return HealthStatus.UNHEALTHY
```

## Monitoring and Alerting

Understanding what's happening with your circuit breakers in production is crucial. Here's how to monitor them effectively.

### Why Monitoring Matters

Without monitoring, you're flying blind:
- You won't know when services are failing
- You can't see patterns in failures
- You'll miss opportunities to prevent outages
- Your users will tell you about problems (bad!)

### Essential Metrics to Track

Here are the key metrics every circuit breaker should expose:

```python
class CircuitBreakerMetrics:
    """Track circuit breaker statistics"""
    
    def __init__(self):
        self.state_changes = []
        self.call_results = defaultdict(int)
        self.failure_reasons = defaultdict(int)
    
    def record_state_change(
        self,
        circuit_name: str,
        old_state: CircuitState,
        new_state: CircuitState
    ):
        """Record state transitions"""
        self.state_changes.append({
            "timestamp": datetime.now(),
            "circuit": circuit_name,
            "old_state": old_state.value,
            "new_state": new_state.value
        })
    
    def record_call_result(
        self,
        circuit_name: str,
        success: bool,
        duration_ms: float,
        error: Optional[Exception] = None
    ):
        """Record call outcomes"""
        result_key = f"{circuit_name}_{'success' if success else 'failure'}"
        self.call_results[result_key] += 1
        
        if error:
            error_key = f"{circuit_name}_{type(error).__name__}"
            self.failure_reasons[error_key] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            "state_changes": len(self.state_changes),
            "recent_changes": self.state_changes[-10:],
            "call_results": dict(self.call_results),
            "failure_reasons": dict(self.failure_reasons),
            "circuit_states": {
                name: cb.state.value
                for name, cb in circuit_breakers.items()
            }
        }
```

### Building a Monitoring Dashboard

Here's a practical example of building a monitoring dashboard:

```python
from datetime import datetime, timedelta
import json
from typing import Dict, List

class CircuitBreakerMonitor:
    """Complete monitoring solution for circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, MonitoredCircuitBreaker] = {}
        self.alert_thresholds = {
            "open_duration_minutes": 5,
            "failure_rate_percent": 50,
            "consecutive_opens": 3
        }
    
    def add_breaker(self, name: str, breaker: MonitoredCircuitBreaker):
        """Register a circuit breaker for monitoring"""
        self.breakers[name] = breaker
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for a monitoring dashboard"""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": self._get_summary(),
            "breakers": self._get_breaker_details(),
            "alerts": self._check_alerts(),
            "graphs": self._get_graph_data()
        }
    
    def _get_summary(self) -> Dict[str, int]:
        """Quick overview of system health"""
        states = [b.state for b in self.breakers.values()]
        return {
            "total_breakers": len(self.breakers),
            "closed": sum(1 for s in states if s == "closed"),
            "open": sum(1 for s in states if s == "open"),
            "half_open": sum(1 for s in states if s == "half_open")
        }
    
    def _get_breaker_details(self) -> List[Dict]:
        """Detailed info for each breaker"""
        details = []
        for name, breaker in self.breakers.items():
            details.append({
                "name": name,
                "state": breaker.state,
                "failure_count": breaker.failure_count,
                "success_rate": self._calculate_success_rate(breaker),
                "last_state_change": self._get_last_state_change(breaker),
                "health_score": self._calculate_health_score(breaker)
            })
        return details
    
    def _calculate_success_rate(self, breaker: MonitoredCircuitBreaker) -> float:
        """Calculate recent success rate"""
        total = breaker.metrics["success_count"] + breaker.metrics["failure_count"]
        if total == 0:
            return 100.0
        return (breaker.metrics["success_count"] / total) * 100
    
    def _calculate_health_score(self, breaker: MonitoredCircuitBreaker) -> int:
        """Score from 0-100 indicating breaker health"""
        score = 100
        
        # Deduct points for being open
        if breaker.state == "open":
            score -= 50
        elif breaker.state == "half_open":
            score -= 25
        
        # Deduct for high failure rate
        success_rate = self._calculate_success_rate(breaker)
        if success_rate < 50:
            score -= 25
        elif success_rate < 80:
            score -= 10
        
        # Deduct for recent state changes
        recent_changes = len([
            c for c in breaker.state_changes[-10:]
            if c["new_state"] == "open"
        ])
        score -= (recent_changes * 5)
        
        return max(0, score)
```

### Setting Up Alerts

```python
class AlertManager:
    """Manage alerts for circuit breaker issues"""
    
    def __init__(self, notification_channels: List[str]):
        self.channels = notification_channels
        self.sent_alerts = {}  # Prevent duplicate alerts
    
    async def check_and_alert(self, monitor: CircuitBreakerMonitor):
        """Check conditions and send alerts"""
        alerts = []
        
        for name, breaker in monitor.breakers.items():
            # Alert: Circuit open too long
            if breaker.state == "open":
                open_duration = self._get_open_duration(breaker)
                if open_duration > timedelta(minutes=5):
                    alerts.append({
                        "severity": "HIGH",
                        "breaker": name,
                        "message": f"Circuit breaker {name} has been open for {open_duration}",
                        "action": "Check service health and logs"
                    })
            
            # Alert: Flapping circuit
            if self._is_flapping(breaker):
                alerts.append({
                    "severity": "MEDIUM",
                    "breaker": name,
                    "message": f"Circuit breaker {name} is flapping between states",
                    "action": "Service may be intermittently failing"
                })
            
            # Alert: High failure rate
            success_rate = monitor._calculate_success_rate(breaker)
            if success_rate < 50 and breaker.state == "closed":
                alerts.append({
                    "severity": "WARNING",
                    "breaker": name,
                    "message": f"High failure rate ({100-success_rate:.1f}%) but circuit still closed",
                    "action": "Monitor closely, may open soon"
                })
        
        # Send unique alerts
        for alert in alerts:
            alert_key = f"{alert['breaker']}_{alert['message'][:20]}"
            if not self._already_sent(alert_key):
                await self._send_alert(alert)
                self.sent_alerts[alert_key] = datetime.now()
    
    def _is_flapping(self, breaker: MonitoredCircuitBreaker) -> bool:
        """Detect if circuit is changing states too frequently"""
        recent_changes = breaker.state_changes[-10:]
        if len(recent_changes) < 5:
            return False
        
        # Check if states changed more than 5 times in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_count = sum(
            1 for c in recent_changes
            if c["timestamp"] > one_hour_ago
        )
        return recent_count > 5
    
    async def _send_alert(self, alert: Dict):
        """Send alert to configured channels"""
        for channel in self.channels:
            if channel == "slack":
                await self._send_slack_alert(alert)
            elif channel == "email":
                await self._send_email_alert(alert)
            elif channel == "pagerduty":
                await self._send_pagerduty_alert(alert)
            
            # Log all alerts
            logger.warning(f"ALERT: {alert}")
```

### Practical Monitoring Setup

Here's how to set up monitoring in your application:

```python
# monitoring_setup.py
import asyncio
from prometheus_client import Counter, Gauge, Histogram

# Prometheus metrics (popular monitoring tool)
circuit_state_gauge = Gauge(
    'circuit_breaker_state',
    'Current state of circuit breaker (0=closed, 1=half-open, 2=open)',
    ['service_name']
)

circuit_failure_counter = Counter(
    'circuit_breaker_failures_total',
    'Total number of failures',
    ['service_name']
)

circuit_success_counter = Counter(
    'circuit_breaker_successes_total',
    'Total number of successes',
    ['service_name']
)

circuit_call_duration = Histogram(
    'circuit_breaker_call_duration_seconds',
    'Duration of calls through circuit breaker',
    ['service_name', 'result']
)

class InstrumentedCircuitBreaker(MonitoredCircuitBreaker):
    """Circuit breaker with metrics instrumentation"""
    
    async def call(self, func, *args, **kwargs):
        start_time = time.time()
        
        try:
            result = await super().call(func, *args, **kwargs)
            
            # Record success metrics
            circuit_success_counter.labels(service_name=self.name).inc()
            circuit_call_duration.labels(
                service_name=self.name,
                result="success"
            ).observe(time.time() - start_time)
            
            return result
            
        except Exception as e:
            # Record failure metrics
            circuit_failure_counter.labels(service_name=self.name).inc()
            circuit_call_duration.labels(
                service_name=self.name,
                result="failure"
            ).observe(time.time() - start_time)
            raise
        
        finally:
            # Update state gauge
            state_value = {
                "closed": 0,
                "half_open": 1,
                "open": 2
            }[self.state]
            circuit_state_gauge.labels(service_name=self.name).set(state_value)

# Background monitoring task
async def monitoring_loop():
    """Run monitoring checks every 30 seconds"""
    monitor = CircuitBreakerMonitor()
    alert_manager = AlertManager(["slack", "email"])
    
    while True:
        try:
            # Collect metrics
            dashboard_data = monitor.get_dashboard_data()
            
            # Check for alerts
            await alert_manager.check_and_alert(monitor)
            
            # Log summary
            logger.info(f"Circuit breaker summary: {dashboard_data['summary']}")
            
            # You could also:
            # - Send to time-series database
            # - Update a web dashboard
            # - Export to monitoring service
            
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            await asyncio.sleep(60)
```

### Creating Visual Dashboards

```python
# Simple terminal dashboard
def print_circuit_breaker_status(monitor: CircuitBreakerMonitor):
    """Print a simple status dashboard to terminal"""
    
    print("\n" + "="*50)
    print("CIRCUIT BREAKER DASHBOARD")
    print("="*50)
    
    data = monitor.get_dashboard_data()
    
    # Summary
    summary = data["summary"]
    print(f"\nTotal: {summary['total_breakers']} | "
          f"✅ Closed: {summary['closed']} | "
          f"🔴 Open: {summary['open']} | "
          f"🟡 Half-Open: {summary['half_open']}")
    
    # Individual breakers
    print("\nBreaker Status:")
    print("-"*50)
    
    for breaker in data["breakers"]:
        # Use emojis for visual status
        status_emoji = {
            "closed": "✅",
            "open": "🔴",
            "half_open": "🟡"
        }[breaker["state"]]
        
        health_bar = "█" * (breaker["health_score"] // 10)
        health_bar += "░" * (10 - len(health_bar))
        
        print(f"{status_emoji} {breaker['name']:20} | "
              f"Health: [{health_bar}] {breaker['health_score']}% | "
              f"Success: {breaker['success_rate']:.1f}%")
    
    # Alerts
    if data["alerts"]:
        print("\n⚠️  ACTIVE ALERTS:")
        for alert in data["alerts"]:
            print(f"  - [{alert['severity']}] {alert['message']}")
    
    print("="*50)

# Web dashboard endpoint
async def dashboard_endpoint(request):
    """API endpoint for dashboard data"""
    monitor = request.app["circuit_monitor"]
    data = monitor.get_dashboard_data()
    
    # Add HTML visualization
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Circuit Breaker Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            .open {{ background-color: #ff4444; }}
            .closed {{ background-color: #44ff44; }}
            .half-open {{ background-color: #ffff44; }}
        </style>
    </head>
    <body>
        <h1>Circuit Breaker Status</h1>
        <table>
            <tr>
                <th>Service</th>
                <th>State</th>
                <th>Health Score</th>
                <th>Success Rate</th>
            </tr>
            {"".join(f'''
            <tr class="{b['state']}">
                <td>{b['name']}</td>
                <td>{b['state']}</td>
                <td>{b['health_score']}%</td>
                <td>{b['success_rate']:.1f}%</td>
            </tr>
            ''' for b in data['breakers'])}
        </table>
    </body>
    </html>
    """
    
    return web.Response(text=html, content_type='text/html')
```

### Alert Examples

Here are examples of good alerts to set up:

```yaml
# alerts.yaml - Alert configuration
alerts:
  - name: circuit_breaker_open_too_long
    condition: state == "open" for 5 minutes
    severity: high
    notification:
      - slack: "#oncall-channel"
      - pagerduty: "escalation-policy-1"
    message: "Circuit breaker {{ name }} has been open for {{ duration }}"
    
  - name: circuit_breaker_flapping
    condition: state changes > 5 in 1 hour
    severity: medium
    notification:
      - slack: "#engineering"
      - email: "team@company.com"
    message: "Circuit breaker {{ name }} is flapping"
    
  - name: high_failure_rate
    condition: failure_rate > 50% and state == "closed"
    severity: warning
    notification:
      - slack: "#engineering"
    message: "High failure rate for {{ name }} but circuit still closed"
```

### Monitoring Best Practices

1. **Start Simple**: Begin with basic metrics (state, success/failure counts)
2. **Use Existing Tools**: Integrate with Prometheus, Grafana, DataDog, etc.
3. **Set Meaningful Alerts**: Avoid alert fatigue with smart thresholds
4. **Track Trends**: Look for patterns over time, not just current state
5. **Include Context**: Add service name, timestamps, and error details
6. **Test Your Monitoring**: Verify alerts work before you need them
7. **Document Runbooks**: What to do when each alert fires

### Troubleshooting with Metrics

When investigating issues, ask:
- When did the circuit first open?
- How many times has it opened today?
- What's the failure pattern? (sudden spike vs gradual increase)
- Are other services affected?
- What errors are we seeing?

```python
# Debugging helper
def analyze_circuit_breaker(breaker: MonitoredCircuitBreaker):
    """Analyze circuit breaker behavior for troubleshooting"""
    
    print(f"\nAnalyzing Circuit Breaker: {breaker.name}")
    print("-" * 40)
    
    # Current state
    print(f"Current State: {breaker.state}")
    print(f"Failure Count: {breaker.failure_count}")
    
    # Recent history
    print("\nRecent State Changes:")
    for change in breaker.state_changes[-5:]:
        print(f"  {change['timestamp']}: {change['old_state']} → {change['new_state']}")
    
    # Failure analysis
    total_calls = breaker.metrics["success_count"] + breaker.metrics["failure_count"]
    if total_calls > 0:
        success_rate = (breaker.metrics["success_count"] / total_calls) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        print(f"Total Calls: {total_calls}")
    
    # Recommendations
    print("\nRecommendations:")
    if breaker.state == "open" and success_rate < 10:
        print("  - Service appears to be down, investigate immediately")
    elif breaker.state == "closed" and success_rate < 50:
        print("  - High failure rate, circuit may open soon")
    elif len(breaker.state_changes) > 20:
        print("  - Frequent state changes, possible flapping")
```

### Resilience Dashboard

```python
async def get_resilience_status() -> Dict[str, Any]:
    """Get comprehensive resilience status"""
    
    return {
        "timestamp": datetime.now().isoformat(),
        "circuit_breakers": {
            name: {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "last_failure": cb.last_failure_time,
                "health_score": calculate_health_score(cb),
                "recommendation": get_recommendation(cb)
            }
            for name, cb in circuit_breakers.items()
        },
        "connection_pools": {
            key: {
                "active": len(session.connector._acquired),
                "limit": session.connector.limit,
                "usage_percent": (len(session.connector._acquired) / session.connector.limit) * 100
            }
            for key, session in connection_pools.items()
        },
        "retry_statistics": {
            "total_retries": retry_counter.total(),
            "successful_retries": retry_success_counter.total(),
            "retry_exhausted": retry_exhausted_counter.total(),
            "retry_success_rate": (retry_success_counter.total() / retry_counter.total() * 100) if retry_counter.total() > 0 else 100
        },
        "health_checks": {
            agent: {
                "status": status.value,
                "last_check": last_check_time.get(agent, "Never"),
                "consecutive_failures": consecutive_failures.get(agent, 0)
            }
            for agent, status in health_checker.health_status.items()
        },
        "system_health": calculate_overall_health()
    }
```

## Best Practices

### 1. Circuit Breaker Configuration

- Set appropriate failure thresholds (5-10 for normal operations)
- Use shorter timeouts for health checks (10s)
- Configure half-open test limits (3-5 calls)
- Monitor state changes closely
- Adjust based on service characteristics

### 2. Retry Strategy

- Use exponential backoff to prevent overwhelming services
- Add jitter to avoid thundering herd
- Limit retry attempts (3-5 typically)
- Only retry transient errors
- Log all retry attempts

### 3. Timeout Management

- Set timeouts at multiple levels
- Health checks: 10 seconds
- Standard requests: 30 seconds
- Long operations: 2-5 minutes
- Always handle timeout errors

### 4. Connection Pooling

- Separate pools by timeout values
- Monitor pool health regularly
- Clean up stale connections
- Set appropriate limits
- Use keep-alive for efficiency

## Common Mistakes and How to Avoid Them

As a junior engineer, you'll likely make these mistakes. Here's how to avoid them!

### Mistake #1: Not Using Thread Safety

**The Problem:**
```python
# BAD - Not thread-safe!
class BadCircuitBreaker:
    def __init__(self):
        self.state = "closed"
        self.failure_count = 0
    
    def call(self, func):
        # Multiple threads can modify state simultaneously!
        if self.state == "open":
            raise Exception("Circuit open")
        
        try:
            result = func()
            self.failure_count = 0  # Race condition!
            return result
        except:
            self.failure_count += 1  # Race condition!
            if self.failure_count >= 5:
                self.state = "open"  # Race condition!
            raise
```

**The Solution:**
```python
# GOOD - Thread-safe with locks
import asyncio

class GoodCircuitBreaker:
    def __init__(self):
        self.state = "closed"
        self.failure_count = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func):
        async with self._lock:
            if self.state == "open":
                raise Exception("Circuit open")
        
        try:
            result = await func()
            async with self._lock:
                self.failure_count = 0
            return result
        except:
            async with self._lock:
                self.failure_count += 1
                if self.failure_count >= 5:
                    self.state = "open"
            raise
```

### Mistake #2: Forgetting the Half-Open State

**The Problem:**
```python
# BAD - No half-open state!
class NoHalfOpenCircuitBreaker:
    def call(self, func):
        if self.state == "open":
            if time.time() - self.last_failure > self.timeout:
                # Immediately goes back to closed - dangerous!
                self.state = "closed"
                self.failure_count = 0
```

**Why It's Bad:**
- If the service is still down, you'll immediately get 5 more failures
- The circuit will oscillate between open and closed
- No gradual recovery testing

**The Solution:**
```python
# GOOD - Proper half-open state
class ProperCircuitBreaker:
    def call(self, func):
        if self.state == "open":
            if time.time() - self.last_failure > self.timeout:
                # Test with half-open first
                self.state = "half_open"
                self.test_calls = 0
        
        if self.state == "half_open":
            # Limit test calls
            if self.test_calls >= 3:
                raise Exception("Too many test calls")
            self.test_calls += 1
            
            try:
                result = func()
                # Only close after successful test
                self.state = "closed"
                return result
            except:
                # Go back to open
                self.state = "open"
                raise
```

### Mistake #3: Wrong Timeout Values

**The Problem:**
```python
# BAD - Timeouts are too short or too long
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=2  # Only 2 seconds! Service won't have time to recover
)

# OR

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=3600  # 1 hour! Users will suffer for too long
)
```

**The Solution:**
```python
# GOOD - Reasonable timeouts based on service type
# For user-facing services
user_service_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=30  # 30 seconds - quick recovery attempt
)

# For background jobs
background_job_breaker = CircuitBreaker(
    failure_threshold=10,
    timeout=300  # 5 minutes - can wait longer
)

# For critical payment services
payment_breaker = CircuitBreaker(
    failure_threshold=3,  # More sensitive
    timeout=60  # 1 minute - balanced approach
)
```

### Mistake #4: Not Handling Circuit Open Exceptions

**The Problem:**
```python
# BAD - Not handling circuit breaker exceptions
async def get_user_data(user_id):
    breaker = get_circuit_breaker("user-service")
    # This will throw CircuitOpenError and crash!
    return await breaker.call(fetch_user, user_id)
```

**The Solution:**
```python
# GOOD - Proper exception handling with fallback
async def get_user_data(user_id):
    breaker = get_circuit_breaker("user-service")
    
    try:
        return await breaker.call(fetch_user, user_id)
    except CircuitOpenError:
        # Circuit is open - use fallback
        logger.warning(f"Circuit open for user service, using cache")
        return await get_user_from_cache(user_id)
    except Exception as e:
        # Other errors - maybe return default
        logger.error(f"Failed to get user {user_id}: {e}")
        return {"id": user_id, "name": "Unknown", "error": True}
```

### Mistake #5: Sharing Circuit Breakers Incorrectly

**The Problem:**
```python
# BAD - One circuit breaker for everything!
global_breaker = CircuitBreaker()

async def call_user_service():
    return await global_breaker.call(user_api_call)

async def call_payment_service():
    return await global_breaker.call(payment_api_call)

async def call_email_service():
    return await global_breaker.call(email_api_call)

# If email service fails, it breaks user and payment too!
```

**The Solution:**
```python
# GOOD - Separate circuit breakers per service
class ServiceBreakers:
    def __init__(self):
        self.breakers = {
            "user-service": CircuitBreaker(failure_threshold=5),
            "payment-service": CircuitBreaker(failure_threshold=3),
            "email-service": CircuitBreaker(failure_threshold=10)
        }
    
    def get_breaker(self, service_name: str):
        return self.breakers[service_name]

# Usage
breakers = ServiceBreakers()

async def call_user_service():
    breaker = breakers.get_breaker("user-service")
    return await breaker.call(user_api_call)

async def call_payment_service():
    breaker = breakers.get_breaker("payment-service")
    return await breaker.call(payment_api_call)
```

### Mistake #6: Not Monitoring Circuit Breaker State

**The Problem:**
```python
# BAD - No visibility into circuit breaker state
circuit_breaker = CircuitBreaker()
# ... use it ...
# How do we know if it's working? When did it last open?
```

**The Solution:**
```python
# GOOD - Add monitoring and metrics
class MonitoredCircuitBreaker(CircuitBreaker):
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.state_changes = []
        self.metrics = {
            "success_count": 0,
            "failure_count": 0,
            "circuit_open_count": 0
        }
    
    def on_state_change(self, old_state, new_state):
        change = {
            "timestamp": datetime.now(),
            "old_state": old_state,
            "new_state": new_state
        }
        self.state_changes.append(change)
        
        # Log for monitoring
        logger.info(
            f"Circuit breaker '{self.name}' changed from "
            f"{old_state} to {new_state}"
        )
        
        # Send metrics to monitoring system
        if new_state == "open":
            self.metrics["circuit_open_count"] += 1
            send_alert(f"Circuit breaker {self.name} is OPEN!")
    
    def get_status(self):
        return {
            "name": self.name,
            "current_state": self.state,
            "failure_count": self.failure_count,
            "metrics": self.metrics,
            "recent_changes": self.state_changes[-5:]
        }
```

### Mistake #7: Wrong Exception Handling

**The Problem:**
```python
# BAD - Counting all exceptions as failures
class BadCircuitBreaker:
    async def call(self, func):
        try:
            return await func()
        except Exception:
            # This counts EVERY exception!
            # Including programming errors, validation errors, etc.
            self.failure_count += 1
            raise
```

**The Solution:**
```python
# GOOD - Only count network/service errors
class SmartCircuitBreaker:
    def __init__(self):
        # Define which exceptions indicate service issues
        self.failure_exceptions = (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ConnectionError,
            # 5xx server errors
            aiohttp.ClientResponseError
        )
        
        # These exceptions don't trigger the circuit breaker
        self.ignore_exceptions = (
            ValueError,  # Bad input
            KeyError,    # Programming error
            ValidationError  # Business logic error
        )
    
    async def call(self, func):
        try:
            return await func()
        except self.ignore_exceptions:
            # Don't count these as circuit breaker failures
            raise
        except self.failure_exceptions as e:
            # These indicate service problems
            if isinstance(e, aiohttp.ClientResponseError):
                # Only count 5xx errors, not 4xx
                if e.status >= 500:
                    self.failure_count += 1
            else:
                self.failure_count += 1
            raise
        except Exception:
            # Unknown exception - log but don't count
            logger.warning(f"Unexpected exception: {type(e)}")
            raise
```

### Mistake #8: Not Testing Circuit Breakers

**The Problem:**
```python
# BAD - No tests for circuit breaker behavior
# How do you know it works in production?
```

**The Solution:**
```python
# GOOD - Comprehensive circuit breaker tests
import pytest
from unittest.mock import AsyncMock

async def test_circuit_breaker_opens_after_failures():
    """Test that circuit opens after threshold failures"""
    breaker = CircuitBreaker(failure_threshold=3)
    failing_func = AsyncMock(side_effect=Exception("Service down"))
    
    # First 3 calls should attempt the function
    for i in range(3):
        with pytest.raises(Exception):
            await breaker.call(failing_func)
    
    # Circuit should now be open
    assert breaker.state == "open"
    
    # Next call should fail fast without calling function
    with pytest.raises(CircuitOpenError):
        await breaker.call(failing_func)
    
    # Function should only be called 3 times, not 4
    assert failing_func.call_count == 3

async def test_circuit_breaker_recovers():
    """Test that circuit breaker recovers properly"""
    breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)
    failing_func = AsyncMock(side_effect=Exception("Service down"))
    success_func = AsyncMock(return_value="Success!")
    
    # Open the circuit
    for i in range(2):
        with pytest.raises(Exception):
            await breaker.call(failing_func)
    
    assert breaker.state == "open"
    
    # Wait for timeout
    await asyncio.sleep(0.2)
    
    # Should move to half-open and succeed
    result = await breaker.call(success_func)
    assert result == "Success!"
    assert breaker.state == "closed"

async def test_circuit_breaker_half_open_failure():
    """Test that circuit reopens if half-open test fails"""
    breaker = CircuitBreaker(failure_threshold=1, timeout=0.1)
    failing_func = AsyncMock(side_effect=Exception("Still down"))
    
    # Open the circuit
    with pytest.raises(Exception):
        await breaker.call(failing_func)
    
    # Wait for timeout
    await asyncio.sleep(0.2)
    
    # Half-open test should fail and reopen circuit
    with pytest.raises(Exception):
        await breaker.call(failing_func)
    
    assert breaker.state == "open"
    
    # Should fail fast again
    with pytest.raises(CircuitOpenError):
        await breaker.call(failing_func)
```

### Quick Reference: Do's and Don'ts

**DO:**
- ✅ Use separate circuit breakers for each external service
- ✅ Make circuit breakers thread-safe with locks
- ✅ Implement all three states (closed, open, half-open)
- ✅ Monitor circuit breaker state changes
- ✅ Handle CircuitOpenError exceptions gracefully
- ✅ Test circuit breaker behavior thoroughly
- ✅ Use reasonable timeout values (30s-5min typically)
- ✅ Only count relevant failures (network/timeout errors)

**DON'T:**
- ❌ Share one circuit breaker across multiple services
- ❌ Forget about thread safety in concurrent environments
- ❌ Skip the half-open state
- ❌ Use extremely short or long timeout values
- ❌ Let CircuitOpenError crash your application
- ❌ Count validation errors as circuit breaker failures
- ❌ Deploy without monitoring circuit breaker metrics
- ❌ Assume circuit breakers work without testing

## Testing Resilience

### Chaos Testing

```python
class ChaosMonkey:
    """Inject failures for testing"""
    
    async def inject_network_failure(self, probability: float = 0.1):
        """Randomly fail network calls"""
        if random.random() < probability:
            raise aiohttp.ClientError("Chaos monkey network failure")
    
    async def inject_timeout(self, probability: float = 0.1):
        """Randomly cause timeouts"""
        if random.random() < probability:
            await asyncio.sleep(120)  # Force timeout
    
    async def inject_circuit_breaker_trip(self, circuit_breaker: CircuitBreaker):
        """Force circuit breaker to open"""
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.failure_count += 1
        circuit_breaker.state = CircuitState.OPEN
```

### Resilience Tests

```python
async def test_circuit_breaker_opens_on_failures():
    """Test circuit breaker opens after threshold"""
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
    
    # Fail 3 times
    for i in range(3):
        try:
            await cb.call(failing_function)
        except:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    # Next call should fail fast
    with pytest.raises(CircuitOpenError):
        await cb.call(normal_function)

async def test_retry_with_backoff():
    """Test exponential backoff calculation"""
    retry = RetryStrategy(RetryConfig(base_delay=1.0))
    
    delays = [retry.calculate_delay(i) for i in range(5)]
    
    # Verify exponential growth
    assert delays[0] < delays[1] < delays[2]
    assert delays[-1] <= retry.config.max_delay
```

## Troubleshooting

### Common Issues

1. **Circuit Breaker Won't Close**
   - Check timeout configuration
   - Verify service is actually healthy
   - Look for persistent errors
   - Check half-open test results

2. **Too Many Retries**
   - Review retry configuration
   - Check if errors are retryable
   - Monitor retry exhaustion
   - Consider circuit breaker integration

3. **Connection Pool Exhaustion**
   - Increase pool limits
   - Check for connection leaks
   - Monitor pool metrics
   - Enable connection cleanup

4. **Cascading Failures**
   - Verify circuit breakers are configured
   - Check timeout propagation
   - Review service dependencies
   - Implement proper fallbacks

## Practical Examples

Let's look at real-world examples of using circuit breakers in different scenarios.

### Example 1: REST API Client with Circuit Breaker

```python
# api_client.py
import aiohttp
import asyncio
from typing import Dict, Any, Optional

class ResilientAPIClient:
    """API client with built-in circuit breaker"""
    
    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url
        self.service_name = service_name
        
        # Configure circuit breaker for this service
        self.circuit_breaker = ConfigurableCircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                half_open_max_calls=3,
                excluded_exceptions=(ValueError, KeyError)  # Don't trip on these
            )
        )
        
        # Session with connection pooling
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=aiohttp.TCPConnector(limit=20)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict:
        """GET request with circuit breaker"""
        
        async def make_request():
            url = f"{self.base_url}{endpoint}"
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        
        try:
            return await self.circuit_breaker.call(make_request)
        except CircuitOpenError:
            # Circuit is open, use fallback
            logger.warning(f"Circuit open for {self.service_name}, using cache")
            return await self.get_from_cache(endpoint, params)
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                # Don't trip circuit for 404s
                raise ValueError(f"Resource not found: {endpoint}")
            raise
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict:
        """POST request with circuit breaker"""
        
        async def make_request():
            url = f"{self.base_url}{endpoint}"
            async with self.session.post(url, json=data) as response:
                response.raise_for_status()
                return await response.json()
        
        return await self.circuit_breaker.call(make_request)
    
    async def get_from_cache(self, endpoint: str, params: Dict) -> Dict:
        """Fallback to cached data when circuit is open"""
        # Implement your caching strategy here
        return {"cached": True, "data": None}

# Usage example
async def main():
    async with ResilientAPIClient(
        "https://api.example.com",
        "user-service"
    ) as client:
        # This will use circuit breaker protection
        user = await client.get("/users/123")
        print(f"User data: {user}")
        
        # Create new user
        new_user = await client.post("/users", {
            "name": "John Doe",
            "email": "john@example.com"
        })
        print(f"Created user: {new_user}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Database Connection with Circuit Breaker

```python
# database_client.py
import asyncpg
import asyncio
from contextlib import asynccontextmanager

class ResilientDatabaseClient:
    """Database client with circuit breaker for connection issues"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
        
        # Circuit breaker for database connections
        self.circuit_breaker = ConfigurableCircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=3,  # More sensitive for DB
                timeout=60.0,
                half_open_max_calls=1,
                excluded_exceptions=(asyncpg.IntegrityConstraintViolationError,)
            )
        )
    
    async def connect(self):
        """Create connection pool"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=20,
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def acquire_connection(self):
        """Get a connection with circuit breaker protection"""
        
        async def get_connection():
            return await self.pool.acquire()
        
        try:
            # Use circuit breaker for connection acquisition
            conn = await self.circuit_breaker.call(get_connection)
            try:
                yield conn
            finally:
                await self.pool.release(conn)
                
        except CircuitOpenError:
            logger.error("Database circuit breaker is open!")
            # Could fall back to read replica or cache
            raise DatabaseUnavailableError("Database is currently unavailable")
    
    async def execute_query(self, query: str, *args) -> list:
        """Execute a query with resilience"""
        
        async def run_query():
            async with self.acquire_connection() as conn:
                return await conn.fetch(query, *args)
        
        try:
            return await self.circuit_breaker.call(run_query)
        except CircuitOpenError:
            # For read queries, maybe use cache
            if query.strip().upper().startswith("SELECT"):
                return await self.get_from_query_cache(query, args)
            raise
    
    async def execute_transaction(self, operations):
        """Execute multiple operations in a transaction"""
        
        async def run_transaction():
            async with self.acquire_connection() as conn:
                async with conn.transaction():
                    results = []
                    for operation in operations:
                        result = await conn.execute(operation['query'], *operation.get('args', []))
                        results.append(result)
                    return results
        
        return await self.circuit_breaker.call(run_transaction)

# Usage example
async def user_service_example():
    db = ResilientDatabaseClient("postgresql://user:pass@localhost/mydb")
    
    try:
        await db.connect()
        
        # Simple query with circuit breaker
        users = await db.execute_query(
            "SELECT * FROM users WHERE active = $1",
            True
        )
        
        # Transaction with circuit breaker
        await db.execute_transaction([
            {
                "query": "INSERT INTO users (name, email) VALUES ($1, $2)",
                "args": ["Alice", "alice@example.com"]
            },
            {
                "query": "INSERT INTO user_logs (user_email, action) VALUES ($1, $2)",
                "args": ["alice@example.com", "created"]
            }
        ])
        
    except DatabaseUnavailableError:
        logger.error("Database is down, degrading gracefully")
        # Return cached data or error response
        
    finally:
        await db.close()
```

### Example 3: Microservice Communication

```python
# microservice_client.py
class MicroserviceClient:
    """Client for inter-service communication with circuit breakers"""
    
    def __init__(self):
        # Different circuit breakers for different services
        self.circuit_breakers = {
            "auth-service": ConfigurableCircuitBreaker(
                CircuitBreakerConfig(
                    failure_threshold=3,  # Critical service
                    timeout=30,
                    half_open_max_calls=2
                )
            ),
            "notification-service": ConfigurableCircuitBreaker(
                CircuitBreakerConfig(
                    failure_threshold=10,  # Less critical
                    timeout=120,
                    half_open_max_calls=5
                )
            ),
            "analytics-service": ConfigurableCircuitBreaker(
                CircuitBreakerConfig(
                    failure_threshold=15,  # Can tolerate more failures
                    timeout=300,
                    half_open_max_calls=3
                )
            )
        }
        
        self.session = None
    
    async def call_service(
        self,
        service_name: str,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict:
        """Call a microservice with appropriate circuit breaker"""
        
        if service_name not in self.circuit_breakers:
            raise ValueError(f"Unknown service: {service_name}")
        
        circuit_breaker = self.circuit_breakers[service_name]
        
        # Service URLs from service discovery or config
        service_urls = {
            "auth-service": "http://auth:8000",
            "notification-service": "http://notifications:8001",
            "analytics-service": "http://analytics:8002"
        }
        
        url = f"{service_urls[service_name]}{endpoint}"
        
        async def make_request():
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    return await response.json()
        
        try:
            return await circuit_breaker.call(make_request)
            
        except CircuitOpenError:
            # Handle based on service criticality
            if service_name == "auth-service":
                # Critical service - might need to fail
                raise ServiceUnavailableError(f"{service_name} is down")
            elif service_name == "notification-service":
                # Queue for later
                await self.queue_notification(kwargs)
                return {"queued": True}
            else:
                # Analytics can be skipped
                logger.warning(f"Skipping {service_name} call - circuit open")
                return {"skipped": True}
    
    async def authenticate_user(self, token: str) -> Dict:
        """Authenticate user with circuit breaker"""
        return await self.call_service(
            "auth-service",
            "POST",
            "/validate",
            json={"token": token}
        )
    
    async def send_notification(self, user_id: str, message: str) -> Dict:
        """Send notification with circuit breaker"""
        return await self.call_service(
            "notification-service",
            "POST",
            "/send",
            json={"user_id": user_id, "message": message}
        )
    
    async def track_event(self, event_data: Dict) -> Dict:
        """Track analytics event with circuit breaker"""
        return await self.call_service(
            "analytics-service",
            "POST",
            "/events",
            json=event_data
        )

# Usage in your application
async def handle_user_action(user_token: str, action: str):
    client = MicroserviceClient()
    
    try:
        # Authenticate (critical)
        auth_result = await client.authenticate_user(user_token)
        user_id = auth_result["user_id"]
        
        # Send notification (nice to have)
        await client.send_notification(
            user_id,
            f"You performed action: {action}"
        )
        
        # Track analytics (optional)
        await client.track_event({
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"success": True, "user_id": user_id}
        
    except ServiceUnavailableError as e:
        # Auth service is down - can't proceed
        return {"success": False, "error": str(e)}
```

### Example 4: Batch Processing with Circuit Breaker

```python
# batch_processor.py
class ResilientBatchProcessor:
    """Process batches with circuit breaker protection"""
    
    def __init__(self, processor_func, batch_size: int = 100):
        self.processor_func = processor_func
        self.batch_size = batch_size
        
        # Circuit breaker for batch processing
        self.circuit_breaker = ConfigurableCircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=2,  # Sensitive to batch failures
                timeout=300,  # 5 minutes for recovery
                half_open_max_calls=1,
                success_threshold=2  # Need 2 successes to close
            )
        )
        
        self.failed_items = []  # Store failed items for retry
    
    async def process_items(self, items: List[Any]) -> Dict:
        """Process items in batches with resilience"""
        
        results = {
            "processed": 0,
            "failed": 0,
            "circuit_trips": 0,
            "details": []
        }
        
        # Process in batches
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            try:
                # Process batch with circuit breaker
                batch_result = await self.circuit_breaker.call(
                    self.processor_func,
                    batch
                )
                
                results["processed"] += len(batch_result["successful"])
                results["failed"] += len(batch_result.get("failed", []))
                results["details"].append({
                    "batch_num": i // self.batch_size + 1,
                    "status": "success",
                    "processed": len(batch_result["successful"])
                })
                
            except CircuitOpenError:
                # Circuit is open, save items for later
                self.failed_items.extend(batch)
                results["circuit_trips"] += 1
                results["details"].append({
                    "batch_num": i // self.batch_size + 1,
                    "status": "circuit_open",
                    "items_saved": len(batch)
                })
                
                # Skip remaining batches if circuit is open
                remaining = items[i + self.batch_size:]
                if remaining:
                    self.failed_items.extend(remaining)
                    results["details"].append({
                        "status": "skipped_remaining",
                        "items_saved": len(remaining)
                    })
                break
                
            except Exception as e:
                # Other errors - save batch for retry
                self.failed_items.extend(batch)
                results["failed"] += len(batch)
                results["details"].append({
                    "batch_num": i // self.batch_size + 1,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    async def retry_failed_items(self) -> Dict:
        """Retry items that failed due to circuit breaker"""
        
        if not self.failed_items:
            return {"message": "No failed items to retry"}
        
        # Check if circuit is still open
        if self.circuit_breaker.state == "open":
            return {
                "message": "Circuit still open, retry later",
                "failed_count": len(self.failed_items)
            }
        
        # Retry with smaller batch size
        items_to_retry = self.failed_items.copy()
        self.failed_items.clear()
        
        original_batch_size = self.batch_size
        self.batch_size = max(10, self.batch_size // 2)  # Smaller batches
        
        try:
            result = await self.process_items(items_to_retry)
            return {
                "retry_complete": True,
                "result": result
            }
        finally:
            self.batch_size = original_batch_size

# Example processor function
async def upload_to_storage(items: List[Dict]) -> Dict:
    """Upload items to cloud storage"""
    successful = []
    failed = []
    
    async with aiohttp.ClientSession() as session:
        for item in items:
            try:
                async with session.post(
                    "https://storage.example.com/upload",
                    json=item,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    successful.append(item["id"])
            except Exception as e:
                failed.append({"id": item["id"], "error": str(e)})
                
                # If more than 50% failed, raise to trip circuit
                if len(failed) > len(items) * 0.5:
                    raise Exception(f"Batch failure rate too high: {len(failed)}/{len(items)}")
    
    return {"successful": successful, "failed": failed}

# Usage
async def process_large_dataset():
    processor = ResilientBatchProcessor(upload_to_storage, batch_size=50)
    
    # Large dataset
    items = [{"id": i, "data": f"item_{i}"} for i in range(1000)]
    
    # Initial processing
    result = await processor.process_items(items)
    print(f"Initial run: {result}")
    
    # Wait a bit and retry failed items
    await asyncio.sleep(60)
    retry_result = await processor.retry_failed_items()
    print(f"Retry result: {retry_result}")
```

### Example 5: Complete Application Example

```python
# app.py - Full application with circuit breakers
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Initialize circuit breaker registry
breaker_registry = CircuitBreakerRegistry()
monitor = CircuitBreakerMonitor()

# Register circuit breakers
for service_name in ["user-db", "cache", "email", "payment"]:
    breaker = InstrumentedCircuitBreaker(
        name=service_name,
        config=breaker_registry._get_config_for_service(service_name)
    )
    monitor.add_breaker(service_name, breaker)

@app.on_event("startup")
async def startup_event():
    """Initialize monitoring on startup"""
    asyncio.create_task(monitoring_loop())

@app.exception_handler(CircuitOpenError)
async def circuit_open_handler(request, exc):
    """Handle circuit breaker open errors"""
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service temporarily unavailable",
            "message": str(exc),
            "retry_after": 30
        },
        headers={"Retry-After": "30"}
    )

@app.get("/health")
async def health_check():
    """Health endpoint with circuit breaker status"""
    dashboard_data = monitor.get_dashboard_data()
    
    # Determine overall health
    open_count = dashboard_data["summary"]["open"]
    total_count = dashboard_data["summary"]["total_breakers"]
    
    if open_count == 0:
        status = "healthy"
        status_code = 200
    elif open_count < total_count / 2:
        status = "degraded"
        status_code = 200
    else:
        status = "unhealthy"
        status_code = 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "circuit_breakers": dashboard_data["summary"],
            "timestamp": dashboard_data["timestamp"]
        }
    )

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    """Get user with multiple service calls"""
    
    # Get circuit breakers
    db_breaker = monitor.breakers["user-db"]
    cache_breaker = monitor.breakers["cache"]
    
    # Try cache first
    try:
        cached_user = await cache_breaker.call(
            get_from_cache,
            f"user:{user_id}"
        )
        if cached_user:
            return {"source": "cache", "user": cached_user}
    except (CircuitOpenError, Exception) as e:
        logger.warning(f"Cache unavailable: {e}")
    
    # Fall back to database
    try:
        user = await db_breaker.call(
            get_user_from_db,
            user_id
        )
        
        # Try to update cache (non-critical)
        try:
            await cache_breaker.call(
                set_in_cache,
                f"user:{user_id}",
                user,
                ttl=300
            )
        except:
            pass  # Cache update is optional
        
        return {"source": "database", "user": user}
        
    except CircuitOpenError:
        # Both cache and DB are down
        raise HTTPException(
            status_code=503,
            detail="User service is currently unavailable"
        )

@app.post("/api/orders")
async def create_order(order_data: Dict):
    """Create order with payment processing"""
    
    payment_breaker = monitor.breakers["payment"]
    email_breaker = monitor.breakers["email"]
    
    try:
        # Process payment (critical)
        payment_result = await payment_breaker.call(
            process_payment,
            order_data["payment_info"]
        )
        
        # Send confirmation email (non-critical)
        try:
            await email_breaker.call(
                send_email,
                order_data["user_email"],
                "Order Confirmation",
                f"Your order {payment_result['order_id']} is confirmed!"
            )
        except (CircuitOpenError, Exception) as e:
            # Email failed but order succeeded
            logger.warning(f"Failed to send confirmation email: {e}")
            # Could queue for later
        
        return {
            "success": True,
            "order_id": payment_result["order_id"],
            "email_sent": email_breaker.state == "closed"
        }
        
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail="Payment service is currently unavailable"
        )

@app.get("/dashboard")
async def circuit_breaker_dashboard():
    """API endpoint for monitoring dashboard"""
    return monitor.get_dashboard_data()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Future Enhancements

1. **Adaptive Circuit Breakers**: ML-based threshold adjustment
2. **Predictive Scaling**: Anticipate load and pre-scale
3. **Distributed Circuit State**: Share state across instances
4. **Advanced Health Checks**: Deep health probes
5. **Resilience Testing Framework**: Automated chaos testing