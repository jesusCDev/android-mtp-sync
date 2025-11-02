"""Transfer statistics tracking for file operations."""

import time
from typing import Optional


class TransferStats:
    """Track transfer statistics for file operations."""
    
    def __init__(self):
        """Initialize transfer statistics."""
        self.start_time: Optional[float] = None
        self.total_bytes: int = 0
        self.files_processed: int = 0
        self.current_file_size: int = 0
        
    def start(self) -> None:
        """Start tracking transfer statistics."""
        self.start_time = time.time()
        self.total_bytes = 0
        self.files_processed = 0
    
    def add_file(self, size_bytes: int) -> None:
        """
        Record a file transfer.
        
        Args:
            size_bytes: Size of the transferred file in bytes
        """
        self.total_bytes += size_bytes
        self.files_processed += 1
    
    def get_elapsed_time(self) -> float:
        """
        Get elapsed time since start.
        
        Returns:
            Elapsed time in seconds, or 0 if not started
        """
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def get_transfer_speed(self) -> float:
        """
        Calculate current transfer speed.
        
        Returns:
            Transfer speed in bytes per second, or 0 if no data yet
        """
        elapsed = self.get_elapsed_time()
        if elapsed <= 0:
            return 0.0
        return self.total_bytes / elapsed
    
    def get_speed_mbps(self) -> float:
        """
        Get transfer speed in MB/s.
        
        Returns:
            Transfer speed in megabytes per second
        """
        return self.get_transfer_speed() / (1024 * 1024)
    
    def estimate_eta(self, remaining_bytes: int) -> float:
        """
        Estimate time remaining for transfer.
        
        Args:
            remaining_bytes: Bytes still to transfer
            
        Returns:
            Estimated time in seconds, or 0 if speed is unknown
        """
        speed = self.get_transfer_speed()
        if speed <= 0:
            return 0.0
        return remaining_bytes / speed
    
    def format_size(self, size_bytes: int) -> str:
        """
        Format byte size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted string (e.g., "1.5 GB", "250 MB")
        """
        if size_bytes >= 1024 * 1024 * 1024:  # GB
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        elif size_bytes >= 1024 * 1024:  # MB
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:  # KB
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} B"
    
    def format_time(self, seconds: float) -> str:
        """
        Format time duration in human-readable format.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted string (e.g., "5m 30s", "1h 15m")
        """
        if seconds < 0:
            return "0s"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def get_summary(self) -> dict:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with formatted statistics
        """
        elapsed = self.get_elapsed_time()
        speed_mbps = self.get_speed_mbps()
        
        return {
            "files": self.files_processed,
            "size": self.format_size(self.total_bytes),
            "size_bytes": self.total_bytes,
            "time": self.format_time(elapsed),
            "time_seconds": elapsed,
            "speed": f"{speed_mbps:.1f} MB/s" if speed_mbps > 0 else "calculating...",
            "speed_mbps": speed_mbps
        }
    
    def format_summary_line(self) -> str:
        """
        Format a one-line summary of transfer stats.
        
        Returns:
            Formatted summary string
        """
        summary = self.get_summary()
        if summary["time_seconds"] < 1:
            return f"{summary['files']} files, {summary['size']}"
        return f"{summary['files']} files, {summary['size']} in {summary['time']} (avg {summary['speed']})"
