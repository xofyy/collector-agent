"""Daemon management for Collector Agent."""

import logging
import os
import signal
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DaemonManager:
    """Manage daemon process lifecycle."""
    
    def __init__(self, pid_file: str = "/var/run/collector-agent.pid"):
        """Initialize daemon manager.
        
        Args:
            pid_file: Path to PID file
        """
        self.pid_file = Path(pid_file)
        self._start_time: Optional[datetime] = None
    
    def get_pid(self) -> Optional[int]:
        """Get the PID of the running daemon.
        
        Returns:
            PID if daemon is running, None otherwise
        """
        if not self.pid_file.exists():
            return None
        
        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process is actually running using /proc
            # This works without requiring signal permissions
            if Path(f"/proc/{pid}").exists():
                return pid
            else:
                self._cleanup_pid_file()
                return None
        except ValueError:
            # Invalid PID in file
            self._cleanup_pid_file()
            return None
    
    def is_running(self) -> bool:
        """Check if the daemon is running.
        
        Returns:
            True if daemon is running
        """
        return self.get_pid() is not None
    
    def write_pid(self) -> None:
        """Write current PID to PID file atomically."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory, then rename (atomic on POSIX)
        fd, temp_path = tempfile.mkstemp(
            dir=self.pid_file.parent,
            prefix=".pid_",
            suffix=".tmp"
        )
        try:
            os.write(fd, f"{os.getpid()}\n".encode())
            os.close(fd)
            os.rename(temp_path, self.pid_file)
            self._start_time = datetime.now()
        except Exception:
            os.close(fd)
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def _cleanup_pid_file(self) -> None:
        """Remove stale PID file."""
        try:
            self.pid_file.unlink(missing_ok=True)
        except PermissionError:
            logger.warning(f"Permission denied removing PID file: {self.pid_file}")
    
    def _get_process_start_time(self, pid: int) -> Optional[datetime]:
        """Get process start time from /proc.

        Args:
            pid: Process ID

        Returns:
            datetime of process start or None

        Raises:
            FileNotFoundError: If proc files don't exist
            PermissionError: If cannot read proc files
            ValueError: If cannot parse proc files
        """
        # Get system boot time from /proc/stat
        boot_time = None
        stat_path = Path("/proc/stat")
        with open(stat_path, "r") as f:
            for line in f:
                if line.startswith("btime "):
                    boot_time = int(line.split()[1])
                    break

        if boot_time is None:
            raise ValueError("Could not find btime in /proc/stat")

        # Get process start time (field 22) from /proc/{pid}/stat
        proc_stat_path = Path(f"/proc/{pid}/stat")
        with open(proc_stat_path, "r") as f:
            content = f.read()

        # Parse stat file - field 22 is starttime (after the comm field in parentheses)
        # Format: pid (comm) state ... field22 ...
        # Find the closing paren to skip the command name (which may contain spaces)
        close_paren = content.rfind(")")
        if close_paren == -1:
            raise ValueError(f"Invalid /proc/{pid}/stat format")

        fields = content[close_paren + 2:].split()
        # starttime is field 22 (1-indexed), but after comm/state it's index 19 (0-indexed)
        # fields[0] is state, so starttime is fields[19]
        starttime_ticks = int(fields[19])

        # Convert ticks to seconds (SC_CLK_TCK is typically 100 on Linux)
        clock_ticks = os.sysconf("SC_CLK_TCK")
        starttime_seconds = boot_time + (starttime_ticks / clock_ticks)

        return datetime.fromtimestamp(starttime_seconds)

    def get_uptime(self) -> Optional[str]:
        """Get daemon uptime as a formatted string.

        Returns:
            Uptime string or None if not running
        """
        if not self.is_running():
            return None

        if self._start_time is None:
            # Try to get start time from /proc
            pid = self.get_pid()
            if pid:
                try:
                    self._start_time = self._get_process_start_time(pid)
                except (FileNotFoundError, PermissionError, ValueError) as e:
                    logger.debug(f"Could not get process start time: {e}")

        if self._start_time is None:
            return "unknown"

        delta = datetime.now() - self._start_time
        total_seconds = int(delta.total_seconds())

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def stop(self) -> bool:
        """Stop the daemon process.
        
        Returns:
            True if daemon was stopped successfully
        """
        pid = self.get_pid()
        if pid is None:
            return True
        
        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(30):  # Wait up to 3 seconds
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    # Process has terminated
                    self._cleanup_pid_file()
                    return True
            
            # Process didn't terminate, send SIGKILL
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.1)
            self._cleanup_pid_file()
            return True
        
        except ProcessLookupError:
            self._cleanup_pid_file()
            return True
        except PermissionError:
            return False
    
    def daemonize(self) -> None:
        """Fork the current process into a daemon.
        
        This performs the classic double-fork to daemonize.
        """
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process, exit
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork #1 failed: {e}\n")
            sys.exit(1)
        
        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        
        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process, exit
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"Fork #2 failed: {e}\n")
            sys.exit(1)
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        
        with open("/dev/null", "a+") as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())
        
        # Write PID file
        self.write_pid()


class GracefulKiller:
    """Handle graceful shutdown signals."""
    
    def __init__(self):
        """Initialize signal handlers."""
        self.kill_now = False
        signal.signal(signal.SIGINT, self._exit_gracefully)
        signal.signal(signal.SIGTERM, self._exit_gracefully)
    
    def _exit_gracefully(self, signum, frame):
        """Signal handler for graceful shutdown."""
        self.kill_now = True
