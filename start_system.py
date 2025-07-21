#!/usr/bin/env python3
"""Utility script to start the entire multi-agent system with A2A orchestrator."""

import os
import sys
import subprocess
import time
import argparse
import threading
import signal
import json
import requests
from typing import List, Tuple

# Add project root to path for src imports
sys.path.insert(0, '.')
from src.utils.logging import get_logger

logger = get_logger("system_startup")

def consume_output(process, name):
    """Consume process output in a separate thread"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.strip()}")
    except Exception as e:
        print(f"Error reading {name} output: {e}")


def check_agent_health(host: str, port: int, timeout: int = 5) -> bool:
    """Check if an agent is healthy and responding."""
    try:
        response = requests.get(f"http://{host}:{port}/a2a/agent-card", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_agent_startup(agents: List[Tuple[str, int]], max_wait: int = 30) -> List[str]:
    """Wait for agents to start up and return list of healthy agents."""
    healthy_agents = []
    start_time = time.time()
    
    print("Waiting for agents to become healthy...")
    
    while time.time() - start_time < max_wait:
        current_healthy = []
        for name, port in agents:
            if check_agent_health("localhost", port):
                if name not in healthy_agents:
                    print(f"✅ {name} is healthy on port {port}")
                    healthy_agents.append(name)
                current_healthy.append(name)
        
        # If all agents are healthy, break early
        if len(current_healthy) == len(agents):
            break
            
        time.sleep(2)
    
    # Final status report
    unhealthy_agents = [name for name, _ in agents if name not in healthy_agents]
    if unhealthy_agents:
        print(f"⚠️  Agents not responding: {', '.join(unhealthy_agents)}")
    
    return healthy_agents


def start_orchestrator_a2a(host: str = "0.0.0.0", port: int = 8000) -> subprocess.Popen:
    """Start the orchestrator A2A server."""
    print(f"Starting Orchestrator A2A Server on {host}:{port}...")
    
    orchestrator_process = subprocess.Popen(
        f"python3 orchestrator.py --host {host} --port {port}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    return orchestrator_process


def display_system_status(healthy_agents: List[str], orchestrator_healthy: bool, orchestrator_port: int):
    """Display the current system status."""
    print("\n" + "="*60)
    print("🚀 MULTI-AGENT SYSTEM STATUS")
    print("="*60)
    
    if orchestrator_healthy:
        print(f"✅ Orchestrator A2A Server: http://localhost:{orchestrator_port}")
    else:
        print(f"❌ Orchestrator A2A Server: Not responding")
    
    print(f"\n📊 Agent Status ({len(healthy_agents)} healthy):")
    agent_ports = {"Salesforce-Agent": 8001, "Jira-Agent": 8002, "ServiceNow-Agent": 8003}
    
    for agent_name, port in agent_ports.items():
        if agent_name in healthy_agents:
            print(f"   ✅ {agent_name}: http://localhost:{port}")
        else:
            print(f"   ❌ {agent_name}: Not responding")
    
    print("\n🔗 System Endpoints:")
    if orchestrator_healthy:
        print(f"   • Orchestrator API: http://localhost:{orchestrator_port}/a2a")
        print(f"   • Agent Card: http://localhost:{orchestrator_port}/a2a/agent-card")
    
    print("\n💡 Usage:")
    print("   • Send tasks to orchestrator API")
    print("   • Use Ctrl+C to shutdown all components")
    print("="*60 + "\n")


def main():
    """Start all components of the multi-agent system with A2A orchestrator."""
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator System with A2A")
    parser.add_argument("--orchestrator-host", type=str, default="0.0.0.0",
                       help="Host for orchestrator server (default: 0.0.0.0)")
    parser.add_argument("--orchestrator-port", type=int, default=8000,
                       help="Port for orchestrator server (default: 8000)")
    parser.add_argument("--agent-startup-timeout", type=int, default=30,
                       help="Max seconds to wait for agents to start (default: 30)")
    args = parser.parse_args()
    
    logger.info("system_startup_begin",
                component="system_startup",
                orchestrator_port=args.orchestrator_port)
    
    print("🚀 Multi-Agent Orchestrator System with A2A")
    print("=" * 50)
    print("Starting specialized agents and orchestrator A2A server...")
    print("Press Ctrl+C to stop all components\n")
    
    # Agent configurations (name, port)
    agents = [
        ("Salesforce-Agent", 8001),
        ("Jira-Agent", 8002), 
        ("ServiceNow-Agent", 8003),
    ]
    
    # Commands to run agents
    commands = [
        ("python3 salesforce_agent.py --port 8001", "Salesforce-Agent"),
        ("python3 jira_agent.py --port 8002", "Jira-Agent"),
        ("python3 servicenow_agent.py --port 8003", "ServiceNow-Agent"),
    ]
    
    processes = []
    output_threads = []
    orchestrator_process = None
    
    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start all agent processes
        for command, name in commands:
            print(f"Starting {name}...")
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            processes.append((process, name))
            
            # Start thread to consume output
            output_thread = threading.Thread(
                target=consume_output,
                args=(process, name),
                daemon=True
            )
            output_thread.start()
            output_threads.append(output_thread)
            
            time.sleep(1)  # Small delay between starts
        
        # Wait for agents to become healthy
        healthy_agents = wait_for_agent_startup(agents, args.agent_startup_timeout)
        
        # Start orchestrator A2A server
        orchestrator_process = start_orchestrator_a2a(args.orchestrator_host, args.orchestrator_port)
        
        # Start thread to consume orchestrator output
        orchestrator_thread = threading.Thread(
            target=consume_output,
            args=(orchestrator_process, "Orchestrator"),
            daemon=True
        )
        orchestrator_thread.start()
        
        # Wait a bit for orchestrator to start
        time.sleep(3)
        
        # Check orchestrator health
        orchestrator_healthy = check_agent_health("localhost", args.orchestrator_port, timeout=10)
        
        # Display system status
        display_system_status(healthy_agents, orchestrator_healthy, args.orchestrator_port)
        
        logger.info("system_startup_complete",
                    component="system_startup", 
                    healthy_agents=len(healthy_agents),
                    total_agents=len(agents),
                    orchestrator_healthy=orchestrator_healthy)
        
        # Keep system running
        try:
            while True:
                time.sleep(1)
                # Check if orchestrator process is still alive
                if orchestrator_process.poll() is not None:
                    print("⚠️  Orchestrator process died, shutting down system...")
                    break
        except KeyboardInterrupt:
            pass
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested...")
    except Exception as e:
        print(f"❌ System error: {e}")
        logger.error("system_startup_error", 
                    component="system_startup",
                    error=str(e))
    
    finally:
        print("Shutting down all components...")
        
        # Stop orchestrator first
        if orchestrator_process:
            print("Stopping Orchestrator...")
            orchestrator_process.terminate()
            try:
                orchestrator_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                orchestrator_process.kill()
        
        # Stop all agent processes
        for process, name in processes:
            print(f"Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        print("✅ All components stopped.")
        logger.info("system_shutdown_complete",
                    component="system_startup",
                    graceful=True)

if __name__ == "__main__":
    main()