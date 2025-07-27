# Human Input Tool

## Overview

The Human Input Tool provides structured interrupt types, validation, error recovery, and comprehensive context management. It's designed to work seamlessly with LangGraph's interrupt mechanism while providing an excellent user experience.

## Key Features

- **Structured Interrupt Types**: Different types for different scenarios (clarification, confirmation, selection, etc.)
- **Response Validation**: Built-in validation for different response types
- **Context Building**: Automatic inclusion of conversation history and state
- **Error Recovery**: Retry logic for invalid inputs
- **Type Safety**: Enum-based interrupt types for better code clarity
- **Observer Integration**: Full tracking of interrupt lifecycle

## Interrupt Types

### CLARIFICATION
Used when the agent needs to clarify ambiguous instructions.

```python
response = await tool.arun(
    interrupt_type=InterruptType.CLARIFICATION,
    question="Which account did you mean?",
    context={"similar_accounts": ["Acme Corp", "Acme Inc", "ACME Ltd"]}
)
```

### CONFIRMATION
Used for yes/no decisions. Automatically normalizes various forms of yes/no.

```python
response = await tool.arun(
    interrupt_type=InterruptType.CONFIRMATION,
    question="Should I proceed with creating 5 new contacts?",
    default_value="no"  # Safe default
)
```

### SELECTION
Used when user needs to choose from a list of options. Supports fuzzy matching.

```python
response = await tool.arun(
    interrupt_type=InterruptType.SELECTION,
    question="Which field would you like to update?",
    options=["name", "email", "phone", "address"]
)
```

### FREEFORM
Used for open-ended input with optional regex validation.

```python
response = await tool.arun(
    interrupt_type=InterruptType.FREEFORM,
    question="Please provide the new email address:",
    validation_regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
```

### APPROVAL
Used for critical actions requiring explicit approval (APPROVE/DENY).

```python
response = await tool.arun(
    interrupt_type=InterruptType.APPROVAL,
    question="Type 'APPROVE' to confirm deletion of 10 records",
    context={"warning": "This action is PERMANENT!"}
)
```

## Usage

Import the tool and interrupt types:

```python
from src.orchestrator.tools import HumanInputTool, InterruptType

tool = HumanInputTool()
response = await tool.arun(
    interrupt_type=InterruptType.SELECTION,
    question="Which account did you mean?",
    options=["Acme Corp", "Acme Inc"],
    timeout_seconds=300
)
```

## Advanced Features

### Context Building

The tool automatically includes relevant context from the state:

- Recent conversation messages
- Current plan and progress
- Completed steps
- Custom context you provide

### Validation

Different interrupt types have built-in validation:

- **CONFIRMATION**: Normalizes yes/no variants
- **SELECTION**: Fuzzy matches against options
- **APPROVAL**: Requires exact APPROVE/DENY
- **FREEFORM**: Optional regex validation

### Error Recovery

The tool can retry on invalid input:

```python
response = await tool.arun(
    interrupt_type=InterruptType.FREEFORM,
    question="Enter phone number:",
    validation_regex=r"^\d{3}-\d{3}-\d{4}$",
    retry_on_invalid=True,  # Will retry up to 3 times
    default_value="000-000-0000"  # Used if all retries fail
)
```

## UI Integration

The structured interrupt types allow UIs to render appropriate interfaces:

- **CLARIFICATION**: Text input with context display
- **CONFIRMATION**: Yes/No buttons
- **SELECTION**: Radio buttons or dropdown
- **FREEFORM**: Text input with validation feedback
- **APPROVAL**: Confirmation dialog with exact match requirement

## Best Practices

1. **Choose the Right Type**: Use the most specific interrupt type for better UX
2. **Provide Context**: Include relevant information to help users make decisions
3. **Set Defaults**: For CONFIRMATION, consider safe defaults
4. **Validate Input**: Use regex for structured data like emails, phones
5. **Handle Errors**: Consider what happens if user provides invalid input

## Examples

See `human_input_examples.py` for comprehensive examples of each interrupt type and advanced usage patterns.