# Phone Migration Tool

Automate file transfers between your Android phone and Linux desktop via MTP (Media Transfer Protocol). Simplify your workflow with configurable sync and move operations.

## Features

- **Device Profiles**: Register your phone with a unique identifier to ensure operations run on the correct device
- **Move Operation**: Copy files from phone to desktop, then delete them from phone (great for photos/videos)
- **Sync Operation**: Mirror desktop folders to phone with desktop as source of truth (perfect for playlists, documents)
- **Smart Sync**: Intelligently skips unchanged files by comparing file sizes (rsync-like behavior) - saves time and bandwidth
- **Conflict Handling**: Automatically rename duplicates with (1), (2), etc. suffixes
- **Dry Run Mode**: Preview operations before executing
- **Path Flexibility**: Support for both `/DCIM/Camera` and `Internal storage/DCIM/Camera` path formats

## Requirements

### System Packages (Fedora Linux)

The tool uses `gio` (part of GVFS) to interact with MTP devices. These packages should already be installed on Fedora:

```bash
# Verify packages are installed
rpm -qa | grep -E "(gvfs|mtp)"
```

You should see:
- `libmtp`
- `gvfs`
- `gvfs-mtp`
- `gvfs-fuse`
- `gvfs-client`

If missing, install with:
```bash
sudo dnf install gvfs gvfs-mtp gvfs-fuse libmtp
```

### Python

- Python 3.10+ (tested with Python 3.14)
- No external dependencies - uses standard library only

## Installation

1. The project is already set up at `~/Programming/project-cli/phone-migration/`

2. Make the main script executable:
```bash
chmod +x ~/Programming/project-cli/phone-migration/main.py
```

3. (Optional) Create an alias in your `~/.zshrc`:
```bash
alias phone-sync='python3 ~/Programming/project-cli/phone-migration/main.py'
```

## How MTP Works on Linux

When you connect your Android phone in File Transfer mode:

1. The phone is detected by the system via USB
2. GVFS (GNOME Virtual File System) automatically mounts it via MTP
3. The mount point appears at `/run/user/$UID/gvfs/mtp:host=...`
4. File managers like Dolphin and Nemo can browse these mounts
5. The `gio` command provides CLI access to these virtual filesystems

This tool uses `gio` commands to interact with your phone through MTP URIs like `mtp://[usb:003,009]/Internal storage/DCIM/Camera`.

## Quick Start

### 1. Connect Your Phone

1. Connect phone via USB cable
2. On your phone, select "File Transfer" or "MTP" mode from the notification
3. Unlock your phone
4. Verify detection: `gio mount -li | grep -i mtp`

### 2. Register Your Device

```bash
cd ~/Programming/project-cli/phone-migration
python3 main.py --add-device --name default
```

This creates a profile that identifies your specific phone.

### 3. Configure Rules

**Move photos from phone to desktop** (copies then deletes from phone):
```bash
python3 main.py --move --profile default \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera
```

**Sync motivational videos from desktop to phone** (desktop is source of truth):
```bash
python3 main.py --sync --profile default \
  --desktop-path ~/Videos/motiv \
  --phone-path /Videos/motiv
```

### 4. Run Sync Operations

```bash
python3 main.py --run
```

The tool will:
- Detect your connected phone
- Match it to the registered profile
- Execute all configured rules
- Show progress and summary

## CLI Reference

### Device Management

```bash
# Register connected phone (creates/updates profile)
python3 main.py --add-device [--name PROFILE_NAME]

# List all profiles
python3 main.py --list-profiles
```

### Rule Management

```bash
# Add move rule (phone → desktop, delete from phone)
python3 main.py --move --profile PROFILE \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera

# Add sync rule (desktop → phone, desktop is source of truth)
python3 main.py --sync --profile PROFILE \
  --desktop-path ~/Videos/motiv \
  --phone-path /Videos/motiv

# List rules for a profile
python3 main.py --list-rules --profile PROFILE

# Remove a rule
python3 main.py --remove-rule --profile PROFILE --id r-0001

# Edit a rule
python3 main.py --edit-rule --profile PROFILE --id r-0001 \
  --phone-path /DCIM/Screenshots
```

### Execution

```bash
# Run all rules for connected device
python3 main.py --run

# Dry run (preview without executing)
python3 main.py --run --dry-run

# Verbose output
python3 main.py --run --verbose
```

## Configuration File

Configuration is stored in JSON at: `~/Programming/project-cli/phone-migration/config.json`

### Example Configuration

```json
{
  "version": 1,
  "profiles": [
    {
      "name": "default",
      "device": {
        "display_name": "My Pixel 7",
        "id_type": "mtp_serial",
        "id_value": "A1B2C3D4E5F6",
        "activation_uri": "mtp://[usb:003,009]/"
      },
      "rules": [
        {
          "id": "r-0001",
          "mode": "move",
          "phone_path": "/DCIM/Camera",
          "desktop_path": "~/Videos/phone_images/Camera",
          "recursive": true
        },
        {
          "id": "r-0002",
          "mode": "sync",
          "desktop_path": "~/Videos/motiv",
          "phone_path": "/Videos/motiv",
          "recursive": true,
          "overwrite": true,
          "delete_extraneous": true
        }
      ]
    }
  ]
}
```

### Configuration Fields

**Profile:**
- `name`: Profile identifier
- `device.display_name`: Human-readable device name
- `device.id_type`: How device is identified (mtp_serial, identifier, usb_address)
- `device.id_value`: Unique device identifier value
- `device.activation_uri`: MTP URI (updated automatically on connection)

**Move Rule:**
- `phone_path`: Source path on phone (e.g., `/DCIM/Camera`)
- `desktop_path`: Destination on desktop (e.g., `~/Videos/phone_images/Camera`)
- Behavior: Copy files to desktop, then delete from phone
- Duplicates: Renamed with (1), (2), etc.

**Sync Rule:**
- `desktop_path`: Source on desktop (source of truth)
- `phone_path`: Destination on phone
- Behavior: Smart sync desktop to phone - only copies new/changed files (by size), deletes extraneous phone files
- Desktop files always take precedence, desktop files are never deleted
- Unchanged files are automatically skipped for faster syncs

## Phone Path Formats

The tool accepts multiple path formats:

```bash
# Leading slash (relative to Internal storage)
/DCIM/Camera

# Explicit storage label
Internal storage/DCIM/Camera
SD Card/DCIM/Camera

# No leading slash (assumes Internal storage)
DCIM/Camera
```

All paths are normalized internally to MTP URIs.

## Common Phone Paths

- **Photos**: `/DCIM/Camera`, `/DCIM/Screenshots`
- **Videos**: `/DCIM/Camera`, `/Movies`
- **Downloads**: `/Download`
- **Documents**: `/Documents`
- **Music**: `/Music`
- **Custom folders**: Any path you create

## Examples

### Scenario 1: Backup All Photos

```bash
# Register device
python3 main.py --add-device

# Move camera photos
python3 main.py --move --profile default \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera

# Move screenshots
python3 main.py --move --profile default \
  --phone-path /DCIM/Screenshots \
  --desktop-path ~/Videos/phone_images/Screenshots

# Run
python3 main.py --run
```

### Scenario 2: Sync Workout Videos

```bash
# Keep workout videos in sync (desktop → phone)
python3 main.py --sync --profile default \
  --desktop-path ~/Videos/Workouts \
  --phone-path /Videos/Workouts

python3 main.py --run
```

### Scenario 3: Multiple Phones

```bash
# Register personal phone
python3 main.py --add-device --name personal

# Register work phone
python3 main.py --add-device --name work

# Add rules to each profile
python3 main.py --move --profile personal \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/personal_photos

python3 main.py --move --profile work \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/work_photos

# Plug in either phone and run - it will use the correct profile
python3 main.py --run
```

## Troubleshooting

### Phone Not Detected

```bash
# Check if MTP device is mounted
gio mount -li | grep -i mtp

# Check USB connection
lsusb | grep -i android

# Verify GVFS services
systemctl --user list-units | grep gvfs
```

**Solutions:**
- Ensure phone is unlocked
- Select "File Transfer" mode in phone notification
- Try disconnecting and reconnecting
- Check USB cable (some cables are charge-only)
- Restart GVFS: `systemctl --user restart gvfs-daemon`

### Profile Not Matching

```bash
# Check device fingerprint
python3 main.py --add-device --name test --verbose

# Manually inspect config
cat ~/Programming/project-cli/phone-migration/config.json
```

### Permission Errors

```bash
# Ensure you're in the right groups
groups

# Check file permissions on destination
ls -la ~/Videos/phone_images
```

### Copy Failures

- **Disk full**: Check available space on desktop
- **File name issues**: Special characters in filenames may cause issues
- **Phone locked**: Keep phone unlocked during transfer
- **Connection timeout**: MTP can be slow; be patient with large files

### Sync Deletes Wrong Files

- Use `--dry-run` first to preview actions
- Verify `desktop_path` is correct - it's the source of truth!
- Check that `delete_extraneous: true` is intended behavior

## Performance Notes

- MTP is slower than direct USB mass storage
- Large files (>100MB) may take time
- Keep phone unlocked and screen on for best reliability
- Network/WiFi won't interfere but avoid heavy phone usage during transfer

## Safety

- **Backups**: Always maintain backups of important files
- **Dry run**: Use `--dry-run` to preview operations
- **Test first**: Try with a small test folder before bulk operations
- **Verification**: Move operations verify file size before deletion
- **No root**: Tool runs as regular user, no root access needed

## Future Enhancements

See `TODO.md` for planned features including:
- Auto-run on device connect (systemd/udev)
- Progress bars for large transfers
- Hash-based duplicate detection
- EXIF date-based organization
- File filtering patterns

## License

This is a personal tool. Use at your own risk.

## Contributing

This is a personal project, but suggestions and improvements are welcome!
