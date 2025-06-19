#!/usr/bin/env python3
"""
Main entry point for the Salesforce Specialized Agent
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.salesforce.main import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())