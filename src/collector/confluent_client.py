"""Base HTTP client for Confluent Cloud APIs"""
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ConfluentAPIError(Exception):
    """Base exception for Confluent API errors"""
    pass


class ConfluentAPIRateLimitError(ConfluentAPIError):
    """Raised when rate limit is exceeded"""
    pass


class ConfluentAPIAuthError(ConfluentAPIError):
    """Raised when authentication fails"""
    pass


class ConfluentCloudClient:
    """
    Base HTTP client for Confluent Cloud APIs
    
    Provides:
    - Basic authentication with API key/secret
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Request/response logging
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize Confluent Cloud API client
        
        Args:
            api_key: Confluent Cloud API key (defaults to settings)
            api_secret: Confluent Cloud API secret (defaults to settings)
            base_url: Base URL for API (defaults to settings)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.confluent_api_key
        self.api_secret = api_secret or settings.confluent_api_secret
        self.base_url = base_url or settings.confluent_cloud_url
        self.timeout = timeout
        
        if not self.api_key or not self.api_secret:
            logger.warning("Confluent API credentials not configured")
        
        # Create HTTP client with auth
        self.client = httpx.Client(
            auth=(self.api_key, self.api_secret),
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"{settings.service_name}/{settings.service_version}",
            },
        )
    
    def _build_url(self, path: str) -> str:
        """Build full URL from path"""
        return urljoin(self.base_url, path)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            params: URL query parameters
            json_data: JSON request body
            
        Returns:
            Response JSON data
            
        Raises:
            ConfluentAPIError: On API errors
            ConfluentAPIRateLimitError: On rate limit (429)
            ConfluentAPIAuthError: On authentication errors (401, 403)
        """
        url = self._build_url(path)
        
        logger.debug(f"API Request: {method} {url}", extra={
            "params": params,
            "has_body": json_data is not None,
        })
        
        try:
            response = self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limit exceeded, retry after {retry_after}s")
                time.sleep(retry_after)
                raise ConfluentAPIRateLimitError(f"Rate limit exceeded")
            
            # Handle authentication errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication failed: {response.status_code}")
                raise ConfluentAPIAuthError(f"Authentication failed: {response.text}")
            
            # Handle other errors
            if response.status_code >= 400:
                logger.error(f"API error {response.status_code}: {response.text}")
                raise ConfluentAPIError(
                    f"API request failed: {response.status_code} - {response.text}"
                )
            
            logger.debug(f"API Response: {response.status_code}", extra={
                "url": url,
                "status": response.status_code,
            })
            
            return response.json()
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {url}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"Network error: {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ConfluentAPIError(f"Request failed: {e}")
    
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request"""
        return self._request("GET", path, params=params)
    
    def post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make POST request"""
        return self._request("POST", path, params=params, json_data=json_data)
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
