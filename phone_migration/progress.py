"""
Progress display utilities with animations and progress bars.
"""

import sys
import time
import threading
from typing import Optional


class Spinner:
    """Animated spinner for long-running operations."""
    
    def __init__(self, message: str = "Processing", color: str = '\033[96m'):
        self.message = message
        self.color = color
        self.reset = '\033[0m'
        self.frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.frame_idx = 0
    
    def _spin(self):
        """Internal spin loop."""
        while self.running:
            frame = self.frames[self.frame_idx % len(self.frames)]
            sys.stdout.write(f'\r{self.color}{frame}{self.reset} {self.message}')
            sys.stdout.flush()
            self.frame_idx += 1
            time.sleep(0.1)
    
    def start(self):
        """Start the spinner."""
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
    
    def stop(self, final_message: Optional[str] = None):
        """Stop the spinner."""
        self.running = False
        if self.thread:
            self.thread.join()
        
        # Clear the line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        
        if final_message:
            sys.stdout.write(final_message + '\n')
        
        sys.stdout.flush()


def print_progress_bar(current: int, total: int, prefix: str = '', suffix: str = '', 
                       length: int = 40, fill: str = '█', color: str = '\033[92m'):
    """
    Print a colored progress bar.
    
    Args:
        current: Current progress value
        total: Total value
        prefix: Text before the bar
        suffix: Text after the bar
        length: Character length of bar
        fill: Bar fill character
        color: ANSI color code
    """
    reset = '\033[0m'
    percent = f"{100 * (current / float(total)):.1f}" if total > 0 else "0.0"
    filled_length = int(length * current // total) if total > 0 else 0
    bar = fill * filled_length + '░' * (length - filled_length)
    
    sys.stdout.write(f'\r{prefix} {color}|{bar}|{reset} {percent}% {suffix}')
    sys.stdout.flush()
    
    if current >= total:
        print()  # New line when complete


def format_time_estimate(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


class RuleProgress:
    """Track and display progress for a rule execution."""
    
    def __init__(self, rule_id: str, mode: str, total_rules: int, current_rule: int):
        self.rule_id = rule_id
        self.mode = mode
        self.total_rules = total_rules
        self.current_rule = current_rule
        self.files_processed = 0
        self.folders_processed = 0
        self.start_time = time.time()
        self.spinner: Optional[Spinner] = None
    
    def start(self):
        """Start the rule progress."""
        msg = f"[{self.current_rule}/{self.total_rules}] {self.mode.upper()} ({self.rule_id})"
        self.spinner = Spinner(msg, color='\033[96m')  # Bright cyan
        self.spinner.start()
    
    def update(self, message: str):
        """Update progress with a status message."""
        if self.spinner:
            self.spinner.message = f"[{self.current_rule}/{self.total_rules}] {self.mode.upper()} - {message}"
    
    def update_counts(self, files: int = 0, folders: int = 0):
        """Update file and folder counts."""
        self.files_processed += files
        self.folders_processed += folders
        
        elapsed = time.time() - self.start_time
        rate = self.files_processed / elapsed if elapsed > 0 else 0
        
        msg = f"[{self.current_rule}/{self.total_rules}] {self.mode.upper()} - {self.files_processed} files"
        if self.folders_processed > 0:
            msg += f", {self.folders_processed} folders"
        if rate > 0.1:
            msg += f" ({rate:.1f} files/s)"
        
        if self.spinner:
            self.spinner.message = msg
    
    def stop(self, success: bool = True, summary: str = ""):
        """Stop the rule progress."""
        if self.spinner:
            elapsed = time.time() - self.start_time
            time_str = format_time_estimate(elapsed)
            
            if success:
                icon = '✅'
                color = '\033[92m'  # Bright green
            else:
                icon = '❌'
                color = '\033[91m'  # Bright red
            
            final = f"{color}{icon} [{self.current_rule}/{self.total_rules}] {self.mode.upper()} - {summary} ({time_str})\033[0m"
            self.spinner.stop(final)


class OperationProgress:
    """Overall operation progress tracker."""
    
    def __init__(self, total_rules: int):
        self.total_rules = total_rules
        self.completed_rules = 0
        self.start_time = time.time()
    
    def update(self):
        """Update overall progress bar."""
        self.completed_rules += 1
        elapsed = time.time() - self.start_time
        
        if self.completed_rules < self.total_rules:
            avg_time = elapsed / self.completed_rules
            remaining = (self.total_rules - self.completed_rules) * avg_time
            eta = f"ETA: {format_time_estimate(remaining)}"
        else:
            eta = f"Done in {format_time_estimate(elapsed)}"
        
        print_progress_bar(
            self.completed_rules, 
            self.total_rules,
            prefix='Overall Progress:',
            suffix=eta,
            color='\033[94m'  # Bright blue
        )
