"""Tests for metrics transformer."""

import pytest

from collector.transformer import (
    CpuMetrics,
    DiskMetrics,
    GpuMetrics,
    MemoryMetrics,
    SystemMetrics,
    metrics_to_dict,
    transform_metrics,
)


class TestTransformMetrics:
    """Tests for transform_metrics function."""
    
    def test_empty_metrics(self):
        """Test transformation with no metrics."""
        result = transform_metrics(None, None)
        
        assert isinstance(result, SystemMetrics)
        assert result.hostname is not None
        assert result.timestamp is not None
        assert result.gpu is None
    
    def test_with_node_metrics(self):
        """Test transformation with node metrics."""
        node_metrics = {
            "cpu": {
                "usage_percent": 45.2,
                "load_1m": 1.5,
                "load_5m": 1.2,
                "load_15m": 0.9,
                "cores": 4,
                "temperature_celsius": 52.0,
            },
            "memory": {
                "total_bytes": 17179869184,
                "available_bytes": 8589934592,
                "usage_percent": 50.0,
            },
            "disks": [
                {
                    "mountpoint": "/",
                    "device": "/dev/sda1",
                    "total_bytes": 274877906944,
                    "available_bytes": 137438953472,
                    "usage_percent": 50.0,
                }
            ],
        }
        
        result = transform_metrics(node_metrics, None)
        
        assert result.cpu.usage_percent == 45.2
        assert result.cpu.load_1m == 1.5
        assert result.cpu.cores == 4
        assert result.cpu.temperature_celsius == 52.0
        
        assert result.memory.total_bytes == 17179869184
        assert result.memory.usage_percent == 50.0
        
        assert len(result.disks) == 1
        assert result.disks[0].mountpoint == "/"
    
    def test_with_gpu_metrics(self):
        """Test transformation with GPU metrics."""
        gpu_metrics = {
            "utilization_percent": 35.0,
            "memory_used_bytes": 4294967296,
            "memory_total_bytes": 12884901888,
            "memory_usage_percent": 33.3,
            "temperature_celsius": 48.0,
            "power_watts": 120.5,
        }
        
        result = transform_metrics(None, gpu_metrics)
        
        assert result.gpu is not None
        assert result.gpu.utilization_percent == 35.0
        assert result.gpu.temperature_celsius == 48.0
        assert result.gpu.power_watts == 120.5
    
    def test_full_metrics(self):
        """Test transformation with all metrics."""
        node_metrics = {
            "cpu": {"usage_percent": 50.0, "load_1m": 1.0, "load_5m": 0.8, "load_15m": 0.5, "cores": 8},
            "memory": {"total_bytes": 32000000000, "available_bytes": 16000000000, "usage_percent": 50.0},
            "disks": [],
        }
        gpu_metrics = {
            "utilization_percent": 80.0,
            "memory_used_bytes": 8000000000,
            "memory_total_bytes": 16000000000,
            "memory_usage_percent": 50.0,
            "temperature_celsius": 75.0,
            "power_watts": 200.0,
        }
        
        result = transform_metrics(node_metrics, gpu_metrics)
        
        assert result.cpu.usage_percent == 50.0
        assert result.memory.total_bytes == 32000000000
        assert result.gpu is not None
        assert result.gpu.utilization_percent == 80.0


class TestMetricsToDict:
    """Tests for metrics_to_dict function."""
    
    def test_basic_conversion(self):
        """Test basic dictionary conversion."""
        metrics = SystemMetrics(
            timestamp="2026-01-13T12:00:00Z",
            hostname="test-host",
            cpu=CpuMetrics(usage_percent=50.0, load_1m=1.0, load_5m=0.8, load_15m=0.5, cores=4),
            memory=MemoryMetrics(total_bytes=16000000000, available_bytes=8000000000, usage_percent=50.0),
            disks=[],
        )
        
        result = metrics_to_dict(metrics)
        
        assert result["timestamp"] == "2026-01-13T12:00:00Z"
        assert result["hostname"] == "test-host"
        assert result["cpu"]["usage_percent"] == 50.0
        assert result["memory"]["total_bytes"] == 16000000000
    
    def test_excludes_none_values(self):
        """Test that None values are excluded."""
        metrics = SystemMetrics(
            timestamp="2026-01-13T12:00:00Z",
            hostname="test-host",
            cpu=CpuMetrics(),
            memory=MemoryMetrics(),
            disks=[],
            gpu=None,
        )
        
        result = metrics_to_dict(metrics)
        
        assert "gpu" not in result
        assert "temperature_celsius" not in result["cpu"]
    
    def test_with_disks(self):
        """Test conversion with disk metrics."""
        metrics = SystemMetrics(
            timestamp="2026-01-13T12:00:00Z",
            hostname="test-host",
            cpu=CpuMetrics(),
            memory=MemoryMetrics(),
            disks=[
                DiskMetrics(mountpoint="/", device="/dev/sda1", total_bytes=100, available_bytes=50, usage_percent=50.0),
                DiskMetrics(mountpoint="/home", device="/dev/sda2", total_bytes=200, available_bytes=100, usage_percent=50.0),
            ],
        )
        
        result = metrics_to_dict(metrics)
        
        assert len(result["disks"]) == 2
        assert result["disks"][0]["mountpoint"] == "/"
        assert result["disks"][1]["mountpoint"] == "/home"
    
    def test_with_gpu(self):
        """Test conversion with GPU metrics."""
        metrics = SystemMetrics(
            timestamp="2026-01-13T12:00:00Z",
            hostname="test-host",
            cpu=CpuMetrics(),
            memory=MemoryMetrics(),
            disks=[],
            gpu=GpuMetrics(
                utilization_percent=50.0,
                memory_used_bytes=4000000000,
                memory_total_bytes=8000000000,
                memory_usage_percent=50.0,
                temperature_celsius=60.0,
                power_watts=150.0,
            ),
        )
        
        result = metrics_to_dict(metrics)
        
        assert "gpu" in result
        assert result["gpu"]["utilization_percent"] == 50.0
        assert result["gpu"]["temperature_celsius"] == 60.0
