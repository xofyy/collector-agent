"""Tests for exporters."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

import httpx

from collector.exporters.base import BaseExporter
from collector.exporters.node import NodeExporter
from collector.exporters.nvidia import NvidiaExporter


class ConcreteExporter(BaseExporter):
    """Concrete implementation for testing BaseExporter."""

    def get_metrics(self):
        return {"test": "metrics"}


class TestBaseExporter:
    """Tests for BaseExporter class."""

    def test_init(self):
        """Test exporter initialization."""
        exporter = ConcreteExporter("http://localhost:9100/metrics", timeout=10)
        assert exporter.url == "http://localhost:9100/metrics"
        assert exporter.timeout == 10

    def test_init_default_timeout(self):
        """Test exporter default timeout."""
        exporter = ConcreteExporter("http://localhost:9100/metrics")
        assert exporter.timeout == 5

    @patch("collector.exporters.base.httpx.Client")
    def test_client_lazy_initialization(self, mock_client_class):
        """Test HTTP client is lazily initialized."""
        exporter = ConcreteExporter("http://localhost:9100/metrics")
        assert exporter._client is None

        _ = exporter.client
        assert exporter._client is not None
        mock_client_class.assert_called_once_with(timeout=5)

    @patch("collector.exporters.base.httpx.Client")
    def test_scrape_success(self, mock_client_class):
        """Test successful scrape."""
        mock_response = MagicMock()
        mock_response.text = "node_load1 1.5"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        result = exporter.scrape()

        assert result is not None

    @patch("collector.exporters.base.httpx.Client")
    def test_scrape_http_status_error(self, mock_client_class):
        """Test scrape handles HTTP status error."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        result = exporter.scrape()

        assert result is None

    @patch("collector.exporters.base.httpx.Client")
    def test_scrape_request_error(self, mock_client_class):
        """Test scrape handles request error."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        result = exporter.scrape()

        assert result is None

    @patch("collector.exporters.base.httpx.Client")
    def test_scrape_unexpected_error(self, mock_client_class):
        """Test scrape handles unexpected error."""
        mock_client = MagicMock()
        mock_client.get.side_effect = RuntimeError("Unexpected")
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        result = exporter.scrape()

        assert result is None

    @patch("collector.exporters.base.httpx.Client")
    def test_is_available_success(self, mock_client_class):
        """Test is_available returns True on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        assert exporter.is_available() is True

    @patch("collector.exporters.base.httpx.Client")
    def test_is_available_non_200(self, mock_client_class):
        """Test is_available returns False for non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        assert exporter.is_available() is False

    @patch("collector.exporters.base.httpx.Client")
    def test_is_available_request_error(self, mock_client_class):
        """Test is_available returns False on request error."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        assert exporter.is_available() is False

    @patch("collector.exporters.base.httpx.Client")
    def test_close(self, mock_client_class):
        """Test close method."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        exporter = ConcreteExporter("http://localhost:9100/metrics")
        _ = exporter.client  # Initialize client
        exporter.close()

        mock_client.close.assert_called_once()
        assert exporter._client is None

    def test_close_without_client(self):
        """Test close when client not initialized."""
        exporter = ConcreteExporter("http://localhost:9100/metrics")
        exporter.close()  # Should not raise


class TestNodeExporter:
    """Tests for NodeExporter class."""

    def test_init_default(self):
        """Test NodeExporter default initialization."""
        exporter = NodeExporter()
        assert exporter.url == "http://localhost:9100/metrics"
        assert exporter.timeout == 5

    def test_init_custom(self):
        """Test NodeExporter custom initialization."""
        exporter = NodeExporter(url="http://custom:9100/metrics", timeout=10)
        assert exporter.url == "http://custom:9100/metrics"
        assert exporter.timeout == 10

    @patch("collector.exporters.base.httpx.Client")
    def test_get_metrics_success(self, mock_client_class, sample_node_exporter_output):
        """Test successful metrics collection."""
        mock_response = MagicMock()
        mock_response.text = sample_node_exporter_output
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        exporter = NodeExporter()
        # First call to establish baseline
        result = exporter.get_metrics()
        # Second call to get actual usage
        result = exporter.get_metrics()

        assert result is not None
        assert "cpu" in result
        assert "memory" in result
        assert "disks" in result

    @patch("collector.exporters.base.httpx.Client")
    def test_get_metrics_failure(self, mock_client_class):
        """Test metrics collection failure."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value = mock_client

        exporter = NodeExporter()
        result = exporter.get_metrics()

        assert result is None


class TestNvidiaExporter:
    """Tests for NvidiaExporter class."""

    def test_init_disabled(self):
        """Test exporter can be disabled."""
        exporter = NvidiaExporter(enabled=False)
        assert exporter.is_available() is False
        assert exporter.get_metrics() is None

    @patch("shutil.which")
    def test_nvidia_smi_not_found(self, mock_which):
        """Test handling when nvidia-smi not found."""
        mock_which.return_value = None

        exporter = NvidiaExporter()
        assert exporter.is_available() is False

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available_success(self, mock_which, mock_run):
        """Test is_available returns True when nvidia-smi works."""
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_run.return_value = MagicMock(returncode=0, stdout="NVIDIA GeForce RTX 3080")

        exporter = NvidiaExporter()
        assert exporter.is_available() is True

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_is_available_nvidia_smi_fails(self, mock_which, mock_run):
        """Test is_available returns False when nvidia-smi fails."""
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_run.return_value = MagicMock(returncode=1)

        exporter = NvidiaExporter()
        assert exporter.is_available() is False

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_get_metrics_success(self, mock_which, mock_run):
        """Test successful GPU metrics collection."""
        mock_which.return_value = "/usr/bin/nvidia-smi"

        # Calls: is_available check, then actual metrics query
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="NVIDIA"),  # is_available
            MagicMock(returncode=0, stdout="35, 4096, 8192, 60, 150")  # get_metrics
        ]

        exporter = NvidiaExporter()
        result = exporter.get_metrics()

        assert result is not None
        assert result["utilization_percent"] == 35.0
        assert result["temperature_celsius"] == 60.0
        assert result["power_watts"] == 150.0

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_get_metrics_timeout(self, mock_which, mock_run):
        """Test handling nvidia-smi timeout."""
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_run.side_effect = [
            MagicMock(returncode=0),  # is_available check
            subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=10)
        ]

        exporter = NvidiaExporter()
        exporter._available = True  # Skip availability check
        result = exporter.get_metrics()

        assert result is None

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_get_metrics_nonzero_returncode(self, mock_which, mock_run):
        """Test handling nvidia-smi non-zero return code."""
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_run.side_effect = [
            MagicMock(returncode=0),  # is_available
            MagicMock(returncode=1, stdout="")  # get_metrics
        ]

        exporter = NvidiaExporter()
        exporter._available = True
        result = exporter.get_metrics()

        assert result is None

    def test_parse_value_normal(self):
        """Test parsing normal numeric values."""
        exporter = NvidiaExporter()

        assert exporter._parse_value("35", 0.0) == 35.0
        assert exporter._parse_value("150.5", 0.0) == 150.5

    def test_parse_value_na(self):
        """Test parsing N/A values from nvidia-smi."""
        exporter = NvidiaExporter()

        assert exporter._parse_value("[N/A]", 0.0) == 0.0
        assert exporter._parse_value("N/A", 42.0) == 42.0
        assert exporter._parse_value("[Not Supported]", 10.0) == 10.0

    def test_parse_value_empty(self):
        """Test parsing empty values."""
        exporter = NvidiaExporter()

        assert exporter._parse_value("", 10.0) == 10.0
        assert exporter._parse_value("   ", 20.0) == 20.0

    def test_close(self):
        """Test close is a no-op."""
        exporter = NvidiaExporter(enabled=False)
        exporter.close()  # Should not raise

    @patch("shutil.which")
    def test_custom_nvidia_smi_path(self, mock_which):
        """Test custom nvidia-smi path."""
        mock_which.return_value = None  # Not in PATH

        exporter = NvidiaExporter(nvidia_smi_path="/custom/path/nvidia-smi")
        assert exporter.nvidia_smi_path == "/custom/path/nvidia-smi"
