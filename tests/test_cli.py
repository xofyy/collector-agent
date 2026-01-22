"""Tests for CLI commands."""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from collector.cli import app


runner = CliRunner()


class TestVersionCommand:
    """Tests for version command."""

    def test_version_output(self):
        """Test version command outputs version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Collector Agent v" in result.output


class TestStatusCommand:
    """Tests for status command."""

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_status_not_running(self, mock_load_config, mock_collector_class):
        """Test status when collector is not running."""
        from collector.config import Config
        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.daemon_manager.is_running.return_value = False
        mock_collector.daemon_manager.get_pid.return_value = None
        mock_collector.daemon_manager.get_uptime.return_value = None
        mock_collector.check_exporters.return_value = (True, False)
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        mock_collector.cleanup.assert_called_once()

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_status_running(self, mock_load_config, mock_collector_class):
        """Test status when collector is running."""
        from collector.config import Config
        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.daemon_manager.is_running.return_value = True
        mock_collector.daemon_manager.get_pid.return_value = 12345
        mock_collector.daemon_manager.get_uptime.return_value = "1h 30m"
        mock_collector.check_exporters.return_value = (True, True)
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0


class TestStartCommand:
    """Tests for start command."""

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_start_already_running(self, mock_load_config, mock_collector_class):
        """Test start when already running."""
        mock_collector = MagicMock()
        mock_collector.daemon_manager.is_running.return_value = True
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["start", "--daemon"])

        assert result.exit_code == 1
        assert "already running" in result.output.lower()


class TestStopCommand:
    """Tests for stop command."""

    @patch("collector.cli.DaemonManager")
    @patch("collector.cli.load_config")
    def test_stop_not_running(self, mock_load_config, mock_daemon_class):
        """Test stop when not running."""
        mock_daemon = MagicMock()
        mock_daemon.is_running.return_value = False
        mock_daemon_class.return_value = mock_daemon

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert "not running" in result.output.lower()

    @patch("collector.cli.DaemonManager")
    @patch("collector.cli.load_config")
    def test_stop_running(self, mock_load_config, mock_daemon_class):
        """Test stop when running."""
        mock_daemon = MagicMock()
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345
        mock_daemon.stop.return_value = True
        mock_daemon_class.return_value = mock_daemon

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        mock_daemon.stop.assert_called_once()

    @patch("collector.cli.DaemonManager")
    @patch("collector.cli.load_config")
    def test_stop_failed(self, mock_load_config, mock_daemon_class):
        """Test stop when stop fails."""
        mock_daemon = MagicMock()
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345
        mock_daemon.stop.return_value = False
        mock_daemon_class.return_value = mock_daemon

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1


class TestConfigCommands:
    """Tests for config subcommands."""

    @patch("collector.cli.load_config")
    def test_config_show(self, mock_load_config):
        """Test config show command."""
        from collector.config import Config
        mock_load_config.return_value = Config()

        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0

    @patch("collector.cli.set_config_value")
    def test_config_set(self, mock_set_value):
        """Test config set command."""
        from collector.config import Config
        mock_set_value.return_value = Config(interval=120)

        result = runner.invoke(app, ["config", "set", "interval", "120"])

        assert result.exit_code == 0
        mock_set_value.assert_called_once_with("interval", "120")

    @patch("collector.cli.set_config_value")
    def test_config_set_invalid_key(self, mock_set_value):
        """Test config set with invalid key."""
        mock_set_value.side_effect = ValueError("Unknown configuration key")

        result = runner.invoke(app, ["config", "set", "invalid.key", "value"])

        assert result.exit_code == 1

    @patch("collector.cli.save_config")
    def test_config_reset(self, mock_save):
        """Test config reset command."""
        result = runner.invoke(app, ["config", "reset"])

        assert result.exit_code == 0
        mock_save.assert_called_once()


class TestMetricsCommand:
    """Tests for metrics command."""

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_metrics_single_shot(self, mock_load_config, mock_collector_class):
        """Test metrics command single shot mode."""
        from collector.config import Config
        from collector.transformer import SystemMetrics, CpuMetrics, MemoryMetrics

        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.collect_once.return_value = SystemMetrics(
            timestamp="2024-01-01T00:00:00+00:00",
            hostname="test-host",
            cpu=CpuMetrics(
                usage_percent=50.0,
                load_1m=1.0,
                load_5m=0.8,
                load_15m=0.5,
                cores=4
            ),
            memory=MemoryMetrics(
                total_bytes=16000000000,
                available_bytes=8000000000,
                usage_percent=50.0
            ),
            disks=[],
            gpu=None
        )
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["metrics"])

        assert result.exit_code == 0
        mock_collector.cleanup.assert_called_once()

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_metrics_with_category(self, mock_load_config, mock_collector_class):
        """Test metrics command with category filter."""
        from collector.config import Config
        from collector.transformer import SystemMetrics, CpuMetrics, MemoryMetrics

        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.collect_once.return_value = SystemMetrics(
            timestamp="2024-01-01T00:00:00+00:00",
            hostname="test-host",
            cpu=CpuMetrics(
                usage_percent=50.0,
                load_1m=1.0,
                load_5m=0.8,
                load_15m=0.5,
                cores=4
            ),
            memory=MemoryMetrics(
                total_bytes=16000000000,
                available_bytes=8000000000,
                usage_percent=50.0
            ),
            disks=[],
            gpu=None
        )
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["metrics", "cpu"])

        assert result.exit_code == 0


class TestTestCommand:
    """Tests for test command."""

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_test_dry_run(self, mock_load_config, mock_collector_class):
        """Test test command with dry-run flag."""
        from collector.config import Config
        from collector.transformer import SystemMetrics, CpuMetrics, MemoryMetrics

        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.collect_once.return_value = SystemMetrics(
            timestamp="2024-01-01T00:00:00+00:00",
            hostname="test-host",
            cpu=CpuMetrics(
                usage_percent=50.0,
                load_1m=1.0,
                load_5m=0.8,
                load_15m=0.5,
                cores=4
            ),
            memory=MemoryMetrics(
                total_bytes=16000000000,
                available_bytes=8000000000,
                usage_percent=50.0
            ),
            disks=[],
            gpu=None
        )
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["test", "--dry-run"])

        assert result.exit_code == 0

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_test_with_send(self, mock_load_config, mock_collector_class):
        """Test test command that sends metrics."""
        from collector.config import Config
        from collector.transformer import SystemMetrics, CpuMetrics, MemoryMetrics

        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.collect_once.return_value = SystemMetrics(
            timestamp="2024-01-01T00:00:00+00:00",
            hostname="test-host",
            cpu=CpuMetrics(
                usage_percent=50.0,
                load_1m=1.0,
                load_5m=0.8,
                load_15m=0.5,
                cores=4
            ),
            memory=MemoryMetrics(
                total_bytes=16000000000,
                available_bytes=8000000000,
                usage_percent=50.0
            ),
            disks=[],
            gpu=None
        )
        mock_collector.sender.test_connection.return_value = (True, "Connection successful")
        mock_collector.sender.send.return_value = True
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["test"])

        assert result.exit_code == 0
        mock_collector.sender.send.assert_called_once()

    @patch("collector.cli.MetricsCollector")
    @patch("collector.cli.load_config")
    def test_test_send_failed(self, mock_load_config, mock_collector_class):
        """Test test command when send fails."""
        from collector.config import Config
        from collector.transformer import SystemMetrics, CpuMetrics, MemoryMetrics

        config = Config()
        mock_load_config.return_value = config

        mock_collector = MagicMock()
        mock_collector.collect_once.return_value = SystemMetrics(
            timestamp="2024-01-01T00:00:00+00:00",
            hostname="test-host",
            cpu=CpuMetrics(
                usage_percent=50.0,
                load_1m=1.0,
                load_5m=0.8,
                load_15m=0.5,
                cores=4
            ),
            memory=MemoryMetrics(
                total_bytes=16000000000,
                available_bytes=8000000000,
                usage_percent=50.0
            ),
            disks=[],
            gpu=None
        )
        mock_collector.sender.send.return_value = False
        mock_collector.config = config
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(app, ["test"])

        assert result.exit_code == 1
