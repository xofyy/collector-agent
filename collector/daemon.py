"""Daemon management for Collector Agent."""

import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


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
        """Write current PID to PID file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        self._start_time = datetime.now()
    
    def _cleanup_pid_file(self) -> None:
        """Remove stale PID file."""
        try:
            self.pid_file.unlink(missing_ok=True)
        except PermissionError:
            pass
    
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
                    stat_file = Path(f"/proc/{pid}/stat")
                    if stat_file.exists():
                        # Use process start time from /proc
                        create_time = os.path.getctime(f"/proc/{pid}")
                        self._start_time = datetime.fromtimestamp(create_time)
                except Exception:
                    pass
        
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
