"""
Test suite for dry-run safety analyzer.

Tests all anomaly detection scenarios to ensure safety checks work correctly.
"""

import pytest
from fake_gio import FakePhone
from phone_migration import dry_run_analyzer, gio_utils, operations


def test_normal_move_operation():
    """Normal move: copied == deleted, no issues."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 10, 'deleted': 10, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings
    assert len(result.blockers) == 0
    assert len(result.warnings) == 0


def test_move_with_skipped_files():
    """Move with skipped files: copied < total, deleted == copied."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 8, 'deleted': 8, 'skipped': 2, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings


def test_move_safety_violation_mismatch():
    """BLOCKER: Move deleted != copied."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 10, 'deleted': 12, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert not result.is_safe
    assert len(result.blockers) == 1
    assert 'SAFETY VIOLATION' in result.blockers[0].message
    assert 'copied 10' in result.blockers[0].message
    assert 'deleted 12' in result.blockers[0].message


def test_copy_with_deletes_blocker():
    """BLOCKER: Copy mode should never delete."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'copy'}, {'copied': 10, 'deleted': 5, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert not result.is_safe
    assert len(result.blockers) == 1
    assert 'Copy mode' in result.blockers[0].message
    assert 'deleted 5 files' in result.blockers[0].message


def test_backup_with_deletes_blocker():
    """BLOCKER: Backup mode should never delete."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'backup'}, {'copied': 100, 'deleted': 1, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert not result.is_safe
    assert len(result.blockers) == 1
    assert 'Backup mode' in result.blockers[0].message


def test_mass_deletion_warning():
    """WARNING: Deleting many files (1000+) with few copied."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 1000, 'deleted': 1000, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    # Should be safe (move is correct) but with warning for large operation
    assert result.is_safe
    assert result.has_warnings
    assert any('1000 files will be removed from phone' in w.message for w in result.warnings)


def test_large_delete_warning():
    """WARNING: Large deletion (>100 files)."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 150, 'deleted': 150, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert result.has_warnings
    assert any('Large deletion' in w.message or '150 files' in w.message for w in result.warnings)


def test_sync_extreme_delete_ratio():
    """WARNING: Sync deleting 5x more than copying."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'sync'}, {'copied': 2, 'deleted': 50, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe  # Not a blocker, just a warning
    assert result.has_warnings
    assert any('delete 50 files' in w.message and 'copy 2' in w.message for w in result.warnings)


def test_sync_large_deletion():
    """WARNING: Sync deleting >500 files."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'sync'}, {'copied': 200, 'deleted': 600, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert result.has_warnings
    assert any('600 files will be removed' in w.message for w in result.warnings)


def test_zero_operation_with_skipped():
    """INFO: Nothing to do, all files exist."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'copy'}, {'copied': 0, 'deleted': 0, 'skipped': 50, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings
    assert len(result.info) == 1
    assert '50 files already exist' in result.info[0].message


def test_zero_operation_empty_source():
    """INFO: Nothing to do, source is empty."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 0, 'deleted': 0, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings
    assert len(result.info) == 1
    assert 'empty or already synchronized' in result.info[0].message


def test_multiple_rules_mixed_issues():
    """Multiple rules: some safe, some with issues."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'move'}, {'copied': 10, 'deleted': 10, 'skipped': 0, 'renamed': 0}),  # Safe
        ({'id': 'r-002', 'mode': 'copy'}, {'copied': 5, 'deleted': 1, 'skipped': 0, 'renamed': 0}),   # BLOCKER!
        ({'id': 'r-003', 'mode': 'sync'}, {'copied': 2, 'deleted': 100, 'skipped': 0, 'renamed': 0}),  # Warning
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert not result.is_safe  # Has blocker
    assert len(result.blockers) == 1
    assert result.blockers[0].rule_id == 'r-002'
    assert result.has_warnings
    assert any(w.rule_id == 'r-003' for w in result.warnings)


def test_format_output_has_colors():
    """Test that formatted output includes color codes."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'copy'}, {'copied': 10, 'deleted': 1, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    formatted = dry_run_analyzer.format_analysis_results(result)
    
    assert formatted
    assert '❌' in formatted or 'BLOCKERS' in formatted
    assert '[r-001]' in formatted


def test_normal_copy_operation():
    """Normal copy: no deletions, safe."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'copy'}, {'copied': 50, 'deleted': 0, 'skipped': 10, 'renamed': 5})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings


def test_normal_sync_operation():
    """Normal sync: balanced operations."""
    rules_stats = [
        ({'id': 'r-001', 'mode': 'sync'}, {'copied': 20, 'deleted': 15, 'skipped': 0, 'renamed': 0})
    ]
    
    result = dry_run_analyzer.analyze_dry_run_results(rules_stats)
    
    assert result.is_safe
    assert not result.has_warnings  # Delete ratio is acceptable


def test_analyzer_accepts_a_real_run_move_rule_stats_dict(tmp_path, monkeypatch):
    """operations.py's new stats dict carries `files`/`folders`/etc. on top of
    the keys the analyzer reads via `.get(...)` - a superset, not a rewrite.
    Feed a real `run_move_rule` result through unmodified and confirm the
    analyzer neither raises nor misreads it as unsafe."""
    FakePhone({"Internal storage/DCIM/a.jpg": b"hello"}).install(monkeypatch)
    rule = {"id": "r-0001", "mode": "move", "phone_path": "/DCIM",
            "desktop_path": str(tmp_path / "dest")}

    stats = operations.run_move_rule(rule, {"activation_uri": "mtp://dev/"})
    result = dry_run_analyzer.analyze_dry_run_results([(rule, stats)])

    assert result.is_safe
    assert not result.has_warnings


def test_analyzer_accepts_dry_run_nested_move_stats(tmp_path, monkeypatch):
    """A nested move's folder cleanup must not count toward `deleted` as a
    file deletion - the analyzer's move-safety check compares `deleted`
    against `copied` file-for-file, and a removed folder is not a file."""
    FakePhone({"Internal storage/DCIM/sub/a.jpg": b"hello"}).install(monkeypatch)
    monkeypatch.setattr(gio_utils, "DRY_RUN", True)
    rule = {"id": "r-0001", "mode": "move", "phone_path": "/DCIM",
            "desktop_path": str(tmp_path / "dest")}

    stats = operations.run_move_rule(rule, {"activation_uri": "mtp://dev/"})
    result = dry_run_analyzer.analyze_dry_run_results([(rule, stats)])

    assert result.is_safe
    assert not result.has_warnings


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
