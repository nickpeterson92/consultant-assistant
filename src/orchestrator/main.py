"""Main entry point for the multi-agent orchestrator."""

import os
import asyncio
import time
import uuid
import logging

from src.utils.config import (
    get_conversation_config, get_llm_config, LOCALHOST, SALESFORCE_AGENT_PORT,
    ENTERPRISE_ASSISTANT_BANNER
)
from src.utils.logging import get_logger, init_session_tracking
from src.utils.ui import (
    animated_banner_display, display_capabilities_banner,
    display_categorized_capabilities_banner,
    type_out, format_markdown_for_console, get_empty_input_response
)

from .graph_builder import get_orchestrator_graph, get_agent_registry, get_global_memory_store

# Initialize logger
logger = get_logger()

# ANSI color codes
CYAN = '\033[36m'
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


async def initialize_orchestrator():
    """Initialize orchestrator and discover available agents."""
    logger.info("Initializing Consultant Assistant Orchestrator...", component="orchestrator")
    
    agent_registry = get_agent_registry()
    
    # Clear any existing conversation summaries for fresh start
    try:
        memory_store = get_global_memory_store()
        logger.info("Initialized without clearing summaries - thread-specific summaries preserved", component="orchestrator")
    except Exception as e:
        logger.warning("summary_clear_failed",
            component="system",
            operation="clear_summaries",
            error=str(e),
            error_type=type(e).__name__
        )
    
    logger.info("Checking agent health...", component="orchestrator")
    health_results = await agent_registry.health_check_all_agents()
    
    online_agents = [name for name, status in health_results.items() if status]
    offline_agents = [name for name, status in health_results.items() if not status]
    
    if online_agents:
        logger.info("agents_online",
            component="system",
            operation="agent_discovery",
            agents=online_agents,
            count=len(online_agents)
        )
    if offline_agents:
        logger.warning("agents_offline",
            component="system",
            operation="agent_discovery",
            agents=offline_agents,
            count=len(offline_agents)
        )
    
    # Attempt auto-discovery if no agents registered
    if not agent_registry.list_agents():
        logger.info("No agents registered, attempting auto-discovery...", component="orchestrator")
        discovery_endpoints = [
            f"http://{LOCALHOST}:{SALESFORCE_AGENT_PORT}",  # Salesforce agent
            f"http://{LOCALHOST}:8002",  # Jira agent
            f"http://{LOCALHOST}:8003",  # ServiceNow agent
        ]
        
        discovered = await agent_registry.discover_agents(discovery_endpoints)
        if discovered > 0:
            logger.info("agents_discovered",
                component="system",
                operation="agent_discovery",
                count=discovered
            )
        else:
            logger.warning("No agents discovered - you may need to start specialized agents manually", component="orchestrator")
    
    logger.info("Orchestrator initialization complete", component="orchestrator")


async def handle_command(command: str, command_parts: list, current_thread_id: str, 
                        local_graph, config: dict, active_threads: dict):
    """Handle special commands."""
    conv_config = get_conversation_config()
    global_memory_store = get_global_memory_store()
    
    if command == "/help":
        print("\nAvailable commands:")
        print("  /help         - Show this help message")
        print("  /state        - Show current conversation state")
        print("  /state -v     - Show detailed state with raw data")
        print("  /new          - Start a new conversation thread")
        print("  /list         - List all conversation threads")
        print("  /switch <id>  - Switch to a different thread")
        print("  quit/exit/q   - Exit the orchestrator\n")
        return current_thread_id
    
    elif command == "/state":
        verbose = len(command_parts) > 1 and command_parts[1] == "-v"
        
        print("\n=== Current Conversation State ===")
        try:
            current_state = local_graph.get_state(config)
            
            print(f"Thread ID: {current_thread_id}")
            print(f"User ID: {config.get('configurable', {})['user_id']}")
            
            state_values = None
            if current_state and current_state.values:
                state_values = current_state.values
            else:
                # Try loading from storage
                if global_memory_store:
                    namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                    key = f"state_{current_thread_id}"
                    stored_state = global_memory_store.sync_get(namespace, key)
                    if stored_state and "state" in stored_state:
                        state_values = stored_state["state"]
                        print("[Loaded from storage]")
            
            if state_values:
                print(f"\nMessages: {len(state_values.get('messages', []))}")
                
                summary = state_values.get('summary', 'No summary available')
                if summary and summary != 'No summary available':
                    print(f"\nSummary Preview (first 200 chars):")
                    print(f"  {summary[:200]}...")
                
                memory = state_values.get('memory', {})
                if memory and isinstance(memory, dict):
                    simple_memory = memory.get('SimpleMemory', {})
                    if simple_memory:
                        print(f"\nMemory Contents:")
                        for key, value in simple_memory.items():
                            if isinstance(value, list) and value:
                                print(f"  {key}: {len(value)} items")
                                if verbose and len(value) > 0:
                                    print(f"    First item: {str(value[0])[:100]}...")
                
                # Events have been removed - using simple triggers now
                if "last_summary_trigger" in state_values:
                    print(f"\nLast Summary Trigger: {state_values['last_summary_trigger']}")
                if "last_memory_trigger" in state_values:
                    print(f"Last Memory Trigger: {state_values['last_memory_trigger']}")
                print(f"Tool Calls Since Memory: {state_values.get('tool_calls_since_memory', 0)}")
                print(f"Agent Calls Since Memory: {state_values.get('agent_calls_since_memory', 0)}")
                
                messages = state_values.get('messages', [])
                if messages:
                    last_msg = messages[-1]
                    msg_type = type(last_msg).__name__
                    msg_content = str(getattr(last_msg, 'content', ''))[:100]
                    print(f"\nLast Message ({msg_type}):")
                    print(f"  {msg_content}...")
            else:
                print("\nNo state found for this thread")
        except Exception as e:
            print(f"\nError retrieving state: {str(e)}")
        
        print("\n=== End State ===\n")
        return current_thread_id
    
    elif command == "/new":
        new_thread_id = f"orchestrator-{str(uuid.uuid4())[:8]}"
        print(f"\nStarting new conversation thread: {new_thread_id}")
        active_threads[new_thread_id] = {"created": time.time(), "messages": 0}
        return new_thread_id
    
    elif command == "/list":
        print("\n=== Conversation Threads ===")
        for thread_id, info in active_threads.items():
            marker = " (current)" if thread_id == current_thread_id else ""
            created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['created']))
            msg_count = info.get('messages', 0)
            print(f"  {thread_id}: {msg_count} messages, created {created_time}{marker}")
        print("\n")
        return current_thread_id
    
    elif command == "/switch":
        if len(command_parts) < 2:
            print("Usage: /switch <thread_id>")
            return current_thread_id
        
        target_thread = command_parts[1]
        if target_thread in active_threads:
            print(f"\nSwitched to thread: {target_thread}")
            return target_thread
        else:
            print(f"Thread '{target_thread}' not found. Use /list to see available threads.")
            return current_thread_id
    
    return current_thread_id


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
    """Main CLI interface for the orchestrator."""
    # Setup logging
    init_session_tracking()
    orchestrator_logger = get_logger('orchestrator')
    
    log_level = logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    orchestrator_logger.info("orchestrator_session_start",
                           components=['orchestrator', 'agents', 'a2a'])
    
    # Suppress verbose logging
    for logger_name in [
        'httpx', 'urllib3', 'requests', 'aiohttp', 'simple_salesforce',
        'openai._base_client', 'httpcore', 'httpcore.connection', 'httpcore.http11',
        'src.a2a.circuit_breaker', 'src.utils.config', 'src.orchestrator.agent_registry',
        'src.orchestrator.main', 'src.a2a.protocol'
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Initialize orchestrator
    await initialize_orchestrator()
    
    local_graph = get_orchestrator_graph()
    agent_registry = get_agent_registry()
    global_memory_store = get_global_memory_store()
    
    # Banner display
    conv_config = get_conversation_config()
    
    if conv_config.animated_banner_enabled:
        await animated_banner_display(ENTERPRISE_ASSISTANT_BANNER)
    else:
        print(ENTERPRISE_ASSISTANT_BANNER)
    
    print("\n")
    
    # Display capabilities
    stats = agent_registry.get_registry_stats()
    
    if stats['available_capabilities']:
        await display_categorized_capabilities_banner(stats['available_capabilities'], agent_stats=stats)
    else:
        print("\n╔════════════════════════════════════════╗")
        print("║      No agents currently available     ║")
        print("║    Please check agent configuration    ║")
        print("╚════════════════════════════════════════╝\n")
    
    # Initialize conversation
    current_thread_id = f"orchestrator-{str(uuid.uuid4())[:8]}"
    llm_config = get_llm_config()
    config = {
        "configurable": {"thread_id": current_thread_id, "user_id": conv_config.default_user_id},
        "recursion_limit": llm_config.recursion_limit
    }
    
    active_threads = {current_thread_id: {"created": time.time(), "messages": 0}}
    namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
    thread_list_key = "thread_list"
    
    try:
        if global_memory_store:
            stored_threads = global_memory_store.sync_get(namespace, thread_list_key) or {}
            if "threads" in stored_threads:
                active_threads.update(stored_threads["threads"])
                logger.info("threads_loaded", component="system", thread_count=len(stored_threads["threads"]))
    except Exception as e:
        logger.info("thread_load_error", component="system", error=str(e))
    
    print(f"\nStarting new conversation thread: {current_thread_id}")
    
    # Main conversation loop
    while True:
        try:
            # Get terminal width
            try:
                terminal_width = os.get_terminal_size().columns
            except:
                terminal_width = 80
            
            box_width = min(terminal_width - 2, 160)
            
            # User prompt
            user_label = " USER "
            remaining_width = box_width - len(user_label) - 2
            left_padding = remaining_width // 2
            right_padding = remaining_width - left_padding
            
            print(f"{CYAN}┌─{CYAN}{'─' * left_padding}{user_label}{'─' * right_padding}─┐{RESET}")
            user_input = input(f"{CYAN}│{RESET} ")
            print(f"{CYAN}└{'─' * (box_width - 2)}┘{RESET}")
            
            logger.info("user_input_raw", component="orchestrator", input=user_input[:1000])
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                logger.info("user_quit", component="orchestrator")
                break
            
            # Handle empty input
            if not user_input.strip():
                empty_response = get_empty_input_response()
                print(f"\n{empty_response}\n")
                continue
            
            # Handle special commands
            if user_input.startswith("/"):
                command_parts = user_input.split()
                command = command_parts[0].lower()
                
                new_thread_id = await handle_command(
                    command, command_parts, current_thread_id,
                    local_graph, config, active_threads
                )
                
                if new_thread_id != current_thread_id:
                    current_thread_id = new_thread_id
                    config = {"configurable": {
                        "thread_id": current_thread_id,
                        "user_id": conv_config.default_user_id
                    }}
                continue
            
            # Process conversation
            try:
                terminal_width = os.get_terminal_size().columns
            except:
                terminal_width = 80
            box_width = min(terminal_width - 2, 160)
            
            # Assistant prompt
            assistant_label = " ASSISTANT "
            remaining_width = box_width - len(assistant_label) - 2
            left_padding = remaining_width // 2
            right_padding = remaining_width - left_padding
            
            print(f"{GREEN}╭─{'─' * left_padding}{assistant_label}{'─' * right_padding}─╮{RESET}")
            print(f"{GREEN}│{RESET} ", end="", flush=True)
            
            # Show processing indicator
            import threading
            processing_done = threading.Event()
            current_operation = {"message": "Processing...", "details": ""}
            
            def update_processing_context(message):
                current_operation["message"] = message
            
            indicator_thread = threading.Thread(
                target=show_processing_indicator,
                args=(processing_done, current_operation)
            )
            indicator_thread.daemon = True
            indicator_thread.start()
            
            # Stream response
            conversation_response = None
            response_shown = False
            
            async for event in local_graph.astream(
                {
                    "messages": [{"role": "user", "content": user_input}],
                    "background_operations": [],
                    "background_results": {}
                },
                config,  # type: ignore[arg-type]  # LangGraph accepts dict configs
                stream_mode="values"
            ):
                # Check for tool calls
                if "messages" in event and event["messages"]:
                    last_msg = event["messages"][-1]
                    
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            tool_name = tool_call.get('name', 'Unknown Tool')
                            
                            if 'salesforce' in tool_name.lower():
                                update_processing_context("Connecting to Salesforce")
                            elif 'jira' in tool_name.lower():
                                update_processing_context("Connecting to Jira")
                            elif 'servicenow' in tool_name.lower():
                                update_processing_context("Connecting to ServiceNow")
                            elif 'agent' in tool_name.lower():
                                if 'salesforce' in tool_name.lower():
                                    update_processing_context("Calling Salesforce Agent")
                                elif 'jira' in tool_name.lower():
                                    update_processing_context("Calling Jira Agent")
                                elif 'servicenow' in tool_name.lower():
                                    update_processing_context("Calling ServiceNow Agent")
                                else:
                                    update_processing_context("Synthesizing")
                            else:
                                update_processing_context("Executing Tools")
                
                # Display AI response
                if "messages" in event and event["messages"] and not response_shown:
                    last_msg = event["messages"][-1]
                    if hasattr(last_msg, 'content') and last_msg.content and hasattr(last_msg, 'type'):
                        from langchain_core.messages import AIMessage
                        if isinstance(last_msg, AIMessage) and not getattr(last_msg, 'tool_calls', None):
                            update_processing_context("Generating Response")
                            
                            await asyncio.sleep(0.2)
                            
                            processing_done.set()
                            indicator_thread.join(timeout=1.0)
                            
                            conversation_response = str(last_msg.content) if last_msg.content else ""
                            formatted_response = format_markdown_for_console(conversation_response)
                            logger.info("user_message_displayed", component="orchestrator", 
                                       response=conversation_response[:1000],
                                       full_length=len(conversation_response))
                            
                            # Format response for box display with proper borders
                            lines = formatted_response.split('\n')
                            for i, line in enumerate(lines):
                                if i > 0:  # Add left border for continuation lines
                                    print(f"{GREEN}│{RESET} ", end="", flush=True)
                                
                                # Type out without the automatic newline
                                import sys
                                for char in line:
                                    sys.stdout.write(char)
                                    sys.stdout.flush()
                                    await asyncio.sleep(0.005)
                                
                                if i < len(lines) - 1:  # Add newline except for last line
                                    print()
                            
                            response_shown = True
                            print(f"\n{GREEN}╰{'─' * (box_width - 2)}╯{RESET}")
            
            if not response_shown:
                processing_done.set()
                indicator_thread.join(timeout=1.0)
                print("Processing your request...")
                print(f"\n{GREEN}╰{'─' * (box_width - 2)}╯{RESET}")
            
            # Update thread info
            if current_thread_id in active_threads:
                active_threads[current_thread_id]["messages"] += 1
                active_threads[current_thread_id]["last_accessed"] = time.time()
                
                # Save thread list
                try:
                    if global_memory_store:
                        namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                        thread_list_key = "thread_list"
                        
                        for attempt in range(3):
                            try:
                                existing = global_memory_store.sync_get(namespace, thread_list_key) or {}
                                all_stored_threads = existing.get("threads", {})
                                all_stored_threads[current_thread_id] = active_threads[current_thread_id]
                                
                                global_memory_store.sync_put(namespace, thread_list_key, {
                                    "threads": all_stored_threads,
                                    "updated": time.time()
                                })
                                break
                                
                            except Exception as e:
                                if "readonly database" in str(e) and attempt < 2:
                                    time.sleep(0.1 * (attempt + 1))
                                    continue
                                elif attempt == 2:
                                    logger.debug("thread_list_update_failed", 
                                        component="orchestrator", 
                                        error=str(e),
                                        attempts=attempt + 1,
                                        info="Non-critical - thread list is for UI only"
                                    )
                                    break
                except Exception as e:
                    logger.debug("thread_update_error", 
                        component="orchestrator", 
                        error=str(e),
                        info="Non-critical - thread list is for UI only"
                    )
                        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nInput stream ended. Goodbye!")
            break
        except Exception as e:
            logger.error("main_loop_error",
                component="orchestrator",
                error=str(e),
                error_type=type(e).__name__
            )
            print(f"\nError: {str(e)}")
            print("Please try again or type 'quit' to exit.\n")
    
    # Clean up the global connection pool before exiting
    try:
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()
        logger.info("Closed all A2A connections",
            component="orchestrator",
            operation="connection_pool_cleanup"
        )
    except Exception as e:
        logger.warning(f"Error cleaning up connection pool: {str(e)}",
            component="orchestrator",
            operation="connection_pool_cleanup_error",
            error=str(e),
            error_type=type(e).__name__
        )


if __name__ == "__main__":
    asyncio.run(main())