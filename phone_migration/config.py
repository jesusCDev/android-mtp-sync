"""Configuration management for phone migration profiles and rules."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# Config file location
CONFIG_DIR = Path.home() / "Programming" / "project-cli" / "phone-migration"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _default_config() -> Dict[str, Any]:
    """Create default configuration structure."""
    return {
        "version": 1,
        "profiles": []
    }


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file, create default if missing."""
    if not CONFIG_FILE.exists():
        config = _default_config()
        save_config(config)
        return config
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def find_profile(config: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """Find a profile by name."""
    for profile in config.get("profiles", []):
        if profile.get("name") == name:
            return profile
    return None


def find_profile_by_device_id(config: Dict[str, Any], id_type: str, id_value: str) -> Optional[Dict[str, Any]]:
    """Find a profile by device ID."""
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
        config["profiles"].append(profile)


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


def add_move_rule(config: Dict[str, Any], profile_name: str, phone_path: str, desktop_path: str) -> None:
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
        "recursive": True
    }
    
    profile["rules"].append(rule)


def add_sync_rule(config: Dict[str, Any], profile_name: str, desktop_path: str, phone_path: str) -> None:
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
        "overwrite": True,
        "delete_extraneous": True
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
              desktop_path: Optional[str] = None) -> None:
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
            return
    
    raise ValueError(f"Rule '{rule_id}' not found in profile '{profile_name}'")


def print_profiles(config: Dict[str, Any]) -> None:
    """Print all configured profiles."""
    profiles = config.get("profiles", [])
    
    if not profiles:
        print("No profiles configured yet.")
        print("Use: python3 main.py --add-device to register your phone")
        return
    
    print(f"Configured profiles ({len(profiles)}):\n")
    for profile in profiles:
        name = profile.get("name", "unknown")
        device = profile.get("device", {})
        display_name = device.get("display_name", "Unknown")
        id_type = device.get("id_type", "")
        id_value = device.get("id_value", "")
        rule_count = len(profile.get("rules", []))
        
        print(f"  Profile: {name}")
        print(f"    Device: {display_name}")
        print(f"    ID: {id_type}={id_value}")
        print(f"    Rules: {rule_count}")
        print()


def print_rules(config: Dict[str, Any], profile_name: str) -> None:
    """Print rules for a specific profile."""
    profile = find_profile(config, profile_name)
    if not profile:
        print(f"Profile '{profile_name}' not found")
        return
    
    rules = profile.get("rules", [])
    if not rules:
        print(f"No rules configured for profile '{profile_name}'")
        return
    
    print(f"Rules for profile '{profile_name}' ({len(rules)}):\n")
    for rule in rules:
        rule_id = rule.get("id", "")
        mode = rule.get("mode", "")
        phone_path = rule.get("phone_path", "")
        desktop_path = rule.get("desktop_path", "")
        
        print(f"  [{rule_id}] {mode.upper()}")
        if mode == "move":
            print(f"    Phone:   {phone_path}")
            print(f"    Desktop: {desktop_path}")
            print(f"    Action:  Copy to desktop, then delete from phone")
        elif mode == "sync":
            print(f"    Desktop: {desktop_path}")
            print(f"    Phone:   {phone_path}")
            print(f"    Action:  Mirror desktop to phone (desktop is source of truth)")
        print()
