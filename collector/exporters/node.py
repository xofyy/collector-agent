"""Node Exporter client for system metrics."""

from typing import Any, Optional

from collector.exporters.base import BaseExporter
from collector.parser import ParsedMetrics


class NodeExporter(BaseExporter):
    """Client for Node Exporter metrics."""
    
    def __init__(self, url: str = "http://localhost:9100/metrics", timeout: int = 5):
        """Initialize Node Exporter client.
        
        Args:
            url: Node Exporter metrics URL
            timeout: HTTP timeout in seconds
        """
        super().__init__(url, timeout)
        self._prev_cpu_total: Optional[dict[str, float]] = None
        self._prev_cpu_idle: Optional[dict[str, float]] = None
    
    def get_metrics(self) -> Optional[dict[str, Any]]:
        """Get system metrics from Node Exporter.
        
        Returns:
            Dictionary containing cpu, memory, disks metrics
        """
        parsed = self.scrape()
        if parsed is None:
            return None
        
        return {
            "cpu": self._get_cpu_metrics(parsed),
            "memory": self._get_memory_metrics(parsed),
            "disks": self._get_disk_metrics(parsed),
        }
    
    def _get_cpu_metrics(self, parsed: ParsedMetrics) -> dict[str, Any]:
        """Extract CPU metrics.
        
        Args:
            parsed: Parsed metrics
            
        Returns:
            CPU metrics dictionary
        """
        # Get load averages
        load_1m = parsed.get_metric_value("node_load1", default=0.0)
        load_5m = parsed.get_metric_value("node_load5", default=0.0)
        load_15m = parsed.get_metric_value("node_load15", default=0.0)
        
        # Count CPU cores from cpu_seconds_total metrics
        cpu_metrics = parsed.get_metrics_by_name("node_cpu_seconds_total")
        cpu_ids = set()
        for metric in cpu_metrics:
            cpu_id = metric.get_label("cpu")
            if cpu_id is not None:
                cpu_ids.add(cpu_id)
        cores = len(cpu_ids) if cpu_ids else 1
        
        # Calculate CPU usage percentage
        usage_percent = self._calculate_cpu_usage(parsed)
        
        # Get CPU temperature from hwmon
        temperature = self._get_cpu_temperature(parsed)
        
        result = {
            "usage_percent": round(usage_percent, 2),
            "load_1m": round(load_1m, 2),
            "load_5m": round(load_5m, 2),
            "load_15m": round(load_15m, 2),
            "cores": cores,
        }
        
        if temperature is not None:
            result["temperature_celsius"] = round(temperature, 1)
        
        return result
    
    def _calculate_cpu_usage(self, parsed: ParsedMetrics) -> float:
        """Calculate CPU usage percentage.
        
        Uses delta between current and previous measurements.
        
        Args:
            parsed: Parsed metrics
            
        Returns:
            CPU usage percentage (0-100)
        """
        # Get all CPU seconds by mode
        cpu_seconds = parsed.get_all_values("node_cpu_seconds_total")
        
        if not cpu_seconds:
            return 0.0
        
        # Sum all CPU times by mode
        total_by_cpu: dict[str, float] = {}
        idle_by_cpu: dict[str, float] = {}
        
        for labels, value in cpu_seconds:
            cpu = labels.get("cpu", "0")
            mode = labels.get("mode", "")
            
            if cpu not in total_by_cpu:
                total_by_cpu[cpu] = 0.0
                idle_by_cpu[cpu] = 0.0
            
            total_by_cpu[cpu] += value
            if mode == "idle":
                idle_by_cpu[cpu] += value
        
        # Calculate usage
        if self._prev_cpu_total is None or self._prev_cpu_idle is None:
            # First measurement, store values and return 0
            self._prev_cpu_total = total_by_cpu.copy()
            self._prev_cpu_idle = idle_by_cpu.copy()
            return 0.0
        
        # Calculate delta
        total_delta = 0.0
        idle_delta = 0.0
        
        for cpu in total_by_cpu:
            if cpu in self._prev_cpu_total:
                total_delta += total_by_cpu[cpu] - self._prev_cpu_total.get(cpu, 0)
                idle_delta += idle_by_cpu[cpu] - self._prev_cpu_idle.get(cpu, 0)
        
        # Update previous values
        self._prev_cpu_total = total_by_cpu.copy()
        self._prev_cpu_idle = idle_by_cpu.copy()
        
        if total_delta <= 0:
            return 0.0
        
        usage = ((total_delta - idle_delta) / total_delta) * 100.0
        return max(0.0, min(100.0, usage))
    
    def _get_cpu_temperature(self, parsed: ParsedMetrics) -> Optional[float]:
        """Get CPU temperature from hwmon metrics.
        
        Args:
            parsed: Parsed metrics
            
        Returns:
            CPU temperature in Celsius or None if not available
        """
        # Try different temperature metric patterns
        temp_metrics = parsed.get_metrics_by_name("node_hwmon_temp_celsius")
        
        for metric in temp_metrics:
            # Look for CPU-related temperature sensors
            chip = metric.get_label("chip", "")
            sensor = metric.get_label("sensor", "")
            
            # Common patterns for CPU temperature
            if "coretemp" in chip or "k10temp" in chip or "cpu" in sensor.lower():
                return metric.value
        
        # Fallback: get the first temperature reading
        if temp_metrics:
            return temp_metrics[0].value
        
        return None
    
    def _get_memory_metrics(self, parsed: ParsedMetrics) -> dict[str, Any]:
        """Extract memory metrics.
        
        Args:
            parsed: Parsed metrics
            
        Returns:
            Memory metrics dictionary
        """
        total = parsed.get_metric_value("node_memory_MemTotal_bytes", default=0)
        available = parsed.get_metric_value("node_memory_MemAvailable_bytes", default=0)
        
        usage_percent = 0.0
        if total > 0:
            usage_percent = ((total - available) / total) * 100.0
        
        return {
            "total_bytes": int(total),
            "available_bytes": int(available),
            "usage_percent": round(usage_percent, 2),
        }
    
    def _get_disk_metrics(self, parsed: ParsedMetrics) -> list[dict[str, Any]]:
        """Extract disk metrics for all mount points.
        
        Args:
            parsed: Parsed metrics
            
        Returns:
            List of disk metrics dictionaries
        """
        disks = []
        
        # Get filesystem size metrics
        size_metrics = parsed.get_all_values("node_filesystem_size_bytes")
        
        # Build a set of mountpoints
        mountpoints: dict[str, dict[str, Any]] = {}
        
        for labels, size in size_metrics:
            mountpoint = labels.get("mountpoint", "")
            device = labels.get("device", "")
            fstype = labels.get("fstype", "")
            
            # Skip pseudo filesystems
            if fstype in ("tmpfs", "devtmpfs", "squashfs", "overlay", "devfs", "nullfs"):
                continue
            
            # Skip system mount points
            if mountpoint.startswith(("/sys", "/proc", "/dev", "/run", "/snap")):
                continue
            
            if mountpoint and size > 0:
                mountpoints[mountpoint] = {
                    "mountpoint": mountpoint,
                    "device": device,
                    "total_bytes": int(size),
                }
        
        # Get available space
        avail_metrics = parsed.get_all_values("node_filesystem_avail_bytes")
        for labels, avail in avail_metrics:
            mountpoint = labels.get("mountpoint", "")
            if mountpoint in mountpoints:
                mountpoints[mountpoint]["available_bytes"] = int(avail)
        
        # Calculate usage percentage and build final list
        for mp_data in mountpoints.values():
            total = mp_data.get("total_bytes", 0)
            available = mp_data.get("available_bytes", 0)
            
            usage_percent = 0.0
            if total > 0:
                usage_percent = ((total - available) / total) * 100.0
            
            disks.append({
                "mountpoint": mp_data["mountpoint"],
                "device": mp_data["device"],
                "total_bytes": total,
                "available_bytes": available,
                "usage_percent": round(usage_percent, 2),
            })
        
        # Sort by mountpoint for consistent output
        disks.sort(key=lambda x: x["mountpoint"])
        
        return disks
