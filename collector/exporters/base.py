"""Base exporter class."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from collector.parser import ParsedMetrics, parse_prometheus_text

logger = logging.getLogger(__name__)


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
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error scraping {self.url}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"Request error scraping {self.url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping {self.url}: {e}")
            return None

    def is_available(self) -> bool:
        """Check if exporter is available.

        Returns:
            True if exporter is reachable
        """
        try:
            response = self.client.get(self.url)
            return response.status_code == 200
        except httpx.HTTPStatusError:
            return False
        except httpx.RequestError as e:
            logger.debug(f"Exporter {self.url} not available: {e}")
            return False
        except Exception as e:
            logger.debug(f"Unexpected error checking {self.url}: {e}")
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
