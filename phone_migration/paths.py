"""Path manipulation utilities for desktop and phone paths."""

import os
from pathlib import Path
from typing import List, Tuple
from urllib.parse import quote


DEFAULT_STORAGE_LABEL = "Internal storage"


def expand_desktop(path_str: str) -> Path:
    """
    Expand desktop path with tilde and environment variables.
    
    Args:
        path_str: Path string potentially with ~ or $VAR
    
    Returns:
        Absolute Path object
    """
    expanded = os.path.expanduser(os.path.expandvars(path_str))
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
        Tuple of (storage_label, path_segments)
    """
    phone_path = phone_path.strip()
    
    # Handle shortcuts: ~/is/ for internal storage, ~/sd/ for SD card
    if phone_path.startswith("~/is/"):
        storage_label = "Internal storage"
        remainder = phone_path[len("~/is/"):]
    elif phone_path.startswith("~/sd/"):
        storage_label = "SD Card"
        remainder = phone_path[len("~/sd/"):]
    # Check if path starts with explicit storage label
    elif phone_path.startswith("Internal storage/") or phone_path.startswith("Internal storage\\"):
        storage_label = "Internal storage"
        remainder = phone_path[len("Internal storage/"):]
    elif phone_path.startswith("SD Card/") or phone_path.startswith("SD Card\\"):
        storage_label = "SD Card"
        remainder = phone_path[len("SD Card/"):]
    elif phone_path.startswith("/"):
        # Leading slash means under default storage (Internal storage)
        storage_label = DEFAULT_STORAGE_LABEL
        remainder = phone_path[1:]  # Remove leading slash
    else:
        # No leading slash or storage label - assume default storage
        storage_label = DEFAULT_STORAGE_LABEL
        remainder = phone_path
    
    # Split into segments, handling both / and \ separators
    segments = [s for s in remainder.replace("\\", "/").split("/") if s]
    
    return storage_label, segments


def build_phone_uri(activation_uri: str, phone_path: str) -> str:
    """
    Build full MTP URI for a phone path.
    
    Args:
        activation_uri: Base MTP URI (e.g., "mtp://[usb:003,009]/")
        phone_path: Path on phone (e.g., "/DCIM/Camera")
    
    Returns:
        Full MTP URI (e.g., "mtp://[usb:003,009]/Internal storage/DCIM/Camera")
    """
    # Ensure activation URI ends with /
    if not activation_uri.endswith("/"):
        activation_uri += "/"
    
    # Normalize phone path
    storage_label, segments = normalize_phone_path(phone_path)
    
    # URL-encode each segment to handle spaces and special characters
    encoded_segments = [quote(s, safe='') for s in segments]
    
    # Build full path: storage_label/segment1/segment2/...
    full_path = storage_label
    if encoded_segments:
        full_path += "/" + "/".join(encoded_segments)
    
    return activation_uri + full_path


def next_available_name(dest_dir: Path, base_name: str) -> Path:
    """
    Find next available filename by appending (1), (2), etc.
    
    Args:
        dest_dir: Destination directory
        base_name: Original filename
    
    Returns:
        Available Path (original or with suffix)
    """
    dest_path = dest_dir / base_name
    
    if not dest_path.exists():
        return dest_path
    
    # Split name and extension
    name_parts = base_name.rsplit(".", 1)
    if len(name_parts) == 2:
        name, ext = name_parts
    else:
        name = base_name
        ext = ""
    
    # Try (1), (2), (3), etc.
    counter = 1
    while True:
        if ext:
            new_name = f"{name} ({counter}).{ext}"
        else:
            new_name = f"{name} ({counter})"
        
        dest_path = dest_dir / new_name
        if not dest_path.exists():
            return dest_path
        
        counter += 1
        
        # Safety limit
        if counter > 1000:
            raise RuntimeError(f"Too many duplicates for {base_name}")
