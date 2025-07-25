"""Cost tracking for LLM usage across all agents and components.

This module provides utilities to track token usage and calculate costs
for various LLM models used in the system.
"""

import tiktoken
from typing import Dict, Any, Optional, List
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("cost_tracking")


class CostTracker:
    """Track LLM usage and costs across the system."""
    
    # Azure OpenAI pricing per 1K tokens (as of 2025)
    # Prices in USD
    MODEL_PRICING = {
        # GPT-4o models
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-2024-05-13": {"input": 0.005, "output": 0.015},
        "gpt-4o-2024-08-06": {"input": 0.0025, "output": 0.01},
        
        # GPT-4o-mini models
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4o-mini-2024-07-18": {"input": 0.00015, "output": 0.0006},
        
        # GPT-4 Turbo models
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4-turbo-2024-04-09": {"input": 0.01, "output": 0.03},
        "gpt-4-1106-preview": {"input": 0.01, "output": 0.03},
        "gpt-4-0125-preview": {"input": 0.01, "output": 0.03},
        
        # GPT-3.5 Turbo models
        "gpt-35-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-35-turbo-16k": {"input": 0.003, "output": 0.004},
        "gpt-35-turbo-0125": {"input": 0.0005, "output": 0.0015},
        "gpt-35-turbo-1106": {"input": 0.001, "output": 0.002},
    }
    
    # Token encoding cache for performance
    _encoders = {}
    
    @classmethod
    def get_encoder(cls, model: str) -> tiktoken.Encoding:
        """Get cached token encoder for a model."""
        if model not in cls._encoders:
            try:
                # Try to get exact encoding for model
                cls._encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for newer models
                cls._encoders[model] = tiktoken.get_encoding("cl100k_base")
        return cls._encoders[model]
    
    @classmethod
    def count_tokens(cls, text: str, model: str = "gpt-4o-mini") -> int:
        """Count tokens in a text string."""
        encoder = cls.get_encoder(model)
        return len(encoder.encode(text))
    
    @classmethod
    def count_message_tokens(cls, messages: List[BaseMessage], model: str = "gpt-4o-mini") -> int:
        """Count tokens in a list of messages.
        
        Based on OpenAI's token counting guide for chat models.
        """
        encoder = cls.get_encoder(model)
        
        # Token overhead per message
        if "gpt-3.5-turbo" in model:
            tokens_per_message = 4  # every message follows <|im_start|>{role/name}\n{content}<|im_end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        else:
            # GPT-4 and newer models
            tokens_per_message = 3
            tokens_per_name = 1
        
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            
            # Count role/type tokens
            if isinstance(message, SystemMessage):
                num_tokens += len(encoder.encode("system"))
            elif isinstance(message, HumanMessage):
                num_tokens += len(encoder.encode("user"))
            elif isinstance(message, AIMessage):
                num_tokens += len(encoder.encode("assistant"))
            elif isinstance(message, ToolMessage):
                num_tokens += len(encoder.encode("tool"))
            
            # Count content tokens
            if hasattr(message, 'content') and message.content:
                num_tokens += len(encoder.encode(str(message.content)))
            
            # Count tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    # Tool name and arguments
                    num_tokens += len(encoder.encode(tool_call.get('name', '')))
                    args_str = str(tool_call.get('args', {}))
                    num_tokens += len(encoder.encode(args_str))
            
            # Count name if present
            if hasattr(message, 'name') and message.name:
                num_tokens += tokens_per_name
                num_tokens += len(encoder.encode(message.name))
        
        # Every reply is primed with <|im_start|>assistant<|im_sep|>
        num_tokens += 3
        
        return num_tokens
    
    @classmethod
    def calculate_cost(cls, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate cost in USD for token usage."""
        # Find the base model name for pricing
        base_model = None
        for model_key in cls.MODEL_PRICING:
            if model_key in model:
                base_model = model_key
                break
        
        if not base_model:
            # Default to gpt-4o-mini pricing if model not found
            logger.warning("cost_model_not_found", 
                          model=model, 
                          defaulting_to="gpt-4o-mini")
            base_model = "gpt-4o-mini"
        
        pricing = cls.MODEL_PRICING[base_model]
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    @classmethod
    def log_llm_usage(
        cls,
        component: str,
        operation: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log LLM usage to the cost tracking log."""
        # Create dedicated cost tracking logger to ensure logs go to cost_tracking.log
        cost_logger = SmartLogger("cost_tracking")
        
        log_entry = {
            "requesting_component": component,  # Renamed to avoid component override
            "operation": operation,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost, 6),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        if metadata:
            log_entry.update(metadata)
        
        # Log to cost_tracking component
        cost_logger.info("llm_usage", **log_entry)
    
    @classmethod
    def track_messages(
        cls,
        messages: List[BaseMessage],
        response: BaseMessage,
        model: str,
        component: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Track token usage and cost for a complete LLM interaction.
        
        Args:
            messages: Input messages sent to LLM
            response: Response message from LLM
            model: Model name/deployment
            component: Component making the call (e.g., "orchestrator", "salesforce")
            operation: Operation being performed (e.g., "plan", "execute", "tool_call")
            metadata: Additional metadata to log
            
        Returns:
            Dict with token counts and cost information
        """
        # Count input tokens
        input_tokens = cls.count_message_tokens(messages, model)
        
        # Count output tokens (just the response)
        output_tokens = cls.count_message_tokens([response], model)
        
        # Calculate cost
        cost = cls.calculate_cost(input_tokens, output_tokens, model)
        
        # Log the usage
        cls.log_llm_usage(
            component=component,
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            metadata=metadata
        )
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost,
            "model": model
        }
    
    @classmethod
    def track_completion(
        cls,
        prompt: str,
        completion: str,
        model: str,
        component: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Track token usage for simple prompt/completion style calls.
        
        Args:
            prompt: Input prompt text
            completion: Output completion text
            model: Model name/deployment
            component: Component making the call
            operation: Operation being performed
            metadata: Additional metadata to log
            
        Returns:
            Dict with token counts and cost information
        """
        # Count tokens
        input_tokens = cls.count_tokens(prompt, model)
        output_tokens = cls.count_tokens(completion, model)
        
        # Calculate cost
        cost = cls.calculate_cost(input_tokens, output_tokens, model)
        
        # Log the usage
        cls.log_llm_usage(
            component=component,
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            metadata=metadata
        )
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost,
            "model": model
        }


class CostAggregator:
    """Aggregate and analyze cost tracking data."""
    
    @staticmethod
    def parse_cost_log(log_path: str) -> List[Dict[str, Any]]:
        """Parse cost tracking log file."""
        import json
        entries = []
        
        try:
            with open(log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get('message') == 'llm_usage':
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            logger.warning("cost_log_not_found", path=log_path)
        
        return entries
    
    @staticmethod
    def aggregate_by_component(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Aggregate costs by component."""
        aggregated = {}
        
        for entry in entries:
            component = entry.get('component', 'unknown')
            if component not in aggregated:
                aggregated[component] = {
                    'total_cost': 0.0,
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'call_count': 0
                }
            
            aggregated[component]['total_cost'] += entry.get('cost_usd', 0)
            aggregated[component]['total_tokens'] += entry.get('total_tokens', 0)
            aggregated[component]['input_tokens'] += entry.get('input_tokens', 0)
            aggregated[component]['output_tokens'] += entry.get('output_tokens', 0)
            aggregated[component]['call_count'] += 1
        
        return aggregated
    
    @staticmethod
    def aggregate_by_model(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Aggregate costs by model."""
        aggregated = {}
        
        for entry in entries:
            model = entry.get('model', 'unknown')
            if model not in aggregated:
                aggregated[model] = {
                    'total_cost': 0.0,
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'call_count': 0
                }
            
            aggregated[model]['total_cost'] += entry.get('cost_usd', 0)
            aggregated[model]['total_tokens'] += entry.get('total_tokens', 0)
            aggregated[model]['input_tokens'] += entry.get('input_tokens', 0)
            aggregated[model]['output_tokens'] += entry.get('output_tokens', 0)
            aggregated[model]['call_count'] += 1
        
        return aggregated
    
    @staticmethod
    def generate_cost_report(log_path: str = "logs/cost_tracking.log") -> str:
        """Generate a human-readable cost report."""
        entries = CostAggregator.parse_cost_log(log_path)
        
        if not entries:
            return "No cost tracking data available."
        
        # Calculate totals
        total_cost = sum(e.get('cost_usd', 0) for e in entries)
        total_tokens = sum(e.get('total_tokens', 0) for e in entries)
        
        # Aggregate by component and model
        by_component = CostAggregator.aggregate_by_component(entries)
        by_model = CostAggregator.aggregate_by_model(entries)
        
        # Build report
        report = []
        report.append("=== LLM Cost Report ===")
        report.append(f"\nTotal Cost: ${total_cost:.4f}")
        report.append(f"Total Tokens: {total_tokens:,}")
        report.append(f"Total API Calls: {len(entries)}")
        
        report.append("\n\n=== Cost by Component ===")
        for component, stats in sorted(by_component.items(), key=lambda x: x[1]['total_cost'], reverse=True):
            report.append(f"\n{component}:")
            report.append(f"  Cost: ${stats['total_cost']:.4f}")
            report.append(f"  Tokens: {stats['total_tokens']:,} (in: {stats['input_tokens']:,}, out: {stats['output_tokens']:,})")
            report.append(f"  Calls: {stats['call_count']}")
            if stats['call_count'] > 0:
                report.append(f"  Avg Cost/Call: ${stats['total_cost']/stats['call_count']:.4f}")
        
        report.append("\n\n=== Cost by Model ===")
        for model, stats in sorted(by_model.items(), key=lambda x: x[1]['total_cost'], reverse=True):
            report.append(f"\n{model}:")
            report.append(f"  Cost: ${stats['total_cost']:.4f}")
            report.append(f"  Tokens: {stats['total_tokens']:,} (in: {stats['input_tokens']:,}, out: {stats['output_tokens']:,})")
            report.append(f"  Calls: {stats['call_count']}")
            if stats['call_count'] > 0:
                report.append(f"  Avg Cost/Call: ${stats['total_cost']/stats['call_count']:.4f}")
        
        return "\n".join(report)