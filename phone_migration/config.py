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
        "overwrite": True,
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
    """Print all configured profiles with color and formatting."""
    # ANSI color codes
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97;1m'
    
    profiles = config.get("profiles", [])
    
    if not profiles:
        print(f"\n{YELLOW}No profiles configured yet.{RESET}")
        print(f"{DIM}Use: phone-sync --add-device to register your phone{RESET}")
        return
    
    print(f"\n{BOLD}{BRIGHT_WHITE}Configured Profiles{RESET} {DIM}({len(profiles)} total){RESET}")
    print(f"{DIM}{'─' * 70}{RESET}\n")
    
    for i, profile in enumerate(profiles, 1):
        name = profile.get("name", "unknown")
        device = profile.get("device", {})
        display_name = device.get("display_name", "Unknown")
        id_type = device.get("id_type", "")
        id_value = device.get("id_value", "")
        rule_count = len(profile.get("rules", []))
        
        # Auto vs manual rule counts
        rules = profile.get("rules", [])
        manual_count = sum(1 for r in rules if r.get("manual_only", False))
        auto_count = rule_count - manual_count
        
        print(f"{BOLD}{BRIGHT_CYAN}📱 {name}{RESET}")
        print(f"  {DIM}Device:{RESET} {GREEN}{display_name}{RESET}")
        print(f"  {DIM}ID:{RESET}     {DIM}{id_type}={id_value}{RESET}")
        
        if rule_count > 0:
            rule_parts = []
            if auto_count > 0:
                rule_parts.append(f"{auto_count} auto")
            if manual_count > 0:
                rule_parts.append(f"{manual_count} {YELLOW}manual{RESET}")
            rule_text = " + ".join(rule_parts)
            print(f"  {DIM}Rules:{RESET}  {rule_text}")
        else:
            print(f"  {DIM}Rules:{RESET}  {YELLOW}0{RESET} {DIM}(none configured){RESET}")
        
        # Separator between profiles
        if i < len(profiles):
            print(f"  {DIM}{'·' * 60}{RESET}")
        print()


def print_rules(config: Dict[str, Any], profile_name: str) -> None:
    """Print rules for a specific profile with color and formatting."""
    # ANSI color codes
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_WHITE = '\033[97;1m'
    
    # Shorten home path
    def shorten(path: str) -> str:
        return path.replace(str(Path.home()), '~', 1) if path else path
    
    profile = find_profile(config, profile_name)
    if not profile:
        print(f"{YELLOW}Profile '{profile_name}' not found{RESET}")
        return
    
    rules = profile.get("rules", [])
    if not rules:
        print(f"{YELLOW}No rules configured for profile '{profile_name}'{RESET}")
        return
    
    # Header
    print(f"\n{BOLD}{BRIGHT_WHITE}Rules for profile '{profile_name}'{RESET} {DIM}({len(rules)} total){RESET}")
    print(f"{DIM}{'─' * 70}{RESET}\n")
    
    for i, rule in enumerate(rules, 1):
        rule_id = rule.get("id", "")
        mode = rule.get("mode", "")
        phone_path = rule.get("phone_path", "")
        desktop_path = rule.get("desktop_path", "")
        manual_only = rule.get("manual_only", False)
        
        # Mode-specific colors and icons
        if mode == "move":
            mode_icon = "📤"
            mode_color = BRIGHT_BLUE
            mode_text = "MOVE"
        elif mode == "copy":
            mode_icon = "📋"
            mode_color = BRIGHT_CYAN
            mode_text = "COPY"
        elif mode == "sync":
            mode_icon = "🔄"
            mode_color = CYAN
            mode_text = "SYNC"
        else:
            mode_icon = "❓"
            mode_color = YELLOW
            mode_text = mode.upper()
        
        # Manual tag
        manual_tag = f" {DIM}[{BRIGHT_YELLOW}MANUAL{RESET}{DIM}]{RESET}" if manual_only else ""
        
        # Rule header
        print(f"{DIM}[{rule_id}]{RESET} {mode_icon} {BOLD}{mode_color}{mode_text}{RESET}{manual_tag}")
        
        # Paths and action
        if mode in ["move", "copy"]:
            print(f"  {DIM}Phone:  {RESET} {CYAN}{phone_path}{RESET}")
            print(f"  {DIM}Desktop:{RESET} {GREEN}{shorten(desktop_path)}{RESET}")
            if mode == "move":
                print(f"  {DIM}Action: {RESET} Copy to desktop, then {YELLOW}delete from phone{RESET}")
            else:
                print(f"  {DIM}Action: {RESET} Copy to desktop, {GREEN}keep on phone{RESET}")
        elif mode == "sync":
            print(f"  {DIM}Desktop:{RESET} {GREEN}{shorten(desktop_path)}{RESET} {DIM}(source){RESET}")
            print(f"  {DIM}Phone:  {RESET} {CYAN}{phone_path}{RESET}")
            print(f"  {DIM}Action: {RESET} Mirror desktop to phone {DIM}(desktop is source of truth){RESET}")
        
        # Separator between rules (not after last one)
        if i < len(rules):
            print(f"  {DIM}{'·' * 60}{RESET}")
        print()
