"""Validate rules by checking if their paths exist and are accessible."""

from typing import Any, Dict, List, Optional
from pathlib import Path
from . import gio_utils, paths


class RuleValidationWarning:
    """Represents a validation warning for a rule."""
    
    def __init__(self, rule_id: str, rule_mode: str, warning_type: str, message: str, path: str = ""):
        self.rule_id = rule_id
        self.rule_mode = rule_mode
        self.warning_type = warning_type  # "missing_phone_path", "missing_desktop_path", "inaccessible"
        self.message = message
        self.path = path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "rule_mode": self.rule_mode,
            "type": self.warning_type,
            "message": self.message,
            "path": self.path
        }


def validate_rule(rule: Dict[str, Any], device_info: Optional[Dict[str, Any]] = None) -> List[RuleValidationWarning]:
    """
    Validate a single rule by checking if its paths exist.
    
    Args:
        rule: Rule dictionary with mode, phone_path, desktop_path, etc.
        device_info: Optional device info for phone path validation
    
    Returns:
        List of validation warnings (empty if all valid)
    """
    warnings = []
    rule_id = rule.get("id", "unknown")
    mode = rule.get("mode", "unknown")
    
    # Validate desktop path (for all modes)
    desktop_path_str = rule.get("desktop_path", "")
    if desktop_path_str:
        try:
            desktop_path = paths.expand_desktop(desktop_path_str)
            if not desktop_path.exists():
                warnings.append(RuleValidationWarning(
                    rule_id=rule_id,
                    rule_mode=mode,
                    warning_type="missing_desktop_path",
                    message=f"Desktop path does not exist: {desktop_path_str}",
                    path=desktop_path_str
                ))
        except Exception as e:
            warnings.append(RuleValidationWarning(
                rule_id=rule_id,
                rule_mode=mode,
                warning_type="invalid_desktop_path",
                message=f"Invalid desktop path: {str(e)}",
                path=desktop_path_str
            ))
    
    # Validate phone path (for modes that need it)
    phone_path = rule.get("phone_path", "")
    if phone_path and device_info:
        activation_uri = device_info.get("activation_uri", "")
        if activation_uri:
            try:
                # Build phone URI and check if accessible
                phone_uri = paths.build_phone_uri(activation_uri, phone_path)
                
                # Try to get info on the path (with 1 second timeout - faster validation)
                info = gio_utils.gio_info(phone_uri, timeout=1)
                
                if not info:
                    warnings.append(RuleValidationWarning(
                        rule_id=rule_id,
                        rule_mode=mode,
                        warning_type="missing_phone_path",
                        message=f"Phone path does not exist or is inaccessible: {phone_path}",
                        path=phone_path
                    ))
            except Exception as e:
                # Timeout or other error - skip validation rather than block
                # This is not critical, just a helpful check
                pass
    
    return warnings


def validate_profile_rules(profile: Dict[str, Any]) -> List[RuleValidationWarning]:
    """
    Validate all rules in a profile.
    
    Args:
        profile: Profile dictionary with rules and device info
    
    Returns:
        List of all validation warnings
    """
    all_warnings = []
    device_info = profile.get("device", {})
    rules = profile.get("rules", [])
    
    for rule in rules:
        warnings = validate_rule(rule, device_info)
        all_warnings.extend(warnings)
    
    return all_warnings


def validate_all_profiles(config: Dict[str, Any]) -> Dict[str, List[RuleValidationWarning]]:
    """
    Validate all profiles in config.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Dictionary mapping profile names to their validation warnings
    """
    results = {}
    
    for profile in config.get("profiles", []):
        profile_name = profile.get("name", "unknown")
        warnings = validate_profile_rules(profile)
        if warnings:
            results[profile_name] = warnings
    
    return results
