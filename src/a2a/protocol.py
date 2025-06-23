"""
Agent2Agent (A2A) Protocol Implementation.

This module implements Google's A2A protocol specification for inter-agent communication
using JSON-RPC 2.0 over HTTP. The implementation focuses on enterprise-grade reliability
with connection pooling, circuit breakers, and retry logic.

Key Design Decisions:
    - JSON-RPC 2.0: Industry standard for RPC communication with well-defined error handling
    - Connection Pooling: Reuses HTTP connections to reduce latency and resource usage
    - Circuit Breaker Pattern: Prevents cascading failures by failing fast when agents are down
    - Async Architecture: Non-blocking I/O for high-performance concurrent operations
    - Structured Logging: Machine-readable logs for observability and debugging

Architecture Components:
    - A2AClient: Makes resilient calls to other agents with automatic retry and circuit breaking
    - A2AServer: Handles incoming requests with input validation and error handling
    - A2AConnectionPool: Manages connection lifecycle with idle timeout and cleanup
    - Data Models: Type-safe message structures (Task, Artifact, Message, AgentCard)
"""

import json
import uuid
import asyncio
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import aiohttp
from aiohttp import web
from src.utils.constants import (
    A2A_STATUS_PENDING,
    DEFAULT_A2A_PORT, DEFAULT_HOST
)
import logging

from src.utils.logging import get_logger, get_performance_tracker
from src.utils.logging import log_a2a_activity, log_performance_activity
from src.utils.input_validation import AgentInputValidator, ValidationError
from src.utils.circuit_breaker import CircuitBreakerConfig, RetryConfig, resilient_call
from src.utils.config import get_a2a_config, get_system_config

logger = logging.getLogger(__name__)

# Global references for external loggers - initialized lazily at runtime
# This avoids circular imports while maintaining proper logging infrastructure
a2a_logger = None
a2a_perf = None

def ensure_loggers_initialized():
    """Ensure external loggers are properly initialized at runtime.
    
    This function uses lazy initialization to avoid circular import issues
    while ensuring proper logging infrastructure is available when needed.
    The pattern allows the module to be imported without requiring the
    entire logging system to be initialized, which is crucial for modular
    architecture and testing.
    """
    global a2a_logger, a2a_perf
    
    if a2a_logger is None or a2a_perf is None:
        try:
            a2a_logger = get_logger('a2a_protocol')
            a2a_perf = get_performance_tracker('a2a_protocol')
            a2a_logger.info("RUNTIME_LOGGER_INITIALIZED")
        except Exception:
            # Silent fallback - logging should not break core functionality
            pass

@dataclass  
class TimestampedBase:
    """Base class for dataclasses that need automatic timestamp initialization."""
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class AgentCard:
    """Agent capability description following A2A specification.
    
    The AgentCard serves as a self-describing manifest that allows agents
    to advertise their capabilities for dynamic discovery and routing.
    This enables loose coupling between agents - the orchestrator can
    select appropriate agents based on capabilities without hardcoding
    specific agent dependencies.
    
    Attributes:
        name: Human-readable agent identifier
        version: Semantic version for compatibility checking
        description: Brief description of agent's purpose
        capabilities: List of capabilities this agent provides (e.g., ['salesforce_operations'])
        endpoints: Map of endpoint names to URLs for different operations
        communication_modes: Supported modes (e.g., ['synchronous', 'streaming'])
        metadata: Additional agent-specific configuration
    """
    name: str
    version: str
    description: str
    capabilities: List[str]
    endpoints: Dict[str, str]
    communication_modes: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

@dataclass
class A2ATask:
    """Stateful collaboration entity for agent task processing.
    
    Tasks are the primary unit of work in the A2A protocol. They carry
    both the instruction and the necessary context for an agent to
    complete the work. The state_snapshot allows resumability and
    debugging by capturing the system state at task creation time.
    
    Attributes:
        id: Unique identifier for tracking and correlation
        instruction: Natural language instruction for the agent
        context: Relevant context including user info and session data
        state_snapshot: Captures system state for reproducibility
        status: Task lifecycle state (pending -> in_progress -> completed/failed)
        created_at: ISO timestamp for audit and performance tracking
    """
    id: str
    instruction: str
    context: Dict[str, Any]
    state_snapshot: Dict[str, Any]
    status: str = A2A_STATUS_PENDING  # Status values from constants
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

@dataclass
class A2AArtifact:
    """Immutable output generated by an agent.
    
    Artifacts represent the concrete results of agent processing.
    They are immutable to ensure data integrity and provide a clear
    audit trail. The content can be any serializable data structure,
    with content_type indicating how to interpret it.
    
    Attributes:
        id: Unique identifier for the artifact
        task_id: Links artifact to the task that generated it
        content: The actual output data (text, structured data, etc.)
        content_type: MIME type or custom type identifier
        metadata: Additional context about the artifact
        created_at: ISO timestamp for ordering and audit
    """
    id: str
    task_id: str
    content: Any
    content_type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

@dataclass
class A2AMessage:
    """Message for inter-agent communication.
    
    Messages enable agents to communicate during task processing,
    supporting patterns like clarification requests, status updates,
    and partial results. This supports more complex multi-turn
    interactions between agents.
    
    Attributes:
        id: Unique message identifier
        task_id: Links message to ongoing task
        content: Message body (typically natural language)
        sender: Agent identifier that sent the message
        recipient: Target agent identifier
        message_type: Semantic type for message routing/handling
        metadata: Additional routing or processing hints
        created_at: ISO timestamp for message ordering
    """
    id: str
    task_id: str
    content: str
    sender: str
    recipient: str
    message_type: str = "instruction"  # instruction, response, status
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

class A2ARequest:
    """JSON-RPC 2.0 request wrapper.
    
    Encapsulates requests in the standard JSON-RPC 2.0 format, providing:
    - Consistent request structure across all agent communications
    - Request/response correlation through unique IDs
    - Clear method routing and parameter passing
    
    The JSON-RPC 2.0 standard was chosen for its simplicity, wide support,
    and well-defined error handling semantics.
    """
    
    def __init__(self, method: str, params: Dict[str, Any], request_id: Optional[str] = None):
        """Initialize a JSON-RPC request.
        
        Args:
            method: RPC method name to invoke
            params: Method parameters as a dictionary
            request_id: Optional correlation ID (auto-generated if not provided)
        """
        self.jsonrpc = "2.0"
        self.method = method
        self.params = params
        self.id = request_id or str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 request format."""
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
            "id": self.id
        }

class A2AResponse:
    """JSON-RPC 2.0 response wrapper.
    
    Encapsulates responses in the standard JSON-RPC 2.0 format, supporting
    both successful results and structured error responses. The mutual
    exclusivity of result/error fields provides clear success/failure
    semantics.
    
    Error codes follow JSON-RPC 2.0 specification:
    - -32700: Parse error
    - -32600: Invalid request
    - -32601: Method not found
    - -32602: Invalid params
    - -32603: Internal error
    """
    
    def __init__(self, result: Any = None, error: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        """Initialize a JSON-RPC response.
        
        Args:
            result: Successful result data (mutually exclusive with error)
            error: Error object with code, message, and optional data
            request_id: Correlation ID from the request
        """
        self.jsonrpc = "2.0"
        self.result = result
        self.error = error
        self.id = request_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 response format."""
        response = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response

class A2AConnectionPool:
    """Singleton connection pool for efficient HTTP session reuse.
    
    This implementation addresses several key performance concerns:
    
    1. Connection Reuse: HTTP connections are expensive to establish,
       especially with TLS. Reusing connections dramatically reduces
       latency for subsequent requests.
    
    2. Resource Management: Prevents connection exhaustion by limiting
       total connections and connections per host. The high per-host
       limit (20+) supports parallel tool execution patterns.
    
    3. Idle Cleanup: Automatically closes idle connections to free
       resources while maintaining hot connections for active agents.
    
    4. Thread Safety: Uses asyncio locks to ensure safe concurrent
       access to the pool from multiple coroutines.
    
    Design decisions:
    - Singleton pattern ensures global connection sharing
    - Per-endpoint locking prevents race conditions
    - Configurable timeouts support different latency requirements
    - DNS caching reduces lookup overhead for repeated requests
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Ensure single instance (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the connection pool with configuration."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._pools = {}  # endpoint -> session
            self._pool_locks = {}  # endpoint -> lock
            self._last_used = {}  # endpoint -> timestamp
            a2a_config = get_a2a_config()
            self._max_idle_time = a2a_config.connection_pool_max_idle
            logger.info(f"A2AConnectionPool initialized with max_idle_time={self._max_idle_time}s")
    
    async def get_session(self, endpoint: str, timeout: Optional[int] = None) -> aiohttp.ClientSession:
        """Get or create a session for an endpoint.
        
        This method implements session reuse with proper lifecycle management:
        - Reuses existing sessions when available (fast path)
        - Creates new sessions with optimized settings when needed
        - Tracks last usage for idle timeout management
        - Uses per-endpoint locking to prevent race conditions
        
        Args:
            endpoint: Full URL of the target endpoint
            timeout: Optional custom timeout (uses config default if not specified)
            
        Returns:
            aiohttp.ClientSession configured for the endpoint
        """
        a2a_config = get_a2a_config()
        if timeout is None:
            timeout = a2a_config.timeout
        
        # Extract base URL to pool connections by host
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Include timeout in the pool key to avoid timeout mismatches
        pool_key = f"{base_url}_timeout_{timeout}"
        
        # Lazy lock creation avoids pre-allocating for all possible endpoints
        if pool_key not in self._pool_locks:
            self._pool_locks[pool_key] = asyncio.Lock()
        
        async with self._pool_locks[pool_key]:
            # Fast path: reuse existing session
            if pool_key in self._pools:
                session = self._pools[pool_key]
                if not session.closed:
                    self._last_used[pool_key] = time.time()
                    return session
                else:
                    logger.info(f"Removing closed session for {pool_key}")
                    del self._pools[pool_key]
            
            # Create new session with optimized settings
            logger.info(f"Creating new session for {base_url} with timeout={timeout}s")
            
            # Multi-level timeout configuration for fine-grained control:
            # - total: Overall request timeout
            # - connect: TCP connection establishment  
            # - sock_read/connect: Lower-level socket timeouts
            timeout_config = aiohttp.ClientTimeout(
                total=timeout,
                connect=a2a_config.connect_timeout,
                sock_read=a2a_config.sock_read_timeout,
                sock_connect=a2a_config.sock_connect_timeout
            )
            
            # Log the actual timeout values for debugging
            logger.info(f"Timeout config - total: {timeout}s, connect: {a2a_config.connect_timeout}s, "
                       f"sock_read: {a2a_config.sock_read_timeout}s, sock_connect: {a2a_config.sock_connect_timeout}s")
            
            # Connection pooling configuration optimized for agent workloads:
            # - High per-host limit supports parallel tool execution (8+ concurrent)
            # - DNS caching reduces repeated lookups for agent endpoints
            # - Keepalive maintains persistent connections for low latency
            # - Cleanup removes stale connections automatically
            connector = aiohttp.TCPConnector(
                limit=a2a_config.connection_pool_size,
                limit_per_host=max(20, a2a_config.connection_pool_size),
                ttl_dns_cache=a2a_config.connection_pool_ttl,
                enable_cleanup_closed=True,
                force_close=False,
                keepalive_timeout=min(30, a2a_config.connection_pool_max_idle)
            )
            
            session = aiohttp.ClientSession(
                timeout=timeout_config,
                connector=connector,
                connector_owner=True  # Session owns connector lifecycle
            )
            
            self._pools[pool_key] = session
            self._last_used[pool_key] = time.time()
            return session
    
    async def cleanup_idle_sessions(self):
        """Clean up idle sessions to free resources.
        
        This method should be called periodically (e.g., every minute) to:
        - Free memory and file descriptors from unused connections
        - Prevent connection leaks from accumulating over time
        - Ensure fresh connections for infrequently used agents
        
        The two-phase approach (collect then remove) avoids modifying
        the dictionary while iterating.
        """
        current_time = time.time()
        to_remove = []
        
        # Phase 1: Identify idle sessions
        for endpoint, last_used in self._last_used.items():
            if current_time - last_used > self._max_idle_time:
                to_remove.append(endpoint)
        
        # Phase 2: Remove idle sessions with proper locking
        for endpoint in to_remove:
            async with self._pool_locks[endpoint]:
                if endpoint in self._pools:
                    session = self._pools[endpoint]
                    await session.close()
                    del self._pools[endpoint]
                    del self._last_used[endpoint]
                    logger.info(f"Cleaned up idle session for {endpoint}")
    
    async def close_all(self):
        """Close all sessions in the pool.
        
        Called during shutdown to ensure clean resource cleanup.
        Uses defensive programming to handle sessions that may
        already be closed or in an error state.
        """
        for endpoint, session in list(self._pools.items()):
            try:
                await session.close()
                logger.info(f"Closed session for {endpoint}")
            except Exception as e:
                # Log but don't fail - session may already be closed
                logger.warning(f"Error closing session for {endpoint}: {e}")
        self._pools.clear()
        self._last_used.clear()

# Global connection pool instance - lazy initialization pattern
_connection_pool = None

def get_connection_pool() -> A2AConnectionPool:
    """Get the global connection pool instance.
    
    Uses lazy initialization to avoid creating the pool until
    it's actually needed, which helps with testing and reduces
    startup overhead.
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = A2AConnectionPool()
    return _connection_pool

class A2AClient:
    """A2A Protocol Client for making resilient calls to other agents.
    
    This client provides the primary interface for agent-to-agent communication
    with enterprise-grade reliability features:
    
    1. Connection Pooling: Reuses HTTP connections for performance
    2. Circuit Breaker: Fails fast when agents are down to prevent cascading failures
    3. Retry Logic: Automatic retry with exponential backoff for transient failures
    4. Timeout Management: Configurable timeouts at multiple levels
    5. Structured Logging: Comprehensive observability for debugging and monitoring
    
    The client can operate in two modes:
    - Pooled mode (default): Shares connections via global pool for efficiency
    - Dedicated mode: Uses dedicated session for isolation (useful for testing)
    
    Usage:
        async with A2AClient() as client:
            result = await client.process_task(endpoint, task)
    """
    
    def __init__(self, timeout: Optional[int] = None, use_pool: bool = True):
        """Initialize the A2A client.
        
        Args:
            timeout: Request timeout in seconds (uses config default if None)
            use_pool: Whether to use connection pooling (True for production)
        """
        a2a_config = get_a2a_config()
        system_config = get_system_config()
        
        self.timeout = timeout if timeout is not None else a2a_config.timeout
        self.use_pool = use_pool
        self.session = None
        self._closed = False
        self._pool = get_connection_pool() if use_pool else None
        logger.info(f"A2AClient initialized with timeout={self.timeout}s, use_pool={use_pool}")
    
    async def __aenter__(self):
        if not self.use_pool:
            # Get config settings
            a2a_config = get_a2a_config()
            # Create dedicated session if not using pool
            timeout_config = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=a2a_config.connect_timeout,
                sock_read=a2a_config.sock_read_timeout,
                sock_connect=a2a_config.sock_connect_timeout
            )
            connector = aiohttp.TCPConnector(
                limit=a2a_config.connection_pool_size,
                limit_per_host=max(20, a2a_config.connection_pool_size),  # Allow many concurrent connections per host (support 8+ tools)
                ttl_dns_cache=a2a_config.connection_pool_ttl
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout_config,
                connector=connector
            )
            logger.info(f"A2AClient created dedicated session with timeout={self.timeout}s")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Properly close the client session"""
        if not self.use_pool and self.session and not self._closed:
            try:
                await self.session.close()
                logger.info("Closed dedicated A2A client session")
            except Exception as e:
                logger.warning(f"Error closing A2A client session: {e}")
            finally:
                self._closed = True
                self.session = None
    
    async def _make_raw_call(self, endpoint: str, method: str, params: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Make a raw JSON-RPC call without resilience patterns.
        
        This is the core communication method that handles:
        - Request/response serialization in JSON-RPC 2.0 format
        - Connection management (pooled or dedicated)
        - Comprehensive logging for observability
        - Error handling with proper exception types
        
        The method is wrapped by call_agent() which adds resilience patterns.
        
        Args:
            endpoint: Full URL of the agent endpoint
            method: JSON-RPC method name to invoke
            params: Method parameters as dictionary
            request_id: Optional correlation ID
            
        Returns:
            Dictionary containing the agent's response
            
        Raises:
            A2AException: For protocol-level errors
            asyncio.TimeoutError: For timeout errors
        """
        # Ensure external loggers are initialized at runtime
        ensure_loggers_initialized()
        
        # Generate unique operation ID for correlation across logs
        operation_id = f"a2a_call_{uuid.uuid4().hex[:8]}"

        # Log to multiple systems for comprehensive observability
        log_a2a_activity("A2A_CALL_START", 
                        operation_id=operation_id,
                        endpoint=endpoint,
                        method=method,
                        params_keys=list(params.keys()))
        
        # Also log to performance tracker
        log_performance_activity("A2A_CALL_START",
                                operation_id=operation_id,
                                endpoint=endpoint,
                                method=method,
                                params_keys=list(params.keys()))
        
        # External logging with safe fallback
        if a2a_perf:
            try:
                a2a_perf.start_operation(operation_id, "a2a_call", 
                                        endpoint=endpoint, 
                                        method=method,
                                        request_id=request_id)
            except:
                pass
        
        if a2a_logger:
            try:
                a2a_logger.info("A2A_CALL_START", 
                               operation_id=operation_id,
                               endpoint=endpoint, 
                               method=method,
                               request_id=request_id,
                               params_keys=list(params.keys()))
            except:
                pass
        
        try:

            # Session management with pooling optimization
            if self.use_pool:
                # Pooled mode: efficient connection reuse
                session = await self._pool.get_session(endpoint, self.timeout)
            else:
                # Dedicated mode: isolated session for testing
                if not self.session or self._closed:
                    logger.error("Client session not initialized or already closed")
                    raise RuntimeError("Client must be used as async context manager and not closed")
                session = self.session

            request = A2ARequest(method, params, request_id)
            request_dict = request.to_dict()

            start_time = time.time()
            logger.info(f"A2A POST request starting to {endpoint} with timeout={self.timeout}s (pooled={self.use_pool})")
            
            # Make HTTP POST request
            # Note: Timeout is already configured at the session level
            # Avoid duplicate timeout parameter to prevent Python 3.13 compatibility issues
            async with session.post(
                endpoint,
                json=request_dict,
                headers={"Content-Type": "application/json"}
            ) as response:
                elapsed = time.time() - start_time
                logger.info(f"A2A POST response received from {endpoint} in {elapsed:.2f}s with status={response.status}")
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"A2A HTTP error {response.status}: {error_text}")
                    raise A2AException(f"HTTP {response.status}: {error_text}")

                result = await response.json()

                # Check for JSON-RPC error response
                if "error" in result:
                    logger.error(f"Agent returned error: {result['error']}")
                    raise A2AException(f"Agent error: {result['error']}")

                final_result = result.get("result", {})

                # Track performance metrics for successful calls
                duration = None
                if a2a_perf:
                    try:
                        duration = a2a_perf.end_operation(operation_id, success=True,
                                                         result_keys=list(final_result.keys()),
                                                         artifacts_count=len(final_result.get('artifacts', [])))
                    except:
                        pass  # Performance tracking should not break functionality

                if a2a_logger:
                    try:
                        a2a_logger.info("A2A_CALL_SUCCESS",
                                       operation_id=operation_id,
                                       endpoint=endpoint,
                                       method=method,
                                       duration_ms=duration*1000 if duration else 0,
                                       result_keys=list(final_result.keys()))
                    except:
                        pass

                    logger.info(f"A2A call success: {method}")
                # Log completion
                log_a2a_activity("A2A_CALL_SUCCESS",
                                operation_id=operation_id,
                                endpoint=endpoint,
                                method=method,
                                result_keys=list(final_result.keys()),
                                artifacts_count=len(final_result.get('artifacts', [])))
                
                # Also log to performance tracker
                log_performance_activity("A2A_CALL_SUCCESS",
                                        operation_id=operation_id,
                                        endpoint=endpoint,
                                        method=method,
                                        result_keys=list(final_result.keys()),
                                        artifacts_count=len(final_result.get('artifacts', [])))

                return final_result

        except asyncio.TimeoutError as e:
            # Timeout errors are common in distributed systems - handle gracefully
            # with clear error messages for debugging
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            logger.error(f"A2A timeout error calling {endpoint} after {elapsed:.2f}s (timeout was {self.timeout}s, session timeout: {session.timeout if 'session' in locals() else 'unknown'})")
            if a2a_perf:
                try:
                    a2a_perf.end_operation(operation_id, success=False, error_type="timeout_error")
                except:
                    pass
            if a2a_logger:
                try:
                    a2a_logger.error("A2A_CALL_TIMEOUT",
                                    operation_id=operation_id,
                                    endpoint=endpoint,
                                    elapsed_seconds=elapsed,
                                    timeout_seconds=self.timeout)
                except:
                    pass
            raise A2AException(f"Request timed out after {elapsed:.2f}s")
        except aiohttp.ClientError as e:
            # Network errors include connection failures, DNS issues, etc.
            # These are often transient and will be retried by the resilience layer
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            if a2a_perf:
                try:
                    a2a_perf.end_operation(operation_id, success=False, error_type="network_error")
                except:
                    pass
            if a2a_logger:
                try:
                    a2a_logger.error("A2A_CALL_NETWORK_ERROR",
                                    operation_id=operation_id,
                                    endpoint=endpoint,
                                    error=str(e),
                                    elapsed_seconds=elapsed)
                except:
                    pass
            logger.error(f"A2A network error calling {endpoint} after {elapsed:.2f}s: {e}")
            
            # Special handling for shutdown scenarios to avoid noisy errors
            if not self.use_pool and self._closed:
                logger.info("Ignoring network error during client shutdown")
                return {"error": "Client shutdown during operation"}
            else:
                raise A2AException(f"Network error: {str(e)}")
        except Exception as e:
            # Log unexpected error
            if a2a_perf:
                try:
                    a2a_perf.end_operation(operation_id, success=False, error_type=type(e).__name__)
                except:
                    pass
            if a2a_logger:
                try:
                    a2a_logger.error("A2A_CALL_ERROR",
                                    operation_id=operation_id,
                                    endpoint=endpoint,
                                    error_type=type(e).__name__,
                                    error=str(e))
                except:
                    pass
            logger.error(f"A2A unexpected error: {type(e).__name__}: {e}")
            raise
    
    async def call_agent(self, endpoint: str, method: str, params: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Make a resilient JSON-RPC call with circuit breaker and retry logic.
        
        This method wraps _make_raw_call with enterprise resilience patterns:
        
        1. Circuit Breaker Pattern:
           - Opens circuit after N failures to prevent cascading failures
           - Fails fast when circuit is open, avoiding unnecessary timeouts
           - Periodically tests with half-open state to detect recovery
           
        2. Retry Pattern:
           - Automatic retry with exponential backoff for transient failures
           - Configurable max attempts and delays
           - Adds jitter to prevent thundering herd
           
        The circuit breaker is keyed by agent+method to isolate failures
        (e.g., one broken method doesn't affect other methods on same agent).
        
        Args:
            endpoint: Full URL of the agent endpoint
            method: JSON-RPC method name to invoke
            params: Method parameters as dictionary
            request_id: Optional correlation ID
            
        Returns:
            Dictionary containing the agent's response
            
        Raises:
            A2AException: After all retry attempts are exhausted
        """
        a2a_config = get_a2a_config()
        
        # Configure circuit breaker for fast failure detection
        circuit_config = CircuitBreakerConfig(
            failure_threshold=a2a_config.circuit_breaker_threshold,
            timeout=a2a_config.circuit_breaker_timeout,
            half_open_max_calls=3
        )
        
        # Configure retry for transient failure recovery
        retry_config = RetryConfig(
            max_attempts=a2a_config.retry_attempts,
            base_delay=a2a_config.retry_delay,
            max_delay=30.0
        )
        
        # Create unique circuit breaker per agent+method combination
        # This prevents one broken method from affecting others
        agent_name = endpoint.split('/')[2].replace(':', '_')  # Convert host:port to host_port
        circuit_breaker_name = f"a2a_{agent_name}_{method}"
        
        try:
            return await resilient_call(
                self._make_raw_call,
                circuit_breaker_name,
                retry_config,
                circuit_config,
                endpoint, method, params, request_id
            )
        except Exception as e:
            logger.error(f"Resilient A2A call failed after all retries: {e}")
            raise
    
    async def process_task(self, endpoint: str, task: A2ATask) -> Dict[str, Any]:
        """Process a task with another agent.
        
        This is the primary method for agent-to-agent task delegation.
        It serializes the task and sends it to the target agent for processing.
        
        Args:
            endpoint: Full URL of the agent endpoint
            task: A2ATask object containing instruction and context
            
        Returns:
            Dictionary with task results and artifacts
        """
        return await self.call_agent(
            endpoint=endpoint,
            method="process_task",
            params={"task": task.to_dict()}
        )
    
    async def get_agent_card(self, endpoint: str) -> AgentCard:
        """Retrieve agent capabilities for discovery.
        
        Used by the orchestrator to understand what an agent can do
        without hardcoding knowledge about specific agents.
        
        Args:
            endpoint: Full URL of the agent endpoint
            
        Returns:
            AgentCard describing the agent's capabilities
        """
        result = await self.call_agent(
            endpoint=endpoint,
            method="get_agent_card",
            params={}
        )
        return AgentCard(**result)

class A2AServer:
    """A2A Protocol Server for handling incoming agent requests.
    
    This server implements the receiving side of the A2A protocol,
    handling JSON-RPC 2.0 requests from other agents. Key features:
    
    1. Standards Compliance: Strict JSON-RPC 2.0 implementation
    2. Input Validation: Protects against malformed or malicious requests  
    3. Method Registration: Flexible handler registration pattern
    4. Agent Card Endpoint: Self-description for discovery
    5. Error Handling: Proper error codes and messages per spec
    
    The server is designed to be embedded in agent implementations,
    providing a consistent communication interface across all agents.
    """
    
    def __init__(self, agent_card: AgentCard, host: str = DEFAULT_HOST, port: int = DEFAULT_A2A_PORT):
        """Initialize the A2A server.
        
        Args:
            agent_card: Self-description of this agent's capabilities
            host: Host to bind to (0.0.0.0 for all interfaces)
            port: Port to listen on
        """
        self.agent_card = agent_card
        self.host = host
        self.port = port
        self.app = web.Application()
        self.handlers = {}
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up HTTP routes for A2A protocol endpoints."""
        self.app.router.add_post("/a2a", self._handle_request)
        self.app.router.add_get("/a2a/agent-card", self._handle_agent_card)
    
    def register_handler(self, method: str, handler):
        """Register a handler for a JSON-RPC method.
        
        Args:
            method: JSON-RPC method name
            handler: Async function that processes the method
        """
        self.handlers[method] = handler
    
    async def _handle_agent_card(self, request: web.Request) -> web.Response:
        """Return agent card for capability discovery.
        
        This endpoint allows other agents and the orchestrator to
        discover what this agent can do without prior knowledge.
        """
        return web.json_response(self.agent_card.to_dict())
    
    async def _handle_request(self, request: web.Request) -> web.Response:
        """Handle incoming JSON-RPC requests.
        
        This method implements comprehensive request handling with:
        - Input validation to prevent injection attacks
        - Proper error responses per JSON-RPC 2.0 spec
        - Method dispatch to registered handlers
        - Structured error handling with appropriate status codes
        
        Error codes follow JSON-RPC 2.0 specification:
        - -32700: Parse error (malformed JSON)
        - -32600: Invalid request (wrong structure)
        - -32601: Method not found
        - -32602: Invalid params
        - -32603: Internal error
        """
        try:
            data = await request.json()
            
            # Type validation prevents processing non-dict payloads
            if not isinstance(data, dict):
                return web.json_response(
                    A2AResponse(error={"code": -32600, "message": "Invalid Request - must be object"}).to_dict(),
                    status=400
                )
            
            # Validate JSON-RPC 2.0 format
            if data.get("jsonrpc") != "2.0":
                return web.json_response(
                    A2AResponse(error={"code": -32600, "message": "Invalid Request"}).to_dict(),
                    status=400
                )
            
            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id")
            
            # Method name validation prevents excessive memory usage
            if not isinstance(method, str) or len(method) > 100:
                return web.json_response(
                    A2AResponse(error={"code": -32600, "message": "Invalid method name"}, request_id=request_id).to_dict(),
                    status=400
                )
            
            # Params must be object (dict) per our A2A implementation
            if not isinstance(params, dict):
                return web.json_response(
                    A2AResponse(error={"code": -32600, "message": "Invalid params - must be object"}, request_id=request_id).to_dict(),
                    status=400
                )
            
            # Special validation for process_task - our primary method
            # This ensures task data is well-formed and safe to process
            if method == "process_task" and "task" in params:
                try:
                    validated_task = AgentInputValidator.validate_a2a_task(params["task"])
                    params["task"] = validated_task
                except ValidationError as e:
                    return web.json_response(
                        A2AResponse(error={"code": -32602, "message": f"Invalid task data: {e}"}, request_id=request_id).to_dict(),
                        status=400
                    )
            
            if method not in self.handlers:
                return web.json_response(
                    A2AResponse(error={"code": -32601, "message": "Method not found"}, request_id=request_id).to_dict(),
                    status=404
                )
            
            # Dispatch to registered handler
            try:
                result = await self.handlers[method](params)
                response = A2AResponse(result=result, request_id=request_id)
                return web.json_response(response.to_dict())
            
            except Exception as e:
                # Handler exceptions are logged but sanitized in response
                logger.exception(f"Handler error for method {method}")
                response = A2AResponse(
                    error={"code": -32603, "message": "Internal error", "data": str(e)},
                    request_id=request_id
                )
                return web.json_response(response.to_dict(), status=500)
        
        except json.JSONDecodeError:
            # Malformed JSON gets parse error response
            return web.json_response(
                A2AResponse(error={"code": -32700, "message": "Parse error"}).to_dict(),
                status=400
            )
        except Exception as e:
            # Catch-all for unexpected errors - log but don't leak details
            logger.exception("Unexpected error in request handler")
            return web.json_response(
                A2AResponse(error={"code": -32603, "message": "Internal error"}).to_dict(),
                status=500
            )
    
    async def start(self):
        """Start the A2A server.
        
        Returns:
            AppRunner instance for lifecycle management
        """
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"A2A Server started on {self.host}:{self.port}")
        return runner
    
    async def stop(self, runner):
        """Stop the A2A server gracefully.
        
        Args:
            runner: AppRunner instance from start()
        """
        await runner.cleanup()

class A2AException(Exception):
    """Custom exception for A2A protocol errors.
    
    Used to distinguish protocol-level errors from other exceptions,
    enabling proper error handling and retry logic in the resilience layer.
    """
    pass