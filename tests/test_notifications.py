"""Tests for phone_migration.notifications.

Two rules: notify-send gets a `--` so a title starting with `-` is text and not
an option, and nothing we send carries an emoji.
"""

import subprocess

import pytest

from phone_migration import notifications


@pytest.fixture
def notify_send(monkeypatch):
    """Pretend notify-send exists and record the argv it is called with."""
    recorded = []

    def fake_run(args, **kwargs):
        recorded.append(args)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(notifications.shutil, "which", lambda name: "/usr/bin/notify-send")
    monkeypatch.setattr(notifications.subprocess, "run", fake_run)
    return recorded


@pytest.fixture
def sent(monkeypatch):
    """Record the title/message the higher-level helpers hand to notify-send."""
    recorded = []
    monkeypatch.setattr(notifications, "send_notification",
                        lambda **kwargs: recorded.append(kwargs) or True)
    return recorded


# --- send_notification -------------------------------------------------------

def test_double_dash_separates_options_from_the_title(notify_send):
    notifications.send_notification("-n 5 files moved", "-and a body")

    argv = notify_send[0]
    assert argv[-3:] == ["--", "-n 5 files moved", "-and a body"]


def test_options_still_reach_notify_send(notify_send):
    notifications.send_notification("t", "m", urgency="critical", icon="phone", timeout=1000)

    argv = notify_send[0]
    assert argv[0] == "notify-send"
    assert argv[1:argv.index("--")] == [
        "--urgency=critical", "--icon=phone", "--expire-time=1000"]


def test_missing_notify_send_is_not_an_error(monkeypatch):
    monkeypatch.setattr(notifications.shutil, "which", lambda name: None)

    assert notifications.send_notification("t", "m") is False


@pytest.mark.parametrize("error", [
    FileNotFoundError("notify-send"),
    subprocess.TimeoutExpired("notify-send", 2),
    subprocess.SubprocessError("boom"),
])
def test_a_broken_notify_send_is_not_an_error(monkeypatch, error):
    monkeypatch.setattr(notifications.shutil, "which", lambda name: "/usr/bin/notify-send")

    def fake_run(args, **kwargs):
        raise error

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    assert notifications.send_notification("t", "m") is False


def test_a_real_bug_is_not_swallowed(monkeypatch):
    """The except used to end in `Exception`, hiding every programming error."""
    monkeypatch.setattr(notifications.shutil, "which", lambda name: "/usr/bin/notify-send")

    def fake_run(args, **kwargs):
        raise TypeError("bad argument")

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    with pytest.raises(TypeError):
        notifications.send_notification("t", "m")


# --- notify_completion / notify_error ----------------------------------------

def test_completion_reports_counts_in_words(sent):
    notifications.notify_completion({"moved": 3, "backed_up": 2, "synced": 1})

    assert sent[0]["title"] == "Phone Migration: completed"
    assert sent[0]["message"] == "3 moved, 2 backed up, 1 synced"
    assert sent[0]["urgency"] == "normal"


def test_completion_without_a_breakdown_falls_back_to_the_total(sent):
    notifications.notify_completion({"copied": 7})

    assert sent[0]["message"] == "7 files processed"


def test_errors_make_the_notification_critical(sent):
    notifications.notify_completion({"moved": 1, "errors": 2})

    assert sent[0]["title"] == "Phone Migration: 2 errors"
    assert sent[0]["urgency"] == "critical"
    assert "2 errors" in sent[0]["message"]


def test_a_dry_run_notifies_nobody(sent):
    notifications.notify_completion({"moved": 3}, dry_run=True)

    assert sent == []


@pytest.mark.parametrize("call", [
    lambda: notifications.notify_completion({"moved": 1, "errors": 1}),
    lambda: notifications.notify_completion({"copied": 1}),
    lambda: notifications.notify_error("phone went away"),
    lambda: notifications.notify_device_not_found(),
])
def test_nothing_we_send_contains_an_emoji(sent, call):
    call()

    for kwargs in sent:
        assert kwargs["title"].isascii(), kwargs["title"]
        assert kwargs["message"].isascii(), kwargs["message"]
