"""
Global pytest configuration and fixtures for multi-agent orchestrator tests.

This file provides shared fixtures, configuration, and utilities for all tests.
Fixtures are organized by scope and purpose to support unit, integration, and e2e tests.
"""

import os
import sys
import asyncio
import json
import pytest
import pytest_asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import tempfile
import aiohttp

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import our modules
from src.utils.config import SystemConfig, LLMConfig
from src.utils.storage.memory_schemas import SimpleMemory
from src.a2a.protocol import A2AServer, A2AClient
from src.a2a.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


# ============================================================================
# Session-Level Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config_path(tmp_path_factory):
    """Create a temporary config file for testing."""
    config_dir = tmp_path_factory.mktemp("config")
    config_file = config_dir / "test_config.json"
    
    test_config = {
        "database": {
            "path": ":memory:",  # Use in-memory SQLite for tests
            "timeout": 5,
            "pool_size": 2
        },
        "logging": {
            "level": "DEBUG",
            "external_logs_dir": str(config_dir / "logs")
        },
        "llm": {
            "model": "gpt-4o-mini",
            "temperature": 0.0,  # Deterministic for tests
            "max_tokens": 100,
            "timeout": 5,
            "pricing": {
                "gpt-4o-mini": {
                    "input_per_1k": 0.00015,
                    "output_per_1k": 0.00060
                }
            }
        },
        "a2a": {
            "timeout": 5,
            "health_check_timeout": 2,
            "circuit_breaker_threshold": 3,
            "circuit_breaker_timeout": 5
        },
        "conversation": {
            "default_user_id": "test-user",
            "default_thread_id": "test-thread"
        }
    }
    
    config_file.write_text(json.dumps(test_config, indent=2))
    return str(config_file)


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    env_vars = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        "AZURE_OPENAI_API_KEY": "test-api-key",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "test-deployment",
        "AZURE_OPENAI_API_VERSION": "2024-06-01",
        "SFDC_USER": "test@example.com",
        "SFDC_PASS": "test-password",
        "SFDC_TOKEN": "test-token",
        "DEBUG_MODE": "true"
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def system_config(test_config_path, mock_env_vars):
    """Get SystemConfig instance."""
    # Load config directly from the test config file
    import json
    with open(test_config_path) as f:
        config_data = json.load(f)
    
    # Create system config
    return SystemConfig(
        environment=config_data.get("environment", "testing"),
        debug_mode=True
    )


# ============================================================================
# LLM and AI Fixtures
# ============================================================================

@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    from langchain_core.messages import AIMessage
    
    llm = Mock()
    # For sync calls
    llm.invoke = Mock(return_value=AIMessage(
        content="Test response",
        tool_calls=[]
    ))
    # For async calls
    llm.ainvoke = AsyncMock(return_value=AIMessage(
        content="Test response",
        tool_calls=[]
    ))
    llm.bind_tools = Mock(return_value=llm)
    return llm


@pytest.fixture
def mock_llm_with_tools():
    """Create a mock LLM that returns tool calls."""
    from langchain_core.messages import AIMessage
    
    llm = Mock()
    
    # First call returns tool call
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{
            "id": "call_123",
            "name": "GetAccountTool",
            "args": {"name": "Acme Corp"}
        }]
    )
    
    # Second call returns final answer
    final_response = AIMessage(
        content="Found Acme Corp account",
        tool_calls=[]
    )
    
    # For sync calls
    llm.invoke = Mock(side_effect=[tool_call_response, final_response])
    # For async calls
    llm.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])
    llm.bind_tools = Mock(return_value=llm)
    return llm


# ============================================================================
# Storage and Memory Fixtures
# ============================================================================

@pytest.fixture
async def memory_store(tmp_path):
    """Create a temporary memory store for testing."""
    from src.utils.storage.async_store_adapter import AsyncStoreAdapter
    
    db_path = tmp_path / "test_memory.db"
    # AsyncStoreAdapter expects a path string, not a store object
    store = AsyncStoreAdapter(str(db_path))
    
    yield store
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_memory_data():
    """Sample memory data for testing."""
    return SimpleMemory(
        accounts=[
            {"id": "001", "name": "Acme Corp"},
            {"id": "002", "name": "TechCo"}
        ],
        contacts=[
            {"id": "003", "name": "John Doe", "email": "john@acme.com", "account_id": "001"}
        ],
        opportunities=[
            {"id": "006", "name": "Big Deal", "amount": 100000, "stage": "Prospecting"}
        ]
    )


# ============================================================================
# A2A Protocol Fixtures
# ============================================================================

@pytest.fixture
def agent_card():
    """Create a sample agent card for testing."""
    return {
        "name": "test-agent",
        "version": "1.0.0",
        "description": "Test agent for unit tests",
        "capabilities": ["test_capability", "mock_operations"],
        "endpoints": {
            "process_task": "/a2a",
            "agent_card": "/a2a/agent-card"
        },
        "communication_modes": ["sync", "streaming"]
    }


@pytest.fixture
async def mock_a2a_client():
    """Create a mock A2A client."""
    client = AsyncMock()
    client.execute_task = AsyncMock(return_value={
        "artifacts": [{
            "id": "test-artifact",
            "content": "Test result",
            "content_type": "text/plain"
        }],
        "status": "completed"
    })
    client.get_agent_card = AsyncMock(return_value={
        "name": "mock-agent",
        "capabilities": ["test"]
    })
    return client


@pytest.fixture
async def a2a_test_server(agent_card):
    """Create a test A2A server."""
    from src.a2a import A2AServer, AgentCard
    
    card = AgentCard(**agent_card)
    server = A2AServer(card, "localhost", 0)  # Use port 0 for random port
    
    # Add test handlers
    async def test_handler(params):
        return {"result": "test"}
    
    server.register_handler("test", test_handler)
    
    yield server


# ============================================================================
# Circuit Breaker Fixtures
# ============================================================================

@pytest.fixture
def circuit_breaker_config():
    """Circuit breaker configuration for testing."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        timeout=2,  # Short timeout for tests
        half_open_max_calls=1,
        reset_timeout=3
    )


@pytest.fixture
def circuit_breaker(circuit_breaker_config):
    """Create a circuit breaker instance."""
    return CircuitBreaker("test-breaker", circuit_breaker_config)


# ============================================================================
# HTTP and Network Fixtures
# ============================================================================

@pytest.fixture
async def aiohttp_client_session():
    """Create an aiohttp client session for testing."""
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def mock_http_responses():
    """Mock HTTP responses for testing."""
    return {
        "success": {
            "status": 200,
            "json": {"result": "success"}
        },
        "error": {
            "status": 500,
            "json": {"error": "Internal server error"}
        },
        "timeout": {
            "exception": asyncio.TimeoutError()
        }
    }


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def salesforce_test_data():
    """Sample Salesforce data for testing."""
    return {
        "accounts": [
            {
                "Id": "001XX000003DHP0",
                "Name": "Acme Corporation",
                "Industry": "Technology",
                "AnnualRevenue": 1000000
            }
        ],
        "contacts": [
            {
                "Id": "003XX000004TMM2",
                "FirstName": "John",
                "LastName": "Doe",
                "Email": "john@acme.com",
                "AccountId": "001XX000003DHP0"
            }
        ],
        "opportunities": [
            {
                "Id": "006XX000002kJgS",
                "Name": "Big Deal",
                "Amount": 50000,
                "StageName": "Qualification",
                "CloseDate": "2025-12-31"
            }
        ]
    }


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def time_machine():
    """Fixture to control time in tests."""
    from freezegun import freeze_time
    return freeze_time


@pytest.fixture
def capture_logs():
    """Capture log output for testing."""
    import logging
    from io import StringIO
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    yield log_capture
    
    # Remove handler
    root_logger.removeHandler(handler)


# ============================================================================
# Markers and Test Utilities
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Markers are defined in pytest.ini
    pass


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Add markers based on test name
        if "async" in item.name or "test_async" in item.name:
            item.add_marker(pytest.mark.asyncio)
        if "slow" in item.name:
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Test Helpers
# ============================================================================

class TestHelpers:
    """Utility methods for tests."""
    
    @staticmethod
    async def wait_for_condition(condition_func, timeout=5, interval=0.1):
        """Wait for a condition to become true."""
        start_time = asyncio.get_event_loop().time()
        while not condition_func():
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("Condition not met within timeout")
            await asyncio.sleep(interval)
    
    @staticmethod
    def create_mock_message(content, role="user", **kwargs):
        """Create a mock message object."""
        from langchain_core.messages import HumanMessage, AIMessage
        
        if role == "user":
            return HumanMessage(content=content, **kwargs)
        else:
            return AIMessage(content=content, **kwargs)


@pytest.fixture
def test_helpers():
    """Provide test helper methods."""
    return TestHelpers()


# ============================================================================
# Cleanup and Teardown
# ============================================================================

@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset all circuit breakers before each test to ensure isolation."""
    # Import here to avoid circular imports
    from src.a2a.circuit_breaker import get_circuit_breaker_registry
    
    # Clear all circuit breakers before each test
    registry = get_circuit_breaker_registry()
    if hasattr(registry, '_breakers'):
        registry._breakers.clear()
    
    yield
    
    # Clear again after test to ensure clean state
    if hasattr(registry, '_breakers'):
        registry._breakers.clear()

# Removed problematic cleanup fixture that was causing recursion error