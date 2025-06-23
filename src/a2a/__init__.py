"""Agent2Agent (A2A) Protocol Package.

This package implements the complete A2A protocol for standards-compliant communication
between distributed agents in the multi-agent orchestrator system. It provides the
foundation for inter-agent collaboration using JSON-RPC 2.0 over HTTP with enterprise
resilience patterns.

The A2A protocol enables:
- Stateful task collaboration between agents via A2ATask entities
- Immutable artifact sharing through A2AArtifact objects
- Context and instruction passing with A2AMessage
- Capability discovery using AgentCard specifications
- Connection pooling for efficient resource utilization
- Circuit breaker patterns for fault tolerance

Key components:
- AgentCard: Describes agent capabilities and supported operations
- A2ATask: Represents stateful collaboration entities
- A2AArtifact: Immutable outputs from agent processing
- A2AMessage: Context and instruction containers
- A2AClient: Client-side protocol implementation with pooling
- A2AServer: Server-side protocol handler
"""

from .protocol import (
    AgentCard,
    A2ATask,
    A2AArtifact,
    A2AMessage,
    A2ARequest,
    A2AResponse,
    A2AClient,
    A2AServer,
    A2AException
)

__all__ = [
    "AgentCard",
    "A2ATask", 
    "A2AArtifact",
    "A2AMessage",
    "A2ARequest",
    "A2AResponse",
    "A2AClient",
    "A2AServer",
    "A2AException"
]