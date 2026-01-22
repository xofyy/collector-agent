"""Rich terminal UI for displaying metrics and status."""

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from collector.transformer import SystemMetrics

console = Console()


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string.
    
    Args:
        bytes_value: Bytes value
        
    Returns:
        Human readable string (e.g., "8.5 GB")
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"


def get_usage_color(percent: float) -> str:
    """Get color based on usage percentage.
    
    Args:
        percent: Usage percentage (0-100)
        
    Returns:
        Color name for Rich
    """
    if percent < 50:
        return "green"
    elif percent < 80:
        return "yellow"
    else:
        return "red"


def get_temp_color(celsius: float) -> str:
    """Get color based on temperature.
    
    Args:
        celsius: Temperature in Celsius
        
    Returns:
        Color name for Rich
    """
    if celsius < 60:
        return "green"
    elif celsius < 80:
        return "yellow"
    else:
        return "red"


def create_progress_bar(percent: float, width: int = 20) -> str:
    """Create a text-based progress bar.
    
    Args:
        percent: Percentage (0-100)
        width: Bar width in characters
        
    Returns:
        Progress bar string
    """
    filled = int(width * percent / 100)
    empty = width - filled
    return "█" * filled + "░" * empty


def display_status(
    running: bool,
    pid: Optional[int],
    uptime: Optional[str],
    last_collect: Optional[str],
    endpoint: str,
    interval: int,
    node_exporter_ok: bool,
    nvidia_smi_ok: bool
) -> None:
    """Display collector status.
    
    Args:
        running: Whether collector is running
        pid: Process ID if running
        uptime: Uptime string if running
        last_collect: Time since last collection
        endpoint: Target endpoint URL
        interval: Collection interval in seconds
        node_exporter_ok: Node Exporter availability
        nvidia_smi_ok: nvidia-smi availability
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")
    
    # Status
    if running:
        status_text = Text("🟢 Running", style="green bold")
    else:
        status_text = Text("🔴 Stopped", style="red bold")
    table.add_row("Status:", status_text)
    
    # PID
    if pid:
        table.add_row("PID:", str(pid))
    
    # Uptime
    if uptime:
        table.add_row("Uptime:", uptime)
    
    # Last collect
    if last_collect:
        table.add_row("Last collect:", last_collect)
    
    # Endpoint
    table.add_row("Endpoint:", endpoint)
    
    # Interval
    table.add_row("Interval:", f"{interval}s")
    
    # Separator
    table.add_row("", "")
    
    # Exporter status
    node_status = Text("🟢 OK", style="green") if node_exporter_ok else Text("🔴 Down", style="red")
    nvidia_status = Text("🟢 OK", style="green") if nvidia_smi_ok else Text("🔴 Down", style="red")
    
    table.add_row("Node Exporter:", node_status)
    table.add_row("nvidia-smi:", nvidia_status)
    
    panel = Panel(table, title="Collector Agent Status", border_style="blue")
    console.print(panel)


def display_metrics(metrics: SystemMetrics, category: Optional[str] = None) -> None:
    """Display system metrics.
    
    Args:
        metrics: System metrics to display
        category: Optional category filter (cpu, gpu, ram, disk, temp)
    """
    if category is None:
        # Display all metrics
        display_cpu_metrics(metrics)
        display_memory_metrics(metrics)
        display_disk_metrics(metrics)
        display_gpu_metrics(metrics)
    elif category == "cpu":
        display_cpu_metrics(metrics)
    elif category == "gpu":
        display_gpu_metrics(metrics)
    elif category == "ram":
        display_memory_metrics(metrics)
    elif category == "disk":
        display_disk_metrics(metrics)
    elif category == "temp":
        display_temperature_metrics(metrics)
    else:
        console.print(f"[red]Unknown category: {category}[/red]")


def display_cpu_metrics(metrics: SystemMetrics) -> None:
    """Display CPU metrics."""
    cpu = metrics.cpu
    color = get_usage_color(cpu.usage_percent)
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim", width=12)
    table.add_column("Value", width=40)
    
    # Usage with progress bar
    bar = create_progress_bar(cpu.usage_percent)
    table.add_row("Usage:", f"[{color}]{cpu.usage_percent:.1f}%[/{color}]  {bar}")
    
    # Load averages
    table.add_row("Load:", f"{cpu.load_1m:.2f} / {cpu.load_5m:.2f} / {cpu.load_15m:.2f}")
    
    # Cores
    table.add_row("Cores:", str(cpu.cores))
    
    # Temperature
    if cpu.temperature_celsius is not None:
        temp_color = get_temp_color(cpu.temperature_celsius)
        table.add_row("Temp:", f"[{temp_color}]{cpu.temperature_celsius:.1f}°C[/{temp_color}]")
    
    panel = Panel(table, title="CPU", border_style="cyan")
    console.print(panel)


def display_memory_metrics(metrics: SystemMetrics) -> None:
    """Display memory metrics."""
    mem = metrics.memory
    color = get_usage_color(mem.usage_percent)
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim", width=12)
    table.add_column("Value", width=40)
    
    # Used/Total
    used = mem.total_bytes - mem.available_bytes
    table.add_row("Used:", f"{format_bytes(used)} / {format_bytes(mem.total_bytes)}")
    
    # Usage with progress bar
    bar = create_progress_bar(mem.usage_percent)
    table.add_row("Usage:", f"[{color}]{mem.usage_percent:.1f}%[/{color}]  {bar}")
    
    # Available
    table.add_row("Available:", format_bytes(mem.available_bytes))
    
    panel = Panel(table, title="Memory", border_style="magenta")
    console.print(panel)


def display_disk_metrics(metrics: SystemMetrics) -> None:
    """Display disk metrics."""
    if not metrics.disks:
        console.print("[dim]No disk metrics available[/dim]")
        return
    
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Mount", style="cyan")
    table.add_column("Device", style="dim")
    table.add_column("Used", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Usage", justify="right")
    table.add_column("", width=20)
    
    for disk in metrics.disks:
        color = get_usage_color(disk.usage_percent)
        used = disk.total_bytes - disk.available_bytes
        bar = create_progress_bar(disk.usage_percent, width=15)
        
        table.add_row(
            disk.mountpoint,
            disk.device,
            format_bytes(used),
            format_bytes(disk.total_bytes),
            f"[{color}]{disk.usage_percent:.1f}%[/{color}]",
            bar
        )
    
    panel = Panel(table, title="Disks", border_style="yellow")
    console.print(panel)


def display_gpu_metrics(metrics: SystemMetrics) -> None:
    """Display GPU metrics."""
    if metrics.gpu is None:
        console.print("[dim]No GPU metrics available[/dim]")
        return
    
    gpu = metrics.gpu
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim", width=12)
    table.add_column("Value", width=40)
    
    # Utilization with progress bar
    util_color = get_usage_color(gpu.utilization_percent)
    util_bar = create_progress_bar(gpu.utilization_percent)
    table.add_row("Usage:", f"[{util_color}]{gpu.utilization_percent:.1f}%[/{util_color}]  {util_bar}")
    
    # Memory
    mem_color = get_usage_color(gpu.memory_usage_percent)
    mem_bar = create_progress_bar(gpu.memory_usage_percent)
    table.add_row(
        "Memory:",
        f"{format_bytes(gpu.memory_used_bytes)} / {format_bytes(gpu.memory_total_bytes)} "
        f"([{mem_color}]{gpu.memory_usage_percent:.1f}%[/{mem_color}])"
    )
    table.add_row("", mem_bar)
    
    # Temperature
    temp_color = get_temp_color(gpu.temperature_celsius)
    table.add_row("Temp:", f"[{temp_color}]{gpu.temperature_celsius:.1f}°C[/{temp_color}]")
    
    # Power
    table.add_row("Power:", f"{gpu.power_watts:.1f}W")
    
    panel = Panel(table, title="GPU", border_style="green")
    console.print(panel)


def display_temperature_metrics(metrics: SystemMetrics) -> None:
    """Display temperature metrics only."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Component", style="cyan", width=12)
    table.add_column("Temperature", width=20)
    
    # CPU temperature
    if metrics.cpu.temperature_celsius is not None:
        temp = metrics.cpu.temperature_celsius
        color = get_temp_color(temp)
        table.add_row("CPU:", f"[{color}]{temp:.1f}°C[/{color}]")
    else:
        table.add_row("CPU:", "[dim]N/A[/dim]")
    
    # GPU temperature
    if metrics.gpu is not None:
        temp = metrics.gpu.temperature_celsius
        color = get_temp_color(temp)
        table.add_row("GPU:", f"[{color}]{temp:.1f}°C[/{color}]")
    else:
        table.add_row("GPU:", "[dim]N/A[/dim]")
    
    panel = Panel(table, title="Temperature", border_style="red")
    console.print(panel)


def display_config(config: dict[str, Any]) -> None:
    """Display configuration.
    
    Args:
        config: Configuration dictionary
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    
    # Flatten and display config
    def add_items(d: dict, prefix: str = ""):
        for key, value in d.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                add_items(value, full_key)
            else:
                table.add_row(full_key, str(value))
    
    add_items(config)
    
    panel = Panel(table, title="Configuration", border_style="blue")
    console.print(panel)


def display_json(data: dict[str, Any]) -> None:
    """Display JSON data with syntax highlighting.
    
    Args:
        data: Dictionary to display as JSON
    """
    import json
    from rich.syntax import Syntax
    
    json_str = json.dumps(data, indent=2, default=str)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✅ {message}[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]❌ {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ️  {message}[/blue]")


def build_metrics_panel(
    metrics: SystemMetrics, 
    category: Optional[str] = None,
    timestamp: Optional[str] = None,
    interval: Optional[int] = None
) -> Panel:
    """Build a metrics panel for display.
    
    Args:
        metrics: System metrics to display
        category: Optional category filter (cpu, gpu, ram, disk, temp)
        timestamp: Optional timestamp to display in header
        interval: Optional interval to display in header
        
    Returns:
        Rich Panel containing the metrics
    """
    table = Table(show_header=True, box=None, padding=(0, 1), expand=True)
    table.add_column("Component", style="bold cyan", width=10)
    table.add_column("Usage", width=8, justify="right")
    table.add_column("Bar", width=22)
    table.add_column("Details", width=35)
    table.add_column("Temp", width=8, justify="right")
    
    # Filter by category if specified
    show_cpu = category is None or category == "cpu"
    show_ram = category is None or category == "ram"
    show_disk = category is None or category == "disk"
    show_gpu = category is None or category == "gpu"
    
    # CPU row
    if show_cpu:
        cpu = metrics.cpu
        cpu_color = get_usage_color(cpu.usage_percent)
        cpu_bar = create_progress_bar(cpu.usage_percent, width=20)
        cpu_temp = ""
        if cpu.temperature_celsius is not None:
            temp_color = get_temp_color(cpu.temperature_celsius)
            cpu_temp = f"[{temp_color}]{cpu.temperature_celsius:.0f}°C[/{temp_color}]"
        else:
            cpu_temp = "[dim]N/A[/dim]"
        
        table.add_row(
            "CPU",
            f"[{cpu_color}]{cpu.usage_percent:.1f}%[/{cpu_color}]",
            cpu_bar,
            f"Load: {cpu.load_1m:.1f}/{cpu.load_5m:.1f}/{cpu.load_15m:.1f} | Cores: {cpu.cores}",
            cpu_temp
        )
    
    # RAM row
    if show_ram:
        mem = metrics.memory
        mem_color = get_usage_color(mem.usage_percent)
        mem_bar = create_progress_bar(mem.usage_percent, width=20)
        used = mem.total_bytes - mem.available_bytes
        
        table.add_row(
            "RAM",
            f"[{mem_color}]{mem.usage_percent:.1f}%[/{mem_color}]",
            mem_bar,
            f"{format_bytes(used)} / {format_bytes(mem.total_bytes)}",
            ""
        )
    
    # GPU row
    if show_gpu and metrics.gpu is not None:
        gpu = metrics.gpu
        gpu_color = get_usage_color(gpu.utilization_percent)
        gpu_bar = create_progress_bar(gpu.utilization_percent, width=20)
        gpu_temp = ""
        temp_color = get_temp_color(gpu.temperature_celsius)
        gpu_temp = f"[{temp_color}]{gpu.temperature_celsius:.0f}°C[/{temp_color}]"
        
        table.add_row(
            "GPU",
            f"[{gpu_color}]{gpu.utilization_percent:.1f}%[/{gpu_color}]",
            gpu_bar,
            f"Mem: {format_bytes(gpu.memory_used_bytes)} / {format_bytes(gpu.memory_total_bytes)} | {gpu.power_watts:.1f}W",
            gpu_temp
        )
    
    # Disk rows
    if show_disk:
        for disk in metrics.disks:
            disk_color = get_usage_color(disk.usage_percent)
            disk_bar = create_progress_bar(disk.usage_percent, width=20)
            used = disk.total_bytes - disk.available_bytes
            
            # Truncate mountpoint if too long
            mp = disk.mountpoint
            if len(mp) > 8:
                mp = mp[:7] + "…"
            
            table.add_row(
                f"Disk {mp}",
                f"[{disk_color}]{disk.usage_percent:.1f}%[/{disk_color}]",
                disk_bar,
                f"{format_bytes(used)} / {format_bytes(disk.total_bytes)}",
                ""
            )
    
    # Build title with optional timestamp
    title = "System Metrics"
    if timestamp:
        title = f"System Metrics • {timestamp}"
    
    # Build subtitle
    subtitle = None
    if interval:
        subtitle = f"[dim]Interval: {interval}s | Ctrl+C to stop[/dim]"
    
    return Panel(table, title=title, subtitle=subtitle, border_style="blue")


def display_metrics_live(metrics: SystemMetrics, category: Optional[str] = None) -> None:
    """Display metrics in a compact live monitoring format.
    
    Args:
        metrics: System metrics to display
        category: Optional category filter (cpu, gpu, ram, disk, temp)
    """
    if category == "temp":
        # Temperature only mode
        display_temperature_metrics(metrics)
        return
    
    panel = build_metrics_panel(metrics, category)
    console.print(panel)
