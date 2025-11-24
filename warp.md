# Phone Migration - Warp Terminal Guide

Quick reference for using the Phone Migration tool in Warp terminal.

## Setup

Add to your shell config (`~/.zshrc`):

```bash
alias phone-sync='python3 ~/Programming/project-cli/phone-migration/main.py'
```

Then reload: `source ~/.zshrc`

## Common Commands

### First Time Setup

```bash
# 1. Connect phone via USB (enable File Transfer mode)
# 2. Register device
phone-sync --add-device --name default

# 3. Add move rule for photos
phone-sync --move --profile default \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera

# 4. Add sync rule for videos
phone-sync --sync --profile default \
  --desktop-path ~/Videos/motiv \
  --phone-path /Videos/motiv
```

### Daily Usage

```bash
# Run all configured rules
phone-sync --run

# Preview what will happen (dry run)
phone-sync --run --dry-run

# Verbose output for debugging
phone-sync --run --verbose
```

### Management

```bash
# List all profiles
phone-sync --list-profiles

# List rules for a profile
phone-sync --list-rules --profile default

# Remove a rule
phone-sync --remove-rule --profile default --id r-0001
```

## Warp Command Palette

You can save these as Warp workflows for quick access:

### Phone Sync - Run
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --run
```

### Phone Sync - Dry Run
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --run --dry-run
```

### Phone Sync - Add Device
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --add-device --name default
```

### Phone Sync - List Profiles
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --list-profiles
```

## Keyboard Shortcuts (Custom)

You can create Warp workflows and assign keyboard shortcuts:

1. Open Warp Settings → Workflows
2. Create new workflow with command above
3. Assign shortcut (e.g., Ctrl+Shift+P for sync)

## Tips

- **Smart Sync**: The sync operation now intelligently skips files that haven't changed by comparing file sizes (similar to rsync). This avoids unnecessary transfers and speeds up syncs.
- Use `--dry-run` first to preview operations and see which files will be copied vs skipped
- Keep phone unlocked during transfer for best results
- Check `config.json` if rules don't match expectations
- Run `gio mount -li` to debug device detection issues

## Example Session

```bash
# Connect phone
# Terminal output shows:
$ gio mount -li | grep -i mtp
Mount(0): My Phone
  Default location: mtp://[usb:003,009]/

# Run sync
$ phone-sync --run
Detecting connected device...
✓ Found registered device: My Phone (profile: default)

Executing 2 rule(s)...
============================================================

Move: /DCIM/Camera → /home/jesuscdev/Videos/phone_images/Camera
  Copying: IMG_20250101.jpg → /home/jesuscdev/Videos/phone_images/Camera/IMG_20250101.jpg
  Copying: IMG_20250102.jpg → /home/jesuscdev/Videos/phone_images/Camera/IMG_20250102.jpg
  Deleting: mtp://[usb:003,009]/Internal storage/DCIM/Camera/IMG_20250101.jpg
  Deleting: mtp://[usb:003,009]/Internal storage/DCIM/Camera/IMG_20250102.jpg
  ✓ Copied: 2, Renamed: 0, Deleted: 2

Sync: /home/jesuscdev/Videos/motiv → /Videos/motiv
  Copying: /home/jesuscdev/Videos/motiv/workout1.mp4 → mtp://[usb:003,009]/Internal storage/Videos/motiv/workout1.mp4
  ✓ Synced: 1, Cleaned: 0

# Second run (files unchanged):
Sync: /home/jesuscdev/Videos/motiv → /Videos/motiv
  ⊙ Skipped: 1, Cleaned: 0

============================================================

Summary:
  Files copied: 3
  Files deleted: 2

✓ All operations completed successfully!
```

## Troubleshooting in Warp

If device not detected:

```bash
# Check MTP mount
gio mount -li | grep -i mtp

# Restart GVFS daemon
systemctl --user restart gvfs-daemon

# Check device with verbose
phone-sync --add-device --name test --verbose

# View config
cat ~/Programming/project-cli/phone-migration/config.json | jq .
```

## Testing

**IMPORTANT**: After making any updates to the main logic, always run tests to ensure everything works as expected.

```bash
# Run full test suite
cd /mnt/port/Programming/projects/android-mtp-sync
python3 tests/test_edge_cases.py
```

### Prerequisites for Testing
- Phone connected via USB (File Transfer mode)
- Phone unlocked during test execution
- 2GB free space on both phone and desktop

### Test Coverage
The test suite covers 12 critical scenarios including:
- Large file transfers (≥1GB)
- Disk space validation
- Symlink handling
- Device disconnection safety
- Concurrent operations
- State corruption recovery
- File permissions

See `tests/docs/TESTING.md` for complete testing documentation.

## Integration with Warp AI

You can ask Warp AI:

- "Run my phone sync"
- "Show phone migration config"
- "Add a new sync rule for Downloads folder"
- "Dry run phone sync"
- "Run phone migration tests"

The AI will suggest the appropriate commands from this tool!
