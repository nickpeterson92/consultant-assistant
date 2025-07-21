#!/usr/bin/env python3
"""Main entry point for the multi-agent orchestrator A2A server."""

import sys
import os
import argparse
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator A2A Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", 
                       help="Host to bind server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port to bind server (default: 8000)")
    
    args = parser.parse_args()
    
    from src.orchestrator.a2a_server import main
    asyncio.run(main(args.host, args.port))