"""Main collection loop for Collector Agent."""

import logging
import time
from datetime import datetime
from typing import Optional

from collector.config import Config, load_config
from collector.daemon import DaemonManager, GracefulKiller
from collector.display import console, print_error, print_info, print_success
from collector.exporters import NodeExporter, NvidiaExporter
from collector.sender import MetricsSender
from collector.transformer import SystemMetrics, metrics_to_dict, transform_metrics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Main metrics collector class."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the collector.
        
        Args:
            config: Configuration object. If None, loads from default location.
        """
        self.config = config or load_config()
        self._setup_logging()
        
        # Initialize components
        self.node_exporter = NodeExporter(
            url=self.config.exporters.node_exporter.url,
            timeout=self.config.exporters.node_exporter.timeout
        )
        self.nvidia_exporter = NvidiaExporter(
            nvidia_smi_path=self.config.exporters.nvidia_smi.nvidia_smi_path,
            enabled=self.config.exporters.nvidia_smi.enabled
        )
        self.sender = MetricsSender(
            endpoint=self.config.endpoint,
            timeout=10,
            max_retries=3
        )
        self.daemon_manager = DaemonManager(self.config.daemon.pid_file)
        
        self._last_collect_time: Optional[datetime] = None
    
    def _setup_logging(self) -> None:
        """Configure logging."""
        log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Add file handler if configured
        if self.config.logging.file:
            try:
                file_handler = logging.FileHandler(self.config.logging.file)
                file_handler.setLevel(log_level)
                file_handler.setFormatter(
                    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
                )
                logging.getLogger().addHandler(file_handler)
            except PermissionError:
                logger.warning(f"Cannot write to log file: {self.config.logging.file}")
    
    def collect_once(self) -> SystemMetrics:
        """Collect metrics once.
        
        Returns:
            SystemMetrics object
        """
        node_metrics = None
        gpu_metrics = None
        
        # Collect from Node Exporter
        if self.config.exporters.node_exporter.enabled:
            try:
                node_metrics = self.node_exporter.get_metrics()
                if node_metrics is None:
                    logger.warning("Failed to collect metrics from Node Exporter")
            except Exception as e:
                logger.error(f"Error collecting from Node Exporter: {e}")
        
        # Collect GPU metrics via nvidia-smi
        if self.config.exporters.nvidia_smi.enabled:
            try:
                gpu_metrics = self.nvidia_exporter.get_metrics()
                if gpu_metrics is None:
                    logger.warning("Failed to collect GPU metrics from nvidia-smi")
            except Exception as e:
                logger.error(f"Error collecting GPU metrics: {e}")
        
        # Transform metrics
        metrics = transform_metrics(node_metrics, gpu_metrics)
        self._last_collect_time = datetime.now()
        
        return metrics
    
    def collect_and_send(self) -> bool:
        """Collect metrics and send to endpoint.
        
        Returns:
            True if successful
        """
        metrics = self.collect_once()
        metrics_dict = metrics_to_dict(metrics)
        
        success = self.sender.send(metrics_dict)
        
        if success:
            logger.info("Metrics collected and sent successfully")
        else:
            logger.error("Failed to send metrics to endpoint")
        
        return success
    
    def run_foreground(self) -> None:
        """Run collector in foreground mode."""
        killer = GracefulKiller()
        
        # Write PID file for status tracking (also used by systemd)
        try:
            self.daemon_manager.write_pid()
        except PermissionError:
            logger.warning("Cannot write PID file (permission denied)")
        
        print_info(f"Starting collector (interval: {self.config.interval}s)")
        print_info(f"Endpoint: {self.config.endpoint}")
        print_info("Press Ctrl+C to stop")
        console.print()
        
        try:
            while not killer.kill_now:
                try:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    console.print(f"[dim][{timestamp}][/dim] 📡 Collecting metrics...")
                    
                    success = self.collect_and_send()
                    
                    if success:
                        console.print(
                            f"[dim][{timestamp}][/dim] [green]✅ Sent to {self.config.endpoint}[/green]"
                        )
                    else:
                        console.print(
                            f"[dim][{timestamp}][/dim] [red]❌ Failed to send metrics[/red]"
                        )
                    
                    # Sleep with interrupt checking
                    for _ in range(self.config.interval * 10):
                        if killer.kill_now:
                            break
                        time.sleep(0.1)
                
                except Exception as e:
                    logger.error(f"Error in collection loop: {e}")
                    time.sleep(1)
        finally:
            console.print()
            print_info("Stopping collector...")
            self.cleanup()
            # Clean up PID file on exit
            self.daemon_manager._cleanup_pid_file()
    
    def run_daemon(self) -> None:
        """Run collector as daemon."""
        if self.daemon_manager.is_running():
            print_error("Collector is already running")
            return
        
        # Daemonize
        self.daemon_manager.daemonize()
        
        # Now we're in the daemon process
        killer = GracefulKiller()
        
        logger.info(f"Collector daemon started (PID: {self.daemon_manager.get_pid()})")
        
        while not killer.kill_now:
            try:
                self.collect_and_send()
                
                # Sleep with interrupt checking
                for _ in range(self.config.interval * 10):
                    if killer.kill_now:
                        break
                    time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                time.sleep(1)
        
        logger.info("Collector daemon stopping")
        self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.node_exporter.close()
        self.nvidia_exporter.close()
        self.sender.close()
    
    def check_exporters(self) -> tuple[bool, bool]:
        """Check if exporters are available.
        
        Returns:
            Tuple of (node_exporter_ok, nvidia_smi_ok)
        """
        node_ok = False
        nvidia_ok = False
        
        if self.config.exporters.node_exporter.enabled:
            node_ok = self.node_exporter.is_available()
        
        if self.config.exporters.nvidia_smi.enabled:
            nvidia_ok = self.nvidia_exporter.is_available()
        
        return node_ok, nvidia_ok
    
    def get_last_collect_time(self) -> Optional[str]:
        """Get time since last collection.
        
        Returns:
            Formatted string or None
        """
        if self._last_collect_time is None:
            return None
        
        delta = datetime.now() - self._last_collect_time
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        else:
            return f"{seconds // 3600}h ago"
