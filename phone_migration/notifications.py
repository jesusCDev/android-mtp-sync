"""Desktop notification support for operation completion and errors."""

import subprocess
import shutil
from typing import Optional


def is_notify_available() -> bool:
    """Check if notify-send is available on the system."""
    return shutil.which("notify-send") is not None


def send_notification(
    title: str,
    message: str,
    urgency: str = "normal",
    icon: Optional[str] = None,
    timeout: int = 5000
) -> bool:
    """
    Send a desktop notification using notify-send.
    
    Args:
        title: Notification title
        message: Notification body text
        urgency: Urgency level - "low", "normal", or "critical"
        icon: Icon name or path (default: phone icon)
        timeout: Display duration in milliseconds (0 = no timeout)
    
    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not is_notify_available():
        return False
    
    # Default icon for phone sync
    if icon is None:
        icon = "phone"  # Standard freedesktop icon name
    
    try:
        cmd = [
            "notify-send",
            f"--urgency={urgency}",
            f"--icon={icon}",
            f"--expire-time={timeout}",
            title,
            message
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=2
        )
        
        return result.returncode == 0
    
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def notify_completion(stats: dict, dry_run: bool = False) -> None:
    """
    Send notification when sync operations complete.
    
    Args:
        stats: Dictionary with operation statistics
        dry_run: Whether this was a dry run
    """
    if dry_run:
        # Don't notify for dry runs
        return
    
    total_copied = stats.get("copied", 0)
    total_errors = stats.get("errors", 0)
    moved_count = stats.get("moved", 0)
    synced_count = stats.get("synced", 0)
    backed_up_count = stats.get("backed_up", 0)
    
    # Build message
    parts = []
    if moved_count > 0:
        parts.append(f"📤 {moved_count} moved")
    if backed_up_count > 0:
        parts.append(f"📋 {backed_up_count} backed up")
    if synced_count > 0:
        parts.append(f"🔄 {synced_count} synced")
    
    if not parts:
        parts.append(f"{total_copied} files processed")
    
    message = ", ".join(parts)
    
    # Add error count if any
    if total_errors > 0:
        message += f"\n⚠️ {total_errors} error(s)"
        urgency = "critical"
        icon = "dialog-warning"
        title = "📱 Phone Sync - Completed with Errors"
    else:
        urgency = "normal"
        icon = "phone"
        title = "📱 Phone Sync - Complete"
    
    send_notification(
        title=title,
        message=message,
        urgency=urgency,
        icon=icon,
        timeout=5000
    )


def notify_error(error_message: str) -> None:
    """
    Send critical notification for errors.
    
    Args:
        error_message: Error description
    """
    send_notification(
        title="📱 Phone Sync - Error",
        message=error_message,
        urgency="critical",
        icon="dialog-error",
        timeout=10000  # Show errors longer
    )


def notify_device_not_found() -> None:
    """Send notification when device is not detected."""
    send_notification(
        title="📱 Phone Sync - Device Not Found",
        message="Phone not connected or not registered.\nConnect phone and enable File Transfer mode.",
        urgency="normal",
        icon="phone-disconnect",
        timeout=5000
    )
