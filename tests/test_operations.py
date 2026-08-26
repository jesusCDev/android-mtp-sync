"""Tests for phone_migration.operations - the code that deletes files.

The desktop side is a real ``tmp_path``; the phone side is an in-memory
``FakePhone``. Assertions are on the bytes that ended up on disk, on the phone
tree afterwards, and on the returned stats - never on mock call counts alone.
"""

import os
import unicodedata
from pathlib import Path

import pytest

from fake_gio import FakePhone
from phone_migration import gio_utils, operations, state
from phone_migration.transfer_stats import TransferStats

DEVICE = {"activation_uri": "mtp://dev/"}
ROOT = "Internal storage/DCIM"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """No real state file, no DRY_RUN leaking between tests."""
    monkeypatch.setattr(state, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(state, "STATE_FILE", tmp_path / "state" / "state.json")
    monkeypatch.setattr(gio_utils, "DRY_RUN", False)


def make_phone(files, monkeypatch):
    return FakePhone(files).install(monkeypatch)


def make_rule(tmp_path, mode="copy", phone_path="/DCIM", desktop=None, **extra):
    return {"id": "r-0001", "mode": mode, "phone_path": phone_path,
            "desktop_path": str(desktop if desktop is not None else tmp_path / "dest"),
            **extra}


def entries(stats, action):
    return [f for f in stats["files"] if f["action"] == action]


ACTIONS = {"copied", "moved", "synced", "deleted", "skipped", "renamed", "failed", "folder"}


def check_shape(stats):
    for entry in stats["files"]:
        assert set(entry) == {"action", "src", "dst", "error"}, entry
        assert entry["action"] in ACTIONS, entry
    return stats


# --- copy --------------------------------------------------------------------

def test_copy_single_file_lands_with_correct_bytes(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"hello"}, monkeypatch)

    stats = check_shape(operations.run_copy_rule(make_rule(tmp_path), DEVICE))

    assert (tmp_path / "dest" / "a.jpg").read_bytes() == b"hello"
    assert stats["copied"] == 1
    assert stats["errors"] == 0
    assert entries(stats, "copied") == [
        {"action": "copied", "src": "a.jpg",
         "dst": str(tmp_path / "dest" / "a.jpg"), "error": None}]


def test_copy_recurses_into_subdirectories(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"a", f"{ROOT}/sub/b.jpg": b"bb"}, monkeypatch)

    stats = check_shape(operations.run_copy_rule(make_rule(tmp_path), DEVICE))

    assert (tmp_path / "dest" / "sub" / "b.jpg").read_bytes() == b"bb"
    assert stats["copied"] == 2
    assert stats["folders"] == 1
    assert entries(stats, "folder")[0]["src"] == "sub"
    assert {e["src"] for e in entries(stats, "copied")} == {"a.jpg", "sub/b.jpg"}


def test_copy_conflict_without_rename_skips_and_never_copies(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"new"}, monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"old")

    stats = check_shape(operations.run_copy_rule(
        make_rule(tmp_path), DEVICE, rename_duplicates=False))

    assert (dest / "a.jpg").read_bytes() == b"old"
    assert phone.copied == []
    assert stats["skipped"] == 1
    assert stats["copied"] == 0
    assert entries(stats, "skipped")[0]["src"] == "a.jpg"


def test_copy_conflict_with_rename_writes_a_numbered_copy(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"new"}, monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"old")

    stats = check_shape(operations.run_copy_rule(
        make_rule(tmp_path), DEVICE, rename_duplicates=True))

    assert (dest / "a.jpg").read_bytes() == b"old"
    assert (dest / "a (1).jpg").read_bytes() == b"new"
    assert stats["renamed"] == 1
    assert stats["copied"] == 1
    assert entries(stats, "renamed")[0]["dst"].endswith("a (1).jpg")


def test_copy_counts_a_short_copy_as_an_error(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"1234567890"}, monkeypatch)
    phone.truncate.add("a.jpg")

    stats = check_shape(operations.run_copy_rule(make_rule(tmp_path), DEVICE))

    assert stats["copied"] == 0
    assert stats["errors"] == 1
    assert "size" in entries(stats, "failed")[0]["error"]


def test_copy_reports_a_failed_copy(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    phone.copy_failures.add("a.jpg")

    stats = check_shape(operations.run_copy_rule(make_rule(tmp_path), DEVICE))

    assert stats["copied"] == 0
    assert stats["errors"] == 1
    assert entries(stats, "failed")[0]["src"] == "a.jpg"


def test_copy_tracks_transferred_bytes(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"12345"}, monkeypatch)
    tracker = TransferStats()

    operations.run_copy_rule(make_rule(tmp_path), DEVICE, transfer_tracker=tracker)

    assert tracker.total_bytes == 5
    assert tracker.files_processed == 1


# --- move --------------------------------------------------------------------

def test_move_deletes_the_original_after_a_size_verified_copy(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"12345"}, monkeypatch)

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert (tmp_path / "dest" / "a.jpg").read_bytes() == b"12345"
    assert phone.removed == [f"{ROOT}/a.jpg"]
    assert f"{ROOT}/a.jpg" not in phone.files
    assert stats["copied"] == 1
    assert stats["deleted"] == 1
    assert stats["errors"] == 0
    assert entries(stats, "moved")[0]["src"] == "a.jpg"


def test_move_keeps_the_original_when_the_copy_is_truncated(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"1234567890"}, monkeypatch)
    phone.truncate.add("a.jpg")

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert phone.removed == []
    assert phone.files[f"{ROOT}/a.jpg"] == b"1234567890"
    assert stats["deleted"] == 0
    assert stats["copied"] == 0
    assert stats["errors"] == 1
    assert "size" in entries(stats, "failed")[0]["error"]


def test_move_keeps_the_original_when_the_copy_fails(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    phone.copy_failures.add("a.jpg")

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert phone.removed == []
    assert phone.files[f"{ROOT}/a.jpg"] == b"x"
    assert stats["errors"] == 1


def test_move_verifies_and_deletes_a_zero_byte_file(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/empty.txt": b""}, monkeypatch)

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert (tmp_path / "dest" / "empty.txt").read_bytes() == b""
    assert phone.removed == [f"{ROOT}/empty.txt"]
    assert stats["copied"] == 1
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


def test_move_removes_emptied_subdirectories_but_keeps_the_root(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/sub/a.jpg": b"a", f"{ROOT}/other/b.jpg": b"b"},
                       monkeypatch)
    phone.copy_failures.add("b.jpg")

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert f"{ROOT}/sub" not in phone.dirs          # emptied, so removed
    assert f"{ROOT}/other" in phone.dirs            # still holds the failed file
    assert ROOT in phone.dirs                       # rule root is never removed
    assert stats["errors"] == 1


def test_move_never_deletes_when_a_listing_fails(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    phone.list_errors.add(ROOT)

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert phone.removed == []
    assert phone.files[f"{ROOT}/a.jpg"] == b"x"
    assert stats["errors"] == 1
    assert stats["copied"] == 0
    assert "busy" in entries(stats, "failed")[0]["error"].lower()


@pytest.mark.parametrize("name", [
    "a b#c.jpg", "100%.jpg", "shot (1).jpg", "a#b%20c d.jpg", "note+&=?.txt",
])
def test_odd_names_round_trip_through_a_move(tmp_path, monkeypatch, name):
    phone = make_phone({f"{ROOT}/{name}": b"xxxxxxx"}, monkeypatch)

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert (tmp_path / "dest" / name).read_bytes() == b"xxxxxxx"
    assert phone.removed == [f"{ROOT}/{name}"]
    assert stats["errors"] == 0


# --- entries that are neither a directory nor a regular file -----------------

@pytest.mark.parametrize("run", ["run_copy_rule", "run_move_rule"])
def test_an_unreadable_entry_is_counted_never_silent(tmp_path, monkeypatch, run):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    phone.ghost(f"{ROOT}/mystery")

    stats = check_shape(getattr(operations, run)(make_rule(tmp_path), DEVICE))

    assert stats["errors"] == 1
    assert entries(stats, "failed")[0]["src"] == "mystery"
    assert stats["copied"] == 1


# --- dry run -----------------------------------------------------------------

def test_dry_run_copy_touches_nothing(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/sub/a.jpg": b"x"}, monkeypatch)
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)

    stats = check_shape(operations.run_copy_rule(make_rule(tmp_path), DEVICE))

    assert not (tmp_path / "dest").exists()
    assert phone.copied == []
    assert stats["copied"] == 1
    assert stats["folders"] == 1


def test_dry_run_move_deletes_nothing(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)

    stats = check_shape(operations.run_move_rule(make_rule(tmp_path, "move"), DEVICE))

    assert not (tmp_path / "dest").exists()
    assert phone.removed == []
    assert phone.files[f"{ROOT}/a.jpg"] == b"x"
    assert stats["copied"] == 1
    assert stats["deleted"] == 1      # preview of what a real run would delete


def test_dry_run_backup_writes_no_state_file(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert not state.STATE_FILE.exists()
    assert not (tmp_path / "dest").exists()
    assert stats["copied"] == 1


def test_dry_run_backup_does_not_clear_saved_progress(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)
    state.save_rule_state("work:r-0001", {"a.jpg"}, {}, 1)
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)

    operations.run_backup_rule(make_rule(tmp_path, "backup"), DEVICE,
                               profile_name="work")

    assert state.has_resume_state("work:r-0001")


def test_dry_run_sync_deletes_nothing(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/gone.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)

    stats = check_shape(operations.run_sync_rule(
        {"id": "r-1", "mode": "sync", "phone_path": "/Music",
         "desktop_path": str(src), "delete_extraneous": True}, DEVICE))

    assert phone.removed == []
    assert phone.files == {"Internal storage/Music/gone.mp3": b"a"}
    assert stats["copied"] == 1
    assert stats["deleted"] == 1      # preview only


# --- backup ------------------------------------------------------------------

def test_backup_copies_everything_and_clears_state_when_complete(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"x", f"{ROOT}/sub/b.jpg": b"yy"}, monkeypatch)

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert (tmp_path / "dest" / "sub" / "b.jpg").read_bytes() == b"yy"
    assert stats["copied"] == 2
    assert stats["failed"] == 0
    assert not state.has_resume_state("work:r-0001")


def test_backup_state_is_keyed_by_profile_and_rule(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x", f"{ROOT}/b.jpg": b"y"}, monkeypatch)
    phone.copy_failures.add("b.jpg")

    operations.run_backup_rule(make_rule(tmp_path, "backup"), DEVICE,
                               profile_name="work")

    assert state.load_rule_state("work:r-0001")["copied"] == {"a.jpg"}
    assert state.load_rule_state("home:r-0001")["copied"] == set()


def test_backup_resume_skips_files_already_there_with_the_same_size(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"12345", f"{ROOT}/b.jpg": b"67890"},
                       monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"12345")
    state.save_rule_state("work:r-0001", {"a.jpg"}, {}, 2)

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert phone.copied == [(f"{ROOT}/b.jpg", str(dest / "b.jpg"))]
    assert stats["resumed"] == 1
    assert stats["copied"] == 1
    assert not state.has_resume_state("work:r-0001")


def test_backup_recopies_a_file_whose_destination_is_truncated(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"12345"}, monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"12")          # half-written by an aborted run
    state.save_rule_state("work:r-0001", {"a.jpg"}, {}, 1)

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert (dest / "a.jpg").read_bytes() == b"12345"
    assert stats["copied"] == 1
    assert stats["resumed"] == 0


def test_backup_keeps_state_when_every_copy_fails(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x", f"{ROOT}/b.jpg": b"y"}, monkeypatch)
    phone.copy_failures.update({"a.jpg", "b.jpg"})

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert stats["failed"] == 2
    assert stats["copied"] == 0
    saved = state.load_rule_state("work:r-0001")
    assert saved["copied"] == set()
    assert set(saved["failed"]) == {"a.jpg", "b.jpg"}
    assert saved["total_files"] == 2
    assert state.has_resume_state("work:r-0001")


def test_backup_counts_a_conflict_as_skipped_and_still_completes(tmp_path, monkeypatch, capsys):
    phone = make_phone({f"{ROOT}/a.jpg": b"new", f"{ROOT}/b.jpg": b"y"}, monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"different")

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert (dest / "a.jpg").read_bytes() == b"different"
    assert phone.copied == [(f"{ROOT}/b.jpg", str(dest / "b.jpg"))]
    assert stats["skipped"] == 1
    assert stats["copied"] == 1
    assert "conflict" in capsys.readouterr().out
    assert not state.has_resume_state("work:r-0001")


def test_backup_keeps_state_when_a_listing_fails(tmp_path, monkeypatch):
    phone = make_phone({f"{ROOT}/a.jpg": b"x", f"{ROOT}/sub/b.jpg": b"y"}, monkeypatch)
    phone.list_errors.add(f"{ROOT}/sub")

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, profile_name="work"))

    assert stats["errors"] == 1
    assert stats["copied"] == 1
    assert state.has_resume_state("work:r-0001")


def test_backup_honours_rename_duplicates_when_asked(tmp_path, monkeypatch):
    make_phone({f"{ROOT}/a.jpg": b"new"}, monkeypatch)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.jpg").write_bytes(b"different")

    stats = check_shape(operations.run_backup_rule(
        make_rule(tmp_path, "backup"), DEVICE, rename_duplicates=True,
        profile_name="work"))

    assert (dest / "a (1).jpg").read_bytes() == b"new"
    assert stats["copied"] == 1
    assert stats["skipped"] == 0


def test_smart_copy_is_the_backup_rule():
    assert operations.run_smart_copy_rule is operations.run_backup_rule


# --- sync --------------------------------------------------------------------

def sync_rule(src, **extra):
    return {"id": "r-1", "mode": "sync", "phone_path": "/Music",
            "desktop_path": str(src), **extra}


def test_sync_copies_new_and_size_changed_files(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/same.mp3": b"aaa",
                        "Internal storage/Music/old.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "same.mp3").write_bytes(b"aaa")
    (src / "old.mp3").write_bytes(b"abcd")
    (src / "new.mp3").write_bytes(b"zz")

    stats = check_shape(operations.run_sync_rule(sync_rule(src), DEVICE))

    assert phone.files["Internal storage/Music/old.mp3"] == b"abcd"
    assert phone.files["Internal storage/Music/new.mp3"] == b"zz"
    assert stats["copied"] == 2
    assert stats["skipped"] == 1
    assert {e["dst"] for e in entries(stats, "synced")} == {"old.mp3", "new.mp3"}


def test_sync_leaves_extraneous_files_alone_by_default(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/extra.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(sync_rule(src), DEVICE))

    assert phone.files["Internal storage/Music/extra.mp3"] == b"a"
    assert stats["deleted"] == 0


def test_sync_deletes_extraneous_files_when_enabled(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/extra.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert "Internal storage/Music/extra.mp3" not in phone.files
    assert phone.files["Internal storage/Music/keep.mp3"] == b"bb"
    assert stats["deleted"] == 1
    assert entries(stats, "deleted")[0]["src"] == "extra.mp3"


def test_sync_refuses_to_delete_when_the_desktop_side_is_empty(tmp_path, monkeypatch, capsys):
    phone = make_phone({"Internal storage/Music/a.mp3": b"a",
                        "Internal storage/Music/b.mp3": b"b"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert len(phone.files) == 2
    assert stats["deleted"] == 0
    assert "refus" in capsys.readouterr().out.lower()


def test_sync_refuses_when_the_desktop_path_is_a_file(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/keep.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src.txt"
    src.write_text("not a directory")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert phone.files["Internal storage/Music/keep.mp3"] == b"a"
    assert stats["errors"] == 1
    assert stats["deleted"] == 0


def test_sync_refuses_when_the_desktop_path_is_missing(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/keep.mp3": b"a"}, monkeypatch)

    stats = check_shape(operations.run_sync_rule(
        sync_rule(tmp_path / "gone", delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert stats["errors"] == 1


def test_sync_recurses_into_phone_subdirectories(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/sub/gone.mp3": b"a",
                        "Internal storage/Music/sub/keep.mp3": b"bb"}, monkeypatch)
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert "Internal storage/Music/sub/gone.mp3" not in phone.files
    assert phone.files["Internal storage/Music/sub/keep.mp3"] == b"bb"
    assert "Internal storage/Music/sub" in phone.dirs   # still wanted by the desktop
    assert stats["deleted"] == 1


def test_sync_compares_names_after_unicode_normalization(tmp_path, monkeypatch):
    # Same name, different encodings: NFD on the phone, NFC on the desktop.
    phone = make_phone({"Internal storage/Music/café.mp3": b"aa"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "café.mp3").write_bytes(b"aa")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert stats["deleted"] == 0


def test_sync_counts_a_listing_failure_instead_of_deleting(tmp_path, monkeypatch):
    phone = make_phone({"Internal storage/Music/extra.mp3": b"a"}, monkeypatch)
    phone.list_errors.add("Internal storage/Music")
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert stats["errors"] == 1
    assert stats["deleted"] == 0


def test_sync_reports_a_failed_copy(tmp_path, monkeypatch):
    phone = make_phone({}, monkeypatch)
    phone.copy_failures.add("keep.mp3")
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(sync_rule(src), DEVICE))

    assert stats["errors"] == 1
    assert stats["copied"] == 0
    assert entries(stats, "failed")[0]["dst"] == "keep.mp3"


# --- an empty desktop_path aborts the rule, it never targets the CWD ---------

@pytest.mark.parametrize("run", ["run_copy_rule", "run_move_rule",
                                 "run_backup_rule", "run_sync_rule"])
def test_an_empty_desktop_path_is_an_error_not_a_crash(monkeypatch, run):
    phone = make_phone({f"{ROOT}/a.jpg": b"x"}, monkeypatch)

    stats = check_shape(getattr(operations, run)(
        {"id": "r-0001", "phone_path": "/DCIM", "desktop_path": ""}, DEVICE))

    assert stats["errors"] == 1
    assert phone.removed == []
    assert phone.copied == []
    assert entries(stats, "failed")[0]["error"]


# --- sync never deletes on the strength of an incomplete desktop scan --------

def test_sync_does_not_treat_an_unreadable_desktop_entry_as_extraneous(tmp_path, monkeypatch):
    """A dangling symlink is not a file, so its name never reaches expected_files -
    the phone's copy of that name must still not be deleted."""
    phone = make_phone({"Internal storage/Music/ghost.jpg": b"a",
                        "Internal storage/Music/keep.mp3": b"bb"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")
    os.symlink("/nonexistent", src / "ghost.jpg")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.files["Internal storage/Music/ghost.jpg"] == b"a"
    assert phone.removed == []
    assert stats["errors"] == 1
    assert stats["deleted"] == 0


@pytest.mark.parametrize("phone_path", ["/", "", "~/is"])
def test_sync_refuses_to_delete_at_the_storage_root(tmp_path, monkeypatch, phone_path, capsys):
    phone = make_phone({"Internal storage/DCIM/holiday.jpg": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    stats = check_shape(operations.run_sync_rule(
        {"id": "r-1", "mode": "sync", "phone_path": phone_path,
         "desktop_path": str(src), "delete_extraneous": True}, DEVICE))

    assert phone.files["Internal storage/DCIM/holiday.jpg"] == b"a"
    assert phone.removed == []
    assert stats["deleted"] == 0
    assert "refus" in capsys.readouterr().out.lower()


def test_sync_survives_a_file_that_vanishes_between_listing_and_stat(tmp_path, monkeypatch):
    """The classic race: the entry is a file when iterdir sees it and gone by the
    time its size is read. The rule reports an error, it does not raise."""
    phone = make_phone({"Internal storage/Music/extra.mp3": b"a"}, monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.mp3").write_bytes(b"bb")

    real_stat, real_is_file = Path.stat, Path.is_file

    def vanished_stat(self, **kwargs):
        if self.name == "keep.mp3":
            raise OSError(2, "No such file or directory")
        return real_stat(self, **kwargs)

    def still_looks_like_a_file(self):
        return True if self.name == "keep.mp3" else real_is_file(self)

    monkeypatch.setattr(Path, "stat", vanished_stat)
    monkeypatch.setattr(Path, "is_file", still_looks_like_a_file)

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.files["Internal storage/Music/extra.mp3"] == b"a"
    assert phone.removed == []
    assert stats["errors"] == 1
    assert stats["deleted"] == 0


def test_sync_refuses_to_delete_when_a_symlink_loops_back_to_an_ancestor(
        tmp_path, monkeypatch, capsys):
    """`dir/sub/loop -> dir`: the loop guard stops infinite recursion by never
    re-walking `dir`'s contents from the symlinked path, so a phone file that
    only exists under that symlinked path can never be proven extraneous - the
    scan must count as incomplete, not silently 'complete'."""
    phone = make_phone({
        "Internal storage/Music/dir/real.txt": b"real",
        "Internal storage/Music/dir/sub/loop/real.txt": b"stale",
    }, monkeypatch)
    src = tmp_path / "src"
    d = src / "dir"
    d.mkdir(parents=True)
    (d / "real.txt").write_bytes(b"real")
    (d / "sub").mkdir()
    os.symlink(d, d / "sub" / "loop")

    stats = check_shape(operations.run_sync_rule(
        sync_rule(src, delete_extraneous=True), DEVICE))

    assert phone.removed == []
    assert phone.files["Internal storage/Music/dir/sub/loop/real.txt"] == b"stale"
    assert stats["deleted"] == 0
    assert stats["errors"] >= 1
    assert "refus" in capsys.readouterr().out.lower()


def test_sync_terminates_on_a_two_node_symlink_cycle(tmp_path, monkeypatch):
    """a <-> b mutual symlinks must not recurse forever."""
    phone = make_phone({}, monkeypatch)
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir(parents=True)
    os.symlink(src / "b", src / "a" / "link_to_b")
    os.symlink(src / "a", src / "b" / "link_to_a")

    stats = check_shape(operations.run_sync_rule(sync_rule(src), DEVICE))

    assert phone.removed == []
