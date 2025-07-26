"""A2A client for making JSON-RPC calls to other agents."""

import json
import uuid
from typing import Dict, Any, Optional
import aiohttp
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("a2a.client")


class A2AClient:
    """Client for making A2A protocol calls to other agents."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize A2A client.
        
        Args:
            base_url: Base URL of the target agent (e.g., http://localhost:8000/a2a)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def call_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a JSON-RPC method on the target agent.
        
        Args:
            method: Method name to call
            params: Parameters for the method
            
        Returns:
            Result from the method call
            
        Raises:
            Exception: If the call fails or returns an error
        """
        request_id = str(uuid.uuid4())
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        logger.debug("a2a_client_request",
                    method=method,
                    request_id=request_id,
                    base_url=self.base_url)
        
        try:
            session = await self._get_session()
            async with session.post(self.base_url, json=payload) as response:
                response_data = await response.json()
                
                # Check for JSON-RPC error
                if "error" in response_data:
                    error = response_data["error"]
                    logger.error("a2a_client_error",
                               method=method,
                               error_code=error.get("code"),
                               error_message=error.get("message"))
                    raise Exception(f"A2A call failed: {error.get('message', 'Unknown error')}")
                
                # Return result
                result = response_data.get("result", {})
                logger.debug("a2a_client_success",
                           method=method,
                           request_id=request_id)
                
                return result
                
        except aiohttp.ClientError as e:
            logger.error("a2a_client_network_error",
                        method=method,
                        error=str(e))
            raise Exception(f"Network error calling {method}: {str(e)}")
        except Exception as e:
            logger.error("a2a_client_unexpected_error",
                        method=method,
                        error=str(e))
            raise
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()