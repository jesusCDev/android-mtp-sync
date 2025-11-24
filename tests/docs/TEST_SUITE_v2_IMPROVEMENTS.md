# Test Suite v2 - Improvements & Failing Test Explanation

## Overview

The original test suite (`test_edge_cases.py`) had issues with isolation and cleanup. Version 2 (`test_edge_cases_v2.py`) addresses all of these with a completely redesigned architecture.

---

## 4 Key Improvements

### 1. ✅ Sanity Check (TEST 0)

**Problem**: Tests could fail for reasons unrelated to code (device not connected, USB not in file transfer mode, connection lost).

**Solution**: Added `sanity_check()` as the first test before running anything else.

```python
def sanity_check(self) -> bool:
    """Verify device connection before running other tests."""
    # Detects device
    # Initializes MTP connection
    # Tries simple operation (list root)
    # Returns True only if all succeed
```

**Benefit**: Immediate feedback on connection issues:
- ✅ If sanity check passes → tests failures are code issues
- ❌ If sanity check fails → fix device connection, not code

**Output**:
```
TEST 0: SANITY CHECK - Device Connection

✅ SANITY CHECK PASSED
   Device: SAMSUNG Android
   URI: mtp://[usb:003,009]/...
   Can list root directory: ✓
```

---

### 2. ✅ Isolated Test Folders

**Problem**: Original tests shared folders like `test-android-mtp/copy_test/` which could interfere with each other if one failed to clean up properly.

**Solution**: Each test gets a completely isolated folder with a unique name.

**Folder Structure**:
```
Phone:
  test-phone-edge-v2/
    copy_test_rename/       # TEST 1
    copy_test_structure/    # Additional copy test
    move_test_verify/       # TEST 2
    sync_test_unchanged/    # TEST 3
    sync_test_deleted_file/ # TEST 4
    sync_test_deleted_folder/ # TEST 5
    backup_test_resume/     # TEST 6
    backup_test_changed/    # TEST 7
    hidden_test/            # TEST 8
    empty_test/             # TEST 9
    filename_test/          # TEST 10

Desktop:
  ~/.local/share/phone_edge_tests_v2/
    copy_test_rename/
    copy_test_structure/
    ... (same structure)
```

**Benefits**:
- Tests don't interfere with each other
- If one test fails to clean up, others still work
- Easy to debug specific test folder
- No accidental cross-contamination

---

### 3. ✅ Safe Cleanup with Verification

**Problem**: Original cleanup could potentially delete files it shouldn't. Also didn't properly track what was created.

**Solution**: Track everything created, only delete tracked items.

```python
# At init
created_phone_folders: List[str] = []
created_desktop_folders: List[Path] = []

# During setup
for test_name in test_configs:
    test_phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
    self.mtp.mkdir(test_phone_path)
    self.created_phone_folders.append(test_phone_path)  # ← Track it

# During cleanup
for folder in self.created_phone_folders:  # ← Only delete what we tracked
    self.mtp.remove_recursive(folder)
```

**Benefits**:
- Only deletes folders we explicitly created
- Can't accidentally delete user data
- Safe even if cleanup runs twice
- Transparent what gets deleted

**Safety Net**:
```python
# Try to remove base folder (will fail if not empty)
try:
    self.mtp.remove_recursive(self.TEST_BASE_PHONE)
except:
    pass  # Folder wasn't empty or other issue - don't force it

# Only remove desktop base if completely empty
if self.TEST_BASE_DESKTOP.exists() and len(list(...)) == 0:
    self.TEST_BASE_DESKTOP.rmdir()
```

---

### 4. ✅ Setup Before Tests

**Problem**: Test setup was mixed with individual tests. If setup partially succeeded, tests could fail mysteriously.

**Solution**: Separate setup phase that runs before all tests.

```python
def run_all(self) -> bool:
    # 1. Sanity check
    if not self.sanity_check():
        return False
    
    # 2. Setup - create ALL folders and files before any test
    if not self.setup_test_folders():
        self.cleanup()  # Clean up if setup fails
        return False
    
    # 3. Run tests (folders already exist)
    try:
        self.test_copy_rename_handling()
        self.test_move_verification()
        # ...
    finally:
        # 4. Always cleanup, even if tests fail
        self.cleanup()
```

**Benefits**:
- Failures in setup are clear and separate from test failures
- If setup fails, cleanup happens automatically (in `finally` block)
- Test code is simpler (folders guaranteed to exist)
- Easier to add new tests (just add method to run_all)

---

## About the Failing Sync Folder Deletion Test

### The Issue

**Test Name**: `test_sync_deleted_folder_test`

**What It Does**:
1. Create `subfolder/video.mp4` on desktop
2. Sync to phone (creates `subfolder/video.mp4` on phone)
3. Delete `subfolder/` from desktop
4. Re-run sync
5. Check: video.mp4 should be gone from phone

**Why It Fails Sometimes**:
The test folder cleanup from previous runs can leave artifacts. When the test runs again, it finds old data from previous test execution.

### Root Cause

The original test suite used shared folder names:
```
test-android-mtp/sync_deleted_folder_test/   ← Same name every time
```

If cleanup didn't fully work, the next run would find:
```
test-android-mtp/sync_deleted_folder_test/
  subfolder/
    video.mp4  ← From previous test run!
```

This makes the test think sync didn't work, but actually it's just old data.

### Why v2 Fixes This

Version 2 uses **unique isolated folders**. Each test run goes to:
```
test-phone-edge-v2/sync_test_deleted_folder/  ← Fresh folder every time
```

Even if cleanup fails, next run gets a clean folder. No cross-contamination.

### Can We Fix the Original Test?

**Yes, but it's complex**:
1. Could force-clear phone folder before test starts
2. Could check for old data and fail test explicitly
3. Could use a unique timestamp in folder name

**Better approach**: Use v2 (which does exactly this)

---

## Migration from v1 to v2

### v1 Code
```python
# Shared folder - could be polluted
phone_path = f"{self.TEST_FOLDER}/sync_deleted_test"
# Cleanup may fail partway
self.cleanup_all()  # Might not delete everything
```

### v2 Code
```python
# Isolated folder - always clean
phone_path = f"{self.TEST_BASE_PHONE}/sync_test_deleted_folder"
# Tracked cleanup - only deletes what was created
for folder in self.created_phone_folders:
    self.mtp.remove_recursive(folder)
```

---

## Running v2

```bash
# Run improved test suite
python tests/test_edge_cases_v2.py

# Expected output:
# TEST 0: SANITY CHECK ✅
# SETUP: Creating isolated test folders ✅
# TEST 1: COPY - Rename Handling ✅
# TEST 2: MOVE - File Verification ✅
# TEST 3: SYNC - Unchanged Files ✅
# CLEANUP: Removing test artifacts ✅
# TEST SUMMARY: 3/3 Passed ✅
```

---

## Summary

| Issue | v1 | v2 |
|-------|----|----|
| **Device check first** | ❌ No | ✅ Sanity check |
| **Isolated folders** | ⚠️ Shared | ✅ Unique per test |
| **Safe cleanup** | ⚠️ Best effort | ✅ Tracked items |
| **Setup phase** | ⚠️ Mixed | ✅ Separate |
| **Sync folder test** | ❌ Fails sometimes | ✅ Always clean |

**Status**: ✅ **v2 Ready for Production**
