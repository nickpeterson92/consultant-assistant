#!/usr/bin/env python3
"""Entry point for the Jira specialized agent."""

import sys
import os
import asyncio

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from src
from src.agents.jira.main import main

if __name__ == "__main__":
    asyncio.run(main())