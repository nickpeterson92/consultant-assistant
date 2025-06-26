#!/usr/bin/env python3
"""
Utility script to start the entire multi-agent system
"""

import os
import sys
import subprocess

# Add project root to path for src imports
sys.path.insert(0, '.')
from src.utils.logging import log_orchestrator_activity

import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor

def consume_output(process, name):
    """Consume process output in a separate thread"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.strip()}")
    except Exception as e:
        print(f"Error reading {name} output: {e}")

def main():
    """Start all components of the multi-agent system"""
    # Setup command-line argument parsing
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator System")
    args = parser.parse_args()
    
    # Log system startup
    
    print("=== Multi-Agent Orchestrator System ===")
    log_orchestrator_activity("SYSTEM_START", components=["orchestrator", "salesforce-agent", "jira-agent", "servicenow-agent"])
    print("Starting specialized agents and orchestrator...")
    print("Press Ctrl+C to stop all components\n")
    
    # Commands to run
    commands = [
        ("python3 salesforce_agent.py --port 8001", "Salesforce-Agent"),
        ("python3 jira_agent.py --port 8002", "Jira-Agent"),
        ("python3 servicenow_agent.py --port 8003", "ServiceNow-Agent"),
        # Add more agents here as they're implemented:
        # ("python3 travel_agent.py --port 8004", "Travel-Agent"),
        # ("python3 expense_agent.py --port 8005", "Expense-Agent"),
    ]
    
    processes = []
    output_threads = []
    
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
            
            time.sleep(2)  # Small delay between starts
        
        print("Waiting for agents to initialize...")
        time.sleep(5)
        
        print("Starting Orchestrator...")
        # Start orchestrator in main thread so we can interact with it
        orchestrator_process = subprocess.Popen(
            "python3 orchestrator.py",
            shell=True,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        # Wait for orchestrator to finish
        orchestrator_process.wait()
        
    except KeyboardInterrupt:
        print("\nShutting down all components...")
    
    finally:
        # Clean up all processes
        for process, name in processes:
            print(f"Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        if 'orchestrator_process' in locals():
            orchestrator_process.terminate()
            try:
                orchestrator_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                orchestrator_process.kill()
        
        print("All components stopped.")
        log_orchestrator_activity("SYSTEM_SHUTDOWN", graceful=True)

if __name__ == "__main__":
    main()