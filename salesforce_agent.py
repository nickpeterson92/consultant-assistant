#!/usr/bin/env python3
"""Entry point for the Salesforce specialized agent."""

import sys
import os

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from src.agents.salesforce.main import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())