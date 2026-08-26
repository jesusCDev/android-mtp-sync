"""Device discovery and registration for MTP devices via GIO."""

import re
from typing import Any, Dict, List
from . import gio_utils, config as cfg

# `gio mount -li` prints drives containing volumes containing mounts:
#
#   Volume(0): Galaxy S21
#     ids:
#      unix-device: '/dev/bus/usb/003/009'
#     activation_root=mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
#     Mount(0): Galaxy S21 -> mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
#
# Parsing is per line, not per blank-line-separated block: two phones plugged in
# at once share one block, and block parsing kept only the last of them.
_HEADING = re.compile(r"(?:Drive|Volume)\(\d+\):\s*(.+)$")
_MOUNT = re.compile(r"Mount\(\d+\):\s*(.*?)\s*->\s*(\S+)$")
_UNIX_DEVICE = re.compile(r"unix-device:\s*'([^']*)'")
_ACTIVATION_ROOT = re.compile(r"activation_root=(\S+)")

# "mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/" -> "R5CY43CZ5AR". Serials are not
# all uppercase: a Pixel reports "2b9c-41ad". Require a digit so a model word
# with none ("mtp://SAMSUNG_SAMSUNG_Android/") is never mistaken for a serial -
# it would let two serial-less phones of one model share a fingerprint.
_URI_SERIAL = re.compile(r'mtp://[^/]+_([A-Za-z0-9-]*\d[A-Za-z0-9-]*)/')


def _mtp_host(uri: str) -> str:
    """The authority of an mtp:// URI - one physical phone, whichever of its
    storages the URI points at."""
    return uri.split("://", 1)[-1].split("/", 1)[0]


def enumerate_mtp_mounts() -> List[Dict[str, str]]:
    """
    Parse 'gio mount -li' output to find MTP devices.

    Returns:
        One dictionary per connected phone, with display_name, activation_uri
        and identifier. Siblings are kept apart; the same phone seen twice
        (volume activation root plus its mount) is reported once.
    """
    devices: Dict[str, Dict[str, str]] = {}
    name = "Unknown Device"
    identifier = ""
    pending_key = None      # entry this volume's activation_root created, if any

    def add(uri: str, display_name: str) -> str | None:
        """Record one device; returns its key, or None when the URI is not MTP."""
        if not uri.startswith("mtp://"):
            return None
        key = _mtp_host(uri)
        devices.setdefault(key, {
            "display_name": display_name or "Unknown Device",
            "activation_uri": uri,
            "identifier": identifier or uri,
        })
        return key

    for raw in gio_utils.gio_mount_list().splitlines():
        line = raw.strip()
        if match := _HEADING.match(line):
            name, identifier, pending_key = match.group(1).strip(), "", None
        elif match := _MOUNT.match(line):
            key = add(match.group(2), match.group(1) or name)
            # ponytail: host-keyed dedup; a volume's activation_root entry is
            # superseded by its own Mount line
            if key:
                if pending_key and pending_key != key:
                    devices.pop(pending_key)
                pending_key = None
        elif match := _UNIX_DEVICE.search(line):
            identifier = match.group(1)
        elif match := _ACTIVATION_ROOT.search(line):
            uri = match.group(1)
            # Only an entry this activation_root just created may be superseded.
            pending_key = None if _mtp_host(uri) in devices else add(uri, name)

    return list(devices.values())


def enrich_mtp_attributes(activation_uri: str) -> Dict[str, str]:
    """
    Get detailed MTP attributes via 'gio info'.

    Args:
        activation_uri: MTP URI like "mtp://[usb:003,009]/"

    Returns:
        Dictionary with serial, model, vendor if available; empty when the
        device cannot be queried (the URI itself still carries the serial).
    """
    try:
        info = gio_utils.gio_info(activation_uri)
    except gio_utils.GioError:
        return {}

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
    Identify a device by its MTP serial number.

    Only the serial is used. The USB address and the mount identifier are
    properties of the *port*, so after a reconnect they name whatever is plugged
    in there now - matching a different phone and running its rules against it.

    Args:
        device_info: Device information from enumerate_mtp_mounts()
        verbose: Print debug information

    Returns:
        ("mtp_serial", serial), or ("", "") for a device that exposes no serial.
    """
    activation_uri = device_info.get("activation_uri", "")

    attributes = enrich_mtp_attributes(activation_uri)

    if verbose:
        print(f"  Device attributes: {attributes}")

    serial = attributes.get("serial", "")

    if not serial:
        match = _URI_SERIAL.search(activation_uri.rstrip("/") + "/")
        if match:
            serial = match.group(1)
            if verbose:
                print(f"  Extracted serial from URI: {serial}")

    if not serial:
        return ("", "")

    return ("mtp_serial", serial)


def register_current_device(config: Dict[str, Any], profile_name: str, verbose: bool = False) -> None:
    """
    Register the currently connected MTP device.

    Args:
        config: Configuration dictionary
        profile_name: Name for the profile
        verbose: Print verbose output

    Raises:
        RuntimeError: If no device, multiple devices, or no serial number
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

    if not id_type:
        raise RuntimeError(
            "Device exposes no serial number; cannot register it reliably")

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
