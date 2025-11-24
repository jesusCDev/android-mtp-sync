# Phone Migration Tool - Test Suite

Comprehensive end-to-end testing framework for all migration operations.

## Quick Start

```bash
# Run all tests
python3 tests/test_e2e_operations.py

# The test suite will:
# 1. Detect your connected Android phone
# 2. Create test-android-mtp folder on phone
# 3. Populate with test files and edge cases
# 4. Run all 4 operation tests (copy, move, sync, backup)
# 5. Verify results match expected behavior
# 6. Cleanup test folder from phone
# 7. Print summary report
```

## Test Structure

### On Your Phone: `test-android-mtp/`

```
test-android-mtp/
├── copy_test/
│   ├── single_file.mp4
│   ├── nested/
│   │   ├── deep/
│   │   │   └── file_in_nested_deep.mp4
│   │   └── file_in_nested.mp4
│   └── empty_folder/
├── move_test/
│   ├── single_file.mp4
│   ├── nested/
│   │   ├── deep/
│   │   │   └── file_in_nested_deep.mp4
│   │   └── file_in_nested.mp4
│   └── empty_folder/
├── sync_test/
│   ├── single_file.mp4
│   ├── nested/
│   │   ├── deep/
│   │   │   └── file_in_nested_deep.mp4
│   │   └── file_in_nested.mp4
└── backup_test/
    ├── single_file.mp4
    ├── nested/
    │   ├── deep/
    │   │   └── file_in_nested_deep.mp4
    │   └── file_in_nested.mp4
    └── empty_folder/
```

### On Desktop: `~/.local/share/phone_migration_tests/`

Test output directories created during testing:
- `copy_output/` - Results of copy test
- `move_output/` - Results of move test
- `sync_source/` - Source files for sync test
- `backup_output/` - Results of backup test

## Test Cases

### 1. COPY Operation
**Expected Behavior:** Files copied to desktop, NOT deleted from phone

- Source: `test-android-mtp/copy_test/`
- Destination: `~/.local/share/phone_migration_tests/copy_output/`
- Verification:
  - Files exist on desktop ✓
  - Files still exist on phone ✓
  - File counts match ✓

**Edge Cases Tested:**
- Single file at root
- Nested folders (1 level deep)
- Deep folders (2+ levels deep)
- Empty directories

### 2. MOVE Operation
**Expected Behavior:** Files copied to desktop, DELETED from phone

- Source: `test-android-mtp/move_test/`
- Destination: `~/.local/share/phone_migration_tests/move_output/`
- Verification:
  - Files exist on desktop ✓
  - Files NOT on phone (empty folder) ✓
  - File counts match source → desktop ✓

### 3. SYNC Operation
**Expected Behavior:** Desktop files mirrored to phone

- Source: `~/.local/share/phone_migration_tests/sync_source/` (desktop)
- Destination: `test-android-mtp/sync_test/` (phone)
- Verification:
  - Files exist on phone ✓
  - File counts match ✓
  - Sync maintains structure ✓

### 4. BACKUP Operation
**Expected Behavior:** Files backed up from phone to desktop (resumable, no deletion)

- Source: `test-android-mtp/backup_test/`
- Destination: `~/.local/share/phone_migration_tests/backup_output/`
- Verification:
  - Files exist on desktop ✓
  - Files still exist on phone ✓
  - Supports resume on interruption ✓

## Requirements

### For Testing

1. **Connected Android Phone** via USB with MTP enabled
2. **File Transfer Mode** enabled on phone (not Charging mode)
3. **Phone Unlocked** during test execution
4. **Test Videos** in `tests/videos/` directory (included)

### Prerequisites

```bash
# Ensure phone_migration tool is installed
cd /home/average_l/Programming/projects/android-mtp-sync
pip install -e .

# Or run directly (no installation)
python3 tests/test_e2e_operations.py
```

## Test Output Example

```
======================================================================
PHONE MIGRATION - END-TO-END TEST SUITE
======================================================================

✓ Connected device: SAMSUNG Android
  Profile: S25-ultra
  URI: mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/

✓ Local test directory: /home/average_l/.local/share/phone_migration_tests

Setting up test folder structure on phone...

✓ Created test-android-mtp/
✓ Found 18 test videos

  copy_test/
    └── single_file/
    └── nested/deep/
    └── empty_folder/
      └── single_file.mp4
        └── file_in_nested.mp4
        └── file_in_nested_deep.mp4
  ...

----------------------------------------------------------------------
TEST 1: COPY OPERATION
----------------------------------------------------------------------
Expected: Files copied from phone to desktop, NOT deleted from phone

Source (phone): test-android-mtp/copy_test
Destination (desktop): /home/average_l/.local/share/phone_migration_tests/copy_output

Files to copy: 3

Running copy operation...

✓ Copied 3 files to desktop
✓ Files still on phone: 3

✅ COPY TEST PASSED
```

## Troubleshooting

### "No device connected"
- Ensure phone is connected via USB
- Check phone shows "File Transfer" mode in USB options
- Try: `gio mount -li | grep -i samsung`

### "Device activation URI not found"
- Device not yet registered in phone_migration config
- Run the web UI to register device first, or manually add to `~/.config/phone-migration/config.json`

### Test hangs on file copy
- Phone likely locked or in sleep mode
- Unlock phone and keep it active during tests
- Check USB connection is stable

### "Failed to create directory"
- Phone write permission issue
- Try running cleanup script first: `./cleanup_mtp_nuclear.sh`
- Check phone isn't connected to other file managers

## Advanced Usage

### Run Specific Test Only

Edit `test_e2e_operations.py` and comment out tests in `main()`:

```python
def main():
    suite = TestSuite()
    if not suite.setup():
        return 1
    if not suite.populate_test_structure():
        return 1
    
    # Uncomment only desired test:
    suite.test_copy_operation()
    # suite.test_move_operation()
    # suite.test_sync_operation()
    # suite.test_backup_operation()
    
    suite.cleanup()
    suite.print_summary()
    return 0 if suite.results["failed"] == 0 else 1
```

### Skip Cleanup

Comment out `suite.cleanup()` to inspect files after test:

```python
def main():
    # ... run tests ...
    # suite.cleanup()  # Skip cleanup to inspect results
    suite.print_summary()
    return 0
```

### Custom Test Videos

Replace files in `tests/videos/`:
```bash
# Add your own test files
cp your_videos/*.mp4 tests/videos/
```

The test suite will automatically use all `.mp4` files found.

## Test Helpers API

### MTPDevice Class

```python
from tests.helpers.mtp_testlib import MTPDevice

device = MTPDevice("mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/")

# Directory operations
device.mkdir("/path/to/dir")
device.list_dir("/path/to/dir")
device.remove("/path/to/item")

# File operations
device.push_file(Path("local.mp4"), "/phone/path/file.mp4")
device.push_file_recursive(Path("local_dir"), "/phone/dir")

# Query operations
device.path_exists("/phone/path")
device.get_file_info("/phone/path")

# Tree structure
tree = device.directory_tree("/phone/path")
```

### compare_trees Function

```python
from tests.helpers.mtp_testlib import compare_trees

tree1 = device.directory_tree("/path1")
tree2 = device.directory_tree("/path2")

differences = compare_trees(tree1, tree2)
for diff in differences:
    print(diff)
```

## Adding New Tests

1. Create new test method in `TestSuite` class:
```python
def test_custom_operation(self) -> bool:
    print("\nTEST X: CUSTOM OPERATION")
    # Your test logic
    self.results["passed"] += 1
    return True
```

2. Call from `main()`:
```python
suite.test_custom_operation()
```

3. Commit and document the test case

## Interpreting Results

| Result | Meaning |
|--------|---------|
| ✅ PASSED | Operation behaved as expected |
| ❌ FAILED | Operation did not match expected behavior |
| ⊘ SKIPPED | Test was not executed |
| 🎉 ALL TESTS PASSED | All tests successful, no regressions |

## Best Practices

1. **Run After Code Changes** - Execute test suite before committing
2. **Keep Phone Connected** - Don't disconnect phone during tests
3. **Monitor Phone** - Unlock and interact if needed (files being transferred)
4. **Check Logs** - Print output shows detailed operation progress
5. **Review Cleanup** - Verify test folders removed from phone after completion

## Performance Notes

- First run populates phone with test files (slower)
- Subsequent runs reuse same files (faster)
- Each operation averages 5-30 seconds depending on network/USB speed
- Total test suite typically completes in 2-5 minutes

## Contributing

Found a bug or have an improvement? Update the test suite:

1. Fix the issue in `phone_migration/`
2. Update relevant test in `tests/test_e2e_operations.py`
3. Verify all tests pass
4. Commit with clear message describing what was tested
