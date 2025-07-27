"""Examples of using the enhanced HumanInputTool."""

from typing import Dict, Any
from .human_input import HumanInputTool, InterruptType


async def example_clarification():
    """Example: Asking for clarification on ambiguous request."""
    tool = HumanInputTool()
    
    response = await tool.arun(
        interrupt_type=InterruptType.CLARIFICATION,
        question="Which account did you mean?",
        context={
            "user_request": "Update the Acme account",
            "similar_accounts": [
                {"name": "Acme Corp", "id": "001"},
                {"name": "Acme Inc", "id": "002"},
                {"name": "ACME Ltd", "id": "003"}
            ],
            "suggestion": "Did you mean one of these accounts?"
        }
    )
    return response


async def example_confirmation():
    """Example: Getting confirmation before proceeding."""
    tool = HumanInputTool()
    
    response = await tool.arun(
        interrupt_type=InterruptType.CONFIRMATION,
        question="Should I proceed with creating 5 new contact records?",
        context={
            "action": "create_contacts",
            "count": 5,
            "sample_data": {
                "contact_1": {"name": "John Doe", "email": "john@example.com"},
                "contact_2": {"name": "Jane Smith", "email": "jane@example.com"}
            },
            "note": "This action cannot be easily undone"
        },
        default_value="no",  # Safe default
        timeout_seconds=60
    )
    return response


async def example_selection():
    """Example: User selecting from options."""
    tool = HumanInputTool()
    
    response = await tool.arun(
        interrupt_type=InterruptType.SELECTION,
        question="Which field would you like to update?",
        options=["name", "email", "phone", "address", "all"],
        context={
            "current_record": {
                "name": "John Doe",
                "email": "john.doe@old-email.com",
                "phone": "555-1234",
                "address": "123 Old Street"
            },
            "hint": "Select the field you want to modify"
        }
    )
    return response


async def example_freeform():
    """Example: Getting freeform input with validation."""
    tool = HumanInputTool()
    
    response = await tool.arun(
        interrupt_type=InterruptType.FREEFORM,
        question="Please provide the new email address:",
        context={
            "current_email": "john.doe@example.com",
            "requirements": [
                "Must be a valid email format",
                "Company domains preferred"
            ]
        },
        validation_regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        retry_on_invalid=True
    )
    return response


async def example_approval():
    """Example: Getting explicit approval for critical action."""
    tool = HumanInputTool()
    
    response = await tool.arun(
        interrupt_type=InterruptType.APPROVAL,
        question="Type 'APPROVE' to confirm deletion of 10 records",
        context={
            "action": "bulk_delete",
            "record_count": 10,
            "records_preview": [
                {"id": "001", "name": "Old Record 1"},
                {"id": "002", "name": "Old Record 2"},
                {"id": "003", "name": "Old Record 3"},
                "... and 7 more records"
            ],
            "warning": "This action is PERMANENT and cannot be undone!"
        },
        validation_regex=r"^APPROVE$",
        metadata={
            "severity": "critical",
            "requires_exact_match": True
        }
    )
    return response


async def example_with_state_context():
    """Example: Using state context to provide conversation history."""
    tool = HumanInputTool()
    
    # Simulated state with conversation history
    state = {
        "messages": [
            {"type": "human", "content": "I need to update some accounts"},
            {"type": "assistant", "content": "I can help you update accounts. Which accounts?"},
            {"type": "human", "content": "The tech companies"}
        ],
        "plan": [
            "Search for tech company accounts",
            "Get user confirmation on which accounts to update",
            "Update the selected accounts"
        ],
        "past_steps": ["Search for tech company accounts"],
        "task_id": "task_123"
    }
    
    response = await tool.arun(
        interrupt_type=InterruptType.SELECTION,
        question="Which tech company accounts should I update?",
        options=["Apple Inc", "Microsoft Corp", "Google LLC", "All of them"],
        context={
            "search_results": {
                "total_found": 3,
                "accounts": [
                    {"name": "Apple Inc", "last_updated": "2024-01-15"},
                    {"name": "Microsoft Corp", "last_updated": "2024-02-01"},
                    {"name": "Google LLC", "last_updated": "2023-12-20"}
                ]
            }
        },
        state=state
    )
    return response


# Usage in LangGraph workflow
def create_human_input_node():
    """Example of creating a node that uses human input tool."""
    tool = HumanInputTool()
    
    async def human_clarification_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Node that asks for human clarification when needed."""
        
        # Determine what clarification is needed based on state
        ambiguous_entities = state.get("ambiguous_entities", [])
        
        if ambiguous_entities:
            # Ask user to clarify
            response = await tool.arun(
                interrupt_type=InterruptType.SELECTION,
                question=f"Multiple matches found for '{ambiguous_entities[0]['query']}'. Which one did you mean?",
                options=[entity["name"] for entity in ambiguous_entities[0]["matches"]],
                context={
                    "search_term": ambiguous_entities[0]["query"],
                    "matches": ambiguous_entities[0]["matches"]
                },
                state=state
            )
            
            # Update state with clarification
            return {
                "clarified_entity": response,
                "ambiguous_entities": ambiguous_entities[1:]  # Remove processed ambiguity
            }
        
        return {}
    
    return human_clarification_node