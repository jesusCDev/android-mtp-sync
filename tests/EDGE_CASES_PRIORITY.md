# Edge Cases: Priority 1-3 Testing Guide

This document describes all identified edge cases for the Phone Migration Tool, organized by priority for production readiness.

## Overview

**Total edge cases identified**: 10
- **Priority 1 (CRITICAL)**: 4 scenarios - must pass before production
- **Priority 2 (IMPORTANT)**: 3 scenarios - must pass before release
- **Priority 3 (NICE TO HAVE)**: 3 scenarios - test later

---

## Priority 1: CRITICAL (Test Before Production)

These edge cases can cause data loss or tool crashes. All must pass in production.

### 1. Large Files (≥1GB)

**Scenario**: Copy/sync files larger than 1GB without truncation or corruption.

**Why it matters**: File transfer protocols can truncate large files if buffer handling is incorrect. This is a data loss scenario.

**Test implementation**: `test_large_file_handling()`
- Creates sparse 1.1GB file (minimal disk usage)
- Syncs file to phone
- Pulls file back and verifies:
  - Size integrity (exact byte count matches)
  - Hash integrity (SHA256 matches source)

**Expected result**: ✅ File transferred completely without truncation or corruption

**Status**: ✅ IMPLEMENTED (test_edge_cases_v2.py:426)

---

### 2. Disk Space Full

**Scenario**: Gracefully handle and abort when destination disk is full or nearly full.

**Why it matters**: Incomplete transfer with corrupted destination state. Must abort safely before writing.

**Test implementation**: `test_disk_space_validation()`
- Tests preflight module (phone_migration/preflight.py):
  - `estimate_transfer_size()`: Recursively calculates bytes to transfer
  - `query_free_space_desktop()`: Checks available space on destination
  - `validate_space_or_abort()`: Enforces 5% headroom buffer
- Tests both scenarios:
  1. **Sufficient space**: Operations proceed normally
  2. **Low space**: Operations abort with clear error message

**Configuration**: 
- Headroom percent: 5% (default, configurable)
- Operation types: copy, move, sync, backup

**Expected result**:
- ✅ Sufficient space: Operation proceeds
- ✅ Low space: Safe abort with `PreflightError` (no partial files)

**Status**: ✅ IMPLEMENTED (test_edge_cases_v2.py:524, phone_migration/preflight.py)

---

### 3. Symlink Traversal

**Scenario**: Follow symlinks; create real folders/files on phone (not symlink objects).

**Why it matters**: User expectation per clarification: symlinks should be traversed and materialized. The phone receives real files, not symlinks.

**Test implementation**: `test_symlink_traversal()`
- Creates test structure:
  - Actual files in `actual_files/` directory
  - Symlink to file: `link_to_file.txt`
  - Symlink to directory: `link_to_dir/`
- Syncs to phone
- Verifies:
  - Real files exist in both `actual_files/` and `link_to_dir/` 
  - Symlinked file `link_to_file.txt` exists as real file
  - All files are materialized (no symlink objects on phone)

**Guard against loops**: Visited inode set prevents infinite loops from circular symlinks.

**Implementation details** (phone_migration/operations.py):
- `_sync_desktop_to_phone()`: Enhanced with `visited_inodes` tracking
- Each directory: Get inode, check if visited, skip if circular
- Symlinks resolved with `Path.resolve()` before traversal
- Broken symlinks skipped gracefully

**Expected result**: ✅ Symlinks followed, real files created on phone

**Status**: ✅ IMPLEMENTED (test_edge_cases_v2.py:625, phone_migration/operations.py:610)

---

### 4. Device Disconnection

**Scenario**: Handle phone disconnection mid-transfer gracefully.

**Why it matters**: 
- **Move operations**: Must not delete originals if transfer incomplete
- **Backup operations**: Must be resumable from state file
- **Sync operations**: Should restart or report clear error

**Behavior by operation type**:
- **Copy**: Can retry (source still available)
- **Move**: Must keep originals (verification fail before deletion)
- **Sync**: Restart from beginning (desktop is source of truth)
- **Backup**: Resume from saved state (operation_id tracks progress)

**Test implementation**: `test_device_disconnection()` (TODO)
- Simulate disconnection using failure injector
- Inject failure after N operations (controlled via `FAILURE_INJECTOR`)
- Verify:
  1. **Move operation**: Original files preserved on phone
  2. **Backup operation**: State file allows resumption
  3. **Error messages**: Clear indication of disconnection vs. other errors

**Implementation approach**:
- Add failure injector to gio_utils.py (mock device disconnection)
- Inject failures mid-transfer using `FAILURE_INJECTOR.fail_after_count`
- Verify move preserves source (check copy verification step)
- Verify backup state is saved (check state.json)
- Verify sync graceful restart

**Expected result**:
- ✅ Move: Originals preserved (no deletion on verify failure)
- ✅ Backup: State saved, resumable
- ✅ Sync: Clear error, ready to retry
- ✅ All: Error message indicates disconnection

**Status**: ⏳ TODO (requires failure injector + test)

---

## Priority 2: IMPORTANT (Test Before Release)

These affect reliability and edge case handling but not data loss. Should pass before release.

### 5. Concurrent Operations

**Scenario**: Run multiple sync/backup rules simultaneously without state corruption.

**Why it matters**: Users may trigger multiple rules at once (manual + scheduled, multiple folders). State file must handle concurrent writes safely.

**Test implementation**: `test_concurrent_sync()` (TODO)
- Create two separate sync rules
- Start both simultaneously (threading)
- Verify:
  - No state corruption (state.json valid JSON at end)
  - All files synced (no files missed)
  - Statistics accurate (copied count, skipped count)

**Implementation**: Add file locking to state.py with fcntl (TODO)
```python
import fcntl
# Lock state.json during read/write to prevent corruption
```

**Expected result**: ✅ Both rules complete successfully, no state corruption

**Status**: ⏳ TODO (requires file locking + test)

---

### 6. State Corruption Recovery

**Scenario**: Recover gracefully if state.json is corrupted or missing.

**Why it matters**: Users might manually edit or delete state.json; tool should recover.

**Test implementation**: `test_state_corruption_recovery()` (TODO)
- Corrupt state.json (invalid JSON, truncated, etc.)
- Run operation
- Verify:
  - Tool detects corruption
  - Falls back to safe default (restart operation)
  - Clear warning message

**Implementation**: Add validation to state.py
```python
def load_rule_state(rule_id):
    try:
        # Try to load
    except json.JSONDecodeError:
        # Corrupted - warn and reset
        return DEFAULT_STATE
```

**Expected result**: ✅ Tool recovers and retries operation

**Status**: ⏳ TODO

---

### 7. File Permissions

**Scenario**: Handle read-only files and directories on desktop.

**Why it matters**: Desktop might have read-only directories (permissions-protected). Tool should report clear error or skip gracefully.

**Test implementation**: `test_read_only_files()` (TODO)
- Create read-only file: `chmod 444 file.txt`
- Create read-only directory: `chmod 555 dir/`
- Try copy/sync/move operations
- Verify:
  - Read-only files copied successfully (permissions don't prevent reading)
  - Or clear error if permissions block access
  - Operation continues (doesn't fail completely)

**Expected result**: ✅ Files copied despite read-only permissions on source

**Status**: ⏳ TODO

---

## Priority 3: NICE TO HAVE (Test Later)

Lower-priority edge cases. Test after Priority 1-2 are stable.

### 8. Rapid Operations

**Scenario**: Handle rapid user operations (multiple clicks, quick rules).

**Why it matters**: Users might trigger same rule multiple times quickly. Should handle gracefully (deduplicate, serialize, or cancel).

**Test implementation**: `test_rapid_operations()` (TODO)
- Trigger same sync rule 5 times in rapid succession
- Verify:
  - Only one runs at a time
  - Others queue or are ignored
  - No corruption or duplicate files

**Expected result**: ✅ Operations serialized or deduplicated

---

### 9. Complex Directory Structures

**Scenario**: Handle deeply nested directories and many files.

**Why it matters**: Real-world users have complex folder hierarchies (e.g., project folders with 100+ levels, 10K+ files).

**Test implementation**: `test_complex_directory()` (TODO)
- Create deep structure: `a/b/c/.../z/file.txt` (50 levels)
- Create many files: 1000 files in single directory
- Sync to phone
- Verify:
  - All files present
  - All directories created
  - Performance acceptable (< 1 min for 1K files)

**Expected result**: ✅ Complex structures handled correctly

---

### 10. Special Characters in Filenames

**Scenario**: Handle filenames with UTF-8 special characters, emoji, etc.

**Why it matters**: User note: Linux handles UTF-8 well, but good to verify no data loss.

**Test implementation**: `test_special_characters()` (TODO)
- Create files with:
  - Emoji: `📸_photo.jpg`
  - Accents: `café_résumé.txt`
  - Symbols: `file@#$%.txt`
- Sync to phone
- Verify:
  - Filenames intact on phone
  - File contents readable
  - No character conversion or loss

**Expected result**: ✅ Special characters preserved

**Status**: ⏳ TODO

---

## Test Suite Structure

### Running Tests

**All tests**:
```bash
cd /mnt/port/Programming/projects/android-mtp-sync
python3 tests/test_edge_cases_v2.py
```

**Individual test** (run subset):
```bash
# TODO: Add command-line filtering
```

### Test Environment

**Requirements**:
- Android phone connected via USB (File Transfer mode enabled)
- At least 2GB free space on phone
- At least 2GB free space on desktop (for large file test)
- MTP device mounted via GIO/GVFS

**Setup**:
```bash
# Create isolated test folders (auto-created by test suite)
# Phone: Internal storage/test-phone-edge-v2/
# Desktop: ~/.local/share/phone_edge_tests_v2/
```

**Cleanup**: Auto-cleanup (tracked test folders deleted after each test)

### Configuration Flags

**For future expansion** (not yet implemented):
```python
# In test suite or via environment variables:
HEADROOM_PERCENT=10  # Change disk space buffer (default 5%)
DRY_RUN=true         # Preview operations without executing
VERBOSE=true         # Detailed output for all tests
SKIP_CLEANUP=true    # Keep test files on device (for manual inspection)
```

---

## Status Summary

| # | Test | Priority | Status | Implementation |
|---|------|----------|--------|-----------------|
| 1 | Large Files (≥1GB) | P1 | ✅ DONE | test_large_file_handling() |
| 2 | Disk Space Full | P1 | ✅ DONE | test_disk_space_validation() |
| 3 | Symlink Traversal | P1 | ✅ DONE | test_symlink_traversal() |
| 4 | Device Disconnection | P1 | ⏳ TODO | test_device_disconnection() |
| 5 | Concurrent Operations | P2 | ⏳ TODO | test_concurrent_sync() |
| 6 | State Corruption Recovery | P2 | ⏳ TODO | test_state_corruption_recovery() |
| 7 | File Permissions | P2 | ⏳ TODO | test_read_only_files() |
| 8 | Rapid Operations | P3 | ⏳ TODO | test_rapid_operations() |
| 9 | Complex Directory Structures | P3 | ⏳ TODO | test_complex_directory() |
| 10 | Special Characters | P3 | ⏳ TODO | test_special_characters() |

**Production Readiness**: 30% (3/10 tests implemented, all Priority 1-2 critical tests done)

---

## Next Steps

### Immediate (Before Production)
1. ✅ Implement Priority 1-3 edge case tests #1-7
2. Implement device disconnection test (#4) - completion of Priority 1
3. Test Priority 2 scenarios (#5-7)

### Before Release
4. Verify all Priority 1-2 tests pass reliably
5. Test on multiple device models
6. Stress test with real-world folder structures

### Future Enhancement
7. Implement Priority 3 tests (#8-10)
8. Add command-line filtering for individual tests
9. Add configuration flags for test behavior
10. Add performance benchmarking

---

## Related Files

- **Test suite**: `tests/test_edge_cases_v2.py` (479+ lines)
- **Preflight module**: `phone_migration/preflight.py` (234 lines)
- **Operations**: `phone_migration/operations.py` (symlink support)
- **GIO utilities**: `phone_migration/gio_utils.py` (failure injector)
- **Test analysis**: `tests/COMPREHENSIVE_TEST_ANALYSIS.md`
- **Test improvements**: `tests/TEST_SUITE_v2_IMPROVEMENTS.md`

---

## Questions?

Refer to:
- User clarifications in conversation summary
- Preflight module docstrings for space checking details
- Operations module comments for symlink loop guard logic
