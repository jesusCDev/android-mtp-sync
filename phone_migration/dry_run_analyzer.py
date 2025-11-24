"""
Dry-Run Analysis Module

Validates dry-run operation results to detect anomalies and safety violations
before actual execution.
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


# Analysis thresholds
THRESHOLDS = {
    "large_delete_count": 100,
    "mass_delete_threshold": 1000,
    "mass_delete_min_copied": 100,
    "sync_delete_ratio_warning": 5,  # Warn if deleting 5x more than copying
    "sync_large_delete": 500,
    "size_mismatch_threshold": 0.2,  # 20% difference
}


@dataclass
class Issue:
    """Represents an analysis issue."""
    severity: str  # 'blocker', 'warning', 'info'
    rule_id: str
    mode: str
    message: str


class AnalysisResult:
    """Results of dry-run analysis."""
    
    def __init__(self):
        self.blockers: List[Issue] = []
        self.warnings: List[Issue] = []
        self.info: List[Issue] = []
    
    def add_blocker(self, rule_id: str, mode: str, message: str):
        self.blockers.append(Issue('blocker', rule_id, mode, message))
    
    def add_warning(self, rule_id: str, mode: str, message: str):
        self.warnings.append(Issue('warning', rule_id, mode, message))
    
    def add_info(self, rule_id: str, mode: str, message: str):
        self.info.append(Issue('info', rule_id, mode, message))
    
    @property
    def is_safe(self) -> bool:
        """Returns True if no blockers found."""
        return len(self.blockers) == 0
    
    @property
    def has_warnings(self) -> bool:
        """Returns True if warnings found."""
        return len(self.warnings) > 0


def analyze_dry_run_results(rules_stats: List[Tuple[Dict[str, Any], Dict[str, int]]]) -> AnalysisResult:
    """
    Analyze dry-run results for all rules.
    
    Args:
        rules_stats: List of (rule, stats) tuples where:
            - rule: Rule dictionary with 'id', 'mode', etc.
            - stats: Statistics dictionary with 'copied', 'deleted', 'skipped', etc.
    
    Returns:
        AnalysisResult with blockers, warnings, and info messages
    """
    result = AnalysisResult()
    
    for rule, stats in rules_stats:
        rule_id = rule.get('id', 'unknown')
        mode = rule.get('mode', 'unknown')
        
        # Run all checks
        _check_copy_safety(rule_id, mode, stats, result)
        _check_move_safety(rule_id, mode, stats, result)
        _check_backup_safety(rule_id, mode, stats, result)
        _check_sync_patterns(rule_id, mode, stats, result)
        _check_large_operations(rule_id, mode, stats, result)
        _check_zero_operations(rule_id, mode, stats, result)
    
    return result


def _check_copy_safety(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Copy operations should NEVER delete anything."""
    if mode != 'copy':
        return
    
    if stats.get('deleted', 0) > 0:
        result.add_blocker(
            rule_id, mode,
            f"SAFETY VIOLATION: Copy mode deleted {stats['deleted']} files (should delete nothing)"
        )


def _check_move_safety(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Move operations: deleted must equal copied."""
    if mode != 'move':
        return
    
    copied = stats.get('copied', 0)
    deleted = stats.get('deleted', 0)
    skipped = stats.get('skipped', 0)
    
    # Expected: only delete files that were successfully copied
    expected_deleted = copied
    
    if deleted != expected_deleted:
        if skipped > 0:
            # Explain the mismatch
            result.add_blocker(
                rule_id, mode,
                f"SAFETY VIOLATION: Move copied {copied} files but deleted {deleted} "
                f"(expected {expected_deleted}). {skipped} files were skipped but should remain on phone."
            )
        else:
            result.add_blocker(
                rule_id, mode,
                f"SAFETY VIOLATION: Move copied {copied} files but deleted {deleted} "
                f"(must match exactly!)"
            )


def _check_backup_safety(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Backup operations should NEVER delete anything."""
    if mode not in ['backup', 'smart_copy']:
        return
    
    if stats.get('deleted', 0) > 0:
        result.add_blocker(
            rule_id, mode,
            f"SAFETY VIOLATION: Backup mode deleted {stats['deleted']} files (should delete nothing)"
        )


def _check_sync_patterns(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Sync operations: check for extreme imbalances."""
    if mode != 'sync':
        return
    
    copied = stats.get('copied', 0)
    deleted = stats.get('deleted', 0)
    
    # Warn if deleting way more than copying (might indicate wrong source path)
    if deleted > copied * THRESHOLDS['sync_delete_ratio_warning'] and copied < 10:
        result.add_warning(
            rule_id, mode,
            f"Sync will delete {deleted} files from phone but only copy {copied} new files. "
            f"Verify desktop source path is correct and files haven't been accidentally moved."
        )
    
    # Warn on very large deletions
    if deleted > THRESHOLDS['sync_large_delete']:
        result.add_warning(
            rule_id, mode,
            f"Large sync deletion: {deleted} files will be removed from phone. "
            f"Ensure this is expected."
        )


def _check_large_operations(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Check for unusually large operations."""
    deleted = stats.get('deleted', 0)
    copied = stats.get('copied', 0)
    
    # Mass deletion with minimal copying
    if deleted > THRESHOLDS['mass_delete_threshold'] and copied < THRESHOLDS['mass_delete_min_copied']:
        result.add_warning(
            rule_id, mode,
            f"Mass deletion detected: {deleted} files will be deleted but only {copied} copied. "
            f"Please review carefully."
        )
    
    # General large deletion warning
    if deleted > THRESHOLDS['large_delete_count'] and mode != 'sync':
        result.add_warning(
            rule_id, mode,
            f"Large deletion: {deleted} files will be removed from phone."
        )


def _check_zero_operations(rule_id: str, mode: str, stats: Dict[str, int], result: AnalysisResult):
    """Check for operations that would do nothing."""
    copied = stats.get('copied', 0)
    deleted = stats.get('deleted', 0)
    skipped = stats.get('skipped', 0)
    renamed = stats.get('renamed', 0)
    
    # Nothing to do
    if copied == 0 and deleted == 0 and renamed == 0:
        if skipped > 0:
            result.add_info(
                rule_id, mode,
                f"No changes needed: all {skipped} files already exist on destination."
            )
        else:
            result.add_info(
                rule_id, mode,
                "No changes needed: source is empty or already synchronized."
            )


def format_analysis_results(result: AnalysisResult) -> str:
    """
    Format analysis results as colored terminal output.
    
    Returns:
        Formatted string ready for print()
    """
    from .operations import Colors
    
    output = []
    
    if result.blockers:
        output.append(f"\n{Colors.RED}{Colors.BOLD}❌ BLOCKERS FOUND - Operation will be aborted:{Colors.RESET}")
        for issue in result.blockers:
            output.append(f"  {Colors.RED}[{issue.rule_id}] {issue.message}{Colors.RESET}")
    
    if result.warnings:
        output.append(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  WARNINGS:{Colors.RESET}")
        for issue in result.warnings:
            output.append(f"  {Colors.YELLOW}[{issue.rule_id}] {issue.message}{Colors.RESET}")
    
    if result.info:
        output.append(f"\n{Colors.CYAN}{Colors.BOLD}ℹ️  INFO:{Colors.RESET}")
        for issue in result.info:
            output.append(f"  {Colors.CYAN}[{issue.rule_id}] {issue.message}{Colors.RESET}")
    
    return "\n".join(output)
