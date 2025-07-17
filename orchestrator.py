#!/usr/bin/env python3
"""Main entry point for the multi-agent orchestrator - A2A mode only."""

import sys
import os
import argparse
import asyncio

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator (A2A Mode)")
    parser.add_argument("--port", type=int, default=8000, help="Port for A2A server (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind A2A server (default: 0.0.0.0)")
    
    args = parser.parse_args()
    
    # Always run in A2A mode
    from src.orchestrator.a2a_main import main as a2a_main
    asyncio.run(a2a_main(args.host, args.port))