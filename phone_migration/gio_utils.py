"""Wrapper utilities for GIO commands to interact with MTP devices.

Every gio invocation goes through :func:`run`, which times out and turns a
non-zero exit into a :class:`GioError` carrying gio's own first stderr line.
A failed listing is never silently reported as an empty directory.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from .theme import Colors, Icons

# Absolute path: this runs from systemd timers and desktop launchers with no PATH.
GIO = "/usr/bin/gio"

TIMEOUT_SHORT = 60      # list / info / remove / mkdir / mount
TIMEOUT_COPY = 3600     # copy; a large video over MTP is genuinely slow

# Dry-run mode flag (set by runner)
DRY_RUN = False

# Substrings gio uses when a file simply is not there, as opposed to a real failure.
_ABSENT = ("no such file or directory", "not found")

_REMOTE_SCHEMES = ("mtp://", "file://", "smb://", "ftp://")


class GioError(RuntimeError):
    """A gio command failed. The message is gio's own first stderr line."""


class FailureInjector:
    """Simulate failures for testing (e.g. device disconnection)."""

    def __init__(self):
        self.enabled = False
        self.fail_on_copy = False
        self.fail_on_list = False
        self.fail_on_info = False
        self.fail_after_count = None  # Fail after N operations
        self._operation_count = 0

    def reset(self):
        """Reset all failure settings."""
        self.enabled = False
        self.fail_on_copy = False
        self.fail_on_list = False
        self.fail_on_info = False
        self.fail_after_count = None
        self._operation_count = 0

    def should_fail_operation(self) -> bool:
        """Check if current operation should fail."""
        if not self.enabled:
            return False

        if self.fail_after_count is not None:
            self._operation_count += 1
            return self._operation_count > self.fail_after_count

        return False


FAILURE_INJECTOR = FailureInjector()


def _error(result: subprocess.CompletedProcess) -> GioError:
    for line in result.stderr.splitlines():
        if line.strip():
            return GioError(line.strip())
    return GioError(f"gio exited {result.returncode}")


def shorten_path(path_str: str) -> str:
    """Shorten path by replacing home with ~."""
    home = str(Path.home())
    path_str = str(path_str)
    if path_str.startswith(home):
        return path_str.replace(home, '~', 1)
    return path_str


def extract_filename(uri_or_path: str) -> str:
    """Extract just the filename from a URI or path."""
    if '/' in uri_or_path:
        return uri_or_path.split('/')[-1]
    return uri_or_path


def run(args: List[str], check: bool = True,
        timeout: int = TIMEOUT_SHORT) -> subprocess.CompletedProcess:
    """
    Run a gio command without a shell.

    Args:
        args: Command and arguments as a list
        check: Raise GioError on a non-zero exit code
        timeout: Seconds before the command is killed

    Returns:
        CompletedProcess object

    Raises:
        GioError: on timeout, or on a non-zero exit code when check is True
    """
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise GioError(f"timeout after {timeout}s: {' '.join(args[:3])}") from None

    if check and result.returncode != 0:
        raise _error(result)
    return result


def child_uri(parent_uri: str, name: str) -> str:
    """
    Append one entry name to a URI, percent-encoding it.

    Entry names come back from gio decoded, so a raw '#' would start a URI
    fragment and a raw '%' would be read as an escape.
    """
    return parent_uri.rstrip("/") + "/" + quote(name, safe="")


def gio_mount_list() -> str:
    """Get raw output of 'gio mount -li'."""
    return run([GIO, "mount", "-li"]).stdout


def gio_mount(activation_uri: str) -> None:
    """Mount a device, best effort. Already-mounted and unmountable both no-op;
    the caller's next gio call reports the real problem."""
    try:
        run([GIO, "mount", activation_uri])
    except GioError:
        pass


def gio_info(location: str, attributes: Optional[List[str]] = None,
             timeout: Optional[int] = None) -> Dict[str, str]:
    """
    Get file/directory information via 'gio info'.

    Args:
        location: URI or path to query
        attributes: List of attributes to query (default: all)
        timeout: Override the default timeout for this call (default:
            TIMEOUT_SHORT). Callers doing quick reachability checks (e.g.
            rule validation) pass a short timeout here.

    Returns:
        Dictionary of attribute:value pairs, or {} when the file does not exist

    Raises:
        GioError: when gio fails for any reason other than a missing file,
            including a timeout
    """
    # Optimization: for local paths, use os.stat directly
    if not location.startswith(_REMOTE_SCHEMES):
        try:
            stat_info = os.stat(location)
        except FileNotFoundError:
            return {}
        except OSError:
            pass  # fall through to gio, which reports why
        else:
            return {
                "standard::size": str(stat_info.st_size),
                "standard::type": "directory" if os.path.isdir(location) else "regular",
            }

    args = [GIO, "info"]
    if attributes:
        args.extend(["-a", ",".join(attributes)])
    args.append(location)

    result = run(args, check=False, timeout=TIMEOUT_SHORT if timeout is None else timeout)
    if result.returncode != 0:
        err = result.stderr.lower()
        if any(marker in err for marker in _ABSENT):
            return {}
        raise _error(result)

    # Parse output: lines in format "attribute: value"
    info = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if ": " in line:
            key, value = line.split(": ", 1)
            info[key.strip()] = value.strip()

    return info


def is_dir(info: Dict[str, str]) -> bool:
    """True when a gio_info result describes a directory ('directory' from the
    local fast path, '2' from gio itself)."""
    return info.get("standard::type") in ("directory", "2")


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

    Raises:
        GioError: if the listing fails (an unreachable phone is not an empty dir)
    """
    result = run([GIO, "list", location])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def gio_list_detailed(location: str) -> List[Dict]:
    """
    List a directory with type and size in one call, so callers do not need a
    'gio info' round trip per entry.

    Returns:
        [{"name": str, "is_dir": bool, "size": int | None}, ...]

    Raises:
        GioError: if the listing fails
    """
    result = run([GIO, "list", "-a", "standard::type,standard::size", location])

    entries = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # gio prints "name\t<size>\t(<type>)" and appends "attr=value" columns
        # for any attribute beyond name/type/size.
        # ponytail: a tab inside a filename would split wrong; gio offers no
        # machine-readable listing, so a name like that needs gio_info instead.
        fields = line.split("\t")
        try:
            size = int(fields[1])
        except (IndexError, ValueError):
            size = None
        file_type = fields[2].strip("()") if len(fields) > 2 else ""
        entries.append({
            "name": fields[0],
            "is_dir": file_type == "directory",
            "size": size,
        })

    return entries


def gio_copy(src: str, dst: str, recursive: bool = False, verbose: bool = False) -> bool:
    """
    Copy file or directory via 'gio copy'. gio overwrites by default.

    Args:
        src: Source URI or path
        dst: Destination URI or path
        recursive: Copy directories recursively
        verbose: Print one line per copy

    Returns:
        True if successful; on failure prints gio's error and returns False
    """
    name = extract_filename(src)
    dst_short = shorten_path(dst)

    # Failure injection for testing (device disconnection simulation)
    if FAILURE_INJECTOR.enabled and FAILURE_INJECTOR.fail_on_copy:
        if FAILURE_INJECTOR.should_fail_operation():
            if verbose:
                print(f"  {Colors.ERROR}{Icons.FAIL} Copy failed "
                      f"(simulated device disconnection){Colors.RESET}")
            return False

    if DRY_RUN:
        if verbose:
            print(f"  {Colors.INFO}{Icons.ARROW}{Colors.RESET} {Colors.DIM}{name}{Colors.RESET} "
                  f"{Colors.DIM}{Icons.ARROW}{Colors.RESET} {Colors.PATH}{dst_short}{Colors.RESET}")
        return True

    args = [GIO, "copy"]
    if recursive:
        args.append("-r")
    args.extend([src, dst])

    try:
        run(args, timeout=TIMEOUT_COPY)
    except GioError as err:
        print(f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} {name}: {err}")
        return False

    if verbose:
        print(f"  {Colors.SUCCESS}{Icons.OK}{Colors.RESET} {name} {Icons.ARROW} "
              f"{Colors.PATH}{dst_short}{Colors.RESET}")
    return True


def gio_remove(location: str, verbose: bool = False) -> bool:
    """
    Remove file or directory via 'gio remove'.

    Args:
        location: URI or path to remove
        verbose: Print one line per deletion

    Returns:
        True if successful; on failure prints gio's error and returns False
    """
    name = extract_filename(location)

    if DRY_RUN:
        print(f"  {Colors.DELETED}{Icons.DELETE}{Colors.RESET} {Colors.DIM}{name}{Colors.RESET}")
        return True

    try:
        run([GIO, "remove", location])
    except GioError as err:
        print(f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} {name}: {err}")
        return False

    if verbose:
        print(f"  {Colors.DELETED}{Icons.DELETE}{Colors.RESET} Deleted: {name}")
    return True


def gio_mkdir(location: str, parents: bool = True) -> bool:
    """
    Create directory via 'gio mkdir'.

    Args:
        location: URI or path to create
        parents: Create parent directories as needed

    Returns:
        True if the directory now exists (an existing directory counts)
    """
    if DRY_RUN:
        return True

    args = [GIO, "mkdir"]
    if parents:
        args.append("-p")
    args.append(location)

    try:
        result = run(args, check=False)
    except GioError as err:
        print(f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} {extract_filename(location)}: {err}")
        return False

    # gio mkdir -p still fails on an already-existing directory; sync calls this
    # on every run, so that is a success here, not an error.
    return result.returncode == 0 or "file exists" in result.stderr.lower()
