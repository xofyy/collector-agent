"""HTTP client for sending metrics to endpoint."""

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class MetricsSender:
    """HTTP client for sending metrics to the endpoint."""
    
    def __init__(
        self,
        endpoint: str,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize the sender.
        
        Args:
            endpoint: Target endpoint URL
            timeout: HTTP timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client
    
    def send(self, metrics: dict[str, Any]) -> bool:
        """Send metrics to the endpoint.
        
        Args:
            metrics: Dictionary of metrics to send
            
        Returns:
            True if successful, False otherwise
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    self.endpoint,
                    json=metrics,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                logger.info(f"Metrics sent successfully to {self.endpoint}")
                return True
            
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"HTTP error {e.response.status_code} sending metrics "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Request error sending metrics: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Unexpected error sending metrics: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error(f"Failed to send metrics after {self.max_retries} attempts: {last_error}")
        return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test connection to the endpoint.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Try a simple POST with empty test data
            response = self.client.post(
                self.endpoint,
                json={"test": True},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code < 500:
                return True, f"Connection OK (status: {response.status_code})"
            else:
                return False, f"Server error (status: {response.status_code})"
        
        except httpx.ConnectError:
            return False, f"Connection refused: {self.endpoint}"
        
        except httpx.TimeoutException:
            return False, f"Connection timeout: {self.endpoint}"
        
        except Exception as e:
            return False, f"Connection error: {e}"
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
