"""Wrapper utilities for GIO commands to interact with MTP devices."""

import subprocess
import os
from pathlib import Path
from typing import Dict, List, Optional

# ANSI colors
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    BRIGHT_BLUE = '\033[94m'

def shorten_path(path_str: str) -> str:
    """Shorten path by replacing home with ~ and extracting filename."""
    home = str(Path.home())
    if path_str.startswith(home):
        return path_str.replace(home, '~', 1)
    return path_str

def extract_filename(uri_or_path: str) -> str:
    """Extract just the filename from a URI or path."""
    # Remove URI prefix if present
    if '/' in uri_or_path:
        return uri_or_path.split('/')[-1]
    return uri_or_path


# Dry-run mode flag (set by runner)
DRY_RUN = False


def run(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a subprocess command without shell.
    
    Args:
        args: Command and arguments as list
        check: Whether to raise on non-zero exit code
    
    Returns:
        CompletedProcess object
    """
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check
    )


def gio_mount_list() -> str:
    """Get raw output of 'gio mount -li'."""
    result = run(["/usr/bin/gio", "mount", "-li"])
    return result.stdout


def gio_info(location: str, attributes: Optional[List[str]] = None, timeout: Optional[int] = None) -> Dict[str, str]:
    """
    Get file/directory information via 'gio info'.
    
    Args:
        location: URI or path to query
        attributes: List of attributes to query (default: all)
        timeout: Timeout in seconds (default: None = no timeout)
    
    Returns:
        Dictionary of attribute:value pairs (empty dict if location doesn't exist)
    """
    # Optimization: for local paths, use os.stat directly
    if not location.startswith(('mtp://', 'file://', 'smb://', 'ftp://')):
        # Local file path
        try:
            if os.path.exists(location):
                stat_info = os.stat(location)
                return {
                    "standard::size": str(stat_info.st_size),
                    "standard::type": "regular" if os.path.isfile(location) else "directory"
                }
            else:
                return {}  # File doesn't exist
        except Exception:
            # Fall back to gio if there's any issue
            pass
    
    args = ["/usr/bin/gio", "info"]
    
    if attributes:
        args.extend(["-a", ",".join(attributes)])
    
    args.append(location)
    
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {}  # Timeout = treat as inaccessible
    
    if result.returncode != 0:
        return {}  # File doesn't exist or error occurred
    
    # Parse output: lines in format "attribute: value"
    info = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if ": " in line:
            key, value = line.split(": ", 1)
            info[key.strip()] = value.strip()
    
    return info


def get_file_size(info: Dict[str, str]) -> Optional[int]:
    """
    Safely extract file size from gio_info result.
    
    Args:
        info: Dictionary returned by gio_info
    
    Returns:
        File size in bytes, or None if size is unavailable/invalid
    """
    size_value = info.get("standard::size")
    if size_value in (None, "", "Unknown"):
        return None
    
    try:
        return int(size_value)
    except (ValueError, TypeError):
        return None


def gio_list(location: str) -> List[str]:
    """
    List directory contents via 'gio list'.
    
    Args:
        location: URI or path to directory
    
    Returns:
        List of entry names
    """
    result = run(["/usr/bin/gio", "list", location], check=False)
    if result.returncode != 0:
        return []
    
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def gio_copy(src: str, dst: str, recursive: bool = False, overwrite: bool = False, verbose: bool = False) -> bool:
    """
    Copy file or directory via 'gio copy'.
    
    Args:
        src: Source URI or path
        dst: Destination URI or path
        recursive: Copy directories recursively
        overwrite: Overwrite existing files
        verbose: Print verbose output (if False in DRY_RUN, don't print)
    
    Returns:
        True if successful, False otherwise
    """
    if DRY_RUN:
        if verbose:  # Only print if verbose is True
            src_name = extract_filename(src)
            dst_short = shorten_path(dst)
            print(f"  {Colors.CYAN}→{Colors.RESET} {Colors.DIM}{src_name}{Colors.RESET} {Colors.DIM}→{Colors.RESET} {Colors.GREEN}{dst_short}{Colors.RESET}")
        return True
    
    args = ["/usr/bin/gio", "copy"]
    
    if recursive:
        args.append("-r")
    if overwrite:
        args.append("--backup=none")  # Overwrite without creating backups
    
    args.extend([src, dst])
    
    if verbose:
        src_name = extract_filename(src)
        dst_short = shorten_path(dst)
        print(f"  {Colors.GREEN}✓{Colors.RESET} {src_name} → {dst_short}")
    
    result = run(args, check=False)
    
    # Debug: Log detailed error information on failure
    if result.returncode != 0:
        import sys
        error_msg = result.stderr or result.stdout or "Unknown error"
        print(f"  {Colors.RED}✗ Copy failed ({result.returncode}){Colors.RESET}", file=sys.stderr)
        if error_msg.strip():
            # Check if it's a directory copy issue
            if "directory" in error_msg.lower() and not recursive:
                print(f"    {Colors.YELLOW}Hint: Source is a directory, need -r flag{Colors.RESET}", file=sys.stderr)
            else:
                print(f"    Error: {error_msg.strip()}", file=sys.stderr)
    
    return result.returncode == 0


def gio_remove(location: str, verbose: bool = False) -> bool:
    """
    Remove file or directory via 'gio remove'.
    
    Args:
        location: URI or path to remove
        verbose: Print verbose output
    
    Returns:
        True if successful, False otherwise
    """
    if DRY_RUN:
        # Extract just the filename from MTP URI for cleaner display
        if location.startswith('mtp://'):
            # Extract path after 'Internal storage/' or similar
            if '/Internal storage/' in location:
                clean_path = location.split('/Internal storage/', 1)[1]
            else:
                # Fallback: just get the last part
                clean_path = location.split('/')[-1]
        else:
            clean_path = shorten_path(location)
        print(f"  {Colors.RED}×{Colors.RESET} {Colors.DIM}{clean_path}{Colors.RESET}")
        return True
    
    if verbose:
        item_name = extract_filename(location)
        print(f"  {Colors.RED}×{Colors.RESET} Deleted: {item_name}")
    
    result = run(["/usr/bin/gio", "remove", location], check=False)
    return result.returncode == 0


def gio_mkdir(location: str, parents: bool = True) -> bool:
    """
    Create directory via 'gio mkdir'.
    
    Args:
        location: URI or path to create
        parents: Create parent directories as needed
    
    Returns:
        True if successful, False otherwise
    """
    if DRY_RUN:
        return True
    
    args = ["/usr/bin/gio", "mkdir"]
    
    if parents:
        args.append("-p")
    
    args.append(location)
    
    result = run(args, check=False)
    return result.returncode == 0


def gio_trash(location: str) -> bool:
    """
    Move file to trash via 'gio trash'.
    
    Args:
        location: URI or path to trash
    
    Returns:
        True if successful, False otherwise
    """
    if DRY_RUN:
        print(f"  TRASH (dry-run): {location}")
        return True
    
    result = run(["/usr/bin/gio", "trash", location], check=False)
    return result.returncode == 0
