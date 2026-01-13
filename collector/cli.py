"""CLI commands for Collector Agent."""

from typing import Optional

import typer
from rich.console import Console

from collector import __version__
from collector.config import Config, load_config, save_config, set_config_value
from collector.collector import MetricsCollector
from collector.daemon import DaemonManager
from collector.display import (
    display_config,
    display_json,
    display_metrics,
    display_status,
    print_error,
    print_info,
    print_success,
)
from collector.transformer import metrics_to_dict

app = typer.Typer(
    name="collector",
    help="System metrics collector agent for kiosk machines.",
    add_completion=False,
)
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")

console = Console()


@app.command()
def start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as daemon"),
):
    """Start the collector."""
    config = load_config()
    collector = MetricsCollector(config)
    
    if daemon:
        if collector.daemon_manager.is_running():
            print_error("Collector is already running")
            raise typer.Exit(1)
        
        print_info("Starting collector as daemon...")
        collector.run_daemon()
        # If we reach here, we're still in parent process
        print_success(f"Collector started as daemon")
    else:
        collector.run_foreground()


@app.command()
def stop():
    """Stop the daemon."""
    config = load_config()
    daemon_manager = DaemonManager(config.daemon.pid_file)
    
    if not daemon_manager.is_running():
        print_info("Collector is not running")
        return
    
    pid = daemon_manager.get_pid()
    print_info(f"Stopping collector (PID: {pid})...")
    
    if daemon_manager.stop():
        print_success("Collector stopped")
    else:
        print_error("Failed to stop collector")
        raise typer.Exit(1)


@app.command()
def status():
    """Show collector status."""
    config = load_config()
    collector = MetricsCollector(config)
    
    running = collector.daemon_manager.is_running()
    pid = collector.daemon_manager.get_pid()
    uptime = collector.daemon_manager.get_uptime()
    
    node_ok, nvidia_ok = collector.check_exporters()
    
    display_status(
        running=running,
        pid=pid,
        uptime=uptime,
        last_collect=None,  # Not available without IPC
        endpoint=config.endpoint,
        interval=config.interval,
        node_exporter_ok=node_ok,
        nvidia_smi_ok=nvidia_ok,
    )
    
    collector.cleanup()


@app.command()
def metrics(
    category: Optional[str] = typer.Argument(
        None,
        help="Metric category: cpu, gpu, ram, disk, temp"
    ),
    follow: bool = typer.Option(
        False, "--follow", "-f",
        help="Continuously monitor metrics"
    ),
    interval: int = typer.Option(
        2, "--interval", "-i",
        help="Update interval in seconds (with --follow)"
    ),
):
    """Show current metrics."""
    import signal
    import time
    from datetime import datetime
    
    config = load_config()
    collector = MetricsCollector(config)
    
    # Signal handler for graceful exit
    stop_flag = False
    def signal_handler(signum, frame):
        nonlocal stop_flag
        stop_flag = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if follow:
            # Follow mode - continuous monitoring with Rich Live
            import logging
            from rich.live import Live
            from collector.display import build_metrics_panel
            
            # Suppress warnings and httpx logs during live mode for cleaner display
            logging.getLogger("collector").setLevel(logging.ERROR)
            logging.getLogger("httpx").setLevel(logging.ERROR)
            logging.getLogger("httpcore").setLevel(logging.ERROR)
            
            # Initial collection
            system_metrics = collector.collect_once()
            timestamp = datetime.now().strftime("%H:%M:%S")
            panel = build_metrics_panel(system_metrics, category, timestamp, interval)
            
            # Use Rich Live for flicker-free updates
            with Live(panel, console=console, refresh_per_second=4, vertical_overflow="visible") as live:
                while not stop_flag:
                    # Sleep with interrupt checking
                    for _ in range(interval * 10):
                        if stop_flag:
                            break
                        time.sleep(0.1)
                    
                    if stop_flag:
                        break
                    
                    # Collect and update display
                    system_metrics = collector.collect_once()
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    panel = build_metrics_panel(system_metrics, category, timestamp, interval)
                    live.update(panel)
            
            console.print("[dim]Monitoring stopped.[/dim]")
        else:
            # Single shot mode
            system_metrics = collector.collect_once()
            display_metrics(system_metrics, category)
    finally:
        collector.cleanup()


@app.command()
def test(
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Show JSON output without sending"
    ),
):
    """Test endpoint connection."""
    config = load_config()
    collector = MetricsCollector(config)
    
    try:
        # Collect metrics
        system_metrics = collector.collect_once()
        metrics_dict = metrics_to_dict(system_metrics)
        
        if dry_run:
            print_info("Collected metrics (dry-run mode):")
            console.print()
            display_json(metrics_dict)
        else:
            print_info(f"Testing connection to {config.endpoint}...")
            
            success, message = collector.sender.test_connection()
            
            if success:
                print_success(message)
                
                # Now try sending actual metrics
                print_info("Sending metrics...")
                if collector.sender.send(metrics_dict):
                    print_success("Metrics sent successfully!")
                else:
                    print_error("Failed to send metrics")
                    raise typer.Exit(1)
            else:
                print_error(message)
                raise typer.Exit(1)
    finally:
        collector.cleanup()


@app.command()
def version():
    """Show version information."""
    console.print(f"Collector Agent v{__version__}")


# Config subcommands
@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = load_config()
    display_config(config.model_dump())


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a configuration value.
    
    Available keys:
    - endpoint: Target endpoint URL
    - interval: Collection interval in seconds
    - logging.level: Log level (DEBUG, INFO, WARNING, ERROR)
    - logging.file: Log file path
    - exporters.node_exporter.url: Node Exporter URL
    - exporters.node_exporter.enabled: Enable Node Exporter (true/false)
    - exporters.dcgm_exporter.url: DCGM Exporter URL
    - exporters.dcgm_exporter.enabled: Enable DCGM Exporter (true/false)
    """
    try:
        config = set_config_value(key, value)
        print_success(f"{key} = {value}")
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except PermissionError:
        print_error("Permission denied. Try running with sudo.")
        raise typer.Exit(1)


@config_app.command("reset")
def config_reset():
    """Reset configuration to defaults."""
    try:
        config = Config()
        save_config(config)
        print_success("Configuration reset to defaults")
    except PermissionError:
        print_error("Permission denied. Try running with sudo.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
