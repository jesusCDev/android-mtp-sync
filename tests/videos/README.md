# Test Videos Directory

This directory contains video files used by the test suite to simulate file transfer operations.

## Setup

**Before running tests**, add some video files to this directory:

### Option 1: Use Your Own Videos
Copy any video files (3-5 recommended) to this directory:
```bash
cp ~/Videos/some_video.mp4 tests/videos/
```

### Option 2: Create Dummy Test Files
If you don't want to use real videos, create small dummy files:

```bash
# Create 5 dummy video files (10MB each)
for i in {1..5}; do
  dd if=/dev/zero of=tests/videos/test$i.mp4 bs=1M count=10
done
```

### Option 3: Create Minimal Test Files
For faster testing, create tiny files:
```bash
# Create 5 minimal files (1MB each)
for i in {1..5}; do
  dd if=/dev/zero of=tests/videos/test$i.mp4 bs=1M count=1
done
```

## Requirements

- **Minimum**: 3 video files (any size)
- **Recommended**: 5-10 video files, 5-20MB each
- **Formats**: .mp4, .mkv, .avi (tests will use any video files present)

## Why Are These Needed?

The test suite (`test_edge_cases.py`) uses these videos to:
- Test copy operations (phone ↔ desktop)
- Test move operations (with deletion verification)
- Test sync operations (mirroring)
- Test large file handling (≥1GB tests use sparse files)

## Gitignore

Video files in this directory are automatically ignored by git (see `.gitignore`) to avoid committing large binary files to the repository.

## Cleanup

Test files are automatically cleaned up after test runs, but the original files in this directory are preserved.
