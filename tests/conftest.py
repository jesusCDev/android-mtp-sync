"""Test isolation: no test may touch the user's real config or state files.

Partially-mocked tests (tests/test_operations.py mocks load/save_rule_state but
not mark_rule_complete) otherwise reach the module-level STATE_FILE and can
rename ~/.local/share/phone-migration/state.json as a side effect of pytest.
"""

import pytest

from phone_migration import config as cfg, state

try:
    from phone_migration import web_ui
except ImportError:          # Flask absent: tests/test_web_ui.py skips itself
    web_ui = None


@pytest.fixture(autouse=True)
def isolate_user_files(tmp_path, monkeypatch):
    """Repoint every module-level config/state/history path at tmp_path."""
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path / "xdg")
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "xdg" / "config.json")
    if hasattr(cfg, "LEGACY_CONFIG_FILE"):      # Task 3 adds the XDG migration path
        monkeypatch.setattr(cfg, "LEGACY_CONFIG_FILE", tmp_path / "checkout" / "config.json")
    if web_ui is not None:
        monkeypatch.setattr(web_ui, "HISTORY_FILE", tmp_path / "history.json")
        monkeypatch.setattr(web_ui, "run_history", [])
        if hasattr(web_ui, "BOOKMARKS_FILE"):
            monkeypatch.setattr(web_ui, "BOOKMARKS_FILE", tmp_path / "bookmarks.json")
            monkeypatch.setattr(web_ui, "bookmarks", {"desktop": [], "phone": []})
