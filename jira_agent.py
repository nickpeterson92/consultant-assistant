#!/usr/bin/env python3
"""Jira Agent Entry Point - Enterprise Issue Tracking and Agile Management.

This script starts the Jira specialized agent that handles all Jira operations
via the A2A protocol. It provides comprehensive issue tracking capabilities
including CRUD operations, search, workflow management, and agile features.

Usage:
    python jira_agent.py [--port PORT] [--host HOST] [-d|--debug]
    
Arguments:
    --port: Port to run the A2A server on (default: 8002)
    --host: Host to bind the A2A server to (default: 0.0.0.0)
    -d, --debug: Enable debug logging

Environment Variables Required:
    JIRA_BASE_URL: Your Jira instance URL (e.g., https://company.atlassian.net)
    JIRA_USER: Your Jira account email
    JIRA_API_TOKEN: Your Jira API token (NOT password)
    
    Plus standard Azure OpenAI variables:
    AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint
    AZURE_OPENAI_API_KEY: Azure OpenAI API key
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from src
from src.agents.jira.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())