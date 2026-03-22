"""
API Clients Module - Generic HTTP client wrappers with retry and logging.

Provides:
- HTTPX-based HTTP client with connection pooling
- Automatic retry logic
- Request/response logging
- Error handling
"""

import httpx
from typing import Dict, Any, Optional, List
from enum import Enum
import json
from utils.logger import get_logger
from core.retry import classify_error_for_routing

logger = get_logger(__name__)


class HTTPMethod(Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"


class APIResponse:
    """Standardized API response."""
    
    def __init__(
        self,
        status_code: int,
        data: Dict[str, Any],
        headers: Dict[str, str],
        raw_text: str = ""
    ):
        """
        Initialize response.
        
        Args:
            status_code: HTTP status code
            data: Parsed response body
            headers: Response headers
            raw_text: Raw response text
        """
        self.status_code = status_code
        self.data = data
        self.headers = headers
        self.raw_text = raw_text
        self.success = 200 <= status_code < 300
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status_code": self.status_code,
            "success": self.success,
            "data": self.data
        }


class APIClient:
    """
    HTTP API client with retry and error handling.
    
    Features:
    - Connection pooling
    - Automatic retries for transient errors
    - Request/response logging
    - Error classification
    """
    
    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize API client.
        
        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            headers: Default headers
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = headers or {}
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=self.default_headers
        )
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL."""
        if endpoint.startswith("http"):
            return endpoint
        return f"{self.base_url}/{endpoint}".replace("//", "/")
    
    def _parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse response body."""
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            else:
                return {"text": response.text}
        except Exception as e:
            logger.warning(f"Response parse error: {str(e)}")
            return {"text": response.text, "parse_error": str(e)}
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """
        GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Request headers
            **kwargs: Additional httpx arguments
            
        Returns:
            APIResponse
        """
        return await self.request(
            HTTPMethod.GET,
            endpoint,
            params=params,
            headers=headers,
            **kwargs
        )
    
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """
        POST request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_body: JSON body
            headers: Request headers
            **kwargs: Additional httpx arguments
            
        Returns:
            APIResponse
        """
        return await self.request(
            HTTPMethod.POST,
            endpoint,
            data=data,
            json_body=json_body,
            headers=headers,
            **kwargs
        )
    
    async def put(
        self,
        endpoint: str,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """
        PUT request.
        
        Args:
            endpoint: API endpoint
            json_body: JSON body
            headers: Request headers
            **kwargs: Additional httpx arguments
            
        Returns:
            APIResponse
        """
        return await self.request(
            HTTPMethod.PUT,
            endpoint,
            json_body=json_body,
            headers=headers,
            **kwargs
        )
    
    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """
        DELETE request.
        
        Args:
            endpoint: API endpoint
            headers: Request headers
            **kwargs: Additional httpx arguments
            
        Returns:
            APIResponse
        """
        return await self.request(
            HTTPMethod.DELETE,
            endpoint,
            headers=headers,
            **kwargs
        )
    
    async def request(
        self,
        method: HTTPMethod,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """
        Generic request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Form data
            json_body: JSON body
            headers: Request headers
            **kwargs: Additional httpx arguments
            
        Returns:
            APIResponse
        """
        url = self._build_url(endpoint)
        merged_headers = {**self.default_headers, **(headers or {})}
        
        # Prepare request kwargs
        request_kwargs = {
            "params": params or {},
            "headers": merged_headers,
            **kwargs
        }
        
        if data:
            request_kwargs["data"] = data
        elif json_body:
            request_kwargs["json"] = json_body
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.request(method.value, url, **request_kwargs)
                
                logger.info(
                    f"API request successful",
                    extra={
                        "method": method.value,
                        "endpoint": endpoint,
                        "status": response.status_code,
                        "attempt": attempt + 1
                    }
                )
                
                return APIResponse(
                    status_code=response.status_code,
                    data=self._parse_response(response),
                    headers=dict(response.headers),
                    raw_text=response.text
                )
            
            except Exception as e:
                last_error = e
                error_type = classify_error_for_routing(str(e))
                
                logger.warning(
                    f"API request failed",
                    extra={
                        "method": method.value,
                        "endpoint": endpoint,
                        "error": str(e),
                        "error_type": error_type,
                        "attempt": attempt + 1
                    }
                )
                
                # Only retry on transient errors
                if error_type != "retry" or attempt == self.max_retries - 1:
                    break
                
                # Exponential backoff: 1s, 2s, 4s
                import asyncio
                await asyncio.sleep(2 ** attempt)
        
        # Return error response
        error_response = {
            "error": str(last_error),
            "error_type": classify_error_for_routing(str(last_error))
        }
        
        logger.error(
            f"API request exhausted retries",
            extra={
                "method": method.value,
                "endpoint": endpoint,
                "error": str(last_error)
            }
        )
        
        return APIResponse(
            status_code=0,
            data=error_response,
            headers={},
            raw_text=str(last_error)
        )
    
    def close(self):
        """Close client connection."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class APIClientPool:
    """Pool of API clients for different services."""
    
    def __init__(self):
        """Initialize client pool."""
        self.clients: Dict[str, APIClient] = {}
    
    def register_client(
        self,
        name: str,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ) -> APIClient:
        """
        Register API client.
        
        Args:
            name: Client name
            base_url: API base URL
            timeout: Request timeout
            max_retries: Max retries
            headers: Default headers
            
        Returns:
            APIClient
        """
        client = APIClient(base_url, timeout, max_retries, headers)
        self.clients[name] = client
        
        logger.info(
            f"API client registered",
            extra={"name": name, "base_url": base_url}
        )
        
        return client
    
    def get_client(self, name: str) -> Optional[APIClient]:
        """Get registered client."""
        return self.clients.get(name)
    
    def close_all(self):
        """Close all clients."""
        for client in self.clients.values():
            client.close()
        self.clients.clear()


# Global client pool
_client_pool: Optional[APIClientPool] = None


def get_api_client_pool() -> APIClientPool:
    """Get or create global API client pool."""
    global _client_pool
    if _client_pool is None:
        _client_pool = APIClientPool()
    return _client_pool
                    return {"status": "error", "message": str(e)}

    def health_check(self):
        try:
            response = requests.get(self.base_url, timeout=self.timeout)
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "code": response.status_code
            }
        except:
            return {"status": "down"}