"""Transform raw metrics to structured JSON format."""

import socket
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel


class CpuMetrics(BaseModel):
    """CPU metrics model."""
    
    usage_percent: float = 0.0
    load_1m: float = 0.0
    load_5m: float = 0.0
    load_15m: float = 0.0
    cores: int = 1
    temperature_celsius: Optional[float] = None


class MemoryMetrics(BaseModel):
    """Memory metrics model."""
    
    total_bytes: int = 0
    available_bytes: int = 0
    usage_percent: float = 0.0


class DiskMetrics(BaseModel):
    """Disk metrics model."""
    
    mountpoint: str
    device: str = ""
    total_bytes: int = 0
    available_bytes: int = 0
    usage_percent: float = 0.0


class GpuMetrics(BaseModel):
    """GPU metrics model."""
    
    utilization_percent: float = 0.0
    memory_used_bytes: int = 0
    memory_total_bytes: int = 0
    memory_usage_percent: float = 0.0
    temperature_celsius: float = 0.0
    power_watts: float = 0.0


class SystemMetrics(BaseModel):
    """Complete system metrics model."""
    
    timestamp: str
    hostname: str
    cpu: CpuMetrics
    memory: MemoryMetrics
    disks: list[DiskMetrics]
    gpu: Optional[GpuMetrics] = None


def get_hostname() -> str:
    """Get the system hostname.
    
    Returns:
        System hostname
    """
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_timestamp() -> str:
    """Get current timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp with timezone
    """
    return datetime.now(timezone.utc).isoformat()


def transform_metrics(
    node_metrics: Optional[dict[str, Any]],
    gpu_metrics: Optional[dict[str, Any]]
) -> SystemMetrics:
    """Transform raw metrics into structured format.
    
    Args:
        node_metrics: Raw metrics from Node Exporter
        gpu_metrics: Raw metrics from DCGM Exporter
        
    Returns:
        SystemMetrics object
    """
    timestamp = get_timestamp()
    hostname = get_hostname()
    
    # Default values
    cpu = CpuMetrics()
    memory = MemoryMetrics()
    disks: list[DiskMetrics] = []
    gpu: Optional[GpuMetrics] = None
    
    # Process node metrics
    if node_metrics:
        # CPU metrics
        if "cpu" in node_metrics:
            cpu_data = node_metrics["cpu"]
            cpu = CpuMetrics(
                usage_percent=cpu_data.get("usage_percent", 0.0),
                load_1m=cpu_data.get("load_1m", 0.0),
                load_5m=cpu_data.get("load_5m", 0.0),
                load_15m=cpu_data.get("load_15m", 0.0),
                cores=cpu_data.get("cores", 1),
                temperature_celsius=cpu_data.get("temperature_celsius"),
            )
        
        # Memory metrics
        if "memory" in node_metrics:
            mem_data = node_metrics["memory"]
            memory = MemoryMetrics(
                total_bytes=mem_data.get("total_bytes", 0),
                available_bytes=mem_data.get("available_bytes", 0),
                usage_percent=mem_data.get("usage_percent", 0.0),
            )
        
        # Disk metrics
        if "disks" in node_metrics:
            for disk_data in node_metrics["disks"]:
                disks.append(DiskMetrics(
                    mountpoint=disk_data.get("mountpoint", ""),
                    device=disk_data.get("device", ""),
                    total_bytes=disk_data.get("total_bytes", 0),
                    available_bytes=disk_data.get("available_bytes", 0),
                    usage_percent=disk_data.get("usage_percent", 0.0),
                ))
    
    # Process GPU metrics
    if gpu_metrics:
        gpu = GpuMetrics(
            utilization_percent=gpu_metrics.get("utilization_percent", 0.0),
            memory_used_bytes=gpu_metrics.get("memory_used_bytes", 0),
            memory_total_bytes=gpu_metrics.get("memory_total_bytes", 0),
            memory_usage_percent=gpu_metrics.get("memory_usage_percent", 0.0),
            temperature_celsius=gpu_metrics.get("temperature_celsius", 0.0),
            power_watts=gpu_metrics.get("power_watts", 0.0),
        )
    
    return SystemMetrics(
        timestamp=timestamp,
        hostname=hostname,
        cpu=cpu,
        memory=memory,
        disks=disks,
        gpu=gpu,
    )


def metrics_to_dict(metrics: SystemMetrics) -> dict[str, Any]:
    """Convert SystemMetrics to dictionary for JSON serialization.
    
    Args:
        metrics: SystemMetrics object
        
    Returns:
        Dictionary representation
    """
    return metrics.model_dump(exclude_none=True)
