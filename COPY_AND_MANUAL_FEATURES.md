# Copy Mode and Manual-Only Rules Implementation

## Overview
Added two major features to support large folder backups and selective rule execution.

## New Features

### 1. Copy Mode
**Purpose**: Backup/archive files from phone without deleting them (unlike move mode which deletes after copy).

**Use Case**: Large folders with thousands of files you want to backup regularly but keep on phone.

**Usage**:
```bash
# Add a copy rule
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Backup/Camera

# Run normally (if not marked as manual)
phone-sync --run -y
```

**Behavior**:
- ✅ Copies files from phone to desktop
- ✅ Handles duplicates with (1), (2) suffixes
- ✅ Processes folders recursively
- ❌ Does NOT delete files from phone (key difference from move)

### 2. Manual-Only Rules
**Purpose**: Mark rules that should only run when explicitly called (not during regular `--run`).

**Use Case**: 
- Monthly photo archives (thousands of files)
- Large video backups
- Infrequent operations you don't want running every sync

**Usage**:
```bash
# Create a manual-only rule
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Monthly_Backup --manual

# List rules (manual rules shown with [MANUAL] tag)
phone-sync --list-rules -p default

# Run only that specific rule
phone-sync --run -r r-0003 -y

# Run multiple specific rules
phone-sync --run -r r-0003 -r r-0005 -y
```

**Behavior**:
- Rules marked with `manual_only: true` are skipped during normal `--run`
- Use `--run -r <rule-id>` to run specific manual rules
- When running with `-r`, the manual_only flag is ignored
- Output shows: "Executing 2 rule(s)... (1 manual rule(s) skipped)"

## Combined Example

### Setup
```bash
# Regular daily rules (auto-run)
phone-sync --move -p default -pp /DCIM/Screenshots -dp ~/Pictures/Screenshots
phone-sync --sync -p default -dp ~/Videos/motiv -pp /Videos/motiv

# Manual monthly backup (large folder)
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Monthly_Backup/$(date +%Y-%m) --manual
```

### Daily Usage
```bash
# Regular sync (skips manual rules)
phone-sync --run -y
# Output: Executing 2 rule(s)... (1 manual rule(s) skipped)
```

### Monthly Backup
```bash
# Run the manual backup rule
phone-sync --list-rules -p default  # Find the rule ID
phone-sync --run -r r-0003 -y       # Run just that rule
```

## Implementation Details

### Files Modified
1. **config.py**
   - Added `add_copy_rule()` function
   - Added `manual_only` parameter to all add_*_rule functions
   - Updated `print_rules()` to show [MANUAL] tag

2. **operations.py**
   - Added `run_copy_rule()` function
   - Added `_process_copy_directory()` helper (like move but no deletion)

3. **runner.py**
   - Added `rule_ids` parameter to `run_for_connected_device()`
   - Filtering logic: if rule_ids provided, run those; else run non-manual rules
   - Added `backed_up` counter to stats
   - Updated summary to show "Files backed up from phone"

4. **main.py**
   - Added `--copy` CLI argument
   - Added `--manual` flag for marking rules
   - Added `-r/--rule-id` argument (can be used multiple times)
   - Updated mode choices to include "copy"

### Rule Schema
```json
{
  "id": "r-0001",
  "mode": "copy",
  "phone_path": "/DCIM/Camera",
  "desktop_path": "~/Backup/Camera",
  "recursive": true,
  "manual_only": true
}
```

## Example Workflows

### Scenario 1: Monthly Photo Archive
```bash
# Setup: Mark large photo backup as manual
phone-sync --copy -p default \
  -pp /DCIM/Camera \
  -dp ~/Archives/Photos/$(date +%Y-%m) \
  --manual

# Monthly: Run the backup
phone-sync --run -r r-0004 -y --verbose
```

### Scenario 2: Video Project Backup
```bash
# Backup large video project folder without deleting from phone
phone-sync --copy -p default \
  -pp /Movies/MyProject \
  -dp ~/Projects/Backup \
  --manual

# Run when needed
phone-sync --run -r r-0005 -y
```

### Scenario 3: Mixed Rules
```bash
# Auto rules (run daily)
phone-sync --move -p default -pp /DCIM/Screenshots -dp ~/Pictures
phone-sync --sync -p default -dp ~/Videos/workout -pp /Videos/workout

# Manual rules (run on-demand)
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Backup/Full --manual
phone-sync --copy -p default -pp /Download -dp ~/Backup/Downloads --manual

# Daily sync (skips 2 manual rules)
phone-sync --run -y

# Full backup (run both manual rules)
phone-sync --run -r r-0003 -r r-0004 -y
```

## Benefits

### Copy Mode
- ✅ Backup files without affecting phone storage
- ✅ Archive important data while keeping originals
- ✅ Create redundant copies for safety
- ✅ Incremental backups (duplicates handled automatically)

### Manual-Only Rules
- ✅ Don't slow down regular daily syncs
- ✅ Control when expensive operations run
- ✅ Avoid accidental execution of large transfers
- ✅ Flexibility for different sync schedules

## Testing Checklist

- [x] Syntax check passes
- [x] Help text displays correctly
- [ ] Create copy rule
- [ ] Create manual-only copy rule
- [ ] Run normal sync (verify manual rules skipped)
- [ ] Run specific rule with -r
- [ ] List rules shows [MANUAL] tag
- [ ] Summary shows "Files backed up from phone"

## Next Steps
1. Test with actual device
2. Update README.md examples
3. Update warp.md with new workflows
4. Add to QUICKSTART.md
