# callbacks.py


import json
from langchain.callbacks.base import BaseCallbackHandler


class MultipleMatchesCallback(BaseCallbackHandler):
    def __init__(self, memory):
        super().__init__()
        self.memory = memory
        
    def on_tool_start(self, *args, **kwargs):
        """Handle tool start dynamically and log inputs."""
        print(f"DEBUG: on_tool_start called with args: {args} and kwargs: {kwargs}")

        # Check the arguments passed
        if len(args) >= 2:
            tool = args[0]
            inputs = args[1]

            # Handle tool as a dictionary or object
            if isinstance(tool, dict):
                tool_name = tool.get("name", "Unknown Tool")
            else:
                tool_name = getattr(tool, "name", "Unknown Tool")

            print(f"DEBUG: Tool '{tool_name}' started with inputs: {inputs}")
        else:
            print("DEBUG: Insufficient arguments passed to on_tool_start.")

    def on_tool_end(self, output, **kwargs):
        print("DEBUG: Tool execution completed.")
        print(f"DEBUG: Tool output: {output}")
        self.memory.clear()
        print("DEBUG: Cleared memory.")
        if isinstance(output, dict) and "multiple_matches" in output:
            matches = output["multiple_matches"]
            stage = output.get("stage")  # Ensure these are retrieved from output
            amount = output.get("amount")

            context = {
                "matches": matches,
                "stage": stage,
                "amount": amount,
            }
            self.memory.save_context(
                {"input": "Multiple matches found"},
                {"output": json.dumps(context)}
            )
            print("DEBUG: Stored matches and context in memory:", context)
            