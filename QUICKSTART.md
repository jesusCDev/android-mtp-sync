# Phone Migration - Quick Start

Get up and running in 5 minutes!

## Prerequisites

✅ Android phone with USB cable  
✅ Fedora Linux (you have this)  
✅ Python 3.10+ (you have 3.14)

## Step 1: Connect Your Phone

1. Plug phone into computer via USB
2. On your phone: Pull down notification shade
3. Tap the USB notification
4. Select **"File Transfer"** or **"Transfer files"**
5. Unlock your phone

**Verify connection:**
```bash
gio mount -li | grep -i mtp
```

You should see something like `Mount(0): Your Phone Name`

## Step 2: Register Your Phone

```bash
cd ~/Programming/project-cli/phone-migration
python3 main.py --add-device --name default
```

You should see: `✓ Device registered to profile 'default'`

## Step 3: Add Your First Rule

### Example: Move Photos from Phone to Desktop

```bash
python3 main.py --move --profile default \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera
```

This will:
- Copy all photos from phone's Camera folder
- Save them to `~/Videos/phone_images/Camera/`
- Delete them from your phone after successful copy

### Example: Sync Videos to Phone

```bash
python3 main.py --sync --profile default \
  --desktop-path ~/Videos/motiv \
  --phone-path /Videos/motiv
```

This will:
- Mirror your desktop `~/Videos/motiv/` folder to phone
- Desktop is the source of truth
- Any changes on desktop will sync to phone

## Step 4: Run the Sync

```bash
python3 main.py --run
```

That's it! Your files are now syncing.

## Step 5: Check Results

List your configured rules:
```bash
python3 main.py --list-rules --profile default
```

## Common Commands

```bash
# See what would happen without actually doing it
python3 main.py --run --dry-run

# More detailed output
python3 main.py --run --verbose

# List all profiles
python3 main.py --list-profiles

# Remove a rule
python3 main.py --remove-rule --profile default --id r-0001
```

## Optional: Create Alias

Add to `~/.zshrc`:
```bash
alias phone-sync='python3 ~/Programming/project-cli/phone-migration/main.py'
```

Then reload: `source ~/.zshrc`

Now you can just run:
```bash
phone-sync --run
```

## Troubleshooting

**Phone not detected?**
```bash
# Check MTP mount
gio mount -li

# Restart GVFS
systemctl --user restart gvfs-daemon
```

**Want to test first?**
- Create a test folder on your phone with a few files
- Add a move rule for that folder
- Run with `--dry-run` first
- Then run without dry-run

## What Next?

- Read `README.md` for detailed documentation
- Check `warp.md` for Warp terminal integration
- See `TODO.md` for upcoming features

## Your First Sync Workflow

```bash
# 1. Connect phone (enable File Transfer mode)
# 2. Register device (one-time)
python3 main.py --add-device

# 3. Add rules (one-time per folder)
python3 main.py --move --profile default \
  --phone-path /DCIM/Camera \
  --desktop-path ~/Videos/phone_images/Camera

# 4. Run sync (every time you want to transfer)
python3 main.py --run

# Done! Disconnect phone.
```

## Safety Tips

- ✅ Use `--dry-run` first to preview
- ✅ Start with a small test folder
- ✅ Keep phone unlocked during transfer
- ✅ Backups are always a good idea!

Happy syncing! 📱💻
