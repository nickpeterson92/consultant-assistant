#!/usr/bin/env python3
"""Simple test to understand circuit breaker behavior"""

import asyncio
import time
from src.a2a.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerException

async def success_func():
    return "success"

async def failing_func():
    raise Exception("Test failure")

async def test_circuit_breaker():
    config = CircuitBreakerConfig(failure_threshold=3, timeout=2)
    breaker = CircuitBreaker("test", config)
    
    print("\n=== Testing successful calls ===")
    # Test successful calls
    for i in range(5):
        result = await breaker.call(success_func)
        print(f"Call {i+1}: {result}, success_count={breaker.success_count}, failure_count={breaker.failure_count}")
    
    print(f"\nAfter 5 successful calls: success_count={breaker.success_count}")
    
    print("\n=== Testing failures to open circuit ===")
    # Test failures
    for i in range(3):
        try:
            await breaker.call(failing_func)
        except Exception as e:
            print(f"Failure {i+1}: {e}, state={breaker.state.value}, failure_count={breaker.failure_count}")
    
    print(f"\nCircuit state after failures: {breaker.state.value}")
    
    print("\n=== Testing open circuit rejection ===")
    # Test open circuit
    try:
        await breaker.call(success_func)
    except CircuitBreakerException as e:
        print(f"Circuit breaker exception: {e}")
    
    print("\n=== Waiting for timeout to transition to half-open ===")
    await asyncio.sleep(2.1)
    
    # Test half-open
    print("\nTrying call after timeout...")
    try:
        result = await breaker.call(success_func)
        print(f"Success in half-open: {result}, state={breaker.state.value}")
    except Exception as e:
        print(f"Failed in half-open: {e}")

if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())