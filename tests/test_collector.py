"""Tests for main collector module."""

import pytest
from unittest.mock import MagicMock, patch

from collector.config import Config
from collector.transformer import SystemMetrics


class TestMetricsCollector:
    """Tests for MetricsCollector class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return Config(
            endpoint="http://localhost:8080/metrics",
            interval=30,
        )
    
    def test_collect_once_returns_system_metrics(self, mock_config):
        """Test that collect_once returns SystemMetrics."""
        with patch("collector.collector.NodeExporter") as MockNodeExporter, \
             patch("collector.collector.NvidiaExporter") as MockNvidiaExporter:
            
            # Setup mocks
            mock_node = MagicMock()
            mock_node.get_metrics.return_value = {
                "cpu": {"usage_percent": 50.0, "load_1m": 1.0, "load_5m": 0.8, "load_15m": 0.5, "cores": 4},
                "memory": {"total_bytes": 16000000000, "available_bytes": 8000000000, "usage_percent": 50.0},
                "disks": [],
            }
            MockNodeExporter.return_value = mock_node
            
            mock_nvidia = MagicMock()
            mock_nvidia.get_metrics.return_value = {
                "utilization_percent": 35.0,
                "memory_used_bytes": 4000000000,
                "memory_total_bytes": 8000000000,
                "memory_usage_percent": 50.0,
                "temperature_celsius": 60.0,
                "power_watts": 150.0,
            }
            MockNvidiaExporter.return_value = mock_nvidia
            
            from collector.collector import MetricsCollector
            collector = MetricsCollector(mock_config)
            
            result = collector.collect_once()
            
            assert isinstance(result, SystemMetrics)
            assert result.cpu.usage_percent == 50.0
            assert result.gpu is not None
            assert result.gpu.utilization_percent == 35.0
            
            collector.cleanup()
    
    def test_collect_once_handles_node_exporter_failure(self, mock_config):
        """Test graceful handling of Node Exporter failure."""
        with patch("collector.collector.NodeExporter") as MockNodeExporter, \
             patch("collector.collector.NvidiaExporter") as MockNvidiaExporter:
            
            mock_node = MagicMock()
            mock_node.get_metrics.return_value = None  # Simulate failure
            MockNodeExporter.return_value = mock_node
            
            mock_nvidia = MagicMock()
            mock_nvidia.get_metrics.return_value = None
            MockNvidiaExporter.return_value = mock_nvidia
            
            from collector.collector import MetricsCollector
            collector = MetricsCollector(mock_config)
            
            result = collector.collect_once()
            
            # Should still return valid SystemMetrics with defaults
            assert isinstance(result, SystemMetrics)
            assert result.cpu.usage_percent == 0.0
            
            collector.cleanup()
    
    def test_check_exporters(self, mock_config):
        """Test exporter availability check."""
        with patch("collector.collector.NodeExporter") as MockNodeExporter, \
             patch("collector.collector.NvidiaExporter") as MockNvidiaExporter:
            
            mock_node = MagicMock()
            mock_node.is_available.return_value = True
            MockNodeExporter.return_value = mock_node
            
            mock_nvidia = MagicMock()
            mock_nvidia.is_available.return_value = False
            MockNvidiaExporter.return_value = mock_nvidia
            
            from collector.collector import MetricsCollector
            collector = MetricsCollector(mock_config)
            
            node_ok, nvidia_ok = collector.check_exporters()
            
            assert node_ok is True
            assert nvidia_ok is False
            
            collector.cleanup()


class TestMetricsSender:
    """Tests for MetricsSender class."""
    
    def test_send_success(self):
        """Test successful metric sending."""
        with patch("collector.sender.httpx.Client") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value = mock_client
            
            from collector.sender import MetricsSender
            sender = MetricsSender("http://localhost:8080/metrics")
            
            result = sender.send({"test": "data"})
            
            assert result is True
            mock_client.post.assert_called_once()
            
            sender.close()
    
    def test_send_retry_on_failure(self):
        """Test retry behavior on failure."""
        with patch("collector.sender.httpx.Client") as MockClient, \
             patch("collector.sender.time.sleep"):
            
            import httpx
            
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value = mock_client
            
            from collector.sender import MetricsSender
            sender = MetricsSender("http://localhost:8080/metrics", max_retries=3)
            
            result = sender.send({"test": "data"})
            
            assert result is False
            assert mock_client.post.call_count == 3  # Should retry 3 times
            
            sender.close()
    
    def test_test_connection(self):
        """Test connection testing."""
        with patch("collector.sender.httpx.Client") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value = mock_client
            
            from collector.sender import MetricsSender
            sender = MetricsSender("http://localhost:8080/metrics")
            
            success, message = sender.test_connection()
            
            assert success is True
            assert "200" in message
            
            sender.close()
