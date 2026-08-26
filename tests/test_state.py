"""Tests for phone_migration.state - resumable backup progress on disk.

tests/conftest.py repoints STATE_FILE/STATE_DIR/LOCK_FILE at tmp_path for every
test; the real ~/.local/share/phone-migration is never touched.
"""

import json
import threading
from pathlib import Path

import pytest

from phone_migration import state


@pytest.fixture
def state_file():
    """The isolated state file conftest.py pointed the module at."""
    return state.STATE_FILE


def test_state_writes_stay_inside_tmp_path(tmp_path, state_file):
    """The isolation fixture, asserted: nothing lands outside tmp_path."""
    assert state_file.parent == tmp_path

    state.mark_rule_complete("x")  # unmocked in test_operations.py
    assert [p.name for p in tmp_path.iterdir()] == ["state.lock"]

    state.save_rule_state("x", {"a.jpg"}, {}, 1)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json", "state.lock"]


def test_lock_file_is_created_under_tmp_path_not_real_home(state_file):
    """The fcntl lock file must follow the isolation fixture too, not the
    module-level default baked in at import time (Path.home())."""
    state.save_rule_state("a:r-0001", {"x.jpg"}, {}, 1)

    assert state.LOCK_FILE.parent == state_file.parent
    assert state.LOCK_FILE.exists()
    assert str(Path.home()) not in str(state.LOCK_FILE)


def test_corrupt_state_file_is_renamed_not_reset(state_file, capsys):
    state_file.write_text('{"a:r-0001": {"copied": ["x.jpg"')  # truncated mid-write

    result = state.load_rule_state("a:r-0001")

    assert result["copied"] == set()
    corrupt = state_file.with_name("state.json.corrupt")
    assert corrupt.exists(), "corrupt file must be preserved, not silently dropped"
    assert corrupt.read_text().startswith('{"a:r-0001"')
    assert not state_file.exists()
    assert "corrupt" in capsys.readouterr().out.lower()


def test_rename_profile_rekeys_matching_entries():
    state.save_rule_state("a:r-0001", {"x.jpg"}, {}, 1)
    state.save_rule_state("a:r-0002", {"y.jpg"}, {}, 1)
    state.save_rule_state("b:r-0001", {"z.jpg"}, {}, 1)

    moved = state.rename_profile("a", "z")

    assert moved == 2
    assert state.load_rule_state("z:r-0001")["copied"] == {"x.jpg"}
    assert state.load_rule_state("z:r-0002")["copied"] == {"y.jpg"}
    assert not state.has_resume_state("a:r-0001")
    assert not state.has_resume_state("a:r-0002")
    assert state.load_rule_state("b:r-0001")["copied"] == {"z.jpg"}


def test_rename_profile_on_empty_store_is_a_noop(state_file):
    moved = state.rename_profile("nope", "x")

    assert moved == 0
    assert not state_file.exists()


def test_corrupt_rename_overwrites_an_older_corrupt_file(state_file):
    state_file.with_name("state.json.corrupt").write_text("older garbage")
    state_file.write_text("newer garbage")

    state.load_rule_state("a:r-0001")

    assert state_file.with_name("state.json.corrupt").read_text() == "newer garbage"


def test_save_leaves_no_temp_file_and_round_trips(state_file):
    state.save_rule_state("a:r-0001", {"b.jpg", "a.jpg"}, {"c.jpg": "boom"}, 3)

    assert [p.name for p in state_file.parent.iterdir()] == ["state.json", "state.lock"]
    loaded = state.load_rule_state("a:r-0001")
    assert loaded["copied"] == {"a.jpg", "b.jpg"}
    assert loaded["failed"] == {"c.jpg": "boom"}
    assert loaded["total_files"] == 3


def test_two_state_keys_do_not_clobber_each_other(state_file):
    state.save_rule_state("work:r-0001", {"a.jpg"}, {}, 1)
    state.save_rule_state("home:r-0001", {"b.jpg"}, {}, 1)

    assert state.load_rule_state("work:r-0001")["copied"] == {"a.jpg"}
    assert state.load_rule_state("home:r-0001")["copied"] == {"b.jpg"}


def test_failed_entries_dedupe_by_path(state_file):
    state.save_rule_state("a:r-0001", set(), {"x.jpg": "first"}, 1)
    failed = state.load_rule_state("a:r-0001")["failed"]
    failed["x.jpg"] = "second"
    state.save_rule_state("a:r-0001", set(), failed, 1)

    assert state.load_rule_state("a:r-0001")["failed"] == {"x.jpg": "second"}


def test_missing_fields_fall_back_to_defaults(state_file):
    state_file.write_text(json.dumps({"a:r-0001": {}}))

    loaded = state.load_rule_state("a:r-0001")

    assert loaded == {"copied": set(), "failed": {}, "total_files": 0, "last_run": None}


def test_mark_rule_complete_removes_only_that_key(state_file):
    state.save_rule_state("a:r-0001", {"a.jpg"}, {}, 1)
    state.save_rule_state("b:r-0001", {"b.jpg"}, {}, 1)

    state.mark_rule_complete("a:r-0001")

    assert state.load_rule_state("a:r-0001")["copied"] == set()
    assert state.load_rule_state("b:r-0001")["copied"] == {"b.jpg"}


def test_has_resume_state(state_file):
    assert state.has_resume_state("a:r-0001") is False
    state.save_rule_state("a:r-0001", {"a.jpg"}, {}, 2)
    assert state.has_resume_state("a:r-0001") is True


def test_get_state_summary(state_file):
    assert state.get_state_summary("a:r-0001") == "No previous progress"
    state.save_rule_state("a:r-0001", {"a.jpg"}, {"b.jpg": "boom"}, 4)
    assert state.get_state_summary("a:r-0001") == "1/4 files (25.0%) - 1 failed"


def test_get_remaining_files():
    assert state.get_remaining_files(["a", "b", "c"], {"b"}) == ["a", "c"]


def test_concurrent_saves_to_different_keys_do_not_corrupt_state(state_file):
    """Two threads hammering save_rule_state on different keys must not lose
    updates, leave a .tmp file behind, or raise - the fcntl lock in
    _acquire_lock serializes the read-modify-write around each save."""
    errors = []

    def hammer(key, n):
        try:
            for i in range(n):
                state.save_rule_state(key, {f"{key}-{i}.jpg"}, {}, n)
        except Exception as e:  # pragma: no cover - failure path under test
            errors.append(e)

    t1 = threading.Thread(target=hammer, args=("work:r-0001", 50))
    t2 = threading.Thread(target=hammer, args=("home:r-0001", 50))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == []
    assert state.load_rule_state("work:r-0001")["copied"] == {"work:r-0001-49.jpg"}
    assert state.load_rule_state("home:r-0001")["copied"] == {"home:r-0001-49.jpg"}
    leftovers = [p.name for p in state_file.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
