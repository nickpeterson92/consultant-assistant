#!/usr/bin/env python3
"""
Main entry point for the ServiceNow Specialized Agent
Handles all ServiceNow ITSM operations via A2A protocol
"""

import sys
import os

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from src.agents.servicenow.main import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())