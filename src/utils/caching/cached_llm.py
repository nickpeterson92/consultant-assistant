"""
Cached LLM Wrapper for Multi-Agent System
Provides transparent caching for Azure OpenAI LLM calls
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union, Iterator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import ChatGeneration, ChatResult

from .llm_cache import get_llm_cache
from ..config import get_llm_config

logger = logging.getLogger(__name__)

class CachedAzureChatOpenAI(AzureChatOpenAI):
    """Azure OpenAI wrapper with intelligent caching"""
    
    def __init__(self, cache_namespace: str = "orchestrator", enable_cache: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.cache_namespace = cache_namespace
        self.enable_cache = enable_cache
        self.cache = get_llm_cache(cache_namespace) if enable_cache else None
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_calls = 0
        self.total_cost_saved = 0.0
        self.total_tokens_saved = 0
    
    def _messages_to_dict(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to dictionary format for caching"""
        dict_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                dict_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                dict_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                dict_messages.append({"role": "system", "content": msg.content})
            else:
                # Fallback for other message types
                dict_messages.append({"role": "user", "content": str(msg.content)})
        return dict_messages
    
    def _estimate_cost_and_tokens(self, messages: List[Dict[str, str]], 
                                 response: str) -> tuple[float, int]:
        """Estimate cost and token count for the request/response"""
        # Simple token estimation (rough approximation)
        input_text = " ".join([msg["content"] for msg in messages])
        input_tokens = len(input_text.split()) * 1.3  # Rough estimate
        output_tokens = len(response.split()) * 1.3
        
        total_tokens = int(input_tokens + output_tokens)
        
        # Cost estimation for GPT-4 (rough rates)
        input_cost = (input_tokens / 1000) * 0.03  # $0.03 per 1K input tokens
        output_cost = (output_tokens / 1000) * 0.06  # $0.06 per 1K output tokens
        total_cost = input_cost + output_cost
        
        return total_cost, total_tokens
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate response with caching"""
        self.total_calls += 1
        
        # If caching is disabled, use parent implementation
        if not self.enable_cache or not self.cache:
            return await super()._agenerate(messages, stop, run_manager, **kwargs)
        
        # Convert messages to dict format for caching
        dict_messages = self._messages_to_dict(messages)
        
        # Prepare cache key parameters
        cache_params = {
            "model": self.model_name or "gpt-4",
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stop": stop,
            **{k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]}
        }
        
        # Try to get from cache
        start_time = time.time()
        cached_response = await self.cache.get(
            messages=dict_messages,
            **cache_params
        )
        
        if cached_response is not None:
            self.cache_hits += 1
            
            # Reconstruct ChatResult from cached response
            if isinstance(cached_response, dict):
                content = cached_response.get("content", "")
                # Estimate savings
                cost_saved, tokens_saved = self._estimate_cost_and_tokens(dict_messages, content)
                self.total_cost_saved += cost_saved
                self.total_tokens_saved += tokens_saved
                
                message = AIMessage(content=content)
                generation = ChatGeneration(message=message)
                result = ChatResult(generations=[generation])
                
                cache_time = time.time() - start_time
                logger.debug(f"Cache hit for {self.cache_namespace}: {cache_time:.3f}s, saved ~${cost_saved:.4f}")
                
                return result
            else:
                # Legacy cache format
                message = AIMessage(content=str(cached_response))
                generation = ChatGeneration(message=message)
                result = ChatResult(generations=[generation])
                
                cache_time = time.time() - start_time
                logger.debug(f"Cache hit (legacy) for {self.cache_namespace}: {cache_time:.3f}s")
                
                return result
        
        # Cache miss - call parent implementation
        self.cache_misses += 1
        llm_start_time = time.time()
        
        result = await super()._agenerate(messages, stop, run_manager, **kwargs)
        
        llm_time = time.time() - llm_start_time
        
        # Cache the response
        if result.generations and len(result.generations) > 0:
            response_content = result.generations[0].message.content
            
            # Estimate cost and tokens
            cost_estimate, token_count = self._estimate_cost_and_tokens(dict_messages, response_content)
            
            # Prepare response for caching
            cache_response = {
                "content": response_content,
                "model": cache_params["model"],
                "timestamp": time.time()
            }
            
            # Cache the response
            await self.cache.put(
                messages=dict_messages,
                response=cache_response,
                cost_estimate=cost_estimate,
                token_count=token_count,
                **cache_params
            )
            
            logger.debug(f"LLM call for {self.cache_namespace}: {llm_time:.3f}s, ~${cost_estimate:.4f}, {token_count} tokens")
        
        return result
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generate with caching"""
        # For sync calls, run the async version in an event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, need to create a new thread
                import concurrent.futures
                
                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self._agenerate(messages, stop, run_manager, **kwargs)
                        )
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._agenerate(messages, stop, run_manager, **kwargs)
                )
        except RuntimeError:
            # No event loop
            return asyncio.run(
                self._agenerate(messages, stop, run_manager, **kwargs)
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get caching statistics for this LLM instance"""
        hit_rate = (self.cache_hits / self.total_calls) if self.total_calls > 0 else 0.0
        
        return {
            "cache_namespace": self.cache_namespace,
            "cache_enabled": self.enable_cache,
            "total_calls": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "total_cost_saved": self.total_cost_saved,
            "total_tokens_saved": self.total_tokens_saved
        }
    
    async def clear_cache(self, confirm: bool = False) -> int:
        """Clear the cache for this LLM instance"""
        if self.cache:
            return await self.cache.clear_cache(confirm=confirm)
        return 0

def create_cached_azure_openai(cache_namespace: str = "default", 
                              enable_cache: bool = None, 
                              **kwargs) -> CachedAzureChatOpenAI:
    """Create a cached Azure OpenAI instance with configuration"""
    
    # Get config
    llm_config = get_llm_config()
    
    # Use config defaults if not specified
    if enable_cache is None:
        enable_cache = llm_config.cache_enabled
    
    # Set up default parameters from config
    default_params = {
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "request_timeout": llm_config.timeout,
    }
    
    # Override with provided kwargs
    default_params.update(kwargs)
    
    return CachedAzureChatOpenAI(
        cache_namespace=cache_namespace,
        enable_cache=enable_cache,
        **default_params
    )