"""Configuration management for phone migration profiles and rules."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .gio_utils import shorten_path
from .theme import Colors, Icons


# Config file location (XDG). LEGACY_CONFIG_FILE is the old dev-checkout path
# that early versions wrote to; it is copied here once, never moved.
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "phone-migration"
CONFIG_FILE = CONFIG_DIR / "config.json"
LEGACY_CONFIG_FILE = Path.home() / "Programming" / "project-cli" / "phone-migration" / "config.json"


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON so an interrupted run never leaves a half-written file.

    Also used by state.py - this is the only copy.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f"{path.stem}.", suffix=".tmp", delete=False
    )
    try:
        with tmp as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def _default_config() -> Dict[str, Any]:
    """Create default configuration structure."""
    return {
        "version": 1,
        "profiles": []
    }


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file, create default if missing."""
    if not CONFIG_FILE.exists() and LEGACY_CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)
        print(f"{Colors.INFO}{Icons.INFO} Migrated config{Colors.RESET} "
              f"{Colors.DIM}{shorten_path(LEGACY_CONFIG_FILE)}{Colors.RESET} "
              f"{Colors.DIM}->{Colors.RESET} {Colors.PATH}{shorten_path(CONFIG_FILE)}{Colors.RESET}")

    if not CONFIG_FILE.exists():
        config = _default_config()
        save_config(config)
        return config

    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to JSON file (atomically)."""
    _atomic_write_json(CONFIG_FILE, config)


def find_profile(config: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Find a profile by name."""
    for profile in config.get("profiles", []):
        if profile.get("name") == name:
            return profile
    return None


def find_profile_by_device_id(config: Dict[str, Any], id_type: str, id_value: str) -> Optional[Dict[str, Any]]:
    """Find a profile by device ID.

    Never matches on an empty id_type/id_value: device_fingerprint returns
    ("", "") for serial-less phones, and a profile can be persisted with
    id_type/id_value both "" - equality matching would then bind every
    serial-less phone to that one profile.
    """
    if not id_type or not id_value:
        return None
    for profile in config.get("profiles", []):
        device = profile.get("device", {})
        if device.get("id_type") == id_type and device.get("id_value") == id_value:
            return profile
    return None


def add_profile(config: Dict[str, Any], profile: Dict[str, Any]) -> None:
    """Add or update a profile."""
    existing = find_profile(config, profile["name"])
    if existing:
        # Update existing profile
        existing.update(profile)
    else:
        # Add new profile
        config.setdefault("profiles", []).append(profile)


def generate_rule_id(profile: Dict[str, Any]) -> str:
    """Generate a unique rule ID for a profile."""
    rules = profile.get("rules", [])
    if not rules:
        return "r-0001"
    
    # Find highest existing ID
    max_num = 0
    for rule in rules:
        rule_id = rule.get("id", "")
        if rule_id.startswith("r-"):
            try:
                num = int(rule_id.split("-")[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass
    
    return f"r-{max_num + 1:04d}"


def add_move_rule(config: Dict[str, Any], profile_name: str, phone_path: str, desktop_path: str, manual_only: bool = False) -> None:
    """Add a move rule to a profile."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    if "rules" not in profile:
        profile["rules"] = []
    
    rule = {
        "id": generate_rule_id(profile),
        "mode": "move",
        "phone_path": phone_path,
        "desktop_path": desktop_path,
        "recursive": True,
        "manual_only": manual_only
    }
    
    profile["rules"].append(rule)


def add_copy_rule(config: Dict[str, Any], profile_name: str, phone_path: str, desktop_path: str, manual_only: bool = False) -> None:
    """Add a copy rule to a profile (copy without deleting from phone)."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    if "rules" not in profile:
        profile["rules"] = []
    
    rule = {
        "id": generate_rule_id(profile),
        "mode": "copy",
        "phone_path": phone_path,
        "desktop_path": desktop_path,
        "recursive": True,
        "manual_only": manual_only
    }
    
    profile["rules"].append(rule)


def add_backup_rule(config: Dict[str, Any], profile_name: str, phone_path: str, desktop_path: str, manual_only: bool = False) -> None:
    """Add a backup rule to a profile (resumable copy with progress tracking)."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    if "rules" not in profile:
        profile["rules"] = []
    
    rule = {
        "id": generate_rule_id(profile),
        "mode": "backup",
        "phone_path": phone_path,
        "desktop_path": desktop_path,
        "recursive": True,
        "manual_only": manual_only
    }
    
    profile["rules"].append(rule)


# Backward compatibility alias
def add_smart_copy_rule(config: Dict[str, Any], profile_name: str, phone_path: str, desktop_path: str, manual_only: bool = False) -> None:
    """Deprecated: Use add_backup_rule instead."""
    return add_backup_rule(config, profile_name, phone_path, desktop_path, manual_only)


def add_sync_rule(config: Dict[str, Any], profile_name: str, desktop_path: str, phone_path: str, manual_only: bool = False) -> None:
    """Add a sync rule to a profile."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    if "rules" not in profile:
        profile["rules"] = []
    
    rule = {
        "id": generate_rule_id(profile),
        "mode": "sync",
        "desktop_path": desktop_path,
        "phone_path": phone_path,
        "recursive": True,
        "delete_extraneous": True,
        "manual_only": manual_only
    }
    
    profile["rules"].append(rule)


def remove_rule(config: Dict[str, Any], profile_name: str, rule_id: str) -> None:
    """Remove a rule from a profile."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    rules = profile.get("rules", [])
    profile["rules"] = [r for r in rules if r.get("id") != rule_id]


def edit_rule(config: Dict[str, Any], profile_name: str, rule_id: str, 
              mode: Optional[str] = None,
              phone_path: Optional[str] = None, 
              desktop_path: Optional[str] = None,
              manual_only: Optional[bool] = None) -> None:
    """Edit an existing rule."""
    profile = find_profile(config, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    for rule in profile.get("rules", []):
        if rule.get("id") == rule_id:
            if mode:
                rule["mode"] = mode
            if phone_path:
                rule["phone_path"] = phone_path
            if desktop_path:
                rule["desktop_path"] = desktop_path
            if manual_only is not None:
                rule["manual_only"] = manual_only
            return
    
    raise ValueError(f"Rule '{rule_id}' not found in profile '{profile_name}'")


def print_profiles(config: Dict[str, Any]) -> None:
    """Print all configured profiles with color and formatting."""
    profiles = config.get("profiles", [])

    if not profiles:
        print(f"\n{Colors.WARNING}No profiles configured yet.{Colors.RESET}")
        print(f"{Colors.DIM}Use: phone-sync --add-device to register your phone{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.HEADER}Configured Profiles{Colors.RESET} {Colors.DIM}({len(profiles)} total){Colors.RESET}")
    print(f"{Colors.SEPARATOR}{'─' * 70}{Colors.RESET}\n")

    for i, profile in enumerate(profiles, 1):
        name = profile.get("name", "unknown")
        device = profile.get("device", {})
        display_name = device.get("display_name", "Unknown")
        id_type = device.get("id_type", "")
        id_value = device.get("id_value", "")
        rules = profile.get("rules", [])
        rule_count = len(rules)

        # Auto vs manual rule counts
        manual_count = sum(1 for r in rules if r.get("manual_only", False))
        auto_count = rule_count - manual_count

        print(f"{Colors.BOLD}{Colors.ACCENT}{Icons.PHONE} {name}{Colors.RESET}")
        print(f"  {Colors.DIM}Device:{Colors.RESET} {Colors.DEVICE_NAME}{display_name}{Colors.RESET}")
        print(f"  {Colors.DIM}ID:{Colors.RESET}     {Colors.DIM}{id_type}={id_value}{Colors.RESET}")

        if rule_count > 0:
            rule_parts = []
            if auto_count > 0:
                rule_parts.append(f"{auto_count} auto")
            if manual_count > 0:
                rule_parts.append(f"{manual_count} {Colors.WARNING}manual{Colors.RESET}")
            rule_text = " + ".join(rule_parts)
            print(f"  {Colors.DIM}Rules:{Colors.RESET}  {rule_text}")
        else:
            print(f"  {Colors.DIM}Rules:{Colors.RESET}  {Colors.WARNING}0{Colors.RESET} {Colors.DIM}(none configured){Colors.RESET}")

        # Separator between profiles
        if i < len(profiles):
            print(f"  {Colors.SEPARATOR}{'·' * 60}{Colors.RESET}")
        print()


# Mode -> (icon, color, label). "smart_copy" is the legacy name for "backup".
_MODE_STYLE = {
    "move": (Icons.MOVE, Colors.MOVED, "MOVE"),
    "copy": (Icons.COPY, Colors.INFO, "COPY"),
    "backup": (Icons.COPY, Colors.BACKED_UP, "BACKUP"),
    "smart_copy": (Icons.COPY, Colors.BACKED_UP, "BACKUP"),
    "sync": (Icons.SYNC, Colors.SYNCED, "SYNC"),
}


def print_rules(config: Dict[str, Any], profile_name: str) -> None:
    """Print rules for a specific profile with color and formatting."""
    profile = find_profile(config, profile_name)
    if not profile:
        print(f"{Colors.WARNING}Profile '{profile_name}' not found{Colors.RESET}")
        return

    rules = profile.get("rules", [])
    if not rules:
        print(f"{Colors.WARNING}No rules configured for profile '{profile_name}'{Colors.RESET}")
        return

    # Header
    print(f"\n{Colors.BOLD}{Colors.HEADER}Rules for profile '{profile_name}'{Colors.RESET} {Colors.DIM}({len(rules)} total){Colors.RESET}")
    print(f"{Colors.SEPARATOR}{'─' * 70}{Colors.RESET}\n")

    for i, rule in enumerate(rules, 1):
        rule_id = rule.get("id", "")
        mode = rule.get("mode", "")
        phone_path = rule.get("phone_path", "")
        desktop_path = rule.get("desktop_path", "")
        manual_only = rule.get("manual_only", False)

        mode_icon, mode_color, mode_text = _MODE_STYLE.get(
            mode, (Icons.SEARCH, Colors.WARNING, mode.upper())
        )

        # Manual tag
        manual_tag = f" {Colors.DIM}[{Colors.WARNING}MANUAL{Colors.RESET}{Colors.DIM}]{Colors.RESET}" if manual_only else ""

        # Rule header
        print(f"{Colors.DIM}[{Colors.RESET}{Colors.RULE_ID}{rule_id}{Colors.RESET}{Colors.DIM}]{Colors.RESET} {mode_icon} {Colors.BOLD}{mode_color}{mode_text}{Colors.RESET}{manual_tag}")

        # Paths and action
        if mode in ("move", "copy", "backup", "smart_copy"):
            print(f"  {Colors.DIM}Phone:  {Colors.RESET} {Colors.PATH}{phone_path}{Colors.RESET}")
            print(f"  {Colors.DIM}Desktop:{Colors.RESET} {Colors.PATH}{shorten_path(desktop_path)}{Colors.RESET}")
            if mode == "move":
                print(f"  {Colors.DIM}Action: {Colors.RESET} Copy to desktop, then {Colors.DELETED}delete from phone{Colors.RESET}")
            elif mode in ("backup", "smart_copy"):
                print(f"  {Colors.DIM}Action: {Colors.RESET} {Colors.BACKED_UP}Backup{Colors.RESET} to desktop {Colors.DIM}(resumable, no deletions){Colors.RESET}")
            else:
                print(f"  {Colors.DIM}Action: {Colors.RESET} Copy to desktop, {Colors.SUCCESS}keep on phone{Colors.RESET}")
        elif mode == "sync":
            print(f"  {Colors.DIM}Desktop:{Colors.RESET} {Colors.PATH}{shorten_path(desktop_path)}{Colors.RESET} {Colors.DIM}(source){Colors.RESET}")
            print(f"  {Colors.DIM}Phone:  {Colors.RESET} {Colors.PATH}{phone_path}{Colors.RESET}")
            print(f"  {Colors.DIM}Action: {Colors.RESET} Mirror desktop to phone {Colors.DIM}(desktop is source of truth){Colors.RESET}")

        # Separator between rules (not after last one)
        if i < len(rules):
            print(f"  {Colors.SEPARATOR}{'·' * 60}{Colors.RESET}")
        print()
