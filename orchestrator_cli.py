#!/usr/bin/env python3
"""CLI client for the orchestrator A2A interface - maintains exact same UI as interactive mode."""

import sys
import os
import asyncio
import time
import uuid

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from src.a2a import A2AClient
from src.utils.config import (
    get_conversation_config, ENTERPRISE_ASSISTANT_BANNER
)
from src.utils.ui import (
    animated_banner_display, display_categorized_capabilities_banner,
    type_out, format_markdown_for_console, get_empty_input_response
)
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger('orchestrator')

# ANSI color codes (same as main.py)
CYAN = '\033[36m'
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


def show_processing_indicator(processing_done, current_operation):
    """Show animated spinner with tool call context."""
    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    spinner_colors = [
        '\033[38;5;36m',   # Cyan
        '\033[38;5;37m',   # Light cyan
        '\033[38;5;44m',   # Bright cyan
        '\033[38;5;45m',   # Light bright cyan
        '\033[38;5;51m',   # Very bright cyan
    ]
    
    i = 0
    while not processing_done.is_set():
        color_idx = i % len(spinner_colors)
        frame_idx = i % len(spinner_frames)
        
        operation_msg = current_operation["message"]
        
        spinner_part = f"{spinner_colors[color_idx]}{spinner_frames[frame_idx]}{RESET}"
        display_text = f"{operation_msg}..."
        
        print(f"\r{GREEN}│{RESET} {spinner_part} {display_text}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    
    print(f"\r{GREEN}│{RESET} {' ' * 50}", end="", flush=True)
    print(f"\r{GREEN}│{RESET} ", end="", flush=True)


async def main():
    """Main CLI interface connecting to orchestrator A2A."""
    # Default A2A endpoint
    orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
    
    print(f"Connecting to orchestrator at {orchestrator_url}...")
    
    # Create A2A client
    async with A2AClient() as client:
        # Check if orchestrator is available by getting agent card
        try:
            # Use aiohttp directly for the GET request
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{orchestrator_url}/a2a/agent-card") as response:
                    if response.status == 200:
                        agent_card = await response.json()
                        print(f"Connected to {agent_card.get('name')} v{agent_card.get('version')}")
                        capabilities_count = len(agent_card.get('capabilities', []))
                        print(f"Available capabilities: {capabilities_count}")
                        print()
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")
        except Exception as e:
            print(f"\n❌ Error: Cannot connect to orchestrator at {orchestrator_url}")
            print(f"   {str(e)}")
            print("\nMake sure the orchestrator is running with: python3 orchestrator.py --a2a")
            return
        
        # Banner display (same as main.py)
        conv_config = get_conversation_config()
        
        if conv_config.animated_banner_enabled:
            await animated_banner_display(ENTERPRISE_ASSISTANT_BANNER)
            # The animated banner already displays the final colored banner
            # Just wait a moment before continuing
            await asyncio.sleep(0.5)
        else:
            # Display static banner with colors when animation is disabled
            from src.utils.ui import display_static_banner
            await display_static_banner(ENTERPRISE_ASSISTANT_BANNER)
        
        print("\n")
        
        # Display capabilities banner using the agent card data
        if agent_card.get('capabilities'):
            # Use the full capabilities list for the banner
            all_capabilities = agent_card.get('capabilities', [])
            
            # Extract metadata for agent stats
            metadata = agent_card.get('metadata', {})
            agent_stats = {
                'total_agents': metadata.get('registered_agents', 0),
                'online_agents': metadata.get('online_agents', 0),
                'offline_agents': metadata.get('offline_agents', 0),
                'capabilities_by_agent': metadata.get('capabilities_by_agent', {})
            }
            
            # Debug output to verify data is available but table not showing
            # print(f"Debug: Total capabilities: {len(all_capabilities)}")
            # print(f"Debug: Agent stats: {agent_stats}")
            # print(f"Debug: Capabilities by agent: {agent_stats.get('capabilities_by_agent', {})}")
            
            await display_categorized_capabilities_banner(
                all_capabilities, 
                agent_stats=agent_stats
            )
        else:
            print("\n╔════════════════════════════════════════╗")
            print("║       Multi-Agent Orchestrator         ║")
            print("║         (A2A Network Mode)             ║")
            print("╚════════════════════════════════════════╝\n")
        
        # Initialize conversation
        current_thread_id = f"cli-{str(uuid.uuid4())[:8]}"
        print(f"Starting new conversation thread: {current_thread_id}")
        
        # Main conversation loop (identical to main.py)
        while True:
            try:
                # Get terminal width
                try:
                    terminal_width = os.get_terminal_size().columns
                except:
                    terminal_width = 80
                
                box_width = min(terminal_width - 2, 160)
                
                # User prompt (exact same as main.py)
                user_label = " USER "
                remaining_width = box_width - len(user_label) - 2
                left_padding = remaining_width // 2
                right_padding = remaining_width - left_padding
                
                print(f"{CYAN}┌─{CYAN}{'─' * left_padding}{user_label}{'─' * right_padding}─┐{RESET}")
                user_input = input(f"{CYAN}│{RESET} ")
                print(f"{CYAN}└{'─' * (box_width - 2)}┘{RESET}")
                
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break
                
                # Handle empty input
                if not user_input.strip():
                    empty_response = get_empty_input_response()
                    print(f"\n{empty_response}\n")
                    continue
                
                # Handle special commands (simplified for A2A mode)
                if user_input.startswith("/"):
                    if user_input.lower() == "/help":
                        print("\nAvailable commands:")
                        print("  /help         - Show this help message")
                        print("  quit/exit/q   - Exit the orchestrator\n")
                    else:
                        print("Command not available in A2A client mode.\n")
                    continue
                
                # Assistant prompt (exact same as main.py)
                assistant_label = " ASSISTANT "
                remaining_width = box_width - len(assistant_label) - 2
                left_padding = remaining_width // 2
                right_padding = remaining_width - left_padding
                
                print(f"{GREEN}╭─{'─' * left_padding}{assistant_label}{'─' * right_padding}─╮{RESET}")
                print(f"{GREEN}│{RESET} ", end="", flush=True)
                
                # Show processing indicator
                import threading
                processing_done = threading.Event()
                current_operation = {"message": "Processing"}
                
                indicator_thread = threading.Thread(
                    target=show_processing_indicator,
                    args=(processing_done, current_operation)
                )
                indicator_thread.daemon = True
                indicator_thread.start()
                
                # Send request to orchestrator via A2A
                try:
                    start_time = time.time()
                    
                    result = await client.call_agent(
                        f"{orchestrator_url}/a2a",
                        "process_task",
                        {
                            "task": {
                                "id": f"{current_thread_id}-{int(time.time())}",
                                "instruction": user_input,
                                "context": {
                                    "thread_id": current_thread_id,
                                    "source": "cli_client"
                                }
                            }
                        }
                    )
                    
                    elapsed = time.time() - start_time
                    
                    # Stop processing indicator
                    processing_done.set()
                    indicator_thread.join(timeout=1.0)
                    
                    # Extract and display response
                    if result.get('status') == 'completed':
                        artifacts = result.get('artifacts', [])
                        if artifacts:
                            response_content = artifacts[0].get('content', 'No response content')
                            formatted_response = format_markdown_for_console(response_content)
                            
                            # Type out response (same animation as main.py)
                            lines = formatted_response.split('\n')
                            for i, line in enumerate(lines):
                                if i > 0:  # Add left border for continuation lines
                                    print(f"{GREEN}│{RESET} ", end="", flush=True)
                                
                                # Type out without the automatic newline
                                for char in line:
                                    sys.stdout.write(char)
                                    sys.stdout.flush()
                                    await asyncio.sleep(0.005)
                                
                                if i < len(lines) - 1:  # Add newline except for last line
                                    print()
                        else:
                            print("Task completed successfully")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        print(f"Error: {error_msg}")
                    
                    print(f"\n{GREEN}╰{'─' * (box_width - 2)}╯{RESET}")
                    
                    # Log response time
                    logger.debug(f"Response time: {elapsed:.2f}s")
                    
                except Exception as e:
                    # Stop processing indicator
                    processing_done.set()
                    indicator_thread.join(timeout=1.0)
                    
                    print(f"\r{GREEN}│{RESET} Error: {str(e)}")
                    print(f"\n{GREEN}╰{'─' * (box_width - 2)}╯{RESET}")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nInput stream ended. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
                print("Please try again or type 'quit' to exit.\n")


if __name__ == "__main__":
    asyncio.run(main())