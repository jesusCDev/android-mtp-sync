# Smart Copy Feature - Design Document

## Overview
Add a `--smart-copy` mode that tracks progress and can resume if interrupted. Perfect for large folders (thousands of files) that might fail mid-copy due to phone disconnect, timeout, or user interrupt.

## Problem Statement
Current `--copy` mode:
- ❌ If interrupted at file 500/1000, you start over from file 1
- ❌ No way to track which files were already copied
- ❌ Wastes time re-copying files that succeeded before

## Solution: Smart Copy with State Tracking
Resume from where you left off, skip already-copied files.

---

## How It Works

### 1. State File
**Location**: `~/.local/share/phone-migration/state.json`

**Schema**:
```json
{
  "r-0005": {
    "copied": ["IMG_0001.jpg", "IMG_0002.jpg", "subfolder/video.mp4"],
    "failed": [
      {"path": "IMG_0050.jpg", "error": "Connection timeout"}
    ],
    "status": "in_progress",
    "last_run": "2025-11-02T19:45:00",
    "total_files": 1000
  }
}
```

### 2. Copy Process

**First Run**:
1. Scan all files in source directory → 1000 files found
2. Load state → empty (no previous run)
3. Copy files one by one:
   - ✓ IMG_0001.jpg → mark as copied (save state)
   - ✓ IMG_0002.jpg → mark as copied (save state)
   - ✗ **[User presses Ctrl+C at file 150]**
4. State saved: 149 files marked as copied

**Resume (Second Run)**:
1. Scan all files → 1000 files found
2. Load state → 149 already copied
3. Show: "📦 Resuming: 149 files already copied, 851 remaining"
4. Skip files 1-149, start from file 150
5. Continue copying:
   - ✓ IMG_0150.jpg (150/1000 - 15%)
   - ✓ IMG_0151.jpg (151/1000 - 15%)
   - ... continue until done
6. On completion: Clear state, show success

---

## User Experience

### Creating Smart Copy Rule
```bash
# Add smart-copy rule (automatically resumable)
phone-sync --smart-copy -p default \
  -pp /DCIM/Camera \
  -dp ~/Backup/Camera_2025

# Mark as manual-only (for monthly backups)
phone-sync --smart-copy -p default \
  -pp /DCIM/Camera \
  -dp ~/Backup/Full --manual
```

### Running Smart Copy

**First run (interrupted)**:
```bash
$ phone-sync --run -r r-0005 -y

📦 Smart Copy: /DCIM/Camera → ~/Backup/Camera_2025

  Scanning source directory...
  Found: 1000 files (total: 15.2 GB)
  
  Progress: 150/1000 files (15%) - 2.3 GB copied
  ^C
  
  ⚠ Interrupted! Progress saved.
  📋 To resume: phone-sync --run -r r-0005 -y
```

**Second run (resumed)**:
```bash
$ phone-sync --run -r r-0005 -y

📦 Smart Copy: /DCIM/Camera → ~/Backup/Camera_2025

  ℹ️ Resuming from previous run
  ✓ Already copied: 150 files (2.3 GB)
  → Remaining: 850 files (12.9 GB)
  
  Progress: 151/1000 files (15%)
  Progress: 500/1000 files (50%)
  Progress: 1000/1000 files (100%)
  
  ✓ Smart copy complete! All 1000 files copied.
  🗑️ State cleared.
```

---

## Implementation Plan

### Phase 1: State Management ✅ DONE
- [x] Created `phone_migration/state.py`
- [x] Functions: load_state, save_state, mark_file_copied, mark_rule_complete
- [x] Atomic file writes

### Phase 2: Smart Copy Operation
- [ ] Add `run_smart_copy_rule()` to `operations.py`
- [ ] Scan all files recursively (build full file list)
- [ ] Load state, filter out already-copied files
- [ ] Copy remaining files one-by-one
- [ ] After each file: `mark_file_copied()` to save progress
- [ ] On completion: `mark_rule_complete()` to clear state
- [ ] Handle Ctrl+C gracefully (state already saved)

### Phase 3: CLI Integration
- [ ] Add `--smart-copy` command to `main.py`
- [ ] Add `add_smart_copy_rule()` to `config.py`
- [ ] Update `print_rules()` to show smart-copy mode with 📦 icon
- [ ] Update runner to handle smart_copy mode

### Phase 4: Progress Indicators
- [ ] Show "Resuming" message if state exists
- [ ] Show progress: "150/1000 (15%)"
- [ ] Show per-file progress in verbose mode
- [ ] Show failed files at end

### Phase 5: Edge Cases
- [ ] Handle files deleted from source since last run
- [ ] Handle files added to source since last run
- [ ] Handle destination file manually deleted → re-copy
- [ ] Verify file size after copy before marking as copied

---

## Key Differences vs Regular Copy

| Feature | Regular Copy | Smart Copy |
|---------|-------------|------------|
| Resume | ❌ No | ✅ Yes |
| State tracking | ❌ None | ✅ Per-file |
| Interruption | ❌ Lose progress | ✅ Save progress |
| Overhead | Low | Slightly higher (state I/O) |
| Use case | Small/fast | Large/slow folders |

---

## Benefits

### For Users
- ✅ **Never lose progress** - interrupt anytime, resume later
- ✅ **Perfect for huge folders** - 10,000+ photos
- ✅ **Handle network issues** - phone disconnect? Just reconnect and resume
- ✅ **Flexible scheduling** - copy 100 files today, 100 tomorrow
- ✅ **Clear visibility** - see exactly what's left

### Technical
- ✅ **Atomic state saves** - no corruption risk
- ✅ **Per-file granularity** - precise resume point
- ✅ **Graceful interruption** - Ctrl+C handled cleanly
- ✅ **Minimal overhead** - state file is small JSON

---

## State File Management

### When State is Created
- First time smart-copy rule runs
- After copying first file

### When State is Updated
- After EVERY successfully copied file
- Immediately (atomic write)

### When State is Cleared
- When ALL files successfully copied
- Rule marked as "completed"
- User can also manually clear: `phone-sync --clear-state -r r-0005`

### State File Location
```
~/.local/share/phone-migration/state.json
```

### Manual Management
```bash
# View state
cat ~/.local/share/phone-migration/state.json | jq

# Clear all state
rm ~/.local/share/phone-migration/state.json

# Clear specific rule state (future command)
phone-sync --clear-state -r r-0005
```

---

## Example Scenarios

### Scenario 1: Monthly Photo Archive
```bash
# Setup: 5000 photos in camera folder
phone-sync --smart-copy -p default \
  -pp /DCIM/Camera \
  -dp ~/Archives/2025-11 \
  --manual

# Start backup (takes 30 minutes)
phone-sync --run -r r-0008 -y

# Interrupted at 15 minutes (2500 photos)
# Resume later (copies remaining 2500)
phone-sync --run -r r-0008 -y
```

### Scenario 2: Phone Disconnect During Copy
```bash
# Start copy
phone-sync --run -r r-0008 -y
# ... phone disconnects at file 1000/5000

# Reconnect phone and resume
phone-sync --run -r r-0008 -y
# Resumes from file 1001
```

### Scenario 3: Copy Over Multiple Days
```bash
# Day 1: Copy 1000 files, then stop
phone-sync --run -r r-0008 -y
# Press Ctrl+C after 1000 files

# Day 2: Copy another 1000 files
phone-sync --run -r r-0008 -y
# Resumes from file 1001
```

---

## Future Enhancements

1. **`--clear-state`** command to manually clear stuck state
2. **Checksum verification** - verify file integrity, not just size
3. **Parallel copying** - copy multiple files simultaneously
4. **Bandwidth throttling** - limit transfer speed
5. **Progress bar** - visual progress indicator
6. **Email notification** - notify when complete
7. **Auto-retry** - retry failed files automatically

---

## Next Steps

1. ✅ Review this design
2. ⏳ Implement Phase 2 (smart copy operation)
3. ⏳ Implement Phase 3 (CLI integration)
4. ⏳ Test with large folder
5. ⏳ Update documentation

---

## Questions to Consider

1. **Should we batch state updates?** (e.g., every 10 files instead of every file)
   - Pro: Less I/O overhead
   - Con: Might lose more progress on crash

2. **Should smart-copy replace regular copy?** Or keep both?
   - Recommendation: Keep both
   - Regular copy: Fast, simple
   - Smart copy: Resumable, complex

3. **Should we auto-clean old state?** (e.g., state older than 30 days)
   - Recommendation: Yes, but make it configurable

4. **How to handle duplicate filenames?**
   - Use same (1), (2) logic as regular copy
   - Store final destination path in state

---

This design provides a robust, resumable copy mechanism perfect for your use case of backing up large folders with thousands of files!
