"""Path manipulation utilities for desktop and phone paths."""

import os
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote


DEFAULT_STORAGE_LABEL = "Internal storage"

# Storage labels a phone path may name explicitly, and the "~/is", "~/sd" shortcuts.
STORAGE_LABELS = ("Internal storage", "SD Card")
STORAGE_SHORTCUTS = {"is": "Internal storage", "sd": "SD Card"}

# Highest " (n)" suffix tried before a copy is given up on.
# ponytail: 1000 is plenty for a camera roll; raise it if a real collection hits it.
MAX_DUPLICATES = 1000


def expand_desktop(path_str: str) -> Path:
    """
    Expand desktop path with tilde and environment variables.

    Args:
        path_str: Path string potentially with ~ or $VAR

    Returns:
        Absolute Path object

    Raises:
        ValueError: if the path is empty — Path("").resolve() is the CWD, and a
            rule silently pointed at the CWD mirrors or deletes the wrong tree.
    """
    if not (path_str or "").strip():
        raise ValueError("desktop_path is empty")

    expanded = os.path.expanduser(os.path.expandvars(path_str.strip()))
    return Path(expanded).resolve()


def ensure_dir(path: Path) -> None:
    """
    Create directory and parents if they don't exist.

    Args:
        path: Path object to create
    """
    path.mkdir(parents=True, exist_ok=True)


def normalize_phone_path(phone_path: str) -> Tuple[str, List[str]]:
    """
    Normalize phone path and extract storage label and segments.

    Args:
        phone_path: Path on phone, supports shortcuts:
            - "/path" or "~/is/path" -> Internal storage (default)
            - "~/sd/path" -> SD Card storage
            - "Internal storage/path" -> Explicit internal storage
            - "SD Card/path" -> Explicit SD card

    Returns:
        Tuple of (storage_label, path_segments). "." and ".." are dropped, so
        the result can never climb above the storage root.
    """
    # Split on both separators first, so a storage label is only recognised as a
    # whole segment ("Internal storage" alone is the label; "Internal storageX"
    # is an ordinary directory).
    segments = [s for s in (phone_path or "").strip().replace("\\", "/").split("/")
                if s and s not in (".", "..")]

    if len(segments) >= 2 and segments[0] == "~" and segments[1] in STORAGE_SHORTCUTS:
        return STORAGE_SHORTCUTS[segments[1]], segments[2:]

    if segments and segments[0] in STORAGE_LABELS:
        return segments[0], segments[1:]

    return DEFAULT_STORAGE_LABEL, segments


def build_phone_uri(activation_uri: str, phone_path: str) -> str:
    """
    Build full MTP URI for a phone path.

    Args:
        activation_uri: Base MTP URI (e.g., "mtp://[usb:003,009]/")
        phone_path: Path on phone (e.g., "/DCIM/Camera")

    Returns:
        Full MTP URI (e.g., "mtp://[usb:003,009]/Internal%20storage/DCIM/Camera")
    """
    if not activation_uri.endswith("/"):
        activation_uri += "/"

    storage_label, segments = normalize_phone_path(phone_path)

    # The storage label holds a space, so it needs encoding just like the rest.
    return activation_uri + "/".join(quote(s, safe='') for s in [storage_label] + segments)


def next_available_name(dest_dir: Path, base_name: str,
                        rename_duplicates: bool = True) -> Optional[Path]:
    """
    Find next available filename by appending (1), (2), etc.

    Args:
        dest_dir: Destination directory
        base_name: Original filename
        rename_duplicates: If True, rename on conflict; if False, skip on conflict

    Returns:
        Available Path (original or with a " (n)" suffix), or None when the name
        is taken and no free variant was found within MAX_DUPLICATES.
    """
    dest_path = dest_dir / base_name
    if not dest_path.exists():
        return dest_path

    if not rename_duplicates:
        return None

    # Path.suffix keeps a leading dot with the stem, so ".bashrc" -> ".bashrc (1)".
    stem, suffix = dest_path.stem, dest_path.suffix

    for counter in range(1, MAX_DUPLICATES + 1):
        candidate = dest_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate

    return None
