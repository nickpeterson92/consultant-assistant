# Circuit Breaker and Resilience Patterns Documentation

## Overview

The resilience patterns in this system protect against cascading failures, network issues, and service degradation in the distributed multi-agent architecture. The implementation centers around the Circuit Breaker pattern, complemented by retry logic, timeouts, and graceful degradation strategies.

## Circuit Breaker Pattern

### Concept

The Circuit Breaker acts like an electrical circuit breaker - it "trips" when too many failures occur, preventing further damage to the system. This protects both the calling service and the failing service from being overwhelmed.

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
│        │ └───────────────┐                          │           │
│        │                 │                          ▼           │
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

## Monitoring and Metrics

### Circuit Breaker Metrics

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
                "last_failure": cb.last_failure_time
            }
            for name, cb in circuit_breakers.items()
        },
        "connection_pools": {
            key: {
                "active": len(session.connector._acquired),
                "limit": session.connector.limit
            }
            for key, session in connection_pools.items()
        },
        "retry_statistics": {
            "total_retries": retry_counter.total(),
            "successful_retries": retry_success_counter.total(),
            "retry_exhausted": retry_exhausted_counter.total()
        },
        "health_checks": {
            agent: status.value
            for agent, status in health_checker.health_status.items()
        }
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

## Future Enhancements

1. **Adaptive Circuit Breakers**: ML-based threshold adjustment
2. **Predictive Scaling**: Anticipate load and pre-scale
3. **Distributed Circuit State**: Share state across instances
4. **Advanced Health Checks**: Deep health probes
5. **Resilience Testing Framework**: Automated chaos testing