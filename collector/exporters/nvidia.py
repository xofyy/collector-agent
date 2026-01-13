"""NVIDIA GPU metrics via nvidia-smi command."""

import logging
import shutil
import subprocess
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NvidiaExporter:
    """Collect GPU metrics using nvidia-smi command.
    
    This works with all NVIDIA GPUs (GeForce, Quadro, Tesla, etc.)
    unlike DCGM which only supports datacenter GPUs.
    """
    
    # nvidia-smi query fields
    QUERY_FIELDS = [
        "utilization.gpu",      # GPU utilization (%)
        "memory.used",          # Memory used (MiB)
        "memory.total",         # Memory total (MiB)
        "temperature.gpu",      # GPU temperature (C)
        "power.draw",           # Power draw (W)
    ]
    
    def __init__(self, nvidia_smi_path: Optional[str] = None, enabled: bool = True):
        """Initialize nvidia-smi exporter.
        
        Args:
            nvidia_smi_path: Path to nvidia-smi binary. Auto-detected if None.
            enabled: Whether GPU metrics collection is enabled.
        """
        self.enabled = enabled
        self._nvidia_smi_path = nvidia_smi_path
        self._available: Optional[bool] = None
    
    @property
    def nvidia_smi_path(self) -> Optional[str]:
        """Get nvidia-smi binary path."""
        if self._nvidia_smi_path is None:
            self._nvidia_smi_path = shutil.which("nvidia-smi")
        return self._nvidia_smi_path
    
    def is_available(self) -> bool:
        """Check if nvidia-smi is available.
        
        Returns:
            True if nvidia-smi is found and working
        """
        if self._available is not None:
            return self._available
        
        if not self.enabled:
            self._available = False
            return False
        
        if self.nvidia_smi_path is None:
            self._available = False
            return False
        
        try:
            result = subprocess.run(
                [self.nvidia_smi_path, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self._available = result.returncode == 0
        except Exception:
            self._available = False
        
        return self._available
    
    def get_metrics(self) -> Optional[dict[str, Any]]:
        """Get GPU metrics from nvidia-smi.
        
        Returns:
            Dictionary containing GPU metrics or None if unavailable
        """
        if not self.enabled:
            return None
        
        if not self.is_available():
            return None
        
        try:
            # Build nvidia-smi command
            query = ",".join(self.QUERY_FIELDS)
            result = subprocess.run(
                [
                    self.nvidia_smi_path,
                    f"--query-gpu={query}",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"nvidia-smi failed: {result.stderr}")
                return None
            
            return self._parse_output(result.stdout)
        
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi timed out")
            return None
        except Exception as e:
            logger.warning(f"Error running nvidia-smi: {e}")
            return None
    
    def _parse_output(self, output: str) -> Optional[dict[str, Any]]:
        """Parse nvidia-smi CSV output.
        
        Args:
            output: nvidia-smi output string
            
        Returns:
            Parsed GPU metrics dictionary
        """
        lines = output.strip().split("\n")
        if not lines:
            return None
        
        # Take first GPU (index 0) if multiple GPUs
        # TODO: Support multiple GPUs in future
        first_gpu = lines[0].strip()
        if not first_gpu:
            return None
        
        values = [v.strip() for v in first_gpu.split(",")]
        
        if len(values) < 5:
            logger.warning(f"Unexpected nvidia-smi output: {first_gpu}")
            return None
        
        try:
            # Parse values (handle [N/A] values)
            utilization = self._parse_value(values[0], 0.0)
            memory_used_mib = self._parse_value(values[1], 0.0)
            memory_total_mib = self._parse_value(values[2], 0.0)
            temperature = self._parse_value(values[3], 0.0)
            power = self._parse_value(values[4], 0.0)
            
            # Convert MiB to bytes
            memory_used_bytes = int(memory_used_mib * 1024 * 1024)
            memory_total_bytes = int(memory_total_mib * 1024 * 1024)
            
            # Calculate memory usage percentage
            memory_usage_percent = 0.0
            if memory_total_bytes > 0:
                memory_usage_percent = (memory_used_bytes / memory_total_bytes) * 100.0
            
            return {
                "utilization_percent": round(utilization, 2),
                "memory_used_bytes": memory_used_bytes,
                "memory_total_bytes": memory_total_bytes,
                "memory_usage_percent": round(memory_usage_percent, 2),
                "temperature_celsius": round(temperature, 1),
                "power_watts": round(power, 2),
            }
        
        except (ValueError, IndexError) as e:
            logger.warning(f"Error parsing nvidia-smi output: {e}")
            return None
    
    def _parse_value(self, value: str, default: float) -> float:
        """Parse a single value from nvidia-smi output.
        
        Args:
            value: String value to parse
            default: Default value if parsing fails
            
        Returns:
            Parsed float value
        """
        value = value.strip()
        if not value or value == "[N/A]" or value == "N/A":
            return default
        try:
            return float(value)
        except ValueError:
            return default
    
    def close(self) -> None:
        """Close the exporter (no-op for nvidia-smi)."""
        pass
