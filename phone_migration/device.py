"""Device discovery and registration for MTP devices via GIO."""

import re
from typing import Any, Dict, List, Optional
from . import gio_utils, config as cfg


def enumerate_mtp_mounts() -> List[Dict[str, str]]:
    """
    Parse 'gio mount -li' output to find MTP devices.
    
    Returns:
        List of device dictionaries with display_name, activation_uri, identifier
    """
    output = gio_utils.gio_mount_list()
    devices = []
    
    # Parse output into blocks separated by blank lines
    current_block = []
    blocks = []
    
    for line in output.splitlines():
        if line.strip():
            current_block.append(line)
        elif current_block:
            blocks.append(current_block)
            current_block = []
    
    if current_block:
        blocks.append(current_block)
    
    # Process each block
    for block in blocks:
        device_info = {}
        is_mtp = False
        
        for line in block:
            line = line.strip()
            
            # Check if this is an MTP mount
            if "Type:" in line and ("MTP" in line.upper() or "mtp" in line):
                is_mtp = True
            
            # Extract mount/volume name
            if line.startswith("Mount(") or line.startswith("Volume("):
                # Extract name from "Mount(0): Name" or "Volume(0): Name"
                match = re.search(r':\s*(.+)$', line)
                if match:
                    device_info["display_name"] = match.group(1).strip()
            
            # Extract activation URI or default location
            if "activation_root=" in line or "Default location:" in line or "Activation root:" in line:
                # Extract URI (format: "mtp://[usb:003,009]/")
                match = re.search(r'(mtp://[^\s]+)', line)
                if match:
                    device_info["activation_uri"] = match.group(1)
                    is_mtp = True
            
            # Extract identifier
            if line.startswith("identifier:") or "unix-device:" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    device_info["identifier"] = parts[1].strip().strip("'\"")
        
        # Add to devices if it's an MTP device with required info
        if is_mtp and "activation_uri" in device_info:
            if "display_name" not in device_info:
                device_info["display_name"] = "Unknown Device"
            if "identifier" not in device_info:
                device_info["identifier"] = device_info["activation_uri"]
            
            devices.append(device_info)
    
    return devices


def enrich_mtp_attributes(activation_uri: str) -> Dict[str, str]:
    """
    Get detailed MTP attributes via 'gio info'.
    
    Args:
        activation_uri: MTP URI like "mtp://[usb:003,009]/"
    
    Returns:
        Dictionary with mtp.serial, mtp.model, mtp.vendor if available
    """
    # Try to get MTP-specific attributes
    info = gio_utils.gio_info(activation_uri)
    
    attributes = {}
    for key, value in info.items():
        # Look for MTP attributes
        if "serial" in key.lower():
            attributes["serial"] = value
        if "model" in key.lower():
            attributes["model"] = value
        if "vendor" in key.lower():
            attributes["vendor"] = value
    
    return attributes


def device_fingerprint(device_info: Dict[str, str], verbose: bool = False) -> tuple[str, str]:
    """
    Generate a unique fingerprint for a device.
    
    Args:
        device_info: Device information from enumerate_mtp_mounts()
        verbose: Print debug information
    
    Returns:
        Tuple of (id_type, id_value)
    """
    activation_uri = device_info.get("activation_uri", "")
    
    # Try to get MTP serial number from gio info
    attributes = enrich_mtp_attributes(activation_uri)
    
    if verbose:
        print(f"  Device attributes: {attributes}")
    
    if "serial" in attributes:
        return ("mtp_serial", attributes["serial"])
    
    # Use MTP serial from activation URI (more stable than USB device path)
    # Extract serial from "mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/"
    match = re.search(r'mtp://[^/]+_([A-Z0-9]+)/', activation_uri)
    if match:
        serial = match.group(1)
        if verbose:
            print(f"  Extracted serial from URI: {serial}")
        return ("mtp_serial", serial)
    
    # Fall back to identifier from mount list (less stable - changes on reconnect)
    if "identifier" in device_info:
        return ("identifier", device_info["identifier"])
    
    # Last resort: use activation URI host part
    # Extract [usb:003,009] from "mtp://[usb:003,009]/"
    match = re.search(r'mtp://\[([^\]]+)\]', activation_uri)
    if match:
        return ("usb_address", match.group(1))
    
    return ("activation_uri", activation_uri)


def register_current_device(config: Dict[str, Any], profile_name: str, verbose: bool = False) -> None:
    """
    Register the currently connected MTP device.
    
    Args:
        config: Configuration dictionary
        profile_name: Name for the profile
        verbose: Print verbose output
    
    Raises:
        RuntimeError: If no device or multiple devices found
    """
    devices = enumerate_mtp_mounts()
    
    if not devices:
        raise RuntimeError(
            "No MTP devices found. Make sure your phone is:\n"
            "  1. Connected via USB\n"
            "  2. Set to 'File Transfer' or 'MTP' mode\n"
            "  3. Unlocked\n"
            "Run 'gio mount -li' to check mounted devices."
        )
    
    if len(devices) > 1:
        print(f"Multiple MTP devices found ({len(devices)}):")
        for i, dev in enumerate(devices, 1):
            print(f"  {i}. {dev.get('display_name', 'Unknown')}")
        raise RuntimeError(
            "Please disconnect other devices and try again, "
            "or specify which device to register."
        )
    
    device_info = devices[0]
    
    if verbose:
        print(f"Found device: {device_info.get('display_name', 'Unknown')}")
        print(f"  URI: {device_info.get('activation_uri', '')}")
    
    # Generate fingerprint
    id_type, id_value = device_fingerprint(device_info, verbose)
    
    if verbose:
        print(f"  Fingerprint: {id_type}={id_value}")
    
    # Create or update profile
    profile = {
        "name": profile_name,
        "device": {
            "display_name": device_info.get("display_name", "Unknown Device"),
            "id_type": id_type,
            "id_value": id_value,
            "activation_uri": device_info.get("activation_uri", "")
        },
        "rules": []
    }
    
    # Check if profile exists and preserve rules
    existing = cfg.find_profile(config, profile_name)
    if existing:
        profile["rules"] = existing.get("rules", [])
        if verbose:
            print(f"  Updating existing profile (preserving {len(profile['rules'])} rules)")
    
    cfg.add_profile(config, profile)
