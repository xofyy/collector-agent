"""Tests for daemon management."""

import os
import signal
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from collector.daemon import DaemonManager, GracefulKiller


class TestDaemonManager:
    """Tests for DaemonManager class."""

    @pytest.fixture
    def tmp_pid_file(self, tmp_path):
        """Create a temporary PID file path."""
        return tmp_path / "test.pid"

    @pytest.fixture
    def daemon_manager(self, tmp_pid_file):
        """Create a DaemonManager with temp PID file."""
        return DaemonManager(str(tmp_pid_file))

    def test_init(self, daemon_manager, tmp_pid_file):
        """Test DaemonManager initialization."""
        assert daemon_manager.pid_file == tmp_pid_file
        assert daemon_manager._start_time is None

    def test_get_pid_no_file(self, daemon_manager):
        """Test get_pid returns None when no PID file exists."""
        assert daemon_manager.get_pid() is None

    def test_get_pid_invalid_content(self, daemon_manager, tmp_pid_file):
        """Test get_pid handles invalid PID file content."""
        tmp_pid_file.write_text("not-a-number")
        assert daemon_manager.get_pid() is None
        # Should clean up invalid PID file
        assert not tmp_pid_file.exists()

    def test_get_pid_stale_process(self, daemon_manager, tmp_pid_file):
        """Test get_pid handles stale PID (non-existent process)."""
        # Use a PID that definitely doesn't exist
        tmp_pid_file.write_text("999999999")
        assert daemon_manager.get_pid() is None

    def test_get_pid_running_process(self, daemon_manager, tmp_pid_file):
        """Test get_pid returns PID for running process."""
        # Use current process PID
        current_pid = os.getpid()
        tmp_pid_file.write_text(str(current_pid))
        assert daemon_manager.get_pid() == current_pid

    def test_is_running_no_pid(self, daemon_manager):
        """Test is_running returns False when no PID file."""
        assert daemon_manager.is_running() is False

    def test_is_running_with_pid(self, daemon_manager, tmp_pid_file):
        """Test is_running returns True for running process."""
        tmp_pid_file.write_text(str(os.getpid()))
        assert daemon_manager.is_running() is True

    def test_write_pid_creates_file(self, daemon_manager, tmp_pid_file):
        """Test write_pid creates PID file."""
        daemon_manager.write_pid()
        assert tmp_pid_file.exists()
        assert tmp_pid_file.read_text().strip() == str(os.getpid())

    def test_write_pid_creates_directory(self, tmp_path):
        """Test write_pid creates parent directory."""
        pid_file = tmp_path / "subdir" / "test.pid"
        manager = DaemonManager(str(pid_file))
        manager.write_pid()
        assert pid_file.exists()

    def test_write_pid_sets_start_time(self, daemon_manager):
        """Test write_pid sets start time."""
        assert daemon_manager._start_time is None
        daemon_manager.write_pid()
        assert daemon_manager._start_time is not None
        assert isinstance(daemon_manager._start_time, datetime)

    def test_write_pid_atomic(self, daemon_manager, tmp_pid_file):
        """Test write_pid is atomic (no partial writes)."""
        # Write PID multiple times quickly
        for _ in range(10):
            daemon_manager.write_pid()
            content = tmp_pid_file.read_text().strip()
            # Should always be a valid integer
            assert content.isdigit()

    def test_cleanup_pid_file(self, daemon_manager, tmp_pid_file):
        """Test _cleanup_pid_file removes file."""
        tmp_pid_file.write_text("12345")
        daemon_manager._cleanup_pid_file()
        assert not tmp_pid_file.exists()

    def test_cleanup_pid_file_missing(self, daemon_manager):
        """Test _cleanup_pid_file handles missing file."""
        # Should not raise
        daemon_manager._cleanup_pid_file()

    def test_get_uptime_not_running(self, daemon_manager):
        """Test get_uptime returns None when not running."""
        assert daemon_manager.get_uptime() is None

    def test_get_uptime_with_start_time(self, daemon_manager, tmp_pid_file):
        """Test get_uptime with known start time."""
        tmp_pid_file.write_text(str(os.getpid()))
        daemon_manager._start_time = datetime.now()

        time.sleep(0.1)  # Small delay

        uptime = daemon_manager.get_uptime()
        assert uptime is not None
        assert "s" in uptime  # Should contain seconds

    def test_get_uptime_format_seconds(self, daemon_manager, tmp_pid_file):
        """Test uptime format for seconds only."""
        tmp_pid_file.write_text(str(os.getpid()))
        daemon_manager._start_time = datetime.now()

        uptime = daemon_manager.get_uptime()
        assert "s" in uptime
        assert "m" not in uptime or "0m" in uptime

    def test_get_uptime_format_minutes(self, daemon_manager, tmp_pid_file):
        """Test uptime format with minutes."""
        tmp_pid_file.write_text(str(os.getpid()))
        # Set start time 2 minutes ago
        from datetime import timedelta
        daemon_manager._start_time = datetime.now() - timedelta(minutes=2, seconds=30)

        uptime = daemon_manager.get_uptime()
        assert "2m" in uptime
        assert "30s" in uptime

    def test_get_uptime_format_hours(self, daemon_manager, tmp_pid_file):
        """Test uptime format with hours."""
        tmp_pid_file.write_text(str(os.getpid()))
        # Set start time 1 hour and 30 minutes ago
        from datetime import timedelta
        daemon_manager._start_time = datetime.now() - timedelta(hours=1, minutes=30)

        uptime = daemon_manager.get_uptime()
        assert "1h" in uptime
        assert "30m" in uptime

    @patch("collector.daemon.Path.exists")
    @patch("collector.daemon.os.kill")
    def test_stop_sends_sigterm(self, mock_kill, mock_exists, daemon_manager, tmp_pid_file):
        """Test stop sends SIGTERM."""
        tmp_pid_file.write_text("12345")
        # Mock /proc/12345 to exist, but PID file check uses real exists
        mock_exists.side_effect = lambda: True

        # Simulate process terminating after SIGTERM
        mock_kill.side_effect = [None, ProcessLookupError()]

        # Manually set up the scenario - override get_pid to return 12345
        with patch.object(daemon_manager, 'get_pid', return_value=12345):
            result = daemon_manager.stop()

        assert result is True
        mock_kill.assert_any_call(12345, signal.SIGTERM)

    def test_stop_not_running(self, daemon_manager):
        """Test stop returns True when not running."""
        assert daemon_manager.stop() is True

    @patch("collector.daemon.os.kill")
    def test_stop_permission_denied(self, mock_kill, daemon_manager, tmp_pid_file):
        """Test stop handles permission denied."""
        tmp_pid_file.write_text("12345")
        mock_kill.side_effect = PermissionError()

        # Override get_pid to return 12345
        with patch.object(daemon_manager, 'get_pid', return_value=12345):
            result = daemon_manager.stop()

        assert result is False

    @patch("collector.daemon.os.kill")
    def test_stop_cleans_up_pid_file(self, mock_kill, daemon_manager, tmp_pid_file):
        """Test stop cleans up PID file after termination."""
        tmp_pid_file.write_text("12345")
        mock_kill.side_effect = [None, ProcessLookupError()]

        with patch.object(daemon_manager, 'get_pid', return_value=12345):
            daemon_manager.stop()

        assert not tmp_pid_file.exists()


class TestGracefulKiller:
    """Tests for GracefulKiller class."""

    def test_initial_state(self):
        """Test initial kill_now is False."""
        killer = GracefulKiller()
        assert killer.kill_now is False

    def test_sigterm_sets_kill_now(self):
        """Test SIGTERM handler sets kill_now."""
        killer = GracefulKiller()
        killer._exit_gracefully(signal.SIGTERM, None)
        assert killer.kill_now is True

    def test_sigint_sets_kill_now(self):
        """Test SIGINT handler sets kill_now."""
        killer = GracefulKiller()
        killer._exit_gracefully(signal.SIGINT, None)
        assert killer.kill_now is True

    def test_multiple_signals(self):
        """Test multiple signal calls still result in kill_now True."""
        killer = GracefulKiller()
        killer._exit_gracefully(signal.SIGTERM, None)
        killer._exit_gracefully(signal.SIGINT, None)
        assert killer.kill_now is True


class TestDaemonManagerProcessStartTime:
    """Tests for _get_process_start_time method."""

    @pytest.fixture
    def daemon_manager(self, tmp_path):
        """Create a DaemonManager with temp PID file."""
        return DaemonManager(str(tmp_path / "test.pid"))

    def test_get_process_start_time_current_process(self, daemon_manager):
        """Test getting start time for current process."""
        pid = os.getpid()
        start_time = daemon_manager._get_process_start_time(pid)

        assert start_time is not None
        assert isinstance(start_time, datetime)
        # Start time should be in the past
        assert start_time < datetime.now()

    def test_get_process_start_time_invalid_pid(self, daemon_manager):
        """Test getting start time for invalid PID raises error."""
        with pytest.raises(FileNotFoundError):
            daemon_manager._get_process_start_time(999999999)
