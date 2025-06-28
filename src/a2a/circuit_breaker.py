"""Circuit breaker pattern for resilient agent-to-agent communication."""

import asyncio
import time
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass
from src.utils.logging import get_logger

logger = get_logger('circuit_breaker')

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing if service is back

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5
    timeout: int = 30  # seconds
    half_open_max_calls: int = 3
    reset_timeout: int = 60  # seconds to wait before trying again

class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker implementation for protecting against cascading failures"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker"""
        async with self._lock:
            current_time = time.time()
            
            # Check if we should transition from OPEN to HALF_OPEN
            if (self.state == CircuitBreakerState.OPEN and 
                current_time - self.last_failure_time >= self.config.timeout):
                time_in_open = current_time - self.last_failure_time
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("circuit_breaker_state_change",
                    component="a2a",
                    operation="state_transition",
                    circuit_name=self.name,
                    from_state="OPEN",
                    to_state="HALF_OPEN",
                    time_in_open=time_in_open,
                    timeout_duration=self.config.timeout,
                    reason="timeout_expired"
                )
            
            # Fast fail if circuit is open
            if self.state == CircuitBreakerState.OPEN:
                time_since_failure = current_time - self.last_failure_time
                logger.warning("circuit_breaker_open",
                    component="a2a",
                    operation="fast_fail",
                    circuit_name=self.name,
                    state="OPEN",
                    failure_count=self.failure_count,
                    time_since_last_failure=round(time_since_failure, 1)
                )
                raise CircuitBreakerException(f"Circuit breaker {self.name} is open")
            
            # Limit calls in half-open state
            if (self.state == CircuitBreakerState.HALF_OPEN and 
                self.half_open_calls >= self.config.half_open_max_calls):
                logger.warning("circuit_breaker_half_open_limit",
                    component="a2a",
                    operation="call",
                    circuit_name=self.name,
                    half_open_calls=self.half_open_calls,
                    limit=self.config.half_open_max_calls
                )
                raise CircuitBreakerException(f"Circuit breaker {self.name} half-open limit exceeded")
        
        # Execute the function
        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
            
            result = await func(*args, **kwargs)
            
            # Handle success
            async with self._lock:
                await self._on_success()
            
            return result
            
        except Exception as e:
            # Handle failure
            async with self._lock:
                await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            # If we've had enough successes in half-open, close the circuit
            if self.success_count >= self.config.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("circuit_breaker_state_change",
                    component="a2a",
                    operation="state_transition",
                    circuit_name=self.name,
                    from_state="HALF_OPEN",
                    to_state="CLOSED",
                    success_count=self.success_count,
                    reason="success_threshold_reached"
                )
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success in closed state
            self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning("circuit_breaker_state_change",
                    component="a2a",
                    operation="state_transition",
                    circuit_name=self.name,
                    from_state="CLOSED",
                    to_state="OPEN",
                    failure_count=self.failure_count,
                    failure_threshold=self.config.failure_threshold,
                    reason="failure_threshold_exceeded"
                )
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open goes back to open
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            logger.warning("circuit_breaker_state_change",
                component="a2a",
                operation="state_transition",
                circuit_name=self.name,
                from_state="HALF_OPEN",
                to_state="OPEN",
                success_count_before_failure=self.success_count,
                reason="failure_in_half_open"
            )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "half_open_calls": self.half_open_calls
        }

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
    
    def get_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self._breakers:
            breaker_config = config or self._default_config
            self._breakers[name] = CircuitBreaker(name, breaker_config)
            logger.info("circuit_breaker_created",
                component="a2a",
                operation="get_breaker",
                circuit_name=name
            )
        return self._breakers[name]
    
    def remove_breaker(self, name: str):
        """Remove a circuit breaker"""
        if name in self._breakers:
            del self._breakers[name]
            logger.info("circuit_breaker_removed",
                component="a2a",
                operation="remove_breaker",
                circuit_name=name
            )
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers"""
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}
    
    def reset_breaker(self, name: str):
        """Reset a circuit breaker to closed state"""
        if name in self._breakers:
            breaker = self._breakers[name]
            breaker.state = CircuitBreakerState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.half_open_calls = 0
            logger.info("circuit_breaker_reset",
                component="a2a",
                operation="reset_breaker",
                circuit_name=name
            )

# Global circuit breaker registry
_registry: Optional[CircuitBreakerRegistry] = None

def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry"""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry

def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get a circuit breaker by name"""
    return get_circuit_breaker_registry().get_breaker(name, config)

class RetryConfig:
    """Configuration for retry mechanism"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 30.0, exponential_base: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

async def retry_with_exponential_backoff(func: Callable, config: RetryConfig, 
                                       circuit_breaker: Optional[CircuitBreaker] = None,
                                       *args, **kwargs) -> Any:
    """Execute a function with retry and exponential backoff"""
    import random
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            if circuit_breaker:
                return await circuit_breaker.call(func, *args, **kwargs)
            else:
                return await func(*args, **kwargs)
                
        except CircuitBreakerException:
            # Don't retry if circuit breaker is open
            raise
            
        except Exception as e:
            last_exception = e
            
            if attempt == config.max_attempts - 1:
                # Last attempt, don't sleep
                break
            
            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning("retry_attempt_failed",
                component="a2a",
                operation="retry",
                attempt=attempt + 1,
                delay_seconds=round(delay, 2),
                error_type=type(e).__name__,
                error=str(e)
            )
            await asyncio.sleep(delay)
    
    # All attempts failed
    logger.error("all_retry_attempts_failed",
        component="a2a",
        operation="retry",
        max_attempts=config.max_attempts
    )
    raise last_exception

async def resilient_call(func: Callable, circuit_breaker_name: str,
                        retry_config: Optional[RetryConfig] = None,
                        circuit_config: Optional[CircuitBreakerConfig] = None,
                        *args, **kwargs) -> Any:
    """Make a resilient call with both circuit breaker and retry"""
    circuit_breaker = get_circuit_breaker(circuit_breaker_name, circuit_config)
    
    if retry_config is None:
        retry_config = RetryConfig()
    
    return await retry_with_exponential_backoff(
        func, retry_config, circuit_breaker, *args, **kwargs
    )