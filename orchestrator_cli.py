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
logger = get_logger()

# ANSI color codes (same as main.py)
CYAN = '\033[36m'
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


# Progress Display Manager (Observer Pattern)
class ProgressDisplayManager:
    def __init__(self):
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_colors = [
            '\033[38;5;36m',   # Cyan
            '\033[38;5;37m',   # Light cyan
            '\033[38;5;44m',   # Bright cyan
            '\033[38;5;45m',   # Light bright cyan
            '\033[38;5;51m',   # Very bright cyan
        ]
        self.frame_index = 0
        self.current_display_mode = "simple"  # simple, plan, completed
        self.plan_tasks = []
        self.completed_steps = []
        self.failed_steps = []
        self.current_step = ""
        
    def update_from_sse_event(self, event_type, data):
        """Observer method - called by SSE events to update display"""
        if event_type == 'plan_created':
            plan = data.get('plan', {})
            self.plan_tasks = plan.get('tasks', [])
            if len(self.plan_tasks) > 1:
                self.current_display_mode = "plan"
                self._display_plan()
        
        elif event_type == 'task_started':
            task = data.get('task', {})
            self.current_step = task.get('content', '')
            if self.current_display_mode == "plan":
                self._display_plan_progress()
        
        elif event_type == 'task_completed':
            # Handle individual task completion within the plan
            task = data.get('task', {})
            task_content = task.get('content', data.get('content', ''))
            success = data.get('success', False)
            
            if success:
                self.completed_steps.append(task_content)
            else:
                self.failed_steps.append(task_content)
            
            # Update the plan display if we're in plan mode
            if self.current_display_mode == "plan":
                self._display_plan_progress()
        
        elif event_type == 'task_error':
            content = data.get('content', '')
            error = data.get('error', '')
            self.failed_steps.append(f"{content} (Error: {error})")
            if self.current_display_mode == "plan":
                self._display_plan_progress()
        
        elif event_type == 'plan_completed':
            self.current_display_mode = "completed"
            if len(self.plan_tasks) > 1:
                self._display_plan_final()
    
    def _display_plan(self):
        """Display initial plan"""
        print(f"\r{GREEN}│{RESET} {' ' * 50}", end="", flush=True)
        print(f"\r{GREEN}│{RESET} **EXECUTION PLAN**")
        print(f"{GREEN}│{RESET} ")
        for i, task in enumerate(self.plan_tasks, 1):
            task_content = task.get('content', 'Unknown task')
            print(f"{GREEN}│{RESET} [ ] {i}. {task_content}")
        print(f"{GREEN}│{RESET} ")
        print(f"{GREEN}│{RESET} ", end="", flush=True)
    
    def _display_plan_progress(self):
        """Update the existing plan display with current progress"""
        # Clear the existing plan display (go back to the start of the plan)
        num_lines_to_clear = len(self.plan_tasks) + 3  # +3 for header, blank line, and footer
        for _ in range(num_lines_to_clear):
            print(f"\033[F\033[K", end="")  # Move up and clear line
        
        # Redraw the plan with current progress
        print(f"\r{GREEN}│{RESET} **EXECUTION PLAN**")
        print(f"{GREEN}│{RESET} ")
        for i, task in enumerate(self.plan_tasks, 1):
            task_content = task.get('content', 'Unknown task')
            if task_content in self.completed_steps:
                print(f"{GREEN}│{RESET} [✓] {i}. {task_content}")
            elif task_content in [fs.split(' (Error:')[0] for fs in self.failed_steps]:
                print(f"{GREEN}│{RESET} [✗] {i}. {task_content}")
            elif task_content == self.current_step:
                print(f"{GREEN}│{RESET} [→] {i}. {task_content}")
            else:
                print(f"{GREEN}│{RESET} [ ] {i}. {task_content}")
        print(f"{GREEN}│{RESET} ")
        print(f"{GREEN}│{RESET} ", end="", flush=True)
    
    def _display_plan_final(self):
        """Update the existing plan display with final status"""
        # Clear the existing plan display (go back to the start of the plan)
        num_lines_to_clear = len(self.plan_tasks) + 3  # +3 for header, blank line, and footer
        for _ in range(num_lines_to_clear):
            print(f"\033[F\033[K", end="")  # Move up and clear line
        
        # Redraw the plan with final status
        print(f"\r{GREEN}│{RESET} **PLAN COMPLETED**")
        print(f"{GREEN}│{RESET} ")
        for i, task in enumerate(self.plan_tasks, 1):
            task_content = task.get('content', 'Unknown task')
            if task_content in self.completed_steps:
                print(f"{GREEN}│{RESET} [✓] {i}. {task_content}")
            elif task_content in [fs.split(' (Error:')[0] for fs in self.failed_steps]:
                print(f"{GREEN}│{RESET} [✗] {i}. {task_content}")
            else:
                print(f"{GREEN}│{RESET} [ ] {i}. {task_content}")
        print(f"{GREEN}│{RESET} ")
        print(f"{GREEN}│{RESET} ", end="", flush=True)
    
    def show_simple_spinner(self, message):
        """Show simple spinner for non-plan tasks"""
        if self.current_display_mode == "simple":
            color_idx = self.frame_index % len(self.spinner_colors)
            frame_idx = self.frame_index % len(self.spinner_frames)
            spinner_part = f"{self.spinner_colors[color_idx]}{self.spinner_frames[frame_idx]}{RESET}"
            print(f"\r{GREEN}│{RESET} {spinner_part} {message}...", end="", flush=True)
            self.frame_index += 1
    
    def clear_display(self):
        """Clear the display area"""
        if self.current_display_mode == "simple":
            print(f"\r{GREEN}│{RESET} {' ' * 50}", end="", flush=True)
            print(f"\r{GREEN}│{RESET} ", end="", flush=True)


async def _stream_request(orchestrator_url, task_data, current_operation, processing_done):
    """Stream request to orchestrator using SSE."""
    import aiohttp
    import json
    
    # Track the final response
    final_response = None
    plan_tasks = []
    
    # Get display manager from current operation (passed by main function)
    display_manager = current_operation.get('display_manager')
    
    try:
        logger.info("sse_stream_request_start",
                   component="client",
                   orchestrator_url=orchestrator_url,
                   task_id=task_data.get("task", {}).get("id", "unknown"))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{orchestrator_url}/a2a/stream",
                json={
                    "jsonrpc": "2.0",
                    "method": "process_task",
                    "params": task_data,
                    "id": "stream_request"
                },
                headers={'Accept': 'text/event-stream'}
            ) as response:
                logger.info("sse_stream_response_received",
                           component="client",
                           status_code=response.status,
                           content_type=response.headers.get('content-type'))
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("sse_stream_request_failed",
                                component="client",
                                status_code=response.status,
                                error_text=error_text)
                    raise Exception(f"HTTP {response.status}: {error_text}")
                
                logger.info("sse_stream_processing_start", component="client")
                
                async for line in response.content:
                    if not line:
                        continue
                    
                    line = line.decode('utf-8').strip()
                    
                    # Parse SSE format
                    if line.startswith('data: '):
                        try:
                            data_json = line[6:]  # Remove 'data: ' prefix
                            event_data = json.loads(data_json)
                            
                            event_type = event_data.get('event')
                            data = event_data.get('data', {})
                            
                            # Log all received events
                            logger.info("sse_event_received",
                                       component="client",
                                       event_type=event_type,
                                       data_keys=list(data.keys()) if data else [],
                                       raw_line=line[:100])  # First 100 chars for debugging
                            
                            if event_type == 'connected':
                                logger.info("sse_connection_established", component="client")
                                
                            elif event_type == 'plan_created':
                                plan = data.get('plan', {})
                                plan_tasks = plan.get('tasks', [])
                                
                                # Update current operation to show plan
                                current_operation['use_progressive'] = True
                                current_operation['current_step'] = "Plan created"
                                current_operation['plan_tasks'] = plan_tasks
                                
                                # Use display manager (Observer pattern)
                                if display_manager:
                                    logger.info("display_manager_update_plan_created",
                                               component="client",
                                               plan_task_count=len(plan_tasks),
                                               display_mode=display_manager.current_display_mode)
                                    display_manager.update_from_sse_event(event_type, data)
                                else:
                                    logger.error("display_manager_is_none",
                                                component="client",
                                                event_type=event_type)
                                
                                logger.info("plan_created_processed",
                                           component="client",
                                           task_count=len(plan_tasks))
                                
                            elif event_type == 'task_started':
                                task = data.get('task', {})
                                task_content = task.get('content', '')
                                
                                # Update current operation
                                current_operation['current_step'] = f"Executing: {task_content}"
                                
                                # Use display manager (Observer pattern)
                                if display_manager:
                                    display_manager.update_from_sse_event(event_type, data)
                                else:
                                    logger.error("Display manager is None in task_started event")
                                
                                logger.info("task_started_event_processed",
                                           component="client",
                                           task_content=task_content)
                                
                            elif event_type == 'task_completed':
                                task_id = data.get('task_id')
                                success = data.get('success', False)
                                content = data.get('content', '')
                                
                                # Update completed steps
                                if success:
                                    current_operation.setdefault('completed_steps', []).append(content)
                                else:
                                    current_operation.setdefault('failed_steps', []).append(content)
                                
                                # Use display manager (Observer pattern)
                                display_manager.update_from_sse_event(event_type, data)
                                
                                logger.info("task_completed_event_processed",
                                           component="client",
                                           task_content=content,
                                           success=success)
                                
                            elif event_type == 'task_error':
                                task_id = data.get('task_id')
                                error = data.get('error', '')
                                content = data.get('content', '')
                                
                                # Update failed steps
                                current_operation.setdefault('failed_steps', []).append(f"{content} (Error: {error})")
                                
                                # Use display manager (Observer pattern)
                                display_manager.update_from_sse_event(event_type, data)
                                
                                logger.error("task_error_received",
                                            component="client",
                                            task_content=content,
                                            error=error)
                                
                            elif event_type == 'agent_response':
                                # This is the actual response content
                                response_content = data.get('content', '')
                                logger.info("agent_response_received",
                                           component="client",
                                           response_length=len(response_content),
                                           response_preview=response_content[:100])
                                
                                final_response = {
                                    'status': 'completed',
                                    'artifacts': [{
                                        'content': response_content,
                                        'content_type': 'text/plain'
                                    }],
                                    'metadata': {}
                                }
                                
                                logger.info("final_response_set",
                                           component="client",
                                           response_status=final_response['status'])
                                
                                # Clear spinner immediately when response is received
                                processing_done.set()
                                # Clear the spinner display area
                                if display_manager:
                                    display_manager.clear_display()
                                
                            elif event_type == 'summary_generated':
                                # LLM-generated summary is ready
                                summary_content = data.get('summary', '')
                                
                                if summary_content:
                                    logger.info("llm_summary_received",
                                               component="client",
                                               summary_length=len(summary_content),
                                               response_content=summary_content[:200])
                                    
                                    final_response = {
                                        'status': 'completed',
                                        'artifacts': [{
                                            'content': summary_content,
                                            'content_type': 'text/plain'
                                        }],
                                        'metadata': {}
                                    }
                                    
                                    logger.info("final_response_set_from_summary",
                                               component="client",
                                               response_status=final_response['status'])
                                    
                                    # Clear spinner immediately when summary is received
                                    processing_done.set()
                                    # Clear the spinner display area
                                    if display_manager:
                                        display_manager.clear_display()
                                
                            elif event_type == 'plan_completed':
                                current_operation['current_step'] = "All tasks completed"
                                
                                # Extract LLM-generated summary from the completed plan
                                plan = data.get('plan', {})
                                plan_summary = data.get('summary', '')
                                
                                # Use the LLM-generated summary if available, otherwise extract from first task
                                if plan_summary:
                                    response_content = plan_summary
                                    logger.info("llm_summary_extracted_from_plan_completed",
                                               component="client",
                                               response_content=response_content[:200])
                                else:
                                    # Fallback to first task response if no summary
                                    tasks = plan.get('tasks', [])
                                    response_content = "Plan execution completed"
                                    
                                    for task in tasks:
                                        if (task.get('status') == 'completed' and 
                                            task.get('result', {}).get('success') and
                                            'result' in task.get('result', {}) and
                                            'response' in task.get('result', {}).get('result', {})):
                                            response_content = task['result']['result']['response']
                                            break
                                    
                                    logger.info("fallback_response_extracted_from_plan_completed",
                                               component="client",
                                               response_content=response_content[:200])
                                
                                final_response = {
                                    'status': 'completed',
                                    'artifacts': [{
                                        'content': response_content,
                                        'content_type': 'text/plain'
                                    }],
                                    'metadata': {}
                                }
                                
                                logger.info("final_response_set_from_plan_completed",
                                           component="client",
                                           response_status=final_response['status'])
                                
                                # Clear spinner immediately when response is received
                                processing_done.set()
                                # Clear the spinner display area
                                if display_manager:
                                    display_manager.clear_display()
                                
                                # Use display manager (Observer pattern)
                                display_manager.update_from_sse_event(event_type, data)
                                
                                logger.info("plan_execution_completed",
                                           component="client")
                                
                            elif event_type == 'completed' or event_type == 'task_completed':
                                current_operation['current_step'] = "Processing completed"
                                logger.info("task_processing_completed",
                                           component="client")
                                
                            elif event_type == 'error':
                                error_msg = data.get('error', 'Unknown error')
                                final_response = {
                                    'status': 'failed',
                                    'error': error_msg,
                                    'artifacts': [],
                                    'metadata': {}
                                }
                                logger.error("sse_error_received",
                                            component="client",
                                            error_msg=error_msg)
                                
                        except json.JSONDecodeError as e:
                            logger.warning("failed_to_parse_sse_data",
                                          component="client",
                                          line=line[:100],
                                          error=str(e))
                            continue
                            
                        except Exception as e:
                            logger.error("error_processing_sse_event",
                                        component="client",
                                        error=str(e),
                                        error_type=type(e).__name__)
                            continue
    
    except Exception as e:
        logger.error("sse_streaming_error",
                    component="client",
                    error=str(e),
                    error_type=type(e).__name__)
        final_response = {
            'status': 'failed',
            'error': str(e),
            'artifacts': [],
            'metadata': {}
        }
    
    # Return the final response in A2A format
    fallback_response = {
        'status': 'completed',
        'artifacts': [{
            'content': 'Task completed successfully',
            'content_type': 'text/plain'
        }],
        'metadata': {}
    }
    
    result = final_response or fallback_response
    logger.info("sse_stream_request_complete",
               component="client",
               using_fallback=final_response is None,
               result_status=result['status'],
               result_content_preview=result['artifacts'][0]['content'][:100] if result['artifacts'] else "NO_CONTENT")
    
    return result


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
            print(f"\n✗ Error: Cannot connect to orchestrator at {orchestrator_url}")
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
        
        # Track interrupted workflow state
        interrupted_workflow = None
        
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
                
                # Show processing indicator with progress polling
                import threading
                processing_done = threading.Event()
                # Create display manager
                display_manager = ProgressDisplayManager()
                
                current_operation = {
                    "message": "Processing",
                    "current_step": "Processing...",
                    "completed_steps": [],
                    "failed_steps": [],
                    "plan_tasks": [],
                    "use_progressive": False,
                    "display_manager": display_manager
                }
                
                def update_processing_context(message):
                    current_operation["message"] = message
                
                # Start progress polling
                async def poll_progress():
                    """Poll the orchestrator for progress updates"""
                    import aiohttp
                    while not processing_done.is_set():
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.post(f"{orchestrator_url}/a2a", json={
                                    "jsonrpc": "2.0",
                                    "method": "get_progress",
                                    "params": {"thread_id": current_thread_id},
                                    "id": "progress_poll"
                                }) as response:
                                    if response.status == 200:
                                        result = await response.json()
                                        if result.get("result", {}).get("success"):
                                            progress_data = result.get("result", {}).get("data", {})
                                            if progress_data.get("current_step"):
                                                current_operation["use_progressive"] = True
                                                current_operation["current_step"] = progress_data["current_step"]
                                                current_operation["completed_steps"] = progress_data.get("completed_steps", [])
                                                current_operation["failed_steps"] = progress_data.get("failed_steps", [])
                        except Exception:
                            pass  # Ignore polling errors
                        await asyncio.sleep(0.5)  # Poll every 500ms
                
                # Start polling task
                polling_task = asyncio.create_task(poll_progress())
                
                
                # Simple spinner for non-streaming mode
                def simple_spinner():
                    while not processing_done.is_set():
                        display_manager.show_simple_spinner(current_operation["message"])
                        time.sleep(0.1)
                    display_manager.clear_display()
                
                # Start simple spinner thread (will be controlled by SSE events)
                spinner_thread = threading.Thread(target=simple_spinner)
                spinner_thread.daemon = True
                spinner_thread.start()
                
                # Initialize context outside try block
                context = {
                    "thread_id": current_thread_id,
                    "source": "cli_client"
                }
                
                # Send request to orchestrator via SSE streaming
                try:
                    start_time = time.time()
                    
                    # Important: Pass interrupted_workflow in the context
                    if interrupted_workflow:
                        context["interrupted_workflow"] = interrupted_workflow
                    
                    # Use SSE streaming for real-time updates
                    result = await _stream_request(
                        orchestrator_url,
                        {
                            "task": {
                                "id": f"{current_thread_id}-{int(time.time())}",
                                "instruction": user_input,
                                "context": context
                            }
                        },
                        current_operation,
                        processing_done
                    )
                    
                    elapsed = time.time() - start_time
                    
                    # Stop processing indicator and polling
                    processing_done.set()
                    polling_task.cancel()
                    spinner_thread.join(timeout=1.0)
                    
                    # Clear any remaining spinner display
                    print(f"\r{GREEN}│{RESET} {' ' * 50}", end="", flush=True)
                    print(f"\r{GREEN}│{RESET} ", end="", flush=True)
                    
                    # Extract and display response
                    if result.get('status') == 'completed':
                        # Synchronize workflow state from server
                        # Use .get() for safety even though metadata should always be present
                        metadata = result.get('metadata', {})
                        
                        # interrupted_workflow is optional in metadata
                        server_workflow_state = metadata.get('interrupted_workflow')
                        
                        # Update local context to match server state
                        if server_workflow_state:
                            # Workflow is interrupted
                            context['interrupted_workflow'] = server_workflow_state
                            interrupted_workflow = server_workflow_state
                            logger.info("workflow_interrupted",
                                       component="client",
                                       workflow_name=server_workflow_state.get("workflow_name"))
                        else:
                            # Workflow completed or not present - clear from context
                            context.pop('interrupted_workflow', None)
                            interrupted_workflow = None
                            logger.info("workflow_state_cleared",
                                       component="client")
                        
                        artifacts = result.get('artifacts', [])
                        if artifacts:  # Empty list is falsy
                            # Safe to access first artifact since list is non-empty
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
                    elapsed = time.time() - start_time
                    logger.info("response_time_recorded",
                               component="client",
                               response_time=f"{elapsed:.2f}s")
                    
                except Exception as e:
                    # Stop processing indicator and polling
                    processing_done.set()
                    polling_task.cancel()
                    spinner_thread.join(timeout=1.0)
                    
                    # Check if this is a timeout error (from A2A client)
                    is_timeout = isinstance(e, asyncio.TimeoutError) or "timed out" in str(e).lower()
                    
                    # Clear interrupted workflow on timeout to prevent stale context
                    if is_timeout and interrupted_workflow:
                        logger.warning(
                            "Clearing interrupted workflow due to timeout",
                            component="orchestrator",
                            operation="cli_timeout_handler",
                            workflow_name=interrupted_workflow.get("workflow_name"),
                            error=str(e)
                        )
                        interrupted_workflow = None
                        context.pop('interrupted_workflow', None)
                        print(f"\r{GREEN}│{RESET} Request timed out. Workflow context cleared.")
                    elif is_timeout:
                        print(f"\r{GREEN}│{RESET} Request timed out. Please try again.")
                    else:
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