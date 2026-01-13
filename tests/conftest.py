"""Pytest configuration and fixtures."""

import pytest


# Sample Prometheus format data for testing
SAMPLE_NODE_EXPORTER_OUTPUT = """
# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{cpu="0",mode="idle"} 10000.5
node_cpu_seconds_total{cpu="0",mode="system"} 500.2
node_cpu_seconds_total{cpu="0",mode="user"} 1500.3
node_cpu_seconds_total{cpu="1",mode="idle"} 9800.1
node_cpu_seconds_total{cpu="1",mode="system"} 600.4
node_cpu_seconds_total{cpu="1",mode="user"} 1700.5
# HELP node_load1 1m load average.
# TYPE node_load1 gauge
node_load1 1.5
# HELP node_load5 5m load average.
# TYPE node_load5 gauge
node_load5 1.2
# HELP node_load15 15m load average.
# TYPE node_load15 gauge
node_load15 0.9
# HELP node_memory_MemTotal_bytes Memory information field MemTotal_bytes.
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes 17179869184
# HELP node_memory_MemAvailable_bytes Memory information field MemAvailable_bytes.
# TYPE node_memory_MemAvailable_bytes gauge
node_memory_MemAvailable_bytes 8589934592
# HELP node_filesystem_size_bytes Filesystem size in bytes.
# TYPE node_filesystem_size_bytes gauge
node_filesystem_size_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 274877906944
node_filesystem_size_bytes{device="/dev/sda2",fstype="ext4",mountpoint="/home"} 549755813888
# HELP node_filesystem_avail_bytes Filesystem space available to non-root users in bytes.
# TYPE node_filesystem_avail_bytes gauge
node_filesystem_avail_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 137438953472
node_filesystem_avail_bytes{device="/dev/sda2",fstype="ext4",mountpoint="/home"} 274877906944
# HELP node_hwmon_temp_celsius Hardware monitor for temperature
# TYPE node_hwmon_temp_celsius gauge
node_hwmon_temp_celsius{chip="coretemp",sensor="temp1"} 52.0
"""

SAMPLE_DCGM_OUTPUT = """
# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization.
# TYPE DCGM_FI_DEV_GPU_UTIL gauge
DCGM_FI_DEV_GPU_UTIL{gpu="0"} 35.0
# HELP DCGM_FI_DEV_FB_USED Framebuffer memory used.
# TYPE DCGM_FI_DEV_FB_USED gauge
DCGM_FI_DEV_FB_USED{gpu="0"} 4096
# HELP DCGM_FI_DEV_FB_FREE Framebuffer memory free.
# TYPE DCGM_FI_DEV_FB_FREE gauge
DCGM_FI_DEV_FB_FREE{gpu="0"} 8192
# HELP DCGM_FI_DEV_GPU_TEMP GPU temperature.
# TYPE DCGM_FI_DEV_GPU_TEMP gauge
DCGM_FI_DEV_GPU_TEMP{gpu="0"} 48.0
# HELP DCGM_FI_DEV_POWER_USAGE Power usage.
# TYPE DCGM_FI_DEV_POWER_USAGE gauge
DCGM_FI_DEV_POWER_USAGE{gpu="0"} 120.5
"""


@pytest.fixture
def sample_node_exporter_output():
    """Return sample Node Exporter output."""
    return SAMPLE_NODE_EXPORTER_OUTPUT


@pytest.fixture
def sample_dcgm_output():
    """Return sample DCGM Exporter output."""
    return SAMPLE_DCGM_OUTPUT
