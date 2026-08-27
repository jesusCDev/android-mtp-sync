# Phone Migration Tool

Automate file transfers between an Android phone and a Linux desktop over MTP
(Media Transfer Protocol). Rules are stored per device profile and executed with
one command, from the CLI or from a local web UI.

> **`--run` previews. `--run -y` transfers.**
> Every execution command defaults to a dry run: it scans, prints exactly what it
> would do, and touches nothing — no files copied, no files deleted, no state
> written. Add `-y` (or `--yes`, or `--execute`) when you actually want the
> transfer to happen. There is no `--dry-run` flag; dry run is the default.

## Features

- **Web UI**: an optional local Flask app with a graphical phone/desktop folder
  browser, live run progress, and run history
- **Four rule modes**: move, copy, backup (resumable), and sync — see
  [docs/OPERATIONS.md](docs/OPERATIONS.md) for what each one does to your files
- **Device profiles**: rules are bound to a phone's MTP serial, so plugging in a
  different phone runs that phone's rules and nothing else
- **Dry run by default**, with a safety analysis of the preview before you commit
  to it
- **Preflight disk-space check** before every real transfer
- **Resumable backups**: a backup that is interrupted picks up where it stopped
- **Manual-only rules**: rules you tag `--manual` are skipped by a plain `--run`
  and execute only when you ask for them — `--run --manual` for all of them, or
  `--run -r <id>` for one
- **Desktop notifications**: `--notify` sends a summary through `notify-send`
- **Path flexibility**: `/DCIM/Camera`, `DCIM/Camera`, `Internal storage/DCIM/Camera`
  and `SD Card/DCIM/Camera` all work

## Requirements

### System packages (Fedora Linux)

The tool shells out to `gio` (part of GVFS) to talk to MTP devices:

```bash
rpm -qa | grep -E "(gvfs|mtp)"
```

You should see `libmtp`, `gvfs`, `gvfs-mtp`, `gvfs-fuse` and `gvfs-client`.
If any are missing:

```bash
sudo dnf install gvfs gvfs-mtp gvfs-fuse libmtp
```

### Python

- Python 3.10 or newer.
- **The CLI needs no third-party packages** — it is standard library only.
- **The web UI needs Flask.** Install it only if you intend to use `--web`:

```bash
pip install -r requirements-web.txt
```

## Installation

1. Clone or copy the project somewhere convenient.

2. Make the entry point executable:

```bash
chmod +x main.py
```

3. (Optional but recommended) add an alias to your `~/.zshrc` or `~/.bashrc`:

```bash
alias phone-sync='python3 /path/to/phone-migration/main.py'
```

The rest of this document writes commands as `phone-sync`; `python3 main.py`
from the project directory is exactly equivalent.

## How MTP works on Linux

When you connect an Android phone in File Transfer mode:

1. The phone is detected over USB.
2. GVFS mounts it via MTP.
3. The mount appears under `/run/user/$UID/gvfs/mtp:host=...`.
4. Graphical file managers browse that mount.
5. `gio` gives command-line access to the same virtual filesystem.

This tool drives `gio` against MTP URIs such as
`mtp://[usb:003,009]/Internal storage/DCIM/Camera`.

### One application at a time

Linux MTP allows only **one** application to hold the device at a time. If a
file manager (Nemo, Dolphin, Nautilus, Thunar, PCManFM) has your phone open
while this tool runs, the device is reported as connected but not accessible.

```bash
# Close the file managers and restart GVFS
killall nemo dolphin nautilus pcmanfm thunar
systemctl --user restart gvfs-daemon
```

## Quick start

### 1. Connect the phone

1. Connect the phone over USB.
2. On the phone, pick "File Transfer" / "MTP" from the USB notification.
3. Unlock the phone and keep it unlocked.
4. Confirm the mount: `gio mount -li | grep -i mtp`

### 2. Register the device

```bash
phone-sync --add-device --name default
```

This writes a profile that identifies your specific phone by its MTP serial.

### 3. Configure rules

Move photos off the phone (copy to desktop, then delete from the phone):

```bash
phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
```

Mirror a desktop folder onto the phone (desktop is the source of truth):

```bash
phone-sync --sync -p default -dp ~/Videos/motiv -pp /Videos/motiv
```

### 4. Preview, then run

```bash
phone-sync --run        # preview: prints what would happen, changes nothing
phone-sync --run -y     # execute
```

## CLI reference

Exactly one command flag is required per invocation.

### Device management

```bash
# Register the connected phone (creates or updates a profile)
phone-sync --add-device [--name PROFILE]

# List every configured profile
phone-sync --list-profiles

# Check whether a registered phone is connected right now
phone-sync --check

# Walk the phone's directory tree interactively
phone-sync --browse-phone
```

`--check` exits `0` when a registered device is connected and `1` when it is
not, which makes it usable as a guard in scripts.

### Rule management

```bash
# Move rule: phone -> desktop, delete from the phone afterwards
phone-sync --move -p PROFILE -pp /DCIM/Camera -dp ~/Pictures/Camera

# Copy rule: phone -> desktop, keep both copies
phone-sync --copy -p PROFILE -pp /DCIM/Camera -dp ~/Pictures/Camera

# Backup rule: phone -> desktop, resumable, never deletes
phone-sync --backup -p PROFILE -pp /DCIM/Camera -dp ~/Backups/Phone

# Sync rule: desktop -> phone, desktop is the source of truth
phone-sync --sync -p PROFILE -dp ~/Videos/motiv -pp /Videos/motiv

# Mark a new rule manual-only (a plain --run skips it)
phone-sync --copy -p PROFILE -pp /DCIM/Screenshots -dp ~/Pictures --manual

# List the rules of a profile
phone-sync --list-rules -p PROFILE

# Edit a rule (any of -pp, -dp, -m, --manual/--no-manual)
phone-sync --edit-rule -p PROFILE -i r-0001 -pp /DCIM/Screenshots
phone-sync --edit-rule -p PROFILE -i r-0001 --no-manual

# Remove a rule
phone-sync --remove-rule -p PROFILE -i r-0001
```

`--smart-copy` is a **deprecated alias for `--backup`**. It still works, and
existing rules stored with `"mode": "smart_copy"` still run as backups, but new
rules should use `--backup`.

### Execution

```bash
# Preview every auto rule (default; changes nothing)
phone-sync --run

# Execute every auto rule
phone-sync --run -y

# Include manual-only rules as well
phone-sync --run --manual -y

# Run specific rules by id (repeat -r for more than one)
phone-sync --run -r r-0003 -y
phone-sync --run -r r-0003 -r r-0005 -y

# File-by-file output
phone-sync --run -y --verbose

# Desktop notification with the summary when the run finishes
phone-sync --run -y --notify
```

`--notify` needs `notify-send` on `PATH` (package `libnotify`); without it the
run still succeeds and the notification is silently skipped. A dry run does not
send the *completion* notification, but it still notifies when no device was
found.

### Web UI

```bash
# Foreground (Ctrl+C to stop)
phone-sync --web

# Background daemon, survives closing the terminal
phone-sync --web --background

# Stop a running instance
phone-sync --web --stop
```

The server binds **`http://127.0.0.1:8080`** — loopback only, never a public
interface. Start-up refuses to proceed if port 8080 is already in use rather
than half-starting.

### Environment variables

| Variable | Effect |
|---|---|
| `NO_COLOR` (any value) | Disables all ANSI color. Color is also off automatically when stdout is not a terminal. |
| `NERD_FONT=1` | Use Nerd Font glyphs for icons. Auto-detected when `WEZTERM_PANE` is set. |
| `PHONE_SYNC_PLAIN_ICONS=1` | Force the plain single-width unicode icon set (`✓ ✗ ⚠ ▸ •`). Wins over `NERD_FONT`. |
| `XDG_CONFIG_HOME` | Relocates the config and history directory. |
| `XDG_STATE_HOME` | Relocates the web UI pid file and log. |

All three theme switches are read once, at start-up.

## What a run does

### Preflight disk-space check

Before each rule of a **real** (non-dry) run, the tool prints
`Preflight: checking disk space for <mode>...` and estimates the transfer by
walking the source tree, then compares it against the free space on the
destination filesystem, requiring the transfer to fit with a 5% headroom left
over. If it does not fit, that rule is **skipped** with a `Preflight check
failed` message listing what is needed, what is free, and the deficit; the run
continues with the remaining rules and the skipped rule counts as an error. A
failure to *estimate* (rather than a genuine shortage) is reported as a warning
and the rule proceeds. Sync is the exception: MTP does not expose the phone's
free space, so a sync rule's space check is logged as skipped rather than
enforced. Dry runs do no preflight at all.

### Dry-run safety analysis

After a dry run that touched at least one rule, the preview is re-read by an
analyzer that looks for results that should be impossible, and prints
`Analyzing dry-run results...` followed by any findings at three severities.

**Blockers** are safety violations: a copy rule that reported deletions, a move
rule whose deletion count does not equal its copies, a backup rule that deleted
anything. Any blocker ends the output with `OPERATION BLOCKED` in place of the
usual "execute with -y" hint.

**Warnings** are legal outcomes worth a second look: a sync that would delete
more than five times what it copies while copying fewer than ten files, a sync
deleting more than 500 files, a non-sync rule deleting more than 100, or more
than 1000 deletions against fewer than 100 copies.

**Info** covers a rule that would change nothing — everything already present, or
an empty source.

With no findings at any severity the analysis prints `All safety checks
passed!`. It reads only the preview's own statistics; it does not touch the
phone or the desktop again.

### Progress display

Each rule shows an animated spinner line — `[2/5] SYNC (r-0003)` — while it
runs, which is replaced on completion by a single line carrying a tick or a
cross, the rule's summary, and its elapsed time. Underneath, an overall bar
tracks completed rules and shows an ETA extrapolated from the rules finished so
far. The spinner writes with carriage returns, so redirect to a file or set
`NO_COLOR` if you want plain, line-oriented output.

## File locations

| What | Path |
|---|---|
| Configuration (profiles + rules) | `~/.config/phone-migration/config.json` |
| Web UI run history | `~/.config/phone-migration/history.json` |
| Web UI folder bookmarks | `~/.config/phone-migration/bookmarks.json` |
| Backup resume state | `~/.local/share/phone-migration/state.json` |
| Backup state lock | `~/.local/share/phone-migration/state.lock` |
| Web UI pid file | `~/.local/state/phone-migration/web.pid` |
| Web UI log | `~/.local/state/phone-migration/web.log` |

`XDG_CONFIG_HOME` overrides the config directory — which is the first three rows,
history and bookmarks included; `XDG_STATE_HOME` overrides the pid file and log.

Every read-modify-write of `state.json` happens while holding an exclusive
`fcntl` lock on `state.lock`, so two runs racing on different rules cannot drop
each other's progress. Both `config.json` and `state.json` are written
atomically — an interrupted write never leaves a truncated file — and a
`state.json` that fails to parse is renamed `state.json.corrupt` with a warning
rather than silently reset.

**Migration from the old location.** Early versions kept `config.json` inside
the project checkout at `~/Programming/project-cli/phone-migration/config.json`.
If that file exists and no XDG config does yet, it is **copied** (not moved) to
`~/.config/phone-migration/config.json` on the next run, and the tool prints a
one-line note saying so. The old file is left untouched so you can verify the
copy before deleting it.

### Example configuration

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
          "desktop_path": "~/Pictures/Camera",
          "recursive": true
        },
        {
          "id": "r-0002",
          "mode": "sync",
          "desktop_path": "~/Videos/motiv",
          "phone_path": "/Videos/motiv",
          "recursive": true,
          "delete_extraneous": true
        },
        {
          "id": "r-0003",
          "mode": "backup",
          "phone_path": "/Documents",
          "desktop_path": "~/Backups/Phone/Documents",
          "recursive": true,
          "manual_only": true
        }
      ]
    }
  ]
}
```

### Configuration fields

**Profile**

- `name` — profile identifier, what you pass to `-p`
- `device.display_name` — human-readable device name
- `device.id_type` — always `mtp_serial`
- `device.id_value` — the phone's MTP serial number
- `device.activation_uri` — MTP URI, refreshed automatically on each connection

**Rule (all modes)**

- `id` — assigned automatically (`r-0001`, `r-0002`, ...)
- `mode` — `move`, `copy`, `backup`, `sync` (or the legacy `smart_copy`)
- `phone_path` / `desktop_path` — the two endpoints
- `recursive` — written into new rules but **never read**; every mode always
  descends into subdirectories. Setting it to `false` changes nothing.
- `manual_only` — when `true`, a plain `--run` skips the rule; run it with
  `--run --manual` or `--run -r <id>`

**Sync rule only**

- `delete_extraneous` — when `true`, phone files that no longer exist on the
  desktop are deleted. See the safety rails in
  [docs/OPERATIONS.md](docs/OPERATIONS.md#sync-mode).

Sync always overwrites a phone file whose size differs from the desktop copy;
there is no flag for it.

## Phone path formats

```bash
/DCIM/Camera                    # leading slash: relative to Internal storage
DCIM/Camera                     # no leading slash: same thing
Internal storage/DCIM/Camera    # explicit storage label
SD Card/DCIM/Camera             # the other storage
```

All forms are normalized to a percent-encoded MTP URI internally.

### Common phone paths

- Photos: `/DCIM/Camera`, `/DCIM/Screenshots`
- Videos: `/DCIM/Camera`, `/Movies`
- Downloads: `/Download`
- Documents: `/Documents`
- Music: `/Music`

## Sample output

Listing profiles:

```
$ phone-sync --list-profiles

Configured Profiles (1 total)
──────────────────────────────────────────────────────────────────────

▪ s25-ultra
  Device: SAMSUNG Android
  ID:     mtp_serial=R5CY43CZ5AR
  Rules:  4 auto + 1 manual
```

Listing rules:

```
$ phone-sync --list-rules -p s25-ultra

Rules for profile 's25-ultra' (5 total)
──────────────────────────────────────────────────────────────────────

[r-0001] ↑ MOVE
  Phone:   /Download
  Desktop: ~/Downloads
  Action:  Copy to desktop, then delete from phone
  ····························································

[r-0003] ⇄ SYNC
  Desktop: ~/Videos/phone_videos/ck (source)
  Phone:   /Videos/ck
  Action:  Mirror desktop to phone (desktop is source of truth)
  ····························································

[r-0004] + BACKUP [MANUAL]
  Phone:   /Documents/ringtone
  Desktop: ~/Downloads/test
  Action:  Backup to desktop (resumable, no deletions)
```

A preview run with nothing plugged in:

```
$ phone-sync --run

────────────────────────────────────────────────────────────
▪  Phone Migration Tool
────────────────────────────────────────────────────────────

! DRY RUN MODE (preview only, no changes)

? Scanning for connected devices...

✗ No device found

Possible reasons:
  • Phone not connected via USB
  • File Transfer mode disabled
  • Phone is locked
  • Device not yet registered

Next steps:
  1. Connect phone & enable File Transfer
  2. Register: phone-sync --add-device --name default
  3. Execute: phone-sync --run -y
```

(These samples were captured with `PHONE_SYNC_PLAIN_ICONS=1 NO_COLOR=1`. With a
Nerd Font terminal the icons are Font Awesome glyphs instead.)

## Web UI guide

```bash
pip install -r requirements-web.txt
phone-sync --web
```

Then open **http://127.0.0.1:8080**. `requirements-web.txt` pins **Flask alone**;
nothing else is needed, and `flask-cors` — which earlier versions listed — is no
longer used. If you installed it for this tool you can `pip uninstall flask-cors`.

### Pages

- **Dashboard** — device connection status, run controls, live progress, and the
  operations list. "Run Auto Rules" skips manual-only rules; "Run Manual Rules"
  runs the ones you tick, by id. Registering the connected phone is done from
  here too.
- **Profiles** — view, rename and delete profiles.
- **Rules** — add and delete rules for any of the four modes, with a graphical
  folder browser for both endpoints. To *change* an existing rule, use the CLI:
  `phone-sync --edit-rule -p PROFILE -i r-0001 ...`.
- **History** — past runs loaded from `~/.config/phone-migration/history.json`,
  filterable by status, with per-rule and per-file detail.
- **Documentation** — this reference material, served in-app.

### Run controls

The dashboard's **"Rename on Conflict" toggle ships on.** That is the opposite of
what a plain CLI `--run` does for backup rules, which skip on conflict. A backup
rule started from the dashboard will rename duplicates unless you untick the
toggle first. Move and copy rename either way. See the conflict table in
[docs/OPERATIONS.md](docs/OPERATIONS.md#conflict-resolution-summary).

Runs are one-at-a-time: starting a second while one is in flight is refused with
`409 A run is already in progress`.

### Run history

`~/.config/phone-migration/history.json` keeps the **100 most recent runs**,
newest first, written atomically so an interrupted save cannot truncate it. Each
entry holds the timestamp, profile, success or failure, the per-rule statistics,
the per-file listings and the run's log lines. It is loaded when the server
starts. `GET /api/history?limit=N` reads it back, with `N` clamped to 1-100
(default 10).

### Folder browser and bookmarks

For desktop paths the browser starts in your home directory; navigate with
breadcrumbs or the Up button, type a path directly, toggle hidden entries, and
create a new folder. For phone paths the phone must be connected and unlocked.
Files are listed for context but only directories can be selected. Folder
bookmarks are saved to `~/.config/phone-migration/bookmarks.json`, also written
atomically.

**Desktop paths are confined to `$HOME`, `/media`, `/mnt` and `/run/media`.**
That applies to folder browsing, to creating a folder, to saving a desktop
bookmark, and to the `desktop_path` you store on a rule — a rule is a path the
runner writes to later, so it is checked when it is stored, not only when it is
browsed. Anything outside those four roots is refused with
`403 Path is outside the allowed directories: <path>`. That message means a
deliberate refusal, not a typo — whereas `404 Directory not found` means the path
really is missing, and `400 Invalid path` means it could not be resolved at all
(an embedded NUL, or a `~user` with no such user).

### Scripting the HTTP API

The API has no auth token. Two rules stand in for one, and the first applies to
**every** request, including GET:

1. **The request must arrive with a `Host` the server answers to** — bare
   `localhost`, `127.0.0.1` or `[::1]`, plus `127.0.0.1:8080` and
   `localhost:8080` for the port actually bound. Note that `[::1]:8080` is *not*
   on the list. Anything else is `403 {"error": "Bad host"}`. This is what stops
   a DNS name rebound to `127.0.0.1` from reaching a server bound to loopback —
   so a `curl` through such a name is refused even on a plain GET.
2. **Every request other than GET, HEAD and OPTIONS must be same-origin.**
   Browsers set `Sec-Fetch-Site: same-origin` automatically, so the UI itself
   just works, but a request from `curl` needs the header spelled out, or an
   `Origin` whose host matches. Otherwise the answer is
   `403 {"error": "Cross-origin request refused"}`.

```bash
# GET: only the Host rule applies
curl http://127.0.0.1:8080/api/status

# Anything mutating: Host *and* the same-origin header
curl -X POST http://127.0.0.1:8080/api/run \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'Content-Type: application/json' \
  -d '{"dry_run": true}'
```

Note that `POST /api/run` defaults `dry_run` to `false` — the opposite of the
CLI. Pass `"dry_run": true` explicitly when you only want a preview. Omitting
`rename_duplicates` entirely leaves each mode's own default in place; sending it
as a bool overrides every mode.

`GET /api/run/status` returns the run's **structured result** — `running`,
`progress`, the log lines, and a `result` object carrying the stats, the per-rule
outcomes and the per-file actions. Nothing in the UI parses the log text to work
out what happened, so rewording a CLI output line cannot break the dashboard.

### Registering a device

There is no `/api/device/register`. `GET /api/device/detect` lists connected
phones, and registration is:

```bash
curl -X POST http://127.0.0.1:8080/api/profiles \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'Content-Type: application/json' \
  -d '{"name": "default", "device_id": "<mtp_id from /api/device/detect>"}'
```

A phone that exposes no MTP serial is listed by `/api/device/detect` but
**cannot** be registered: the route answers
`400 Device exposes no serial number; cannot register it reliably`, for the same
reason the CLI refuses it.

### Running the hardware test suite

`POST /api/tests/run` starts `tests/test_edge_cases.py` as a subprocess and
streams its output to `GET /api/tests/status`. **This is not a dry run.** That
script performs real file operations on the connected phone and on the desktop,
and it reads and rewrites your real `~/.local/share/phone-migration/state.json`
— do not trigger it in the middle of a backup you care about resuming. It needs
a connected device (`400` otherwise) and video files you supply yourself in
`tests/videos/`; see [tests/README_TESTS.md](tests/README_TESTS.md). Being a
POST, it sits behind the same host and same-origin guards as every other
mutating route, and a second start while one is running is refused with `409`.

## Examples

### Archive all photos off the phone

```bash
phone-sync --add-device --name default

phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
phone-sync --move -p default -pp /DCIM/Screenshots -dp ~/Pictures/Screenshots

phone-sync --run          # preview first
phone-sync --run -y       # then transfer
```

### Keep workout videos mirrored onto the phone

```bash
phone-sync --sync -p default -dp ~/Videos/Workouts -pp /Videos/Workouts
phone-sync --run -y
```

### Resumable backup of a large folder

```bash
phone-sync --backup -p default -pp /DCIM -dp ~/Backups/Phone/DCIM --manual
phone-sync --run -r r-0004 -y
# interrupted? run the same command again - it resumes
```

### Two phones, one config

```bash
phone-sync --add-device --name personal
phone-sync --add-device --name work

phone-sync --move -p personal -pp /DCIM/Camera -dp ~/Pictures/personal
phone-sync --move -p work     -pp /DCIM/Camera -dp ~/Pictures/work

# Plug in either phone; the matching profile is selected by serial number
phone-sync --run -y
```

## Troubleshooting

### Phone not detected

```bash
gio mount -li | grep -i mtp          # is it mounted?
lsusb | grep -i android              # is it on the bus?
systemctl --user list-units | grep gvfs
```

- Unlock the phone and keep it unlocked.
- Select "File Transfer" mode in the phone's USB notification.
- Reconnect; try a different cable (many are charge-only).
- Restart GVFS: `systemctl --user restart gvfs-daemon`
- Close any file manager that has the phone open — see
  [One application at a time](#one-application-at-a-time).

### "Device exposes no serial number; cannot register it reliably"

`--add-device` refuses phones that do not publish an MTP serial. A profile
without a serial would match *every* serial-less phone plugged into this
machine, which is how rules end up running against the wrong device and
deleting the wrong files — so registration is refused instead.

Some phones only publish a serial once the USB mode is fully settled. Unlock the
phone, re-pick "File Transfer" in the USB notification, unplug and replug, then
retry. If the serial never appears, the device cannot be used with this tool.

### Profile not matching

```bash
phone-sync --check --verbose
cat ~/.config/phone-migration/config.json | jq .
```

A registered phone matches on `device.id_value`. If the serial changed (a
factory reset can do this), re-register with `--add-device --name <profile>`.

### Permission errors

```bash
groups
ls -la ~/Pictures/Camera
```

The tool runs entirely as your user; it never needs root.

### Copy failures

- **Disk full** — the preflight check reports the deficit and skips the rule.
- **Phone locked** — MTP stalls the moment the screen locks.
- **Timeouts** — a single `gio copy` is given one hour; listing operations get
  60 seconds. A timeout is reported as an error, and nothing is deleted.
- **Size mismatch** — if the copy that arrives is not the same size as the
  source, the file is reported failed and, in a move rule, the original stays on
  the phone.

### Sync deleted something unexpected

- Run without `-y` first — a dry run prints every deletion it would make, then
  analyzes the preview for exactly this class of mistake.
- Check that `desktop_path` is the folder you meant: in sync mode it is the
  source of truth, and the phone side is made to match it.
- `delete_extraneous` has its own refusals; see [Safety](#safety).

### Web UI will not start

- `Error: port 8080 still in use; nothing started` — something already holds the
  port. `phone-sync --web --stop` if it is a previous instance of this tool.
- `phone-sync --web --stop` exiting `1` means the process ignored the signal and
  is still running; the pid file is deliberately kept so you can kill it by hand.
- Background start failures are logged to
  `~/.local/state/phone-migration/web.log`.
- `ModuleNotFoundError: No module named 'flask'` — run
  `pip install -r requirements-web.txt`.

## Safety

- **Dry run is the default.** `--run` previews; only `-y` transfers.
- **Every real run is preflighted.** A rule whose transfer would not fit on the
  destination with 5% to spare is skipped before it starts.
- **Move verifies before deleting.** A file is deleted from the phone only after
  the desktop copy exists and its size matches the source. If the source size
  cannot be read, the copy is kept and the original is left on the phone.
- **Sync fails closed on a bad desktop path.** If `desktop_path` is not a
  directory the rule errors out immediately and nothing is copied or deleted.
- **Sync refuses to delete blindly.** With `delete_extraneous: true`, deletion is
  skipped entirely — with a warning, while the copying half still runs — when the
  desktop scan hit any unreadable entry (a broken symlink, or a symlinked
  directory that loops back into the tree already walked), when the scan found no
  files at all, or when the phone path is the storage root. A partial scan never
  becomes a mass deletion.
- **Backup never deletes anything**, on either side.
- **Keep backups** of anything irreplaceable, and test a new rule against a small
  folder first.
- **No root.** The tool runs as a regular user.

## Performance notes

- MTP is substantially slower than USB mass storage; large files take time.
- Keep the phone unlocked and awake for the duration of a transfer.
- Avoid heavy phone use during a run.
- For very large trees, prefer a `backup` rule: it is resumable, so an
  interrupted transfer does not start over.

## Documentation

- [docs/OPERATIONS.md](docs/OPERATIONS.md) — what each of the four rule modes
  does to your files, with the exact conflict and deletion rules
- [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) — the CLI palette and icon set
- [docs/warp.md](docs/warp.md) — quick reference for Warp Terminal users
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — version history
- [docs/TODO.md](docs/TODO.md) — known gaps and planned work
- [tests/README_TESTS.md](tests/README_TESTS.md) — how to run the test suites
- [docs/archive/](docs/archive/) — superseded documents, kept for reference

## License

A personal tool. Use at your own risk.
