# Agent Registry and Service Discovery Documentation

## Overview

The Agent Registry system implements enterprise-grade service discovery for the multi-agent architecture. It provides dynamic agent registration, health monitoring, capability-based routing, and distributed service management following microservices best practices. The registry serves as the central nervous system that enables agents to find and communicate with each other.

## Architecture

### Service Discovery Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│                    Service Discovery Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐   ┌─────────────────┐   ┌──────────────────┐│
│  │   Service      │   │     Agent       │   │    Capability    ││
│  │ Registration   │   │    Registry     │   │     Matching     ││
│  │                │──>│   (Central)     │──>│                  ││
│  └────────────────┘   └─────────────────┘   └──────────────────┘│
│                                │                                │
│                                ▼                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 Health Monitoring                          │ │
│  ├──────────────────┬──────────────────┬──────────────────────┤ │
│  │  Active Probes   │  Circuit Breaker │   Status Updates     │ │
│  │  (Every 30s)     │   Integration    │   (Real-time)        │ │
│  └──────────────────┴──────────────────┴──────────────────────┘ │
│                                │                                │
│                                ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Service Routing                          ││
│  ├──────────────────┬──────────────────┬───────────────────────┤│
│  │ Load Balancing   │ Failover Logic   │ Performance Metrics   ││
│  └──────────────────┴──────────────────┴───────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Registry Components

1. **Service Registry**: Central repository of agent metadata
2. **Health Monitor**: Active health checking system
3. **Capability Matcher**: Intelligent agent selection
4. **Configuration Manager**: Persistent registry state
5. **Discovery Client**: Agent registration interface

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

## Future Enhancements

1. **Multi-Region Support**: Cross-region service discovery
2. **Service Mesh Integration**: Istio/Linkerd compatibility
3. **Advanced Load Balancing**: ML-based routing decisions
4. **Service Dependencies**: Dependency graph management
5. **Auto-Scaling Integration**: Dynamic capacity management