# Agent Registry and Service Discovery Documentation

## What is Service Discovery? (For Junior Engineers)

### The Phone Directory Analogy

Imagine you're in a large office building with hundreds of specialists - accountants, lawyers, engineers, designers. When you need help with taxes, you need to:
1. Find out which accountants are available today
2. Know their office numbers and phone extensions
3. Check if they're busy or free to help
4. Choose the best accountant for your specific tax issue

Service discovery in our multi-agent system works exactly like this office directory:
- **Agents** = Office specialists (Salesforce agent, Travel agent, HR agent)
- **Registry** = The building's directory system
- **Health Checks** = Checking if someone is in their office
- **Capabilities** = What each specialist can help with
- **Endpoints** = Office numbers/phone extensions

### Why Do Agents Need Service Discovery?

In traditional software, components are hardcoded to know about each other. But in modern distributed systems:

1. **Dynamic Environment**: Agents can start, stop, or move to different servers
2. **Scalability**: Multiple copies of the same agent might run simultaneously
3. **Resilience**: If one agent fails, others should be found automatically
4. **Flexibility**: New agents can join without changing existing code

Think of it like Uber:
- Without service discovery: You'd need to know every driver's phone number
- With service discovery: The app finds available drivers for you automatically

## Overview

The Agent Registry system implements enterprise-grade service discovery for the multi-agent architecture. It provides dynamic agent registration, health monitoring, capability-based routing, and distributed service management following microservices best practices. The registry serves as the central nervous system that enables agents to find and communicate with each other.

## Architecture

### Service Discovery Patterns

```
┌──────────────────────────────────────────────────────────────────┐
│                    Service Discovery Architecture                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐   ┌─────────────────┐   ┌──────────────────┐ │
│  │   Service      │   │     Agent       │   │    Capability    │ │
│  │ Registration   │   │    Registry     │   │     Matching     │ │
│  │                │──>│   (Central)     │──>│                  │ │
│  └────────────────┘   └─────────────────┘   └──────────────────┘ │
│                                │                                 │
│                                ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                 Health Monitoring                          │  │
│  ├──────────────────┬──────────────────┬──────────────────────┤  │
│  │  Active Probes   │  Circuit Breaker │   Status Updates     │  │
│  │  (Every 30s)     │   Integration    │   (Real-time)        │  │
│  └──────────────────┴──────────────────┴──────────────────────┘  │
│                                │                                 │
│                                ▼                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Service Routing                          │ │
│  ├──────────────────┬──────────────────┬───────────────────────┤ │
│  │ Load Balancing   │ Failover Logic   │ Performance Metrics   │ │
│  └──────────────────┴──────────────────┴───────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Registry Components

1. **Service Registry**: Central repository of agent metadata
2. **Health Monitor**: Active health checking system
3. **Capability Matcher**: Intelligent agent selection
4. **Configuration Manager**: Persistent registry state
5. **Discovery Client**: Agent registration interface

## Step-by-Step Guide: Registering a New Agent

### Prerequisites
1. Your agent must have an A2A endpoint (`/a2a` and `/a2a/agent-card`)
2. The agent must be running and accessible via HTTP
3. You need to know the agent's capabilities

### Quick Registration Example

```python
# Step 1: Create your agent with A2A endpoints
class MyNewAgent:
    def __init__(self):
        self.name = "expense-agent"
        self.capabilities = ["expense_reporting", "receipt_processing"]
        self.description = "Handles expense reports and receipt OCR"
    
    # This endpoint tells others what you can do
    @app.get("/a2a/agent-card")
    async def get_agent_card(self):
        return AgentCard(
            name=self.name,
            description=self.description,
            capabilities=self.capabilities
        )

# Step 2: Register with the orchestrator's registry
from src.orchestrator.agent_registry import AgentRegistry

registry = AgentRegistry()
registry.register_agent(
    name="expense-agent",
    endpoint="http://localhost:8003"  # Where your agent is running
)

# Step 3: Verify registration worked
print(registry.list_agents())
# Output: ['salesforce-agent', 'expense-agent']  ✅ Success!
```

### Manual Registration (for testing)

1. **Edit agent_registry.json directly**:
```json
{
  "agents": [
    {
      "name": "expense-agent",
      "endpoint": "http://localhost:8003",
      "agent_card": {
        "name": "expense-agent",
        "description": "Expense and receipt processing",
        "capabilities": ["expense_reporting", "receipt_processing"]
      },
      "status": "unknown"
    }
  ]
}
```

2. **Restart the orchestrator** to load the new configuration

### Common Registration Mistakes

❌ **Wrong endpoint format**:
```python
# Bad - missing protocol
registry.register_agent("my-agent", "localhost:8003")

# Good - includes http://
registry.register_agent("my-agent", "http://localhost:8003")
```

❌ **Agent not running**:
```python
# This will register but health checks will fail
registry.register_agent("my-agent", "http://localhost:9999")  # Nothing on port 9999!
```

❌ **Missing A2A endpoints**:
```python
# Your agent MUST implement these endpoints:
# GET /a2a/agent-card - Returns what you can do
# POST /a2a - Processes tasks
```

## Service Registration

### Agent Registration Process

```python
class AgentRegistry:
    """Enterprise service registry for multi-agent discovery"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.agents: Dict[str, RegisteredAgent] = {}
        self.config_path = config_path or "agent_registry.json"
        self.client = None
        self._load_config()
    
    def register_agent(
        self,
        name: str,
        endpoint: str,
        agent_card: Optional[AgentCard] = None
    ):
        """Register a service instance with the discovery system"""
        
        if agent_card is None:
            # Auto-discover capabilities if not provided
            agent_card = self._discover_capabilities(endpoint)
        
        registered_agent = RegisteredAgent(
            name=name,
            endpoint=endpoint,
            agent_card=agent_card,
            status="unknown",
            registration_time=datetime.now().isoformat()
        )
        
        self.agents[name] = registered_agent
        
        # Persist to disk for disaster recovery
        self.save_config()
        
        # Log registration event
        log_orchestrator_activity(
            "AGENT_REGISTERED",
            agent_name=name,
            endpoint=endpoint,
            capabilities=agent_card.capabilities
        )
```

### Service Instance Model

```python
@dataclass
class RegisteredAgent:
    """Service record for a registered agent"""
    name: str                               # Unique service identifier
    endpoint: str                          # Service URL
    agent_card: AgentCard                  # Capability manifest
    status: str = "unknown"                # Service health status
    last_health_check: Optional[str] = None # Last health probe time
    registration_time: Optional[str] = None # When service registered
    metrics: Optional[Dict[str, Any]] = None # Performance metrics
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence"""
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "agent_card": self.agent_card.to_dict(),
            "status": self.status,
            "last_health_check": self.last_health_check,
            "registration_time": self.registration_time,
            "metrics": self.metrics
        }
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is currently healthy"""
        return self.status == "online"
    
    @property
    def uptime(self) -> Optional[float]:
        """Calculate service uptime in seconds"""
        if not self.registration_time:
            return None
        
        reg_time = datetime.fromisoformat(self.registration_time)
        return (datetime.now() - reg_time).total_seconds()
```

## Health Checking and Monitoring

### What is Health Checking?

Health checking is like a heartbeat monitor for your agents. The registry regularly "pings" each agent to ensure they're:
- **Alive**: The agent process is running
- **Responsive**: It can handle requests
- **Healthy**: It's not overloaded or erroring

### How Health Checks Work

```python
# Every 30 seconds, the registry does this:
for each registered agent:
    try:
        response = HTTP GET to agent's /a2a/agent-card endpoint
        if response is successful:
            mark agent as "online" ✅
        else:
            mark agent as "error" ❌
    except timeout:
        mark agent as "offline" 🔴
```

### Implementing Health Checks in Your Agent

```python
# Minimal health check endpoint
@app.get("/a2a/agent-card")
async def health_check():
    # Check your agent's health
    if database_connected and not overloaded:
        return AgentCard(...), 200  # Healthy
    else:
        return {"error": "unhealthy"}, 503  # Unhealthy

# Advanced health check with details
@app.get("/health")
async def detailed_health():
    return {
        "status": "healthy",
        "checks": {
            "database": "connected",
            "memory_usage": "45%",
            "active_tasks": 3,
            "uptime_seconds": 3600
        }
    }
```

### Monitoring Agent Status

```python
# Check single agent health
agent = registry.get_agent("salesforce-agent")
print(f"Status: {agent.status}")
print(f"Last checked: {agent.last_health_check}")
print(f"Healthy: {agent.is_healthy}")

# Get system-wide health
stats = registry.get_registry_stats()
print(f"Total agents: {stats['total_agents']}")
print(f"Online agents: {stats['status_distribution']['online']}")
print(f"System availability: {stats['availability_percentage']}%")

# Monitor specific capability availability
salesforce_agents = registry.find_agents_by_capability("salesforce_operations")
online_count = sum(1 for agent in salesforce_agents if agent.is_healthy)
print(f"Salesforce capability: {online_count} agents available")
```

### Health Check Troubleshooting

**Problem: Agent shows as "offline" but is running**
```bash
# Debug steps:
1. Check if agent is really running:
   ps aux | grep salesforce_agent
   
2. Test the health endpoint manually:
   curl http://localhost:8001/a2a/agent-card
   
3. Check firewall/network:
   telnet localhost 8001
   
4. Review agent logs:
   tail -f logs/salesforce_agent.log
```

**Problem: Agent keeps flapping (online → offline → online)**
```python
# Common causes:
1. Agent is overloaded (increase resources)
2. Network issues (check connectivity)
3. Timeout too short (increase health check timeout)

# Solution: Adjust health check settings
config = {
    "health_check_interval": 60,  # Check less frequently
    "health_check_timeout": 15,    # Allow more time
    "failure_threshold": 3         # Require 3 failures before marking offline
}
```

## Health Monitoring

### Active Health Probes

```python
async def health_check_agent(self, agent_name: str) -> bool:
    """Execute health probe for a specific service instance"""
    
    agent = self.get_agent(agent_name)
    if not agent:
        logger.warning(f"Health check failed: agent {agent_name} not in registry")
        return False
    
    start_time = time.time()
    previous_status = agent.status
    
    try:
        # Use shorter timeout for health checks
        from src.utils.config import get_a2a_config
        a2a_config = get_a2a_config()
        
        async with A2AClient(timeout=a2a_config.health_check_timeout) as client:
            # Probe /a2a/agent-card endpoint
            agent_card = await client.get_agent_card(agent.endpoint + "/a2a")
            
            # Update service metadata
            agent.agent_card = agent_card
            agent.status = "online"
            agent.last_health_check = datetime.now().isoformat()
            
            # Track health transition
            duration = time.time() - start_time
            
            if previous_status != "online":
                logger.info(
                    f"Service recovered: {agent_name} "
                    f"({previous_status} -> online) in {duration:.2f}s"
                )
            
            return True
            
    except A2AException as e:
        agent.status = "error"
        duration = time.time() - start_time
        logger.warning(
            f"Health check failed: {agent_name} "
            f"({previous_status} -> error) in {duration:.2f}s: {e}"
        )
        return False
        
    except asyncio.TimeoutError:
        agent.status = "offline"
        duration = time.time() - start_time
        logger.warning(
            f"Health check timeout: {agent_name} "
            f"({previous_status} -> offline) after {duration:.2f}s"
        )
        return False
        
    except Exception as e:
        agent.status = "offline"
        duration = time.time() - start_time
        logger.error(
            f"Health check error: {agent_name} "
            f"({previous_status} -> offline) in {duration:.2f}s: {e}"
        )
        return False
```

### Concurrent Health Monitoring

```python
async def health_check_all_agents(self) -> Dict[str, bool]:
    """Concurrent health monitoring for all service instances"""
    
    if not self.agents:
        logger.info("No agents registered for health checking")
        return {}
    
    logger.info(f"Starting health check for {len(self.agents)} agents")
    start_time = time.time()
    
    # Create concurrent health check tasks
    tasks = []
    for agent_name in self.agents.keys():
        task = asyncio.create_task(
            self.health_check_agent(agent_name),
            name=f"health_check_{agent_name}"
        )
        tasks.append((agent_name, task))
    
    # Wait for all health checks to complete
    results = {}
    for agent_name, task in tasks:
        try:
            results[agent_name] = await task
        except Exception as e:
            logger.error(f"Health check task failed for {agent_name}: {e}")
            results[agent_name] = False
    
    # Persist updated status
    self.save_config()
    
    # Log summary
    duration = time.time() - start_time
    online_count = sum(1 for status in results.values() if status)
    logger.info(
        f"Health check completed in {duration:.2f}s: "
        f"{online_count}/{len(results)} agents online"
    )
    
    return results
```

## How Agents Find Each Other

### The Discovery Process (Simple Example)

When the orchestrator needs to process expense reports:

```python
# 1. User asks: "Process my expense report"
# 2. Orchestrator thinks: "Who can handle expense_reporting?"

# 3. Discovery process:
registry = AgentRegistry()

# Option A: Find by specific capability
expense_agents = registry.find_agents_by_capability("expense_reporting")
print(expense_agents)
# [RegisteredAgent(name='expense-agent', status='online', endpoint='http://localhost:8003')]

# Option B: Smart matching based on task description
best_agent = registry.find_best_agent_for_task("I need to submit my receipts")
print(best_agent.name)  # 'expense-agent'

# 4. Orchestrator sends the task to the discovered agent
response = await send_task_to_agent(best_agent.endpoint, task)
```

### Behind the Scenes: How Discovery Works

```
User Request
    |
    v
Orchestrator: "I need someone who can do X"
    |
    v
Registry: "Let me check my directory..."
    |
    v
[Searches through all registered agents]
    |
    v
Registry: "I found 3 agents that can do X!"
    |
    v
[Filters by health status - only healthy agents]
    |
    v
[Sorts by performance - fastest agent first]
    |
    v
Orchestrator: "Thanks! I'll use the best one"
    |
    v
[Task sent to selected agent]
```

### Practical Discovery Examples

```python
# Example 1: Finding any CRM agent
crm_agents = registry.find_agents_by_capability("crm_management")
if crm_agents:
    selected = crm_agents[0]  # Use first available
    print(f"Found CRM agent: {selected.name} at {selected.endpoint}")

# Example 2: Load balancing between multiple agents
from collections import defaultdict

task_counter = defaultdict(int)

def get_agent_round_robin(capability: str):
    agents = registry.find_agents_by_capability(capability)
    if not agents:
        return None
    
    # Rotate through available agents
    index = task_counter[capability] % len(agents)
    task_counter[capability] += 1
    return agents[index]

# Example 3: Fallback when preferred agent is down
def get_agent_with_fallback(preferred_name: str, capability: str):
    # Try preferred agent first
    preferred = registry.get_agent(preferred_name)
    if preferred and preferred.is_healthy:
        return preferred
    
    # Fallback to any agent with the capability
    print(f"⚠️ {preferred_name} is down, finding alternative...")
    alternatives = registry.find_agents_by_capability(capability)
    return alternatives[0] if alternatives else None
```

## Service Discovery

### Capability-Based Routing

```python
def find_agents_by_capability(self, capability: str) -> List[RegisteredAgent]:
    """Find all agents that provide a specific capability"""
    
    matching_agents = []
    for agent in self.agents.values():
        if capability in agent.agent_card.capabilities:
            matching_agents.append(agent)
    
    # Sort by health status and performance
    return sorted(
        matching_agents,
        key=lambda a: (
            a.status != "online",  # Healthy agents first
            a.metrics.get("avg_response_time", 0) if a.metrics else 0
        )
    )

def find_best_agent_for_task(
    self,
    task_description: str,
    required_capabilities: List[str] = None
) -> Optional[RegisteredAgent]:
    """Intelligent service selection using capability matching"""
    
    # First, try exact capability matching
    if required_capabilities:
        candidates = []
        for agent in self.agents.values():
            if (agent.status == "online" and 
                all(cap in agent.agent_card.capabilities for cap in required_capabilities)):
                candidates.append(agent)
        
        if candidates:
            # Select best performer among capable agents
            return min(
                candidates,
                key=lambda a: a.metrics.get("avg_response_time", float('inf'))
                if a.metrics else float('inf')
            )
    
    # Fallback to keyword matching
    task_lower = task_description.lower()
    for agent in self.agents.values():
        if agent.status == "online":
            # Build searchable keywords from agent metadata
            keywords = [
                cap.lower() for cap in agent.agent_card.capabilities
            ]
            keywords.extend([
                agent.name.lower(),
                agent.agent_card.description.lower()
            ])
            
            # Check for keyword overlap
            if any(keyword in task_lower for keyword in keywords):
                return agent
    
    return None
```

### Load Balancing

```python
class LoadBalancer:
    """Load balancing strategies for service discovery"""
    
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.round_robin_counters = defaultdict(int)
    
    def round_robin_select(
        self,
        capability: str
    ) -> Optional[RegisteredAgent]:
        """Round-robin selection among capable agents"""
        
        agents = self.registry.find_agents_by_capability(capability)
        healthy_agents = [a for a in agents if a.is_healthy]
        
        if not healthy_agents:
            return None
        
        # Round-robin selection
        counter = self.round_robin_counters[capability]
        selected = healthy_agents[counter % len(healthy_agents)]
        self.round_robin_counters[capability] += 1
        
        return selected
    
    def least_connections_select(
        self,
        capability: str
    ) -> Optional[RegisteredAgent]:
        """Select agent with least active connections"""
        
        agents = self.registry.find_agents_by_capability(capability)
        healthy_agents = [a for a in agents if a.is_healthy]
        
        if not healthy_agents:
            return None
        
        # Select agent with minimum active connections
        return min(
            healthy_agents,
            key=lambda a: a.metrics.get("active_connections", 0)
            if a.metrics else 0
        )
    
    def weighted_response_time_select(
        self,
        capability: str
    ) -> Optional[RegisteredAgent]:
        """Select agent based on weighted response times"""
        
        agents = self.registry.find_agents_by_capability(capability)
        healthy_agents = [a for a in agents if a.is_healthy]
        
        if not healthy_agents:
            return None
        
        # Calculate weights (inverse of response time)
        weights = []
        for agent in healthy_agents:
            response_time = (
                agent.metrics.get("avg_response_time", 1000)
                if agent.metrics else 1000
            )
            weights.append(1.0 / max(response_time, 1))  # Avoid division by zero
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(healthy_agents)
        
        weights = [w / total_weight for w in weights]
        selected_idx = random.choices(range(len(healthy_agents)), weights=weights)[0]
        return healthy_agents[selected_idx]
```

## Auto-Discovery

### Network Scanning

```python
async def discover_agents(
    self,
    discovery_endpoints: List[str]
) -> int:
    """Dynamic service discovery from potential endpoints"""
    
    discovered_count = 0
    
    logger.info(f"Starting discovery scan of {len(discovery_endpoints)} endpoints")
    
    # Scan endpoints concurrently
    tasks = [
        self._probe_endpoint(endpoint)
        for endpoint in discovery_endpoints
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for endpoint, result in zip(discovery_endpoints, results):
        if isinstance(result, Exception):
            logger.debug(f"Discovery failed for {endpoint}: {result}")
        elif result:
            discovered_count += 1
            logger.info(f"Discovered agent at {endpoint}")
    
    if discovered_count > 0:
        self.save_config()
        logger.info(f"Discovery complete: {discovered_count} agents found")
    
    return discovered_count

async def _probe_endpoint(self, endpoint: str) -> bool:
    """Probe a single endpoint for agent presence"""
    
    try:
        async with A2AClient(timeout=5) as client:  # Short timeout for discovery
            agent_card = await client.get_agent_card(endpoint + "/a2a")
            
            # Register discovered agent
            self.register_agent(
                name=agent_card.name,
                endpoint=endpoint,
                agent_card=agent_card
            )
            return True
            
    except Exception as e:
        logger.debug(f"No agent found at {endpoint}: {e}")
        return False
```

### DNS-SD Integration

```python
class DNSServiceDiscovery:
    """Integration with DNS Service Discovery (DNS-SD)"""
    
    def __init__(self, domain: str = "local"):
        self.domain = domain
        self.service_type = "_consultant-agent._tcp"
    
    async def discover_via_dns(self) -> List[str]:
        """Discover agents via DNS-SD"""
        
        import aiodns
        
        endpoints = []
        resolver = aiodns.DNSResolver()
        
        try:
            # Query for service instances
            service_name = f"{self.service_type}.{self.domain}."
            answers = await resolver.query(service_name, "PTR")
            
            for answer in answers:
                # Resolve SRV record for each instance
                try:
                    srv_records = await resolver.query(answer.host, "SRV")
                    for srv in srv_records:
                        endpoint = f"http://{srv.host}:{srv.port}"
                        endpoints.append(endpoint)
                except Exception as e:
                    logger.debug(f"Failed to resolve SRV for {answer.host}: {e}")
                    
        except Exception as e:
            logger.warning(f"DNS-SD discovery failed: {e}")
        
        return endpoints
```

## Configuration Management

### Persistent Registry

```python
def save_config(self):
    """Persist registry state for disaster recovery"""
    
    config = {
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "agents": [agent.to_dict() for agent in self.agents.values()]
    }
    
    try:
        # Atomic write to prevent corruption
        temp_path = f"{self.config_path}.tmp"
        with open(temp_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Atomic rename
        os.rename(temp_path, self.config_path)
        
        logger.debug(f"Registry saved: {len(self.agents)} agents")
        
    except Exception as e:
        logger.error(f"Failed to save registry config: {e}")

def _load_config(self):
    """Load persistent service registry from disk"""
    
    if not os.path.exists(self.config_path):
        logger.info("No registry config found, starting with empty registry")
        return
    
    try:
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Validate config version
        version = config.get("version", "unknown")
        if version != "1.0":
            logger.warning(f"Registry config version mismatch: {version}")
        
        # Load agents
        for agent_config in config.get("agents", []):
            try:
                agent_card = AgentCard(**agent_config["agent_card"])
                registered_agent = RegisteredAgent(
                    name=agent_config["name"],
                    endpoint=agent_config["endpoint"],
                    agent_card=agent_card,
                    status=agent_config.get("status", "unknown"),
                    last_health_check=agent_config.get("last_health_check"),
                    registration_time=agent_config.get("registration_time"),
                    metrics=agent_config.get("metrics")
                )
                self.agents[agent_config["name"]] = registered_agent
                
            except Exception as e:
                logger.error(f"Failed to load agent config: {e}")
                continue
        
        logger.info(f"Loaded {len(self.agents)} agents from registry")
        
    except Exception as e:
        logger.error(f"Error loading registry config: {e}")
```

## Metrics and Monitoring

### Service Metrics

```python
def get_registry_stats(self) -> Dict[str, Any]:
    """Service mesh observability metrics"""
    
    total_agents = len(self.agents)
    status_counts = defaultdict(int)
    capability_counts = defaultdict(int)
    
    # Count by status
    for agent in self.agents.values():
        status_counts[agent.status] += 1
        
        # Count capabilities
        for capability in agent.agent_card.capabilities:
            capability_counts[capability] += 1
    
    # Calculate availability metrics
    online_agents = status_counts.get("online", 0)
    availability = (online_agents / total_agents * 100) if total_agents > 0 else 0
    
    # Get performance metrics
    response_times = []
    for agent in self.agents.values():
        if agent.metrics and "avg_response_time" in agent.metrics:
            response_times.append(agent.metrics["avg_response_time"])
    
    avg_response_time = (
        sum(response_times) / len(response_times)
        if response_times else 0
    )
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_agents": total_agents,
        "status_distribution": dict(status_counts),
        "availability_percentage": round(availability, 2),
        "capability_distribution": dict(capability_counts),
        "performance": {
            "avg_response_time_ms": round(avg_response_time, 2),
            "agents_with_metrics": len(response_times)
        },
        "health_check": {
            "last_check": max(
                (agent.last_health_check for agent in self.agents.values() 
                 if agent.last_health_check),
                default=None
            )
        }
    }
```

### Performance Tracking

```python
def update_agent_metrics(
    self,
    agent_name: str,
    response_time: float,
    success: bool
):
    """Update performance metrics for an agent"""
    
    agent = self.get_agent(agent_name)
    if not agent:
        return
    
    if not agent.metrics:
        agent.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "total_response_time": 0,
            "avg_response_time": 0,
            "last_updated": datetime.now().isoformat()
        }
    
    # Update counters
    agent.metrics["total_requests"] += 1
    if success:
        agent.metrics["successful_requests"] += 1
    
    # Update response time average
    agent.metrics["total_response_time"] += response_time
    agent.metrics["avg_response_time"] = (
        agent.metrics["total_response_time"] / agent.metrics["total_requests"]
    )
    
    agent.metrics["last_updated"] = datetime.now().isoformat()
    
    # Persist metrics
    self.save_config()
```

## Integration Patterns

### Kubernetes Service Discovery

```python
class KubernetesDiscovery:
    """Integration with Kubernetes service discovery"""
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self.label_selector = "app=consultant-agent"
    
    async def discover_k8s_agents(self) -> List[str]:
        """Discover agents via Kubernetes API"""
        
        from kubernetes import client, config
        
        try:
            # Load cluster config
            config.load_incluster_config()
            v1 = client.CoreV1Api()
            
            # List services with agent label
            services = v1.list_namespaced_service(
                namespace=self.namespace,
                label_selector=self.label_selector
            )
            
            endpoints = []
            for service in services.items:
                service_name = service.metadata.name
                for port in service.spec.ports:
                    if port.name == "a2a":  # Agent port
                        endpoint = f"http://{service_name}.{self.namespace}:{port.port}"
                        endpoints.append(endpoint)
            
            return endpoints
            
        except Exception as e:
            logger.error(f"Kubernetes discovery failed: {e}")
            return []
```

### Consul Integration

```python
class ConsulDiscovery:
    """Integration with HashiCorp Consul"""
    
    def __init__(self, consul_host: str = "localhost", consul_port: int = 8500):
        self.consul_url = f"http://{consul_host}:{consul_port}"
        self.service_name = "consultant-agent"
    
    async def register_with_consul(
        self,
        agent_name: str,
        endpoint: str,
        health_check_url: str
    ):
        """Register agent with Consul"""
        
        import aiohttp
        
        # Parse endpoint
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        
        registration_data = {
            "ID": agent_name,
            "Name": self.service_name,
            "Address": parsed.hostname,
            "Port": parsed.port,
            "Tags": ["consultant", "agent"],
            "Check": {
                "HTTP": health_check_url,
                "Interval": "30s",
                "Timeout": "10s"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.consul_url}/v1/agent/service/register",
                json=registration_data
            ) as response:
                if response.status == 200:
                    logger.info(f"Registered {agent_name} with Consul")
                else:
                    logger.error(f"Consul registration failed: {response.status}")
    
    async def discover_consul_agents(self) -> List[str]:
        """Discover agents from Consul"""
        
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.consul_url}/v1/health/service/{self.service_name}?passing"
                ) as response:
                    if response.status == 200:
                        services = await response.json()
                        endpoints = []
                        
                        for service in services:
                            service_info = service["Service"]
                            address = service_info["Address"]
                            port = service_info["Port"]
                            endpoint = f"http://{address}:{port}"
                            endpoints.append(endpoint)
                        
                        return endpoints
                    else:
                        logger.error(f"Consul discovery failed: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Consul discovery error: {e}")
            return []
```

## Best Practices

### 1. Service Registration

- Use descriptive, unique service names
- Include comprehensive capability metadata
- Implement graceful shutdown with deregistration
- Provide accurate health check endpoints
- Version your service interfaces

### 2. Health Monitoring

- Set appropriate check intervals (30s standard)
- Use shorter timeouts for health checks (10s)
- Implement circuit breaker integration
- Log health transitions
- Monitor aggregate health metrics

### 3. Service Discovery

- Cache discovery results appropriately
- Implement fallback strategies
- Use load balancing for high availability
- Monitor discovery performance
- Handle service versions gracefully

### 4. Configuration Management

- Persist registry state for disaster recovery
- Use atomic file operations
- Implement configuration validation
- Support hot reloading
- Version your configuration schema

## Common Registry Problems and Solutions

### Problem 1: "Agent Not Found" Errors

**Symptoms**: Orchestrator can't find agents that should exist

```python
# Error message:
"No agent found capable of handling: salesforce_operations"
```

**Solutions**:
```python
# 1. Check if agent is registered
print(registry.list_agents())
# If missing, register it!

# 2. Check agent capabilities
agent = registry.get_agent("salesforce-agent")
print(agent.agent_card.capabilities)
# Make sure it includes the needed capability

# 3. Check agent health
print(f"Agent status: {agent.status}")
# If offline, investigate why

# 4. Force a health check
await registry.health_check_agent("salesforce-agent")
```

### Problem 2: Registration Failures

**Symptoms**: Can't register new agents

```python
# Debug registration issues:
try:
    registry.register_agent("my-agent", "http://localhost:8004")
except Exception as e:
    print(f"Registration failed: {e}")
    
    # Common fixes:
    # 1. Check endpoint format (needs http://)
    # 2. Verify agent is running
    # 3. Test A2A endpoint manually:
    #    curl http://localhost:8004/a2a/agent-card
    # 4. Check for port conflicts
    # 5. Review agent logs for startup errors
```

### Problem 3: Performance Issues

**Symptoms**: Slow agent discovery or routing

```python
# Diagnose performance:
import time

# Test discovery speed
start = time.time()
agents = registry.find_agents_by_capability("salesforce_operations")
print(f"Discovery took: {time.time() - start:.2f}s")

# If slow (>0.1s), try:
# 1. Reduce number of registered agents
# 2. Optimize capability matching
# 3. Enable caching:
registry.enable_discovery_cache(ttl=60)  # Cache for 60 seconds
```

### Problem 4: Inconsistent Agent Selection

**Symptoms**: Same request goes to different agents randomly

```python
# Implement consistent routing:
def get_consistent_agent(task_id: str, capability: str):
    """Always route same task to same agent"""
    agents = registry.find_agents_by_capability(capability)
    if not agents:
        return None
    
    # Use task ID to select agent consistently
    index = hash(task_id) % len(agents)
    return agents[index]

# Or use sticky sessions:
user_agent_map = {}

def get_sticky_agent(user_id: str, capability: str):
    """Keep user with same agent"""
    if user_id in user_agent_map:
        agent = registry.get_agent(user_agent_map[user_id])
        if agent and agent.is_healthy:
            return agent
    
    # Find new agent
    agent = registry.find_best_agent_for_task(capability)
    if agent:
        user_agent_map[user_id] = agent.name
    return agent
```

## Testing Service Discovery

### Unit Tests for Your Registry Integration

```python
import pytest
from src.orchestrator.agent_registry import AgentRegistry

class TestServiceDiscovery:
    def test_agent_registration(self):
        """Test that agents can register successfully"""
        registry = AgentRegistry()
        
        # Register test agent
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:9999"
        )
        
        # Verify registration
        agent = registry.get_agent("test-agent")
        assert agent is not None
        assert agent.endpoint == "http://localhost:9999"
    
    def test_capability_discovery(self):
        """Test finding agents by capability"""
        registry = AgentRegistry()
        
        # Register agents with different capabilities
        registry.register_agent(
            name="crm-agent",
            endpoint="http://localhost:8001",
            agent_card=AgentCard(
                name="crm-agent",
                capabilities=["crm_management", "salesforce_operations"]
            )
        )
        
        # Test discovery
        crm_agents = registry.find_agents_by_capability("crm_management")
        assert len(crm_agents) == 1
        assert crm_agents[0].name == "crm-agent"
    
    def test_health_check_failure_handling(self):
        """Test that offline agents aren't selected"""
        registry = AgentRegistry()
        
        # Register agent
        registry.register_agent("test-agent", "http://localhost:9999")
        
        # Simulate health check failure
        agent = registry.get_agent("test-agent")
        agent.status = "offline"
        
        # Verify offline agents aren't returned
        healthy_agents = registry.find_agents_by_capability("any")
        assert "test-agent" not in [a.name for a in healthy_agents]
```

### Integration Tests

```python
# test_registry_integration.py
import asyncio
import aiohttp

async def test_full_discovery_flow():
    """Test complete service discovery workflow"""
    
    # 1. Start test agent
    test_agent = await start_test_agent(port=9999)
    
    # 2. Register with registry
    registry = AgentRegistry()
    registry.register_agent("test-agent", "http://localhost:9999")
    
    # 3. Wait for health check
    await asyncio.sleep(2)
    await registry.health_check_all_agents()
    
    # 4. Discover agent
    agent = registry.find_best_agent_for_task("test task")
    assert agent is not None
    assert agent.status == "online"
    
    # 5. Send test request
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{agent.endpoint}/a2a",
            json={"instruction": "test"}
        ) as response:
            assert response.status == 200
    
    # Cleanup
    await test_agent.stop()
```

### Manual Testing Checklist

```bash
# 1. Start your agent
python3 my_agent.py --port 8004

# 2. Test A2A endpoint
curl http://localhost:8004/a2a/agent-card
# Should return agent capabilities

# 3. Register with orchestrator
curl -X POST http://localhost:8000/admin/register \
  -d '{"name": "my-agent", "endpoint": "http://localhost:8004"}'

# 4. Check registration
curl http://localhost:8000/admin/agents
# Should list your agent

# 5. Test discovery
curl http://localhost:8000/admin/discover?capability=my_capability
# Should return your agent if it has that capability

# 6. Monitor health
watch -n 5 'curl http://localhost:8000/admin/health'
# Should show agent status updating
```

## Scaling Considerations

### Handling Multiple Agent Instances

```python
# Scenario: Running 3 copies of salesforce-agent for load balancing

# Register each instance with unique name
registry.register_agent("salesforce-agent-1", "http://server1:8001")
registry.register_agent("salesforce-agent-2", "http://server2:8001")
registry.register_agent("salesforce-agent-3", "http://server3:8001")

# Load balancer will distribute requests
load_balancer = LoadBalancer(registry)
for i in range(10):
    agent = load_balancer.round_robin_select("salesforce_operations")
    print(f"Request {i} -> {agent.name}")
# Output: Requests distributed evenly across all 3 instances
```

### Registry High Availability

```python
# Option 1: Primary-Secondary registry
class HARegistry:
    def __init__(self, primary_config: str, secondary_config: str):
        self.primary = AgentRegistry(primary_config)
        self.secondary = AgentRegistry(secondary_config)
    
    def register_agent(self, name: str, endpoint: str):
        # Write to both registries
        self.primary.register_agent(name, endpoint)
        self.secondary.register_agent(name, endpoint)
    
    def find_agents_by_capability(self, capability: str):
        try:
            # Try primary first
            return self.primary.find_agents_by_capability(capability)
        except Exception:
            # Fallback to secondary
            return self.secondary.find_agents_by_capability(capability)

# Option 2: Distributed registry with consensus
# Use etcd, Consul, or Zookeeper for distributed state
```

### Performance at Scale

```python
# Registry optimizations for 100+ agents:

1. Enable caching:
   registry.enable_caching(
       discovery_cache_ttl=60,      # Cache discovery results
       health_cache_ttl=30,         # Cache health status
       capability_index=True        # Index by capability for fast lookup
   )

2. Batch health checks:
   # Instead of checking all agents every 30s,
   # spread checks across the interval
   registry.enable_staggered_health_checks(
       batch_size=10,               # Check 10 agents at a time
       interval_between_batches=3   # Wait 3s between batches
   )

3. Use connection pooling:
   registry.configure_connection_pool(
       max_connections=100,         # Total pool size
       max_per_host=10             # Per-agent connection limit
   )

4. Implement sharding:
   # Split agents across multiple registries by capability
   crm_registry = AgentRegistry("crm_registry.json")
   travel_registry = AgentRegistry("travel_registry.json")
   hr_registry = AgentRegistry("hr_registry.json")
```

### Monitoring at Scale

```python
# Metrics to track as you scale:

1. Discovery latency:
   - p50, p95, p99 response times
   - Cache hit rate
   
2. Health check performance:
   - Time to check all agents
   - Failed check rate
   
3. Registry availability:
   - Uptime percentage
   - Error rate
   
4. Agent distribution:
   - Agents per capability
   - Geographic distribution
   - Load distribution

# Example monitoring setup:
from prometheus_client import Counter, Histogram, Gauge

discovery_duration = Histogram(
    'registry_discovery_duration_seconds',
    'Time spent discovering agents'
)
agent_count = Gauge(
    'registry_agent_count',
    'Number of registered agents',
    ['status']
)
error_count = Counter(
    'registry_errors_total',
    'Total number of registry errors',
    ['operation']
)
```

## Troubleshooting

### Common Issues

1. **Agents Not Appearing in Registry**
   - Check network connectivity
   - Verify A2A endpoint accessibility
   - Review registration logs
   - Confirm agent is running

2. **Health Checks Failing**
   - Verify health check endpoint
   - Check timeout configurations
   - Review circuit breaker status
   - Monitor network latency

3. **Discovery Not Finding Agents**
   - Check discovery endpoint configuration
   - Verify network scanning ranges
   - Review DNS configuration
   - Check service labels/selectors

4. **Poor Load Balancing**
   - Monitor agent performance metrics
   - Check load balancing strategy
   - Review capability matching logic
   - Verify agent capacity limits

## Quick Reference Card

### Essential Commands

```python
# Register an agent
registry.register_agent("my-agent", "http://localhost:8001")

# Find agents by capability
agents = registry.find_agents_by_capability("salesforce_operations")

# Get specific agent
agent = registry.get_agent("salesforce-agent")

# Check agent health
is_healthy = agent.is_healthy

# List all agents
all_agents = registry.list_agents()

# Get system stats
stats = registry.get_registry_stats()

# Force health check
await registry.health_check_agent("salesforce-agent")
```

### Key Files and Locations

```
/src/orchestrator/agent_registry.py  # Registry implementation
/agent_registry.json                 # Persistent registry data
/logs/orchestrator.log              # Registry operations log
/system_config.json                 # Registry configuration
```

### Debugging Tips

1. **Enable debug logging**:
   ```bash
   DEBUG_MODE=true python3 orchestrator.py
   ```

2. **Check registry state**:
   ```python
   print(json.dumps(registry.get_registry_stats(), indent=2))
   ```

3. **Monitor in real-time**:
   ```bash
   tail -f logs/orchestrator.log | grep -E "AGENT_REGISTERED|HEALTH_CHECK"
   ```

4. **Test connectivity**:
   ```bash
   curl -s http://localhost:8001/a2a/agent-card | jq .
   ```

## Future Enhancements

1. **Multi-Region Support**: Cross-region service discovery
2. **Service Mesh Integration**: Istio/Linkerd compatibility
3. **Advanced Load Balancing**: ML-based routing decisions
4. **Service Dependencies**: Dependency graph management
5. **Auto-Scaling Integration**: Dynamic capacity management