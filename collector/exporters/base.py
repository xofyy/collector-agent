"""Base exporter class."""

from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from collector.parser import ParsedMetrics, parse_prometheus_text


class BaseExporter(ABC):
    """Base class for metric exporters."""
    
    def __init__(self, url: str, timeout: int = 5):
        """Initialize exporter.
        
        Args:
            url: Exporter metrics URL
            timeout: HTTP timeout in seconds
        """
        self.url = url
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client
    
    def scrape(self) -> Optional[ParsedMetrics]:
        """Scrape metrics from the exporter.
        
        Returns:
            ParsedMetrics if successful, None if failed
        """
        try:
            response = self.client.get(self.url)
            response.raise_for_status()
            return parse_prometheus_text(response.text)
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if exporter is available.
        
        Returns:
            True if exporter is reachable
        """
        try:
            response = self.client.get(self.url)
            return response.status_code == 200
        except Exception:
            return False
    
    @abstractmethod
    def get_metrics(self) -> Optional[dict[str, Any]]:
        """Get transformed metrics from the exporter.
        
        Returns:
            Dictionary of metrics or None if unavailable
        """
        pass
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
