"""State management for resumable backup operations.

State is keyed by ``"<profile_name>:<rule_id>"`` - rule IDs restart at r-0001 in
every profile, so a bare rule ID would make two phones share one backup state.

On-disk shape::

    {"work:r-0001": {"copied": [...], "failed": {path: error}, "total_files": 9,
                     "last_run": "2026-08-26T12:00:00"}}

Every read-modify-write of the file happens inside ``_acquire_lock`` (fcntl,
POSIX only), so two processes/threads racing on ``save_rule_state`` for
different keys can't drop each other's writes - the whole cycle is one
lock hold, not a load-then-save pair each locked separately.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

from .config import _atomic_write_json
from .theme import Colors, Icons

# State file location
STATE_DIR = Path.home() / ".local" / "share" / "phone-migration"
STATE_FILE = STATE_DIR / "state.json"

# Lock file for concurrent access protection
LOCK_FILE = STATE_DIR / "state.lock"


@contextmanager
def _acquire_lock():
    """Serialize state.json reads/writes across processes/threads.

    Blocks until the lock is free. fcntl locking is POSIX-only, matching the
    rest of this tool's Linux/gio dependency.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_state() -> Dict[str, Any]:
    """Read the state file's raw contents. Caller must hold the lock.

    A corrupt file is preserved (renamed to ``.corrupt``), never silently
    reset - that would let the next save wipe every other rule's progress.
    """
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        corrupt = STATE_FILE.with_name(STATE_FILE.name + ".corrupt")
        os.replace(STATE_FILE, corrupt)
        print(f"{Colors.WARNING}{Icons.WARN} State file was corrupt{Colors.RESET} "
              f"{Colors.DIM}- moved to {corrupt}; resume progress starts over.{Colors.RESET}")
        return {}


def _write_state(state: Dict[str, Any]) -> None:
    """Write the state file atomically. Caller must hold the lock."""
    _atomic_write_json(STATE_FILE, state)


def load_rule_state(state_key: str) -> Dict[str, Any]:
    """
    Load state for a specific rule.

    Args:
        state_key: "profile_name:rule_id"

    Returns:
        Dict with keys: copied (set), failed (dict path -> error), total_files, last_run
    """
    with _acquire_lock():
        rule_state = _read_state().get(state_key, {})

    return {
        "copied": set(rule_state.get("copied", [])),
        "failed": dict(rule_state.get("failed", {})),
        "total_files": rule_state.get("total_files", 0),
        "last_run": rule_state.get("last_run", None),
    }


def save_rule_state(state_key: str, copied: Set[str], failed: Dict[str, str],
                    total_files: int = 0) -> None:
    """
    Save state for a specific rule.

    Args:
        state_key: "profile_name:rule_id"
        copied: Set of relative paths that were successfully copied
        failed: Map of relative path -> last error (one entry per path)
        total_files: Total number of files to copy
    """
    with _acquire_lock():
        state = _read_state()
        state[state_key] = {
            "copied": sorted(copied),  # set -> sorted list for JSON
            "failed": dict(failed),
            "total_files": total_files,
            "last_run": datetime.now().isoformat(),
        }
        _write_state(state)


def mark_file_copied(state_key: str, relative_path: str) -> None:
    """Mark a single file as copied.

    # ponytail: removed by Task 4 (operations.py still calls this per-file;
    # Task 4 batches through save_rule_state every 25 files instead).
    """
    rule_state = load_rule_state(state_key)
    rule_state["copied"].add(relative_path)
    save_rule_state(state_key, rule_state["copied"], rule_state["failed"], rule_state["total_files"])


def mark_file_failed(state_key: str, relative_path: str, error: str = "") -> None:
    """Mark a single file as failed.

    # ponytail: removed by Task 4 (operations.py still calls this per-file;
    # Task 4 batches through save_rule_state every 25 files instead).
    """
    rule_state = load_rule_state(state_key)
    rule_state["failed"][relative_path] = error
    save_rule_state(state_key, rule_state["copied"], rule_state["failed"], rule_state["total_files"])


def mark_rule_complete(state_key: str) -> None:
    """Mark a rule as completed by clearing its state."""
    with _acquire_lock():
        state = _read_state()
        if state_key in state:
            del state[state_key]
            _write_state(state)


def rename_profile(old_name: str, new_name: str) -> int:
    """Re-key every rule's saved state from ``old_name:*`` to ``new_name:*``.

    Returns the number of keys moved (0, with no file created, if there was
    nothing to move).
    """
    with _acquire_lock():
        state = _read_state()
        prefix = f"{old_name}:"
        matching = [key for key in state if key.startswith(prefix)]

        for key in matching:
            state[f"{new_name}:{key[len(prefix):]}"] = state.pop(key)

        if matching:
            _write_state(state)

    return len(matching)


def get_remaining_files(all_files: List[str], copied_files: Set[str]) -> List[str]:
    """Return the files that still need to be copied."""
    return [f for f in all_files if f not in copied_files]


def has_resume_state(state_key: str) -> bool:
    """True if a previous run left progress to resume from."""
    rule_state = load_rule_state(state_key)
    return bool(rule_state["copied"] or rule_state["failed"])


def get_state_summary(state_key: str) -> str:
    """Human-readable summary of a rule's saved progress."""
    rule_state = load_rule_state(state_key)
    copied_count = len(rule_state["copied"])
    failed_count = len(rule_state["failed"])
    total = rule_state["total_files"]

    if copied_count == 0:
        return "No previous progress"

    if total > 0:
        percent = (copied_count / total) * 100
        return f"{copied_count}/{total} files ({percent:.1f}%) - {failed_count} failed"
    return f"{copied_count} files copied - {failed_count} failed"
