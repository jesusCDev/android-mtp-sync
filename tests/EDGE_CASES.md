# Edge Case Testing Documentation

## Overview

This document describes comprehensive edge case tests for the Phone Migration Tool, covering scenarios that could cause data loss, corruption, or unexpected behavior. All edge cases are tested in `tests/test_edge_cases.py`.

---

## 1. COPY/MOVE OPERATIONS

### 1.1 Rename Handling (Duplicates)

**Scenario**: Multiple files with the same name in different directories are copied to same desktop location.

**Test**: `test_copy_rename_handling()`

**What we're testing**:
- File 1: `root/video.mp4` → Desktop: `video.mp4`
- File 2: `root/subdir1/video.mp4` → Desktop: `video (1).mp4`
- File 3: `root/subdir2/video.mp4` → Desktop: `video (2).mp4`

**Expected behavior**:
- Each file gets a unique name using `(N)` suffix pattern
- No files overwrite each other
- All 3 files are present on desktop with unique names

**Why this matters**:
- Prevents silent data loss if files conflict
- Shows that duplicate detection works across directories

---

### 1.2 File Verification Before Deletion (Move Operation)

**Scenario**: Move operation must verify copy succeeded before deleting from phone.

**Test**: `test_move_file_verification()`

**What we're testing**:
1. Start with N files on phone
2. Run move operation (copy then delete)
3. Count files on desktop (should equal N)
4. Count files on phone (should equal 0)

**Expected behavior**:
- All files copied to desktop
- All files deleted from phone
- Counts match exactly (pre-move count = desktop count, phone count = 0)

**Safety guarantee**:
- If copy fails for any file, that file is NOT deleted from phone
- Move operation code verifies destination file exists AND has size > 0 before marking for deletion
- Files only added to `files_to_delete` list AFTER successful copy

---

## 2. SYNC OPERATIONS (Desktop → Phone mirror)

Sync is designed to make phone match desktop (desktop is source of truth).

### 2.1 Unchanged Files (Re-run with no changes)

**Scenario**: Sync same files twice without any changes.

**Test**: `test_sync_unchanged_files()`

**What we're testing**:
1. First sync: Copy 3 files from desktop to phone
   - Stats: copied=3
2. Second sync: Same files, unchanged
   - Stats: skipped=3, copied=0

**Expected behavior**:
- Smart sync detects files by comparing size (like rsync)
- If file exists on phone with same size, it's skipped
- No unnecessary copying

**Why this matters**:
- Saves bandwidth and time on repeated syncs
- Ensures sync is idempotent (safe to run multiple times)

---

### 2.2 Deleted File Detection

**Scenario**: File deleted from desktop, sync should remove it from phone.

**Test**: `test_sync_deleted_file()`

**What we're testing**:
1. First sync: 3 files copied to phone
2. Delete 1 file from desktop
3. Second sync: Should detect deletion and remove from phone
   - Phone should have 2 files remaining
   - Stats: deleted=1

**Expected behavior**:
- Sync tracks which files should exist (based on desktop state)
- Files on phone NOT on desktop are deleted
- Result: phone mirrors desktop exactly

**Why this matters**:
- Prevents accumulation of old files
- Ensures phone storage doesn't bloat with obsolete files

---

### 2.3 Deleted Folder Detection

**Scenario**: Entire folder deleted from desktop, sync should remove it from phone.

**Test**: `test_sync_deleted_folder()`

**What we're testing**:
1. First sync: Creates `subfolder/` with files on phone
2. Delete entire `subfolder/` from desktop
3. Second sync: Should detect and remove folder
   - Stats: deleted > 0
   - Folder no longer exists on phone

**Expected behavior**:
- Sync recursively cleans up empty directories
- Folder and all contents removed from phone
- Phone storage cleaned up

**Why this matters**:
- Prevents orphaned folders on phone
- Keeps phone organized and clean

---

## 3. BACKUP OPERATIONS (Resumable copy)

Backup is designed to be resumable - can pick up where it left off.

### 3.1 Resume After Interruption

**Scenario**: Backup interrupted (Ctrl+C), restarted later. Should resume, not restart.

**Test**: `test_backup_resume_after_interrupt()`

**What we're testing**:
1. Start backup of 17 files
2. Interrupt partway through (state saved)
3. Resume backup
4. All files eventually copied

**Expected behavior**:
- First run: Copies some files, state saved for each
  - Stats: copied=N, resumed=0
- Resume run: Skips already-copied files, copies remainder
  - Stats: copied=M, resumed=N (total = N+M = 17)
- No files copied twice

**How it works**:
- State stored in `~/.local/share/phone-migration/state.json`
- Each successfully copied file path stored in `copied` set
- On resume, only files NOT in `copied` set are copied
- Once all files copied, state cleared

**Why this matters**:
- Handles network interruptions gracefully
- Saves bandwidth by not re-copying files
- Can split large backups across multiple sessions

**Verification**:
- Check that `state.mark_file_copied()` is called after successful copy
- Check that `state.mark_rule_complete()` clears state when done
- Check that state survives restart (persisted to JSON)

---

### 3.2 Changed Files Behavior

**Scenario**: Files on phone change during backup (new files added). Backup should detect and copy them.

**Test**: `test_backup_changed_files()`

**What we're testing**:
1. First backup: Copy 1 file
   - Desktop: 1 file (backup_file.mp4)
2. Add new file to phone
3. Resume backup: Should detect new file and copy it
   - Desktop: Now 2 files (backup_file.mp4, new_backup_file.mp4)
   - Stats: copied=1 (new file), resumed=1 (original)

**Expected behavior**:
- Backup rebuilds file list each time
- New files detected by comparing current file list vs already_copied
- New files added to copy list
- State updated with new file entries

**Why this matters**:
- Backup is robust to phone changes mid-process
- Doesn't miss files that appear during backup

---

## 4. HIDDEN FILES HANDLING

### 4.1 Hidden Files (dotfiles)

**Scenario**: How are dotfiles (`.hidden`, `.config`, etc.) handled?

**Test**: `test_hidden_files_handling()`

**What we're testing**:
1. Push regular file to phone: `visible.mp4`
2. Create hidden file on desktop: `.hidden_video.mp4`
3. Run copy operation
4. Check what appears on desktop

**Expected behavior**:
- Regular files copied normally
- Hidden files on desktop are left alone (not copied over)
- If hidden files are on phone, they may or may not be copied (MTP/GIO dependent)

**Current implementation**:
- All files (including hidden) are copied by GIO
- No special filtering for dotfiles
- Hidden files are treated like any other file

**Why this matters**:
- Prevents accidental loss of config files
- Documents expected behavior for edge case

---

## 5. MISCELLANEOUS EDGE CASES

### 5.1 Empty Directory Handling

**Scenario**: Nested empty directories (no files). Should they be preserved?

**Test**: `test_empty_directory_handling()`

**What we're testing**:
1. Create nested structure with NO files:
   - `test_path/empty1/empty2/empty3/` (all empty)
2. Run copy operation
3. Verify all directories created on desktop

**Expected behavior**:
- All directories created on desktop
- Directory structure preserved even with no files
- Can restore empty folder hierarchies

**Why this matters**:
- Preserves directory structure
- Some workflows need specific folder layouts
- Shows operation handles empty dirs correctly

---

### 5.2 Long Filenames

**Scenario**: Very long filenames (104+ characters). Are they preserved?

**Test**: `test_large_filename_handling()`

**What we're testing**:
1. Create file with 104-character name: `aaaa...aaaa.mp4`
2. Copy to phone
3. Copy back to desktop
4. Verify name preserved

**Expected behavior**:
- Long filename handled correctly
- No truncation
- File copied with full name

**Limits**:
- Most filesystems support 255-character filenames
- MTP protocol has different limits depending on device
- Some Android devices limit to 255 UTF-8 bytes

**Why this matters**:
- Ensures filename data isn't lost
- Shows system handles unusual filenames

---

## 6. COMPLETE EDGE CASE MATRIX

| Operation | Edge Case | Test Name | Category |
|-----------|-----------|-----------|----------|
| Copy | Duplicate filenames | `test_copy_rename_handling` | Rename |
| Copy | Verify files copied | `test_copy_rename_handling` | Verification |
| Copy | Empty directories | `test_empty_directory_handling` | Structure |
| Copy | Long filenames | `test_large_filename_handling` | Filename |
| Copy | Hidden files | `test_hidden_files_handling` | Hidden |
| Move | Verify copy before delete | `test_move_file_verification` | Safety |
| Move | Correct file count post-move | `test_move_file_verification` | Verification |
| Sync | Skip unchanged files | `test_sync_unchanged_files` | Idempotence |
| Sync | Delete removed files | `test_sync_deleted_file` | Cleanup |
| Sync | Delete removed folders | `test_sync_deleted_folder` | Cleanup |
| Backup | Resume after interrupt | `test_backup_resume_after_interrupt` | Resumption |
| Backup | Handle new files | `test_backup_changed_files` | Robustness |

---

## 7. POTENTIAL EDGE CASES NOT YET TESTED

These are identified edge cases that could be tested in future iterations:

### 7.1 File Permissions
- What happens with read-only files?
- Are permissions preserved?
- How does MTP handle permission-denied scenarios?

### 7.2 Symlinks
- Are symlinks followed or preserved?
- Can MTP even handle symlinks?
- Desktop symlinks referencing phone files?

### 7.3 Special Characters in Filenames
- Unicode characters (emoji, CJK, etc.)
- Filesystem-special chars (/, \, :, *, ?, ", etc.)
- Case sensitivity differences

### 7.4 Large Files
- Files > 1GB
- Network timeout during large file copy
- Resume of large file (partial transfer)

### 7.5 Concurrent Operations
- Multiple sync rules at same time
- User manually modifying phone while sync running
- Backup interrupted mid-file

### 7.6 Disk Space
- Destination disk full during copy
- Source disk full (phone storage exhausted)
- Partial file write on disk full

### 7.7 Device Disconnection
- Phone disconnected mid-operation
- Connection loss during copy
- Automatic reconnection handling

### 7.8 State File Corruption
- Corrupted JSON in state.json
- Concurrent writes to state file
- State file permissions issues

### 7.9 Rapid Operations
- Re-running operations in quick succession
- Queue multiple rules simultaneously
- Very fast file changes (faster than scan frequency)

### 7.10 Complex Scenarios
- File moved from one folder to another on phone
- File renamed on phone
- Directory moved/renamed while sync in progress
- Nested move operations (move from A→B while B→C running)

---

## 8. TEST EXECUTION

### Running Edge Case Tests

```bash
# Run all edge cases
python tests/test_edge_cases.py

# Or use pytest
pytest tests/test_edge_cases.py -v
```

### Expected Output

```
======================================================================
EDGE CASE TEST SUITE
======================================================================

✓ Device connected

----------------------------------------------------------------------
TEST: COPY - Rename Handling (Duplicates)
----------------------------------------------------------------------

✓ Files correctly renamed: ['video.mp4', 'video (1).mp4', 'video (2).mp4']
✅ COPY RENAME TEST PASSED

... (more tests) ...

======================================================================
EDGE CASE TEST SUMMARY
======================================================================

Total: 10 | ✅ Passed: 10 | ❌ Failed: 0
```

---

## 9. SAFETY GUARANTEES

### Copy Operation
✅ No data is deleted  
✅ Files are verified on destination before counting  
✅ Duplicates are renamed, not overwritten  
✅ Empty directories preserved  

### Move Operation
✅ Files copied BEFORE deletion  
✅ Copy verified (size > 0) BEFORE marking for deletion  
✅ If copy fails, file is NOT deleted  
✅ All files must match in count before operation succeeds  

### Sync Operation
✅ Phone mirrors desktop exactly  
✅ Files removed from desktop are removed from phone  
✅ Unchanged files are skipped (safe to re-run)  
✅ Empty directories cleaned up  

### Backup Operation
✅ Resumable - safe to interrupt with Ctrl+C  
✅ State persisted to disk  
✅ Can be resumed later without re-copying  
✅ New files detected and copied on resume  
✅ Files backed up atomically (verified before marking complete)

---

## 10. DEBUGGING EDGE CASES

### Check State File
```bash
cat ~/.local/share/phone-migration/state.json | jq .
```

### Verbose Mode
```bash
python tests/test_edge_cases.py --verbose
```

### Check Test Artifacts
- Phone: `Internal storage/test-android-mtp-edge/`
- Desktop: `~/.local/share/phone_migration_edge_tests/`

### Manual Inspection
```bash
# List test folders on phone
gio list mtp://.../ | grep test-android-mtp-edge

# List desktop test folder
ls -la ~/.local/share/phone_migration_edge_tests/
```

---

## 11. SUMMARY

The edge case test suite provides comprehensive coverage of:
- **10 major edge case scenarios**
- **Copy, Move, Sync, Backup operations**
- **File verification and safety checks**
- **Resume and interruption handling**
- **Hidden files and special filenames**
- **Directory structure preservation**

All tests use **isolated test directories** (never touching user data) and include **automatic cleanup**.
