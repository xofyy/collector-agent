"""Configuration management for Collector Agent."""

import logging
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# Config file paths
CONFIG_DIR = Path("/etc/collector-agent")
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_CONFIG_FILE = Path(__file__).parent.parent / "config.default.yaml"


class NodeExporterConfig(BaseModel):
    """Configuration for Node Exporter."""

    enabled: bool = True
    url: str = "http://localhost:9100/metrics"
    timeout: int = Field(default=5, ge=1, le=300)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(pattern, v):
            raise ValueError(f"Invalid URL format: {v}")
        return v


class NvidiaSmiConfig(BaseModel):
    """Configuration for nvidia-smi GPU metrics."""
    
    enabled: bool = True
    nvidia_smi_path: Optional[str] = None  # Auto-detect if None


class ExportersConfig(BaseModel):
    """Configuration for all exporters."""
    
    node_exporter: NodeExporterConfig = Field(default_factory=NodeExporterConfig)
    nvidia_smi: NvidiaSmiConfig = Field(default_factory=NvidiaSmiConfig)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "/var/log/collector-agent.log"

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of: {', '.join(sorted(valid_levels))}"
            )
        return upper_v


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    pid_file: str = "/var/run/collector-agent.pid"

    @field_validator("pid_file")
    @classmethod
    def validate_pid_file(cls, v: str) -> str:
        """Validate PID file path is absolute."""
        if not v or not v.startswith("/"):
            raise ValueError(f"PID file must be an absolute path: {v}")
        return v


class Config(BaseModel):
    """Main configuration model."""

    endpoint: str = "http://localhost:8080/metrics"
    interval: int = Field(default=30, ge=1, le=3600)
    exporters: ExportersConfig = Field(default_factory=ExportersConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint URL format."""
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(pattern, v):
            raise ValueError(f"Invalid endpoint URL format: {v}")
        return v


def get_default_config() -> Config:
    """Get default configuration."""
    return Config()


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to /etc/collector-agent/config.yaml

    Returns:
        Config object
    """
    if config_path is None:
        config_path = CONFIG_FILE

    if not config_path.exists():
        logger.debug(f"Config file not found at {config_path}, using defaults")
        return get_default_config()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return Config(**data)
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in config file {config_path}: {e}. Using defaults.")
        return get_default_config()
    except ValidationError as e:
        logger.warning(f"Invalid configuration in {config_path}: {e}. Using defaults.")
        return get_default_config()
    except PermissionError:
        logger.warning(f"Permission denied reading config file {config_path}. Using defaults.")
        return get_default_config()
    except Exception as e:
        logger.warning(f"Error loading config from {config_path}: {e}. Using defaults.")
        return get_default_config()


def save_config(config: Config, config_path: Optional[Path] = None) -> None:
    """Save configuration to YAML file.
    
    Args:
        config: Config object to save
        config_path: Path to config file. Defaults to /etc/collector-agent/config.yaml
    """
    if config_path is None:
        config_path = CONFIG_FILE
    
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False)


def set_config_value(key: str, value: str, config_path: Optional[Path] = None) -> Config:
    """Set a configuration value.
    
    Args:
        key: Configuration key (e.g., 'endpoint', 'interval')
        value: Value to set
        config_path: Path to config file
        
    Returns:
        Updated Config object
    """
    config = load_config(config_path)
    
    # Handle nested keys
    if key == "endpoint":
        config.endpoint = value
    elif key == "interval":
        config.interval = int(value)
    elif key == "logging.level":
        config.logging.level = value
    elif key == "logging.file":
        config.logging.file = value
    elif key == "daemon.pid_file":
        config.daemon.pid_file = value
    elif key == "exporters.node_exporter.url":
        config.exporters.node_exporter.url = value
    elif key == "exporters.node_exporter.enabled":
        config.exporters.node_exporter.enabled = value.lower() == "true"
    elif key == "exporters.node_exporter.timeout":
        config.exporters.node_exporter.timeout = int(value)
    elif key == "exporters.nvidia_smi.enabled":
        config.exporters.nvidia_smi.enabled = value.lower() == "true"
    elif key == "exporters.nvidia_smi.nvidia_smi_path":
        config.exporters.nvidia_smi.nvidia_smi_path = value if value else None
    else:
        raise ValueError(f"Unknown configuration key: {key}")
    
    save_config(config, config_path)
    return config
