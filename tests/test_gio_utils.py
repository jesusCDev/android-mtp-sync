"""Tests for phone_migration.gio_utils.

gio is a hard dependency of this tool and works on ``file://`` URIs, so the
cheap checks run it for real against a tmp_path instead of mocking it. Only the
timeout path is faked.
"""

import subprocess

import pytest

from phone_migration import gio_utils, theme


def uri(path) -> str:
    return path.as_uri()


@pytest.fixture
def tree(tmp_path):
    """A tmp dir holding one regular file, one empty file and one subdir."""
    (tmp_path / "a b#c.jpg").write_bytes(b"hello world")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "sub dir").mkdir()
    return tmp_path


# --- colors come from theme, gio_utils defines none of its own ---------------

def test_colors_come_from_theme():
    assert gio_utils.Colors is theme.Colors
    assert gio_utils.Icons is theme.Icons


# --- run() ------------------------------------------------------------------

def test_run_raises_gio_error_with_gio_stderr(tmp_path):
    with pytest.raises(gio_utils.GioError) as exc:
        gio_utils.run([gio_utils.GIO, "list", uri(tmp_path / "nope")])
    assert "No such file or directory" in str(exc.value)


def test_run_check_false_returns_the_failed_process(tmp_path):
    result = gio_utils.run([gio_utils.GIO, "list", uri(tmp_path / "nope")], check=False)
    assert result.returncode != 0


def test_run_turns_a_timeout_into_gio_error(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    with pytest.raises(gio_utils.GioError) as exc:
        gio_utils.run([gio_utils.GIO, "list", "mtp://phone/x"], timeout=7)
    assert str(exc.value) == f"timeout after 7s: {gio_utils.GIO} list mtp://phone/x"


def test_copy_uses_the_long_timeout(monkeypatch, tmp_path):
    seen = {}

    def record(args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", record)
    gio_utils.gio_copy(str(tmp_path / "src"), str(tmp_path / "dst"))
    assert seen["timeout"] == gio_utils.TIMEOUT_COPY


# --- child_uri --------------------------------------------------------------

def test_child_uri_percent_encodes_the_whole_name():
    assert gio_utils.child_uri("mtp://x/a", "b c#d.jpg") == "mtp://x/a/b%20c%23d.jpg"


def test_child_uri_does_not_double_the_separator():
    assert gio_utils.child_uri("mtp://x/a/", "b") == "mtp://x/a/b"


def test_child_uri_encodes_slashes_in_the_name():
    assert gio_utils.child_uri("mtp://x", "a/b") == "mtp://x/a%2Fb"


# --- gio_list ---------------------------------------------------------------

def test_gio_list_returns_entry_names(tree):
    assert sorted(gio_utils.gio_list(uri(tree))) == ["a b#c.jpg", "empty.txt", "sub dir"]


def test_gio_list_raises_on_a_missing_directory(tmp_path):
    """Finding #7: a failed listing must never look like an empty directory."""
    with pytest.raises(gio_utils.GioError):
        gio_utils.gio_list(uri(tmp_path / "nope"))


def test_gio_list_of_an_empty_directory_is_empty(tmp_path):
    (tmp_path / "empty").mkdir()
    assert gio_utils.gio_list(uri(tmp_path / "empty")) == []


# --- gio_list_detailed ------------------------------------------------------

def test_gio_list_detailed_reports_type_and_size(tree):
    entries = {e["name"]: e for e in gio_utils.gio_list_detailed(uri(tree))}
    assert set(entries) == {"a b#c.jpg", "empty.txt", "sub dir"}
    assert entries["a b#c.jpg"] == {"name": "a b#c.jpg", "is_dir": False, "size": 11}
    assert entries["empty.txt"] == {"name": "empty.txt", "is_dir": False, "size": 0}
    assert entries["sub dir"]["is_dir"] is True


def test_gio_list_detailed_raises_on_a_missing_directory(tmp_path):
    with pytest.raises(gio_utils.GioError):
        gio_utils.gio_list_detailed(uri(tmp_path / "nope"))


def test_gio_list_detailed_parses_a_captured_sample(monkeypatch):
    """Real `gio list -a standard::type,standard::size` output (gio 2.88.3)."""
    sample = "sub dir#1\t40\t(directory)\na b#c.jpg\t11\t(regular)\nempty.txt\t0\t(regular)\n"
    monkeypatch.setattr(
        gio_utils, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, sample, ""),
    )
    assert gio_utils.gio_list_detailed("mtp://phone/x") == [
        {"name": "sub dir#1", "is_dir": True, "size": 40},
        {"name": "a b#c.jpg", "is_dir": False, "size": 11},
        {"name": "empty.txt", "is_dir": False, "size": 0},
    ]


# --- gio_info ---------------------------------------------------------------

def test_gio_info_on_a_missing_file_returns_empty(tmp_path):
    assert gio_utils.gio_info(uri(tmp_path / "nope")) == {}


def test_gio_info_raises_when_the_failure_is_not_a_missing_file(monkeypatch):
    """Finding: `{}` must mean "absent", never "gio broke". A phone that dropped
    off the bus used to look like a file that was never there."""
    monkeypatch.setattr(
        gio_utils, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 2, "", "gio: mtp://phone/x: Permission denied\n"),
    )
    with pytest.raises(gio_utils.GioError, match="Permission denied"):
        gio_utils.gio_info("mtp://phone/x")


def test_gio_info_reports_size_and_type(tree):
    info = gio_utils.gio_info(uri(tree / "a b#c.jpg"), ["standard::type", "standard::size"])
    assert gio_utils.get_file_size(info) == 11
    assert gio_utils.is_dir(info) is False


def test_gio_info_marks_directories(tree):
    assert gio_utils.is_dir(gio_utils.gio_info(uri(tree / "sub dir"))) is True


def test_is_dir_accepts_both_gio_spellings():
    assert gio_utils.is_dir({"standard::type": "2"}) is True
    assert gio_utils.is_dir({"standard::type": "directory"}) is True
    assert gio_utils.is_dir({"standard::type": "1"}) is False
    assert gio_utils.is_dir({}) is False


def test_get_file_size_is_none_when_unavailable():
    assert gio_utils.get_file_size({}) is None
    assert gio_utils.get_file_size({"standard::size": "Unknown"}) is None
    assert gio_utils.get_file_size({"standard::size": "12"}) == 12


# --- gio_copy ---------------------------------------------------------------

def test_gio_copy_takes_no_overwrite_argument(tmp_path):
    """Finding #8: `--backup=none` was never a valid gio value."""
    with pytest.raises(TypeError):
        gio_utils.gio_copy("a", "b", overwrite=True)


def test_gio_copy_overwrites_without_leaving_a_backup(tree, tmp_path):
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "a b#c.jpg").write_bytes(b"stale")

    assert gio_utils.gio_copy(uri(tree / "a b#c.jpg"), str(dest / "a b#c.jpg")) is True
    assert (dest / "a b#c.jpg").read_bytes() == b"hello world"
    assert sorted(p.name for p in dest.iterdir()) == ["a b#c.jpg"]


def test_gio_copy_prints_success_only_after_the_copy_succeeds(tmp_path, capsys):
    ok = gio_utils.gio_copy(uri(tmp_path / "nope"), str(tmp_path / "dst"), verbose=True)
    out = capsys.readouterr().out
    assert ok is False
    assert theme.Icons.OK not in out
    assert theme.Icons.FAIL in out
    assert "No such file or directory" in out


def test_gio_copy_prints_the_success_line_when_verbose(tree, tmp_path, capsys):
    gio_utils.gio_copy(uri(tree / "empty.txt"), str(tmp_path / "copy.txt"), verbose=True)
    assert theme.Icons.OK in capsys.readouterr().out


def test_gio_copy_is_a_no_op_in_dry_run(tree, tmp_path, monkeypatch):
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)
    dest = tmp_path / "dry.txt"
    assert gio_utils.gio_copy(uri(tree / "empty.txt"), str(dest)) is True
    assert not dest.exists()


# --- gio_remove / gio_mkdir / gio_mount -------------------------------------

def test_gio_remove_deletes_and_reports_failure(tree, tmp_path, capsys):
    assert gio_utils.gio_remove(uri(tree / "empty.txt")) is True
    assert not (tree / "empty.txt").exists()

    capsys.readouterr()
    assert gio_utils.gio_remove(uri(tmp_path / "nope")) is False
    assert theme.Icons.FAIL in capsys.readouterr().out


def test_gio_mkdir_creates_the_directory(tmp_path):
    assert gio_utils.gio_mkdir(uri(tmp_path / "new")) is True
    assert (tmp_path / "new").is_dir()


def test_gio_mkdir_is_idempotent(tmp_path):
    """`gio mkdir -p` still errors on an existing directory; sync calls this on
    every run and must not read that as a failure."""
    (tmp_path / "there").mkdir()
    assert gio_utils.gio_mkdir(uri(tmp_path / "there")) is True


def test_gio_mkdir_returns_false_on_timeout_instead_of_raising(monkeypatch, capsys):
    """A hung MTP mkdir must not violate operations.py's 'a rule never
    raises' contract: run()'s TimeoutExpired->GioError has to be caught here
    too, same as gio_copy and gio_remove already do."""
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    assert gio_utils.gio_mkdir("mtp://phone/stuck") is False
    assert theme.Icons.FAIL in capsys.readouterr().out


def test_gio_mount_swallows_failures(monkeypatch):
    def boom(*args, **kwargs):
        raise gio_utils.GioError("device is not mounted")

    monkeypatch.setattr(gio_utils, "run", boom)
    assert gio_utils.gio_mount("mtp://[usb:999,999]/") is None


# --- upstream features kept: FailureInjector and gio_info(timeout=) ---------

def test_failure_injector_can_simulate_a_disconnect():
    """Test-only hook upstream added to simulate a phone dropping off mid-copy."""
    gio_utils.FAILURE_INJECTOR.reset()
    gio_utils.FAILURE_INJECTOR.enabled = True
    gio_utils.FAILURE_INJECTOR.fail_on_copy = True
    gio_utils.FAILURE_INJECTOR.fail_after_count = 0
    try:
        assert gio_utils.gio_copy("mtp://phone/a", "/tmp/a") is False
    finally:
        gio_utils.FAILURE_INJECTOR.reset()


def test_gio_info_timeout_override_is_routed_through_run(monkeypatch):
    """rule_validator.py calls gio_info(uri, timeout=1); the override must reach
    the shared run(), not bypass it with a separate subprocess.run call."""
    seen = {}

    def record(args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", record)
    gio_utils.gio_info("mtp://phone/x", timeout=1)
    assert seen["timeout"] == 1


def test_gio_info_without_a_timeout_uses_the_default(monkeypatch):
    seen = {}

    def record(args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", record)
    gio_utils.gio_info("mtp://phone/x")
    assert seen["timeout"] == gio_utils.TIMEOUT_SHORT


def test_a_missing_gio_binary_is_a_gio_error(monkeypatch):
    """Every caller guards against GioError; a bare FileNotFoundError escapes them all."""
    monkeypatch.setattr(gio_utils, "GIO", "/nonexistent/bin/gio")

    with pytest.raises(gio_utils.GioError, match="not found"):
        gio_utils.gio_list("mtp://Pixel/")

    gio_utils.gio_mount("mtp://Pixel/")  # best effort: must stay silent
