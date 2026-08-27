"""Runner tests: the RunResult contract, rule filtering, and error accounting.

Every test fakes `operations.run_*_rule`, so nothing here touches gio or a
phone. `preflight.*` and `progress.*` are also faked here (autouse): the real
preflight functions touch the real filesystem (`shutil.disk_usage` on the
rule's desktop path) and the real progress classes spin a background thread
per rule - neither belongs in a unit test.
"""

import pytest

from phone_migration import runner, operations, gio_utils, device, preflight, progress, dry_run_analyzer


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _rule(rule_id, mode, manual=False, phone="/DCIM/Camera", desktop="~/Pictures"):
    return {
        "id": rule_id,
        "mode": mode,
        "phone_path": phone,
        "desktop_path": desktop,
        "manual_only": manual,
    }


def _profile(*rules, name="default"):
    return {
        "name": name,
        "device": {"display_name": "Pixel 7", "activation_uri": "mtp://Pixel/"},
        "rules": list(rules),
    }


class _FakeRuleProgress:
    def __init__(self, *a, **kw):
        pass

    def start(self):
        pass

    def stop(self, success=True, summary=""):
        pass


class _FakeOperationProgress:
    def __init__(self, *a, **kw):
        pass

    def update(self):
        pass


@pytest.fixture(autouse=True)
def quiet_device(monkeypatch):
    """No gio, no notifications, no access check, no real preflight/progress."""
    monkeypatch.setattr(gio_utils, "gio_mount", lambda uri: None)
    monkeypatch.setattr(gio_utils, "gio_list", lambda uri: ["DCIM"])
    monkeypatch.setattr(gio_utils, "DRY_RUN", False)
    for name in ("preflight_move", "preflight_copy", "preflight_backup", "preflight_sync"):
        monkeypatch.setattr(preflight, name, lambda rule, device: None)
    monkeypatch.setattr(progress, "RuleProgress", _FakeRuleProgress)
    monkeypatch.setattr(progress, "OperationProgress", _FakeOperationProgress)


@pytest.fixture
def ops(monkeypatch):
    """Record every op call; each op returns whatever the test queued for it."""
    calls = []
    returns = {}

    def make(name, default):
        def fake(rule, dev, verbose=False, transfer_tracker=None, **kwargs):
            calls.append({"op": name, "rule": rule, "kwargs": kwargs})
            return returns.get(name, default)
        return fake

    monkeypatch.setattr(operations, "run_copy_rule",
                        make("copy", {"copied": 0, "renamed": 0, "errors": 0, "skipped": 0,
                                      "folders": 0, "files": []}))
    monkeypatch.setattr(operations, "run_move_rule",
                        make("move", {"copied": 0, "renamed": 0, "deleted": 0, "errors": 0,
                                      "skipped": 0, "folders": 0, "files": []}))
    monkeypatch.setattr(operations, "run_backup_rule",
                        make("backup", {"copied": 0, "resumed": 0, "skipped": 0, "failed": 0,
                                        "errors": 0, "files": []}))
    monkeypatch.setattr(operations, "run_sync_rule",
                        make("sync", {"copied": 0, "skipped": 0, "deleted": 0, "errors": 0,
                                      "files": []}))
    return {"calls": calls, "returns": returns}


@pytest.fixture
def connected(monkeypatch):
    """Install a profile as the connected device; returns a setter."""
    def use(profile):
        monkeypatch.setattr(runner, "detect_connected_device", lambda cfg, verbose=False: profile)
    return use


# --------------------------------------------------------------------------
# RunResult shape
# --------------------------------------------------------------------------

def test_run_result_has_the_documented_shape(ops, connected):
    connected(_profile(_rule("r-1", "copy")))
    ops["returns"]["copy"] = {
        "copied": 3, "renamed": 1, "errors": 0, "skipped": 2, "folders": 4,
        "files": [{"action": "copied", "src": "a.jpg", "dst": "~/Pictures/a.jpg", "error": None}],
    }

    result = runner.run_for_connected_device({}, dry_run=True)

    assert result["dry_run"] is True
    assert result["profile"] == "default"
    assert result["device"] == "Pixel 7"
    assert set(result["stats"]) == {"copied", "renamed", "deleted", "errors", "skipped",
                                    "moved", "synced", "backed_up", "resumed", "folders"}
    assert all(isinstance(v, int) for v in result["stats"].values())
    assert set(result["transfer"]) == {"size_bytes", "seconds"}

    rule = result["rules"][0]
    assert set(rule) == {"id", "mode", "phone_path", "desktop_path", "stats", "error", "files"}
    assert rule["id"] == "r-1"
    assert rule["mode"] == "copy"
    assert rule["phone_path"] == "/DCIM/Camera"
    assert rule["desktop_path"] == "~/Pictures"
    assert rule["error"] is None
    assert rule["files"] == [{"action": "copied", "src": "a.jpg",
                              "dst": "~/Pictures/a.jpg", "error": None}]
    assert "files" not in rule["stats"]


def test_no_device_returns_an_empty_run_result(monkeypatch):
    monkeypatch.setattr(runner, "detect_connected_device", lambda cfg, verbose=False: None)

    result = runner.run_for_connected_device({}, dry_run=False)

    assert result["profile"] is None
    assert result["device"] is None
    assert result["rules"] == []
    assert result["stats"]["copied"] == 0


def test_no_device_hint_tells_you_to_pass_y_to_actually_run(monkeypatch, capsys):
    """The tool defaults to dry-run; a hint that says plain `--run` would just
    preview again, not execute."""
    monkeypatch.setattr(runner, "detect_connected_device", lambda cfg, verbose=False: None)

    runner.run_for_connected_device({}, dry_run=False)

    assert "phone-sync --run -y" in capsys.readouterr().out


def test_no_rules_returns_an_empty_run_result_naming_the_profile(ops, connected):
    connected(_profile(name="phone"))

    result = runner.run_for_connected_device({})

    assert result["profile"] == "phone"
    assert result["device"] == "Pixel 7"
    assert result["rules"] == []


# --------------------------------------------------------------------------
# finding #1: DRY_RUN is assigned unconditionally
# --------------------------------------------------------------------------

def test_dry_run_is_reset_on_the_next_real_run(ops, connected):
    connected(_profile(_rule("r-1", "copy")))

    runner.run_for_connected_device({}, dry_run=True)
    assert gio_utils.DRY_RUN is True

    runner.run_for_connected_device({}, dry_run=False)
    assert gio_utils.DRY_RUN is False


# --------------------------------------------------------------------------
# finding #16: rule filtering
# --------------------------------------------------------------------------

def test_default_runs_only_non_manual_rules(ops, connected):
    connected(_profile(_rule("auto", "copy"), _rule("manual", "copy", manual=True)))

    result = runner.run_for_connected_device({})

    assert [r["id"] for r in result["rules"]] == ["auto"]


def test_include_manual_runs_every_rule(ops, connected):
    connected(_profile(_rule("auto", "copy"), _rule("manual", "copy", manual=True)))

    result = runner.run_for_connected_device({}, include_manual=True)

    assert [r["id"] for r in result["rules"]] == ["auto", "manual"]


def test_rule_ids_select_those_rules_ignoring_manual_only(ops, connected):
    connected(_profile(_rule("auto", "copy"), _rule("manual", "copy", manual=True)))

    result = runner.run_for_connected_device({}, rule_ids=["manual"])

    assert [r["id"] for r in result["rules"]] == ["manual"]


def test_unmatched_rule_ids_produce_no_rules(ops, connected):
    connected(_profile(_rule("auto", "copy")))

    result = runner.run_for_connected_device({}, rule_ids=["nope"])

    assert result["rules"] == []


# --------------------------------------------------------------------------
# per-rule error handling
# --------------------------------------------------------------------------

def test_unknown_mode_is_an_error_not_a_crash(ops, connected):
    connected(_profile(_rule("r-1", "teleport")))

    result = runner.run_for_connected_device({})

    assert result["rules"][0]["error"] == "unknown mode teleport"
    assert result["rules"][0]["files"] == []
    assert result["stats"]["errors"] == 1


def test_a_raising_rule_is_counted_and_later_rules_still_run(ops, connected, monkeypatch):
    connected(_profile(_rule("boom", "copy"), _rule("fine", "sync")))

    def explode(*a, **kw):
        raise RuntimeError("gio went away")
    monkeypatch.setattr(operations, "run_copy_rule", explode)
    ops["returns"]["sync"] = {"copied": 2, "skipped": 0, "deleted": 0, "errors": 0, "files": []}

    result = runner.run_for_connected_device({})

    assert result["rules"][0]["error"] == "gio went away"
    assert result["rules"][1]["error"] is None
    assert result["stats"]["errors"] == 1
    assert result["stats"]["synced"] == 2


# --------------------------------------------------------------------------
# upstream feature: per-rule preflight disk-space check
# --------------------------------------------------------------------------

def test_preflight_failure_is_recorded_as_an_error_and_other_rules_still_run(ops, connected, monkeypatch):
    connected(_profile(_rule("big", "copy"), _rule("fine", "sync")))

    def not_enough_space(rule, device):
        raise preflight.PreflightError("not enough space")
    monkeypatch.setattr(preflight, "preflight_copy", not_enough_space)
    ops["returns"]["sync"] = {"copied": 1, "skipped": 0, "deleted": 0, "errors": 0, "files": []}

    result = runner.run_for_connected_device({})

    assert result["rules"][0]["error"] == "not enough space"
    assert result["rules"][1]["error"] is None
    assert result["stats"]["errors"] == 1
    assert result["stats"]["synced"] == 1
    # The copy operation itself was never reached - preflight aborted first.
    assert [c["op"] for c in ops["calls"]] == ["sync"]


def test_a_preflight_estimation_failure_warns_but_does_not_abort_the_rule(ops, connected, monkeypatch):
    connected(_profile(_rule("r-1", "copy")))

    def flaky_estimate(rule, device):
        raise OSError("could not stat filesystem")
    monkeypatch.setattr(preflight, "preflight_copy", flaky_estimate)
    ops["returns"]["copy"] = {"copied": 1, "renamed": 0, "errors": 0, "skipped": 0,
                              "folders": 0, "files": []}

    result = runner.run_for_connected_device({})

    assert result["rules"][0]["error"] is None
    assert result["stats"]["backed_up"] == 1
    assert [c["op"] for c in ops["calls"]] == ["copy"]


def test_preflight_is_skipped_during_a_dry_run(ops, connected, monkeypatch):
    connected(_profile(_rule("r-1", "copy")))
    calls = []
    monkeypatch.setattr(preflight, "preflight_copy", lambda rule, device: calls.append(1))

    runner.run_for_connected_device({}, dry_run=True)

    assert calls == []


# --------------------------------------------------------------------------
# upstream feature: skip_validation toggles the auto-validation header
# --------------------------------------------------------------------------

def test_skip_validation_suppresses_the_auto_validate_message(ops, connected, capsys):
    connected(_profile(_rule("r-1", "copy")))

    runner.run_for_connected_device({}, dry_run=False, skip_validation=False)
    assert "Auto-validating" in capsys.readouterr().out

    runner.run_for_connected_device({}, dry_run=False, skip_validation=True)
    assert "Auto-validating" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# upstream feature: dry-run analyzer adapter
# --------------------------------------------------------------------------

def test_dry_run_analyzer_receives_rule_stats_tuples(ops, connected, monkeypatch):
    connected(_profile(_rule("r-1", "copy")))
    ops["returns"]["copy"] = {"copied": 3, "renamed": 0, "errors": 0, "skipped": 0,
                              "folders": 0, "files": []}
    seen = []

    def fake_analyze(rules_stats):
        seen.extend(rules_stats)
        return dry_run_analyzer.AnalysisResult()
    monkeypatch.setattr(dry_run_analyzer, "analyze_dry_run_results", fake_analyze)

    runner.run_for_connected_device({}, dry_run=True)

    assert len(seen) == 1
    rule, stats = seen[0]
    assert rule["id"] == "r-1"
    assert stats == {"copied": 3, "renamed": 0, "errors": 0, "skipped": 0, "folders": 0}


def test_a_dry_run_blocker_stops_before_the_hint_and_the_notification(ops, connected, monkeypatch):
    connected(_profile(_rule("r-1", "copy")))
    ops["returns"]["copy"] = {"copied": 1, "renamed": 0, "errors": 0, "skipped": 0,
                              "folders": 0, "files": []}

    class _Blocked:
        is_safe = False
        has_warnings = False
        info = []
    monkeypatch.setattr(dry_run_analyzer, "analyze_dry_run_results", lambda rules_stats: _Blocked())
    monkeypatch.setattr(dry_run_analyzer, "format_analysis_results", lambda result: "")

    from phone_migration import notifications
    notified = []
    monkeypatch.setattr(notifications, "notify_completion", lambda stats, dry_run: notified.append(1))

    out = runner.run_for_connected_device({}, dry_run=True, notify=True)

    assert notified == []
    assert out["stats"]["backed_up"] == 1  # the result is still fully populated


# --------------------------------------------------------------------------
# totals
# --------------------------------------------------------------------------

def test_move_totals_feed_moved_and_deleted(ops, connected):
    connected(_profile(_rule("r-1", "move")))
    ops["returns"]["move"] = {"copied": 5, "renamed": 1, "deleted": 5, "errors": 0,
                              "skipped": 1, "folders": 2, "files": []}

    stats = runner.run_for_connected_device({})["stats"]

    assert stats["moved"] == 5
    assert stats["copied"] == 5
    assert stats["deleted"] == 5
    assert stats["renamed"] == 1
    assert stats["folders"] == 2
    assert stats["backed_up"] == 0


def test_backup_backed_up_excludes_resumed_and_resumed_is_its_own_total(ops, connected):
    connected(_profile(_rule("r-1", "backup")))
    ops["returns"]["backup"] = {"copied": 2, "resumed": 7, "skipped": 1, "failed": 0,
                                "errors": 0, "files": []}

    stats = runner.run_for_connected_device({})["stats"]

    assert stats["backed_up"] == 2
    assert stats["resumed"] == 7


def test_backup_failures_count_as_errors(ops, connected, capsys):
    connected(_profile(_rule("r-1", "backup")))
    ops["returns"]["backup"] = {"copied": 0, "resumed": 0, "skipped": 0, "failed": 4,
                                "errors": 0, "files": []}

    result = runner.run_for_connected_device({})

    assert result["stats"]["errors"] == 4
    assert "All operations successful" not in capsys.readouterr().out


def test_the_files_list_is_never_summed_into_the_totals(ops, connected):
    connected(_profile(_rule("r-1", "copy")))
    ops["returns"]["copy"] = {
        "copied": 1, "renamed": 0, "errors": 0, "skipped": 0, "folders": 0,
        "files": [{"action": "copied", "src": "a", "dst": "b", "error": None}],
    }

    stats = runner.run_for_connected_device({})["stats"]

    assert all(isinstance(v, int) for v in stats.values())
    assert stats["copied"] == 1


def test_transfer_block_reports_bytes_and_seconds(ops, connected):
    connected(_profile(_rule("r-1", "copy")))

    transfer = runner.run_for_connected_device({})["transfer"]

    assert transfer["size_bytes"] == 0
    assert isinstance(transfer["seconds"], float)


# --------------------------------------------------------------------------
# arguments forwarded to the ops
# --------------------------------------------------------------------------

def test_backup_receives_the_profile_name_and_the_rename_flag(ops, connected):
    connected(_profile(_rule("r-1", "backup"), name="pixel"))

    runner.run_for_connected_device({}, rename_duplicates=True)

    kwargs = ops["calls"][0]["kwargs"]
    assert kwargs["profile_name"] == "pixel"
    assert kwargs["rename_duplicates"] is True


def test_backup_skips_conflicts_by_default_while_move_renames(ops, connected):
    """Tri-state default: None means "each mode's own default", not True for all."""
    connected(_profile(_rule("m", "move"), _rule("b", "backup")))

    runner.run_for_connected_device({})  # no rename_duplicates argument at all

    assert ops["calls"][0]["kwargs"]["rename_duplicates"] is True   # move renames
    assert ops["calls"][1]["kwargs"]["rename_duplicates"] is False  # backup skips


def test_an_explicit_rename_flag_overrides_the_backup_default(ops, connected):
    connected(_profile(_rule("b", "backup")))

    runner.run_for_connected_device({}, rename_duplicates=True)

    assert ops["calls"][0]["kwargs"]["rename_duplicates"] is True


def test_sync_is_not_given_rename_duplicates(ops, connected):
    connected(_profile(_rule("r-1", "sync")))

    runner.run_for_connected_device({}, rename_duplicates=False)

    assert "rename_duplicates" not in ops["calls"][0]["kwargs"]


def test_move_and_copy_receive_rename_duplicates(ops, connected):
    connected(_profile(_rule("m", "move"), _rule("c", "copy")))

    runner.run_for_connected_device({}, rename_duplicates=False)

    assert ops["calls"][0]["kwargs"]["rename_duplicates"] is False
    assert ops["calls"][1]["kwargs"]["rename_duplicates"] is False


# --------------------------------------------------------------------------
# mounting + device detection
# --------------------------------------------------------------------------

def test_the_device_is_mounted_through_gio_utils(ops, connected, monkeypatch):
    mounted = []
    monkeypatch.setattr(gio_utils, "gio_mount", mounted.append)
    connected(_profile(_rule("r-1", "copy")))

    runner.run_for_connected_device({})

    assert mounted == ["mtp://Pixel/"]


def test_detect_skips_a_device_with_no_serial(monkeypatch, capsys):
    monkeypatch.setattr(device, "enumerate_mtp_mounts",
                        lambda: [{"display_name": "Mystery", "activation_uri": "mtp://x/"}])
    monkeypatch.setattr(device, "device_fingerprint", lambda info, verbose=False: ("", ""))

    matched = []

    def never(config, id_type, id_value):
        matched.append((id_type, id_value))
        return {"name": "should-not-match"}

    from phone_migration import config as cfg
    monkeypatch.setattr(cfg, "find_profile_by_device_id", never)

    assert runner.detect_connected_device({}) is None
    assert matched == []
    assert "Mystery" in capsys.readouterr().out


def test_detect_matches_a_device_with_a_serial(monkeypatch):
    monkeypatch.setattr(device, "enumerate_mtp_mounts",
                        lambda: [{"display_name": "Pixel", "activation_uri": "mtp://p/"}])
    monkeypatch.setattr(device, "device_fingerprint",
                        lambda info, verbose=False: ("mtp_serial", "ABC"))

    from phone_migration import config as cfg
    profile = {"name": "default", "device": {}}
    monkeypatch.setattr(cfg, "find_profile_by_device_id", lambda c, t, v: profile)

    assert runner.detect_connected_device({}) is profile
    assert profile["device"]["activation_uri"] == "mtp://p/"


# --------------------------------------------------------------------------
# notifications consume the RunResult stats
# --------------------------------------------------------------------------

def test_notify_receives_the_result_stats(ops, connected, monkeypatch):
    from phone_migration import notifications
    seen = []
    monkeypatch.setattr(notifications, "notify_completion",
                        lambda stats, dry_run: seen.append((stats, dry_run)))
    connected(_profile(_rule("r-1", "copy")))

    result = runner.run_for_connected_device({}, notify=True)

    assert seen == [(result["stats"], False)]


# The real check, captured before the autouse fixture swaps it out.
_REAL_PREFLIGHT_COPY = preflight.preflight_copy


def test_the_real_preflight_passes_a_rule_whose_desktop_dir_does_not_exist_yet(
        ops, connected, monkeypatch, tmp_path):
    """The operation creates the destination moments later; preflight must not skip it."""
    monkeypatch.setattr(preflight, "preflight_copy", _REAL_PREFLIGHT_COPY)
    monkeypatch.setattr(gio_utils, "gio_list_detailed", lambda uri: [])
    dest = tmp_path / "Phone" / "Camera"  # deliberately not created
    connected(_profile(_rule("r-1", "copy", desktop=str(dest))))

    result = runner.run_for_connected_device({}, dry_run=False)

    assert result["rules"][0]["error"] is None
    assert result["stats"]["errors"] == 0
