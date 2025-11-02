"""State management for resumable smart-copy operations."""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Set
from datetime import datetime

# State file location
STATE_DIR = Path.home() / ".local" / "share" / "phone-migration"
STATE_FILE = STATE_DIR / "state.json"


def _ensure_state_dir() -> None:
    """Ensure state directory exists."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_state_file() -> Dict[str, Any]:
    """Load entire state file."""
    _ensure_state_dir()
    if not STATE_FILE.exists():
        return {}
    
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_state_file(state: Dict[str, Any]) -> None:
    """Save entire state file atomically."""
    _ensure_state_dir()
    
    # Write to temp file first, then rename (atomic on POSIX)
    temp_file = STATE_FILE.with_suffix('.tmp')
    try:
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        temp_file.rename(STATE_FILE)
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        raise e


def load_rule_state(rule_id: str) -> Dict[str, Any]:
    """
    Load state for a specific rule.
    
    Returns:
        Dict with keys: copied (set), failed (list), status, last_run, total_files
    """
    state = _load_state_file()
    rule_state = state.get(rule_id, {})
    
    return {
        "copied": set(rule_state.get("copied", [])),
        "failed": rule_state.get("failed", []),
        "status": rule_state.get("status", "new"),
        "last_run": rule_state.get("last_run", None),
        "total_files": rule_state.get("total_files", 0)
    }


def save_rule_state(rule_id: str, copied: Set[str], failed: List[str], 
                     status: str, total_files: int = 0) -> None:
    """
    Save state for a specific rule.
    
    Args:
        rule_id: Rule identifier
        copied: Set of relative paths that were successfully copied
        failed: List of relative paths that failed
        status: "in_progress", "completed", or "failed"
        total_files: Total number of files to copy
    """
    state = _load_state_file()
    
    state[rule_id] = {
        "copied": sorted(list(copied)),  # Convert set to sorted list for JSON
        "failed": failed,
        "status": status,
        "last_run": datetime.now().isoformat(),
        "total_files": total_files
    }
    
    _save_state_file(state)


def mark_file_copied(rule_id: str, relative_path: str) -> None:
    """
    Mark a single file as copied (for incremental updates during copy).
    
    Args:
        rule_id: Rule identifier
        relative_path: Relative path of the file that was copied
    """
    rule_state = load_rule_state(rule_id)
    rule_state["copied"].add(relative_path)
    rule_state["status"] = "in_progress"
    
    save_rule_state(
        rule_id,
        rule_state["copied"],
        rule_state["failed"],
        rule_state["status"],
        rule_state["total_files"]
    )


def mark_file_failed(rule_id: str, relative_path: str, error: str = "") -> None:
    """
    Mark a single file as failed.
    
    Args:
        rule_id: Rule identifier
        relative_path: Relative path of the file that failed
        error: Optional error message
    """
    rule_state = load_rule_state(rule_id)
    
    # Add to failed list if not already there
    failed_entry = {"path": relative_path, "error": error}
    if failed_entry not in rule_state["failed"]:
        rule_state["failed"].append(failed_entry)
    
    save_rule_state(
        rule_id,
        rule_state["copied"],
        rule_state["failed"],
        "in_progress",
        rule_state["total_files"]
    )


def mark_rule_complete(rule_id: str) -> None:
    """
    Mark a rule as completed and clear its state.
    
    Args:
        rule_id: Rule identifier
    """
    state = _load_state_file()
    if rule_id in state:
        del state[rule_id]
        _save_state_file(state)


def get_remaining_files(all_files: List[str], copied_files: Set[str]) -> List[str]:
    """
    Get list of files that still need to be copied.
    
    Args:
        all_files: List of all file paths
        copied_files: Set of already-copied file paths
        
    Returns:
        List of file paths that haven't been copied yet
    """
    return [f for f in all_files if f not in copied_files]


def has_resume_state(rule_id: str) -> bool:
    """
    Check if a rule has resumable state.
    
    Args:
        rule_id: Rule identifier
        
    Returns:
        True if there's state to resume from
    """
    rule_state = load_rule_state(rule_id)
    return len(rule_state["copied"]) > 0 or rule_state["status"] == "in_progress"


def get_state_summary(rule_id: str) -> str:
    """
    Get a human-readable summary of the rule's state.
    
    Args:
        rule_id: Rule identifier
        
    Returns:
        Summary string
    """
    rule_state = load_rule_state(rule_id)
    copied_count = len(rule_state["copied"])
    failed_count = len(rule_state["failed"])
    total = rule_state["total_files"]
    
    if copied_count == 0:
        return "No previous progress"
    
    if total > 0:
        percent = (copied_count / total) * 100
        return f"{copied_count}/{total} files ({percent:.1f}%) - {failed_count} failed"
    else:
        return f"{copied_count} files copied - {failed_count} failed"
