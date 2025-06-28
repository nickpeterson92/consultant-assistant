#!/usr/bin/env python3
"""Workflow Agent - Entry point for running the workflow orchestration agent"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.workflow.main import run_workflow_server


if __name__ == "__main__":
    try:
        asyncio.run(run_workflow_server())
    except KeyboardInterrupt:
        print("\nWorkflow Agent shutting down...")
    except Exception as e:
        print(f"Error running Workflow Agent: {e}")
        sys.exit(1)