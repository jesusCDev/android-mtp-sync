# Phone Migration - Quick Start

> **Archived.** The onboarding path now lives in the root
> [README.md](../../README.md), which this file duplicates in shorter form. It is
> kept because it is still accurate and still the fastest way in. Everything
> below is verified against the current CLI.

Up and running in five minutes.

> **The one thing to remember:** `--run` is a *preview*. It prints what it would
> do and changes nothing. Add `-y` when you want the transfer to actually
> happen. There is no `--dry-run` flag — dry run is the default.

## Prerequisites

- An Android phone and a USB cable
- Fedora Linux with `gvfs`, `gvfs-mtp` and `libmtp` installed
- Python 3.10 or newer (no third-party packages needed for the CLI)

## Step 1: Connect the phone

1. Plug the phone in over USB.
2. On the phone, pull down the notification shade.
3. Tap the USB notification.
4. Choose **"File Transfer"** / **"Transfer files"**.
5. Unlock the phone and leave it unlocked.

Verify:

```bash
gio mount -li | grep -i mtp
```

You should see a line like `Mount(0): Your Phone Name`.

## Step 2: Register the phone

```bash
python3 main.py --add-device --name default
```

You should see `✓ Device registered to profile 'default'`.

If instead you get `Device exposes no serial number; cannot register it
reliably`, re-pick File Transfer mode on the phone, unplug and replug, and try
again — a profile without a serial would match every serial-less phone, so it is
refused rather than saved.

## Step 3: Add your first rule

### Move photos off the phone

```bash
python3 main.py --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
```

This will copy every photo from the phone's Camera folder to
`~/Pictures/Camera/`, then delete it from the phone once the desktop copy is
verified by size.

### Or: copy them and keep both

```bash
python3 main.py --copy -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
```

### Or: mirror a desktop folder onto the phone

```bash
python3 main.py --sync -p default -dp ~/Videos/motiv -pp /Videos/motiv
```

The desktop side is the source of truth: it is never modified, and the phone is
made to match it.

Not sure which mode you want? See [docs/OPERATIONS.md](../OPERATIONS.md).

## Step 4: Preview, then run

```bash
# Preview - prints every file it would touch, changes nothing
python3 main.py --run

# Happy with the preview? Execute it
python3 main.py --run -y
```

## Step 5: Check what you configured

```bash
python3 main.py --list-rules -p default
```

## Common commands

```bash
# Is my phone connected and recognized?
python3 main.py --check

# Preview a run
python3 main.py --run

# Execute a run
python3 main.py --run -y

# Execute with file-by-file output
python3 main.py --run -y --verbose

# Include manual-only rules
python3 main.py --run --manual -y

# Run one specific rule
python3 main.py --run -r r-0001 -y

# List all profiles
python3 main.py --list-profiles

# Browse the phone's folders from the terminal
python3 main.py --browse-phone

# Remove a rule
python3 main.py --remove-rule -p default -i r-0001
```

## Optional: create an alias

Add to `~/.zshrc`:

```bash
alias phone-sync='python3 /path/to/phone-migration/main.py'
```

Reload with `source ~/.zshrc`, then:

```bash
phone-sync --run -y
```

## Optional: the web UI

The web UI is the only part that needs a third-party package:

```bash
pip install -r requirements-web.txt
python3 main.py --web
```

Open **http://127.0.0.1:8080**. Use `--web --background` to keep it running
after you close the terminal, and `--web --stop` to shut it down.

## Where your settings live

| What | Path |
|---|---|
| Profiles and rules | `~/.config/phone-migration/config.json` |
| Backup resume state | `~/.local/share/phone-migration/state.json` (+ `state.lock`) |
| Web UI pid + log | `~/.local/state/phone-migration/` |

If you used an older version that kept `config.json` inside the project folder,
it is copied to the new location automatically on the next run, and the original
is left in place.

## Troubleshooting

**Phone not detected?**

```bash
# Check the MTP mount
gio mount -li

# Restart GVFS
systemctl --user restart gvfs-daemon
```

Then unlock the phone and re-select File Transfer mode.

**Want to test safely first?**

- Create a small test folder on the phone with a couple of files.
- Add a rule for that folder.
- Run `python3 main.py --run` and read the preview.
- Only then add `-y`.

**Colors or icons look wrong?**

```bash
NO_COLOR=1 python3 main.py --run              # no ANSI color
PHONE_SYNC_PLAIN_ICONS=1 python3 main.py --run  # plain unicode icons
NERD_FONT=1 python3 main.py --run             # Nerd Font glyphs
```

## What next?

- [README.md](../../README.md) — the full reference
- [docs/OPERATIONS.md](../OPERATIONS.md) — what each mode does to your files
- [docs/DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md) — the CLI palette and icon set

## Your first sync workflow

```bash
# 1. Connect phone (File Transfer mode, unlocked)
# 2. Register the device (one time)
python3 main.py --add-device --name default

# 3. Add rules (one time per folder)
python3 main.py --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera

# 4. Preview, then transfer (every time)
python3 main.py --run
python3 main.py --run -y

# Done - disconnect the phone.
```

## Safety tips

- Run without `-y` first and read the preview.
- Start with a small test folder.
- Keep the phone unlocked for the whole transfer.
- Move deletes from the phone only after the desktop copy is size-verified.
- Sync with `delete_extraneous` deletes phone files; the desktop side is never
  touched.
- Keep independent backups of anything irreplaceable.
