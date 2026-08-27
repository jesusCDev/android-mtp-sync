"""
Preflight checks for migration operations.

Validates disk space, estimates transfer sizes, and provides safety checks
before copy, move, sync, and backup operations.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging

from . import gio_utils, paths

logger = logging.getLogger(__name__)


class PreflightError(Exception):
    """Raised when preflight checks fail."""
    pass


def estimate_transfer_size(source_path: str, rule_type: str = "copy") -> int:
    """
    Estimate total bytes to transfer for a rule.
    
    Args:
        source_path: Path to copy from (desktop for copy/move/backup, phone for sync)
        rule_type: 'copy', 'move', 'backup', or 'sync'
    
    Returns:
        Total bytes to transfer
    """
    if not os.path.exists(source_path):
        logger.warning(f"Source path does not exist: {source_path}")
        return 0
    
    total_bytes = 0
    visited_inodes = set()
    
    for root, dirs, files in os.walk(source_path, followlinks=True):
        # Guard against symlink loops
        try:
            inode = os.stat(root).st_ino
            if inode in visited_inodes:
                dirs[:] = []  # Don't recurse
                continue
            visited_inodes.add(inode)
        except OSError:
            continue
        
        for file in files:
            file_path = os.path.join(root, file)
            try:
                total_bytes += os.path.getsize(file_path)
            except OSError as e:
                logger.warning(f"Could not get size of {file_path}: {e}")
                continue
    
    return total_bytes



def estimate_phone_size(rule: Dict[str, Any], device: Dict[str, Any],
                        max_entries: int = 2000) -> int:
    """
    Lower bound on the bytes a phone-to-desktop rule will pull down.

    Walks the rule's phone directory with gio, summing file sizes. A subtree
    that will not list is skipped rather than aborting the estimate, and a
    phone that is unreachable estimates 0 (the check then always passes, which
    is what the caller wants - a bad estimate must not block a real transfer).

    # ponytail: a lower bound truncated at max_entries, not an exact total. An
    # exhaustive walk of a large MTP tree costs minutes before a transfer that
    # is itself minutes long. Raise the cap (or estimate per-entry averages) if
    # runs start passing preflight and then running out of space.

    Args:
        rule: Rule dict with 'phone_path'
        device: Device dict with 'activation_uri'
        max_entries: Stop after inspecting this many directory entries

    Returns:
        Total bytes of the files seen before the cap was reached
    """
    root = paths.build_phone_uri(device.get("activation_uri", ""),
                                 rule.get("phone_path", ""))
    total_bytes = 0
    seen = 0
    stack = [root]

    while stack and seen < max_entries:
        uri = stack.pop()
        try:
            entries = gio_utils.gio_list_detailed(uri)
        except gio_utils.GioError as e:
            logger.warning(f"Could not list {uri} for the size estimate: {e}")
            continue

        for entry in entries:
            seen += 1
            if entry["is_dir"]:
                stack.append(gio_utils.child_uri(uri, entry["name"]))
            else:
                total_bytes += entry.get("size") or 0
            if seen >= max_entries:
                logger.info(f"Size estimate truncated at {max_entries} entries")
                break

    return total_bytes


def query_free_space_desktop(path: str) -> int:
    """
    Query free space on the desktop filesystem holding `path`.

    The destination directory usually does not exist yet - the operation
    creates it moments after this check - so the nearest existing ancestor is
    measured instead. It is on the same filesystem in every case that matters.

    Args:
        path: Path on desktop filesystem

    Returns:
        Free bytes available
    """
    probe = Path(path).expanduser()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent

    try:
        stat = shutil.disk_usage(probe)
        return stat.free
    except OSError as e:
        logger.error(f"Could not query free space for {path}: {e}")
        raise PreflightError(f"Cannot determine free space: {e}")


def query_free_space_phone(device_info: Dict[str, Any]) -> Optional[int]:
    """
    Query free space on phone (best-effort, may not be available).
    
    Args:
        device_info: Device information dict with activation_uri
    
    Returns:
        Free bytes if available, None if cannot determine
    """
    # Note: MTP protocol does not standardly expose free space
    # This is a placeholder for future enhancement or fallback
    logger.info("Phone free space query not yet supported via MTP")
    return None


def validate_space_or_abort(
    total_bytes: int,
    free_bytes: int,
    headroom_percent: float = 5.0,
    operation_name: str = "Transfer"
) -> None:
    """
    Validate sufficient space is available.
    
    Args:
        total_bytes: Total bytes to transfer
        free_bytes: Free space available on destination
        headroom_percent: Minimum free space to reserve after operation (default 5%)
        operation_name: Name of operation (for error message)
    
    Raises:
        PreflightError: If insufficient space
    """
    # Calculate headroom
    required_total = total_bytes + (free_bytes * headroom_percent / 100)
    
    if required_total > free_bytes:
        deficit = required_total - free_bytes
        raise PreflightError(
            f"{operation_name} failed preflight check:\n"
            f"  Need: {_format_bytes(total_bytes)}\n"
            f"  Free: {_format_bytes(free_bytes)}\n"
            f"  Deficit: {_format_bytes(deficit)}\n"
            f"  (+ {headroom_percent}% headroom)\n"
            f"Please free up space and try again."
        )
    
    logger.info(
        f"{operation_name} preflight OK: {_format_bytes(total_bytes)} "
        f"to transfer, {_format_bytes(free_bytes)} available"
    )


def preflight_copy(rule: Dict[str, Any], device: Dict[str, Any]) -> None:
    """
    Preflight check for copy operation.
    
    Args:
        rule: Copy rule dict with 'phone_path' and 'desktop_path'
        device: Device dict with 'activation_uri'
    
    Raises:
        PreflightError: If checks fail
    """
    desktop_path = rule.get("desktop_path", "")
    desktop_path = os.path.expanduser(desktop_path)
    
    # For copy, we need space on desktop
    total_bytes = estimate_phone_size(rule, device)
    free_bytes = query_free_space_desktop(desktop_path)
    
    validate_space_or_abort(total_bytes, free_bytes, operation_name="Copy")


def preflight_move(rule: Dict[str, Any], device: Dict[str, Any]) -> None:
    """
    Preflight check for move operation.
    
    Args:
        rule: Move rule dict with 'phone_path' and 'desktop_path'
        device: Device dict with 'activation_uri'
    
    Raises:
        PreflightError: If checks fail
    """
    desktop_path = rule.get("desktop_path", "")
    desktop_path = os.path.expanduser(desktop_path)
    
    # For move, same as copy - we need space on desktop
    total_bytes = estimate_phone_size(rule, device)
    free_bytes = query_free_space_desktop(desktop_path)
    
    validate_space_or_abort(total_bytes, free_bytes, operation_name="Move")


def preflight_sync(rule: Dict[str, Any], device: Dict[str, Any]) -> None:
    """
    Preflight check for sync operation.
    
    Args:
        rule: Sync rule dict with 'desktop_path' and 'phone_path'
        device: Device dict with 'activation_uri'
    
    Raises:
        PreflightError: If checks fail
    """
    desktop_path = rule.get("desktop_path", "")
    desktop_path = os.path.expanduser(desktop_path)
    
    # For sync, we need space on phone (best-effort)
    total_bytes = estimate_transfer_size(desktop_path, "sync")
    
    # Try to query phone free space (may not be available)
    free_bytes = query_free_space_phone(device)
    if free_bytes is None:
        logger.warning(
            "Cannot determine phone free space. "
            "Skipping space check for sync. "
            f"Estimated transfer: {_format_bytes(total_bytes)}"
        )
        return
    
    validate_space_or_abort(total_bytes, free_bytes, operation_name="Sync")


def preflight_backup(rule: Dict[str, Any], device: Dict[str, Any]) -> None:
    """
    Preflight check for backup operation.
    
    Args:
        rule: Backup rule dict with 'desktop_path' and 'phone_path'
        device: Device dict with 'activation_uri'
    
    Raises:
        PreflightError: If checks fail
    """
    desktop_path = rule.get("desktop_path", "")
    desktop_path = os.path.expanduser(desktop_path)
    
    # For backup, we need space on desktop
    total_bytes = estimate_phone_size(rule, device)
    free_bytes = query_free_space_desktop(desktop_path)
    
    validate_space_or_abort(total_bytes, free_bytes, operation_name="Backup")


def _format_bytes(num_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"
