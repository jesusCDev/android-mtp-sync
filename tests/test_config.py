"""Tests for phone_migration.config - profiles, rules, and the XDG config file.

tests/conftest.py repoints CONFIG_FILE/LEGACY_CONFIG_FILE at tmp_path for every
test; the real ~/.config/phone-migration and the repo config.json are never touched.
"""

import json
from pathlib import Path

from phone_migration import config as cfg


def _write_legacy(data):
    """Populate the old dev-checkout config location (isolated by conftest.py)."""
    legacy = cfg.LEGACY_CONFIG_FILE
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps(data))
    return legacy


def test_config_dir_follows_xdg_config_home(tmp_path, monkeypatch):
    """CONFIG_DIR must be the XDG path, not the developer's checkout."""
    import importlib

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdgroot"))
    try:
        reloaded = importlib.reload(cfg)
        assert reloaded.CONFIG_DIR == tmp_path / "xdgroot" / "phone-migration"
        assert "project-cli" not in str(reloaded.CONFIG_DIR)
    finally:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        importlib.reload(cfg)


def test_config_dir_falls_back_when_xdg_config_home_is_set_but_empty(monkeypatch):
    """An empty XDG_CONFIG_HOME ("" - set but blank, distinct from unset) must
    not become a relative './phone-migration' path."""
    import importlib

    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    try:
        reloaded = importlib.reload(cfg)
        assert reloaded.CONFIG_DIR.is_absolute()
        assert reloaded.CONFIG_DIR == Path.home() / ".config" / "phone-migration"
    finally:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        importlib.reload(cfg)


def test_legacy_config_is_copied_once_and_never_moved(capsys):
    legacy = _write_legacy({"version": 1, "profiles": [{"name": "phone"}]})

    loaded = cfg.load_config()

    assert loaded["profiles"][0]["name"] == "phone"
    assert legacy.exists(), "the legacy config must be copied, never moved"
    assert cfg.CONFIG_FILE.exists()
    assert "migrat" in capsys.readouterr().out.lower()

    # Second load reads the new file and does not re-copy over local edits.
    cfg.save_config({"version": 1, "profiles": []})
    assert cfg.load_config()["profiles"] == []


def test_load_config_creates_default_when_nothing_exists():
    loaded = cfg.load_config()

    assert loaded == {"version": 1, "profiles": []}
    assert json.loads(cfg.CONFIG_FILE.read_text()) == loaded


def test_save_config_is_atomic_and_leaves_no_temp_file():
    cfg.save_config({"version": 1, "profiles": [{"name": "phone"}]})

    assert [p.name for p in cfg.CONFIG_DIR.iterdir()] == ["config.json"]
    assert json.loads(cfg.CONFIG_FILE.read_text())["profiles"][0]["name"] == "phone"


def test_add_profile_works_on_a_hand_edited_config_without_profiles():
    config = {}

    cfg.add_profile(config, {"name": "phone"})

    assert config["profiles"] == [{"name": "phone"}]


def test_add_profile_updates_an_existing_profile():
    config = {"profiles": [{"name": "phone", "rules": []}]}

    cfg.add_profile(config, {"name": "phone", "device": {"id_value": "abc"}})

    assert len(config["profiles"]) == 1
    assert config["profiles"][0]["device"] == {"id_value": "abc"}


def test_find_profile_by_device_id():
    config = {"profiles": [{"name": "phone", "device": {"id_type": "serial", "id_value": "abc"}}]}

    assert cfg.find_profile_by_device_id(config, "serial", "abc")["name"] == "phone"
    assert cfg.find_profile_by_device_id(config, "serial", "zzz") is None
    assert cfg.find_profile_by_device_id({}, "serial", "abc") is None


def test_edit_rule_can_turn_manual_only_off():
    config = {"profiles": [{"name": "phone", "rules": [{"id": "r-0001", "manual_only": True}]}]}

    cfg.edit_rule(config, "phone", "r-0001", manual_only=False)

    assert config["profiles"][0]["rules"][0]["manual_only"] is False


def test_add_sync_rule_writes_delete_extraneous_and_no_dead_overwrite_flag():
    config = {"profiles": [{"name": "phone", "rules": []}]}

    cfg.add_sync_rule(config, "phone", "~/Music", "/Music")

    rule = config["profiles"][0]["rules"][0]
    assert rule["delete_extraneous"] is True
    assert "overwrite" not in rule


def test_print_rules_uses_no_emoji(capsys):
    config = {
        "profiles": [
            {
                "name": "phone",
                "rules": [
                    {"id": "r-0001", "mode": "move", "phone_path": "/DCIM", "desktop_path": "/tmp/x"},
                    {"id": "r-0002", "mode": "sync", "phone_path": "/Music", "desktop_path": "/tmp/y"},
                    {"id": "r-0003", "mode": "backup", "phone_path": "/V", "desktop_path": "/tmp/z"},
                    {"id": "r-0004", "mode": "copy", "phone_path": "/C", "desktop_path": "/tmp/c"},
                ],
            }
        ]
    }

    cfg.print_rules(config, "phone")
    cfg.print_profiles(config)

    out = capsys.readouterr().out
    assert not any(ch in out for ch in "\U0001F4F1\U0001F4E4\U0001F4CB\U0001F4BE\U0001F504\u2753")
