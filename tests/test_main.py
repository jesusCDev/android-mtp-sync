"""CLI tests: argument parsing, dispatch, and web-server process management."""

import os
import pathlib
import signal
import subprocess
import sys
import unicodedata

import pytest

import main
from phone_migration import config as cfg, device, runner


@pytest.fixture
def parser():
    return main.build_parser()


@pytest.fixture
def no_config(monkeypatch):
    """load_config/save_config never touch disk."""
    monkeypatch.setattr(cfg, "load_config", lambda: {"profiles": []})
    monkeypatch.setattr(cfg, "save_config", lambda config: None)


@pytest.fixture
def pid_file(tmp_path, monkeypatch):
    path = tmp_path / "web.pid"
    monkeypatch.setattr(main, "STATE_DIR", tmp_path)
    monkeypatch.setattr(main, "PID_FILE", path)
    monkeypatch.setattr(main, "WEB_LOG", tmp_path / "web.log")
    return path


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def test_run_with_an_unknown_dry_run_flag_exits_2(parser):
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--run", "--dry-run"])
    assert exc.value.code == 2


def test_edit_rule_accepts_no_manual(parser):
    args = parser.parse_args(["--edit-rule", "-p", "default", "-i", "r-1", "--no-manual"])
    assert args.manual is False


def test_edit_rule_accepts_manual(parser):
    args = parser.parse_args(["--edit-rule", "-p", "default", "-i", "r-1", "--manual"])
    assert args.manual is True


def test_manual_is_none_when_the_flag_is_absent(parser):
    args = parser.parse_args(["--edit-rule", "-p", "default", "-i", "r-1"])
    assert args.manual is None


def test_edit_rule_forwards_the_tri_state_manual_value(monkeypatch, no_config):
    seen = {}
    monkeypatch.setattr(cfg, "edit_rule",
                        lambda config, profile, rule_id, **kw: seen.update(kw))

    main.main(["--edit-rule", "-p", "default", "-i", "r-1", "--no-manual"])
    assert seen["manual_only"] is False

    main.main(["--edit-rule", "-p", "default", "-i", "r-1", "--manual"])
    assert seen["manual_only"] is True

    main.main(["--edit-rule", "-p", "default", "-i", "r-1", "-m", "copy"])
    assert seen["manual_only"] is None


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------

def test_run_manual_reaches_the_runner_with_include_manual(monkeypatch, no_config):
    seen = {}
    monkeypatch.setattr(runner, "run_for_connected_device",
                        lambda config, **kw: seen.update(kw) or {})

    assert main.main(["--run", "--manual"]) == 0
    assert seen["include_manual"] is True
    assert seen["dry_run"] is True


def test_run_without_manual_does_not_include_manual_rules(monkeypatch, no_config):
    seen = {}
    monkeypatch.setattr(runner, "run_for_connected_device",
                        lambda config, **kw: seen.update(kw) or {})

    assert main.main(["--run", "-y"]) == 0
    assert seen["include_manual"] is False
    assert seen["dry_run"] is False


def test_add_device_without_a_serial_reports_the_error_and_exits_1(monkeypatch, no_config, capsys):
    def refuse(config, name, verbose=False):
        raise RuntimeError("Device exposes no serial number; cannot register it")
    monkeypatch.setattr(device, "register_current_device", refuse)

    assert main.main(["--add-device"]) == 1
    assert "no serial number" in capsys.readouterr().err


def test_backup_and_smart_copy_add_the_same_rule(monkeypatch, no_config, capsys):
    added = []
    monkeypatch.setattr(cfg, "add_backup_rule",
                        lambda config, profile, pp, dp, manual_only=False:
                        added.append((profile, pp, dp, manual_only)))

    argv = ["-p", "default", "-pp", "/DCIM", "-dp", "~/Backup"]
    assert main.main(["--backup"] + argv) == 0
    backup_out = capsys.readouterr().out

    assert main.main(["--smart-copy"] + argv) == 0
    smart_out = capsys.readouterr().out

    assert added == [("default", "/DCIM", "~/Backup", False)] * 2
    assert "deprecated" in smart_out.lower()
    assert "deprecated" not in backup_out.lower()


# --------------------------------------------------------------------------
# web process management (finding #25)
# --------------------------------------------------------------------------

def test_stop_does_not_signal_a_pid_that_is_not_the_web_ui(pid_file, monkeypatch, capsys):
    pid_file.write_text(str(os.getpid()))  # pytest's own cmdline: no main.py --web
    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    assert main.main(["--web", "--stop"]) == 0
    assert killed == []
    assert "No running web UI" in capsys.readouterr().out


def test_stop_with_no_pid_file_is_a_no_op(pid_file, monkeypatch, capsys):
    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    assert main.main(["--web", "--stop"]) == 0
    assert killed == []
    assert "No running web UI" in capsys.readouterr().out


def test_stop_signals_the_recorded_web_process_and_clears_the_pid_file(pid_file, capsys):
    # A real process whose /proc cmdline carries both "main.py" and "--web".
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)",
                             "main.py", "--web"])
    try:
        pid_file.write_text(str(proc.pid))

        assert main.main(["--web", "--stop"]) == 0
        assert "Stopped web UI" in capsys.readouterr().out
        assert not pid_file.exists()
        assert proc.wait(timeout=5) != 0  # terminated by the signal
    finally:
        proc.kill()
        proc.wait()


def test_stop_keeps_the_pid_file_and_exits_1_when_the_server_survives(pid_file, monkeypatch, capsys):
    pid_file.write_text("4242")
    monkeypatch.setattr(main, "_web_pid", lambda: 4242)  # never exits
    monkeypatch.setattr(main, "STOP_TIMEOUT", 0.2)
    monkeypatch.setattr(os, "kill", lambda pid, sig: None)

    assert main.main(["--web", "--stop"]) == 1
    assert pid_file.exists()  # the only handle on the survivor must not be thrown away
    err = capsys.readouterr().err
    assert "still running" in err and "4242" in err


def test_web_start_aborts_when_the_port_never_frees(pid_file, monkeypatch, capsys):
    from phone_migration import web_ui
    started = []
    monkeypatch.setattr(web_ui, "start_web_ui", lambda **kw: started.append(kw))
    monkeypatch.setattr(main, "_wait_port", lambda port, want_open, timeout=5.0: False)

    assert main.main(["--web"]) == 1
    assert started == []
    assert f"{main.WEB_PORT} still in use" in capsys.readouterr().err


def test_a_web_failure_does_not_leak_a_traceback(pid_file, monkeypatch, capsys):
    def boom():
        raise OSError("state dir is read-only")
    monkeypatch.setattr(main, "_web_pid", boom)

    assert main.main(["--web"]) == 1
    assert "state dir is read-only" in capsys.readouterr().err


def test_a_stale_pid_file_is_removed(pid_file, capsys):
    pid_file.write_text("999999")  # no such process

    assert main.main(["--web", "--stop"]) == 0
    assert not pid_file.exists()


def test_web_pid_rejects_a_garbage_pid_file(pid_file):
    pid_file.write_text("not-a-pid")
    assert main._web_pid() is None


def test_background_start_reports_failure_when_the_port_never_opens(pid_file, monkeypatch, capsys):
    main.WEB_LOG.parent.mkdir(parents=True, exist_ok=True)
    main.WEB_LOG.write_text("Traceback: ImportError: no flask\n")

    class FakeProc:
        pid = 4242
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProc())
    # The port frees fine, it just never comes back up.
    monkeypatch.setattr(main, "_wait_port",
                        lambda port, want_open, timeout=5.0: want_open is False)

    assert main.main(["--web", "--background"]) == 1
    assert "ImportError" in capsys.readouterr().err


def test_background_start_reports_the_url_when_the_port_opens(pid_file, monkeypatch, capsys):
    class FakeProc:
        pid = 4242
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(main, "_wait_port", lambda port, want_open, timeout=5.0: True)

    assert main.main(["--web", "--background"]) == 0
    assert f"127.0.0.1:{main.WEB_PORT}" in capsys.readouterr().out


def test_foreground_web_writes_and_removes_its_pid_file(pid_file, monkeypatch):
    from phone_migration import web_ui

    seen = {}

    def fake_start(host, port, debug):
        seen["running_pid"] = pid_file.read_text().strip()
        seen["args"] = (host, port, debug)
    monkeypatch.setattr(web_ui, "start_web_ui", fake_start)
    monkeypatch.setattr(main, "_wait_port", lambda port, want_open, timeout=5.0: True)

    assert main.main(["--web"]) == 0
    assert seen["running_pid"] == str(os.getpid())
    assert seen["args"] == ("127.0.0.1", main.WEB_PORT, False)
    assert not pid_file.exists()


def test_port_probe_reports_a_closed_port():
    assert main._port_open(1) is False   # nothing listens on port 1


def test_port_probe_still_sees_a_bound_but_unaccepting_server():
    """A full listen backlog drops the SYN; that is "in use", not "free"."""
    import socket
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((main.WEB_HOST, 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert main._port_open(port) is True
        for _ in range(4):        # saturate the accept queue, nobody accepts
            main._port_open(port)
        assert main._port_open(port) is True
    finally:
        srv.close()


# --------------------------------------------------------------------------
# repo rule: no emoji in CLI output
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["main.py", "phone_migration/runner.py"])
def test_no_emoji_or_double_width_glyphs(path):
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for lineno, line in enumerate((root / path).read_text(encoding="utf-8").splitlines(), 1):
        for ch in line:
            if unicodedata.east_asian_width(ch) == "W" or ch == "\ufe0f" or "①" <= ch <= "⑳":
                offenders.append(f"{path}:{lineno}: {ch!r}")
    assert offenders == []


def test_run_exits_1_when_the_run_reported_errors(monkeypatch, no_config):
    monkeypatch.setattr(runner, "run_for_connected_device",
                        lambda config, **kw: {"stats": {"errors": 2}})
    assert main.main(["--run"]) == 1


def test_run_exits_0_when_the_run_reported_no_errors(monkeypatch, no_config):
    monkeypatch.setattr(runner, "run_for_connected_device",
                        lambda config, **kw: {"stats": {"errors": 0}})
    assert main.main(["--run"]) == 0
