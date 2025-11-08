# Phone Migration Tool

Automate file transfers between your Android phone and Linux desktop via MTP (Media Transfer Protocol). Simplify your workflow with configurable sync and move operations.

## Features

- **Web UI**: Modern web interface for managing devices, rules, and running operations with a graphical folder browser
- **Device Profiles**: Register your phone with a unique identifier to ensure operations run on the correct device
- **Move Operation**: Copy files from phone to desktop, then delete them from phone (great for photos/videos)
- **Sync Operation**: Mirror desktop folders to phone with desktop as source of truth (perfect for playlists, documents)
- **Smart Sync**: Intelligently skips unchanged files by comparing file sizes (rsync-like behavior) - saves time and bandwidth
- **Folder Browser**: Graphical folder picker for both phone (MTP) and desktop paths - no more guessing folder names!
- **Conflict Handling**: Toggle between two strategies for duplicate files:
  - **Rename on Conflict** (default): Automatically rename duplicates with (1), (2), etc. suffixes
  - **Skip on Conflict**: Skip files that already exist without renaming them
- **Device Accessibility Check**: Automatically detects when phone is locked and inaccessible
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

### Web UI

```bash
# Start web interface (recommended)
python3 main.py --web

# Then open http://127.0.0.1:8080 in your browser
```

The web UI provides a user-friendly interface with:
- Dashboard showing device connection status
- Profile management with device registration
- Rule configuration with **graphical folder browser**
- **Conflict handling toggle**: Choose between renaming or skipping duplicate files
- Live operation execution with progress tracking
- Operation history and logs

## Configuration Files

### Main Configuration
Configuration is stored in JSON at: `~/Programming/project-cli/phone-migration/config.json`

### History Storage
Operation history is persisted at: `~/.config/phone-migration/history.json`

This file stores the last 100 sync operations with:
- Timestamps and profile information
- Success/failure status
- File operation statistics (moved, synced, errors)
- Complete operation logs

History is automatically loaded when the web UI starts and saved after each operation.

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

## Web UI Guide

The web interface is the easiest way to use the phone migration tool.

### Starting the Web UI

```bash
cd ~/Programming/project-cli/phone-migration
python3 main.py --web
```

Open your browser to: **http://127.0.0.1:8080**

### Web UI Features

#### 1. Dashboard
- **Improved Device Status**: Horizontal layout showing Device, Profile, and Rules in a clean grid
- **Run Operations**: Execute rules with real-time progress tracking
- **Dry Run & Notifications**: Toggle options before running
- **Manual Rules**: Run specific manual-only rules on demand
- **Live Statistics**: See files moved, backed up, synced, and errors in real-time
- **Operation History**: Persistent history across app restarts

#### 2. Profiles Page
- Register new devices with one click
- View all registered devices
- Delete old profiles

#### 3. Rules Page (with Folder Browser!)
- Add rules with an intuitive form
- **Browse phone folders** - click the Browse button next to Phone Path to visually navigate your phone's folder structure
- **Browse desktop folders** - click the Browse button next to Desktop Path to navigate your computer's filesystem
- **Folder Browser Features:**
  - Navigate with breadcrumbs or Up button
  - Type or paste paths directly in the path bar (press Enter to jump)
  - Create new folders on desktop with the "New Folder" button
  - Toggle "Show hidden" to see/hide hidden files (those starting with `.`)
  - Files are shown but grayed out (directories only for selection)
  - Single-click to select, double-click to navigate into folders
  - ESC or click outside to close the browser
- Edit or delete existing rules
- See all rules for your connected device

#### 4. Dashboard - Run Operations (Enhanced)
- Execute configured rules with real-time progress
- See which files are being transferred
- View operation statistics
- Option for dry-run preview
- **Rename on Conflict toggle**: Control duplicate file handling:
  - **Enabled** (default): Rename duplicates as `filename (1).ext`, `filename (2).ext`, etc.
  - **Disabled**: Skip files that already exist without renaming them
  - Affects all operation types: move, copy, smart copy, and sync
- **Command Preview**: Displays the exact command that will execute with color-coded syntax
- **Operation Details Modal**: Click "Expand" on any operation card to:
  - View the formatted command in **Command View** tab
  - See detailed file listings in **Detail View** tab showing:
    - Files being copied (with source and destination)
    - Files being deleted
    - Files being skipped
    - Folders being created
  - Modal displays full-screen with close button and Escape key support

#### 5. History Page
- **Persistent Storage**: History is now saved to `~/.config/phone-migration/history.json`
- **Survives Restarts**: View operation history even after closing and reopening the web UI
- View past operation logs with expandable details
- See success/failure status with color-coded badges
- Review file counts and statistics for each run
- Filter by status (success/error) and limit results
- Relative timestamps ("5 minutes ago", "2 hours ago", etc.)
- Last 100 operations are kept

### Using the Folder Browser

The folder browser makes it easy to select paths without knowing exact folder names:

**For Desktop Paths:**
1. Click "Browse" next to Desktop Path
2. Browser starts at your home directory (`~`)
3. Navigate by clicking folders or using the Up button
4. Use breadcrumbs to jump to parent folders
5. Type/paste a path in the path bar and press Enter to jump directly
6. Click "New Folder" to create a new destination folder
7. Check "Show hidden" if you need to navigate to hidden folders (like `.config`)
8. Click "Select Current Folder" when you're in the right place

**For Phone Paths:**
1. Connect your phone first (unlocked, in File Transfer mode)
2. Click "Browse" next to Phone Path
3. Browser shows your phone's root directories (DCIM, Download, etc.)
4. Navigate the same way as desktop folders
5. Common folders like `/DCIM/Camera` are easy to find by clicking
6. Files are shown for context but cannot be selected

**Tips:**
- Hidden files are hidden by default (toggle with checkbox)
- Desktop browsing works across the entire filesystem (including `/mnt`, `/media`)
- Phone browsing requires the device to be connected
- You can still type paths manually if you prefer!

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

## UI Design

### Color Palette
The web UI uses a soft pastel color scheme designed to be easy on the eyes during extended use:
- **Accent (Lavender)**: `#C8A2E0` - Primary interactive elements
- **Info (Sky Blue)**: `#9DD4FF` - Information and status updates
- **Success (Mint Green)**: `#8FD6B5` - Successful operations
- **Warning (Peachy-Gold)**: `#FFD699` - Warnings and cautions
- **Danger (Coral Red)**: `#FF9898` - Errors and destructive actions

### Operation Details
Each operation card includes an "Expand" button that opens a detailed modal showing:
1. **Command View**: The exact command being executed with syntax highlighting
   - Color-coded flags and parameters
   - Execute mode vs. dry-run indicators
2. **Detail View**: File-level breakdown by category
   - Individual files being copied/moved
   - Files marked for deletion
   - Files being skipped
   - Folders being created

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
