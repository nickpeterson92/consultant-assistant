"""Multi-Agent Orchestrator System.

This is the root package for the enterprise-grade multi-agent orchestrator system
that implements cutting-edge 2024 best practices for distributed AI systems,
microservices patterns, and agentic workflows.

The system consists of several core components:
- orchestrator: Central coordination hub managing agent communication via A2A protocol
- agents: Specialized agents (Salesforce, Travel, HR, etc.) with domain expertise
- a2a: Agent-to-Agent protocol implementation for standards-compliant messaging
- tools: Domain-specific tool implementations for agent capabilities
- utils: Cross-cutting concerns including config, logging, storage, and resilience

The architecture follows enterprise patterns including:
- Supervisor architecture with capability-based agent selection
- Microservices pattern with independently deployable agents
- MACH architecture (Microservices, API-first, Cloud-native, Headless)
- Resilience patterns including circuit breakers and connection pooling
"""