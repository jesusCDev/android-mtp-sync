# Phone Migration - Warp Terminal Guide

Quick reference for using the Phone Migration tool in Warp terminal.

> **`--run` previews, `--run -y` transfers.** There is no `--dry-run` flag: dry
> run is what a bare `--run` already does. Passing `--dry-run` is an argparse
> error.

## Setup

Add to your shell config (`~/.zshrc`):

```bash
alias phone-sync='python3 ~/Programming/project-cli/phone-migration/main.py'
```

Then reload: `source ~/.zshrc`

Warp renders the tool's Nerd Font icons if your Warp font is a Nerd Font. If it
is not, force the plain single-width set:

```bash
export PHONE_SYNC_PLAIN_ICONS=1
```

## Common Commands

### First Time Setup

```bash
# 1. Connect phone via USB (enable File Transfer mode, unlock it)
# 2. Register device
phone-sync --add-device --name default

# 3. Add move rule for photos
phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera

# 4. Add sync rule for videos
phone-sync --sync -p default -dp ~/Videos/motiv -pp /Videos/motiv
```

### Daily Usage

```bash
# Preview what would happen (changes nothing)
phone-sync --run

# Execute
phone-sync --run -y

# Execute with file-by-file output
phone-sync --run -y --verbose

# Execute and get a desktop notification when it finishes
phone-sync --run -y --notify
```

### Management

```bash
# Is the phone connected and recognized?
phone-sync --check

# List all profiles
phone-sync --list-profiles

# List rules for a profile
phone-sync --list-rules -p default

# Browse the phone's folders from the terminal
phone-sync --browse-phone

# Remove a rule
phone-sync --remove-rule -p default -i r-0001
```

## Warp Command Palette

You can save these as Warp workflows for quick access:

### Phone Sync - Preview
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --run
```

### Phone Sync - Execute
```bash
cd ~/Programming/project-cli/phone-migration && python3 main.py --run -y
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

1. Open Warp Settings, then Workflows
2. Create a new workflow with one of the commands above
3. Assign a shortcut (e.g. Ctrl+Shift+P for the preview)

## Tips

- **Preview first.** A bare `--run` prints every file it would copy, rename and
  delete, then analyzes that preview for unsafe patterns. Read it before adding
  `-y`.
- **Sync skips unchanged files by size.** A phone file whose size already matches
  the desktop copy is left alone; there is no hashing and no timestamp
  comparison, so a same-size edit is not detected.
- Keep the phone unlocked for the whole transfer.
- Check `~/.config/phone-migration/config.json` if rules do not match
  expectations.
- Run `gio mount -li` to debug device detection issues.

## Troubleshooting in Warp

If the device is not detected:

```bash
# Check MTP mount
gio mount -li | grep -i mtp

# Restart GVFS daemon
systemctl --user restart gvfs-daemon

# Check device detection verbosely
phone-sync --check --verbose

# View config
cat ~/.config/phone-migration/config.json | jq .
```

## Testing

After changing the main logic, run the test suite:

```bash
cd ~/Programming/project-cli/phone-migration
python3 -m pytest -q
```

That is the whole automated suite and it needs no phone. The hardware
integration script (`python3 tests/test_edge_cases.py`) is separate: it needs a
connected, unlocked phone and video files you supply yourself in `tests/videos/`.
See [tests/README_TESTS.md](../tests/README_TESTS.md).

## Integration with Warp AI

You can ask Warp AI:

- "Preview my phone sync"
- "Show phone migration config"
- "Add a new sync rule for Downloads folder"
- "Run the phone migration tests"

The AI will suggest the appropriate commands from this tool.
