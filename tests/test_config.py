"""Tests for configuration management."""

import pytest
from pathlib import Path

import yaml
from pydantic import ValidationError

from collector.config import (
    Config,
    LoggingConfig,
    DaemonConfig,
    NodeExporterConfig,
    ExportersConfig,
    load_config,
    save_config,
    set_config_value,
    get_default_config,
)


class TestNodeExporterConfig:
    """Tests for NodeExporterConfig validation."""

    def test_valid_url(self):
        """Test valid URL passes validation."""
        config = NodeExporterConfig(url="http://localhost:9100/metrics")
        assert config.url == "http://localhost:9100/metrics"

    def test_valid_https_url(self):
        """Test valid HTTPS URL passes validation."""
        config = NodeExporterConfig(url="https://example.com:9100/metrics")
        assert config.url == "https://example.com:9100/metrics"

    def test_invalid_url_raises_error(self):
        """Test invalid URL raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeExporterConfig(url="not-a-valid-url")

    def test_invalid_url_no_protocol(self):
        """Test URL without protocol raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeExporterConfig(url="localhost:9100/metrics")

    def test_timeout_valid(self):
        """Test valid timeout value."""
        config = NodeExporterConfig(timeout=30)
        assert config.timeout == 30

    def test_timeout_min_bound(self):
        """Test timeout minimum bound (1)."""
        config = NodeExporterConfig(timeout=1)
        assert config.timeout == 1

    def test_timeout_max_bound(self):
        """Test timeout maximum bound (300)."""
        config = NodeExporterConfig(timeout=300)
        assert config.timeout == 300

    def test_timeout_below_min_raises_error(self):
        """Test timeout below minimum raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeExporterConfig(timeout=0)

    def test_timeout_above_max_raises_error(self):
        """Test timeout above maximum raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeExporterConfig(timeout=301)


class TestLoggingConfig:
    """Tests for LoggingConfig validation."""

    def test_valid_log_levels(self):
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_lowercase_log_level_normalized(self):
        """Test lowercase log level is normalized to uppercase."""
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"

    def test_mixed_case_log_level_normalized(self):
        """Test mixed case log level is normalized to uppercase."""
        config = LoggingConfig(level="Warning")
        assert config.level == "WARNING"

    def test_invalid_log_level_raises_error(self):
        """Test invalid log level raises ValidationError."""
        with pytest.raises(ValidationError):
            LoggingConfig(level="INVALID")

    def test_invalid_log_level_typo(self):
        """Test typo in log level raises ValidationError."""
        with pytest.raises(ValidationError):
            LoggingConfig(level="INFOO")


class TestDaemonConfig:
    """Tests for DaemonConfig validation."""

    def test_valid_pid_file(self):
        """Test valid PID file path."""
        config = DaemonConfig(pid_file="/var/run/test.pid")
        assert config.pid_file == "/var/run/test.pid"

    def test_relative_path_raises_error(self):
        """Test relative path raises ValidationError."""
        with pytest.raises(ValidationError):
            DaemonConfig(pid_file="relative/path.pid")

    def test_empty_path_raises_error(self):
        """Test empty path raises ValidationError."""
        with pytest.raises(ValidationError):
            DaemonConfig(pid_file="")


class TestConfig:
    """Tests for main Config validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.endpoint == "http://localhost:8080/metrics"
        assert config.interval == 30

    def test_valid_endpoint(self):
        """Test valid endpoint URL."""
        config = Config(endpoint="https://api.example.com/metrics")
        assert config.endpoint == "https://api.example.com/metrics"

    def test_invalid_endpoint_raises_error(self):
        """Test invalid endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            Config(endpoint="not-a-url")

    def test_interval_valid(self):
        """Test valid interval value."""
        config = Config(interval=60)
        assert config.interval == 60

    def test_interval_min_bound(self):
        """Test interval minimum bound (1)."""
        config = Config(interval=1)
        assert config.interval == 1

    def test_interval_max_bound(self):
        """Test interval maximum bound (3600)."""
        config = Config(interval=3600)
        assert config.interval == 3600

    def test_interval_below_min_raises_error(self):
        """Test interval below minimum raises ValidationError."""
        with pytest.raises(ValidationError):
            Config(interval=0)

    def test_interval_above_max_raises_error(self):
        """Test interval above maximum raises ValidationError."""
        with pytest.raises(ValidationError):
            Config(interval=3601)


class TestGetDefaultConfig:
    """Tests for get_default_config function."""

    def test_returns_config(self):
        """Test get_default_config returns Config instance."""
        config = get_default_config()
        assert isinstance(config, Config)

    def test_default_values(self):
        """Test default values are correct."""
        config = get_default_config()
        assert config.endpoint == "http://localhost:8080/metrics"
        assert config.interval == 30
        assert config.logging.level == "INFO"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_nonexistent_file_returns_defaults(self, tmp_path):
        """Test loading nonexistent file returns defaults."""
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.endpoint == "http://localhost:8080/metrics"

    def test_load_valid_config(self, tmp_path):
        """Test loading valid config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({
            "endpoint": "http://test.com/metrics",
            "interval": 60
        }))

        config = load_config(config_path)
        assert config.endpoint == "http://test.com/metrics"
        assert config.interval == 60

    def test_load_partial_config(self, tmp_path):
        """Test loading partial config merges with defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({
            "interval": 120
        }))

        config = load_config(config_path)
        assert config.endpoint == "http://localhost:8080/metrics"  # default
        assert config.interval == 120  # from file

    def test_load_invalid_yaml_returns_defaults(self, tmp_path):
        """Test loading invalid YAML returns defaults with warning."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content: [")

        config = load_config(config_path)
        assert config.endpoint == "http://localhost:8080/metrics"

    def test_load_invalid_values_returns_defaults(self, tmp_path):
        """Test loading invalid values returns defaults with warning."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({
            "endpoint": "not-a-valid-url"
        }))

        config = load_config(config_path)
        assert config.endpoint == "http://localhost:8080/metrics"

    def test_load_empty_file_returns_defaults(self, tmp_path):
        """Test loading empty file returns defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        config = load_config(config_path)
        assert config.endpoint == "http://localhost:8080/metrics"


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config(self, tmp_path):
        """Test saving configuration."""
        config_path = tmp_path / "config.yaml"
        config = Config(endpoint="http://test.com/metrics", interval=120)

        save_config(config, config_path)

        assert config_path.exists()
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["endpoint"] == "http://test.com/metrics"
        assert loaded["interval"] == 120

    def test_save_creates_directory(self, tmp_path):
        """Test save creates parent directory."""
        config_path = tmp_path / "subdir" / "config.yaml"
        config = Config()

        save_config(config, config_path)

        assert config_path.exists()

    def test_save_overwrites_existing(self, tmp_path):
        """Test save overwrites existing file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("old: content")

        config = Config(interval=60)
        save_config(config, config_path)

        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["interval"] == 60
        assert "old" not in loaded


class TestSetConfigValue:
    """Tests for set_config_value function."""

    def test_set_endpoint(self, tmp_path):
        """Test setting endpoint value."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        config = set_config_value("endpoint", "http://new.com/metrics", config_path)
        assert config.endpoint == "http://new.com/metrics"

    def test_set_interval(self, tmp_path):
        """Test setting interval value."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        config = set_config_value("interval", "120", config_path)
        assert config.interval == 120

    def test_set_logging_level(self, tmp_path):
        """Test setting logging level."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        config = set_config_value("logging.level", "DEBUG", config_path)
        assert config.logging.level == "DEBUG"

    def test_set_exporter_enabled(self, tmp_path):
        """Test setting exporter enabled flag."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        config = set_config_value("exporters.node_exporter.enabled", "false", config_path)
        assert config.exporters.node_exporter.enabled is False

    def test_set_unknown_key_raises_error(self, tmp_path):
        """Test setting unknown key raises ValueError."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        with pytest.raises(ValueError, match="Unknown configuration key"):
            set_config_value("unknown.key", "value", config_path)

    def test_set_persists_to_file(self, tmp_path):
        """Test set_config_value persists changes to file."""
        config_path = tmp_path / "config.yaml"
        save_config(Config(), config_path)

        set_config_value("interval", "90", config_path)

        # Reload from file to verify persistence
        reloaded = load_config(config_path)
        assert reloaded.interval == 90
