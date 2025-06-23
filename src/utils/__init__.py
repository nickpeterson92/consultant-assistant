"""Utilities Package.

This package provides cross-cutting concerns and shared functionality used throughout
the multi-agent orchestrator system. It implements enterprise patterns for configuration,
logging, storage, validation, and system messaging.

Core utility modules:
- config: Centralized configuration management with environment variable support
- logging: Structured logging system with distributed tracing capabilities
- storage: Persistence layer with async adapters and memory schemas
- helpers: Message processing and utility functions
- input_validation: Security-focused validation and sanitization
- sys_msg: System message templates for agent communication
- soql_query_builder: Safe SOQL query construction with injection prevention
- events: Event handling and notification patterns

Enterprise features:
- Thread-safe operations with async support
- Comprehensive error handling and recovery
- Performance monitoring and metrics
- Security-first design with input validation
- Modular architecture for easy extension
- Standards compliance (JSON-RPC 2.0, etc.)

The utilities are designed to be reusable across all components while maintaining
loose coupling and high cohesion.
"""