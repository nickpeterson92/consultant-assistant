#!/usr/bin/env python3
"""
Utility script to start the entire multi-agent system
"""

import os
import sys
import subprocess

# Add src to path for centralized logging
sys.path.insert(0, 'src')
from utils.activity_logger import log_multi_agent_activity

import time
import signal
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor

def run_process(command, name):
    """Run a process and handle its output"""
    print(f"Starting {name}...")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream output
        for line in iter(process.stdout.readline, ''):
            print(f"[{name}] {line.strip()}")
        
        process.wait()
        
    except KeyboardInterrupt:
        print(f"Stopping {name}...")
        process.terminate()
        process.wait()
    except Exception as e:
        print(f"Error running {name}: {e}")

def main():
    """Start all components of the multi-agent system"""
    # Setup command-line argument parsing
    parser = argparse.ArgumentParser(description="Consultant Assistant Multi-Agent System")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (detailed logging and no animations)")
    
    args = parser.parse_args()
    DEBUG_MODE = args.debug
    
    # Set environment variable for all child processes
    os.environ['DEBUG_MODE'] = 'true' if DEBUG_MODE else 'false'
    
    print("=== Consultant Assistant Multi-Agent System ===")
    log_multi_agent_activity("SYSTEM_START", components=["orchestrator", "salesforce-agent"])
    print("Starting specialized agents and orchestrator...")
    if DEBUG_MODE:
        print("DEBUG MODE ENABLED - Detailed logging active")
    print("Press Ctrl+C to stop all components\n")
    
    # Commands to run - add debug flag if enabled
    debug_flag = " -d" if DEBUG_MODE else ""
    commands = [
        (f"python3 salesforce_agent.py{debug_flag}", "Salesforce-Agent"),
        # Add more agents here as they're implemented:
        # (f"python3 travel_agent.py{debug_flag}", "Travel-Agent"),
        # (f"python3 expense_agent.py{debug_flag}", "Expense-Agent"),
    ]
    
    processes = []
    
    try:
        # Start all agent processes
        for command, name in commands:
            print(f"Starting {name}...")
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            processes.append((process, name))
            time.sleep(2)  # Small delay between starts
        
        print("Waiting for agents to initialize...")
        time.sleep(5)
        
        print("Starting Orchestrator...")
        # Start orchestrator in main thread so we can interact with it
        orchestrator_process = subprocess.Popen(
            f"python3 orchestrator.py{debug_flag}",
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
        log_multi_agent_activity("SYSTEM_SHUTDOWN", graceful=True)

if __name__ == "__main__":
    main()