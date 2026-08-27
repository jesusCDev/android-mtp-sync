# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

Two independent lines of work land in this release: a **web UI generation**
(modal dialogs, a softer palette, the run page folded into the dashboard, a
preflight disk-space check, a dry-run safety analyzer and a progress display),
and a **review pass over the whole tool**. The headline behavior change from the
review is that dry run is now genuinely side-effect free and **`--run` without
`-y` transfers nothing**, plus the rename of Smart Copy to Backup.

---

# Review pass

### Renamed

- **Smart Copy is now Backup.** The CLI flag is `--backup`, the rule mode is
  `"backup"`, and the web UI labels it "Backup".
  - `--smart-copy` remains as a **deprecated alias** and still works.
  - Existing rules stored with `"mode": "smart_copy"` still run, as backups. No
    config migration is needed.
  - The old "smart comparison" claim is gone from the docs. Backup skips a file
    on one condition: the desktop already holds a file at that relative path
    with the same size. There is no hashing and no timestamp comparison, and the
    state file is not consulted for this decision — it only decides whether a
    size mismatch is overwritten or treated as a conflict.

### Security

- **Removed the CORS wildcard** from the web UI. The API has no auth token;
  instead every non-GET request must be same-origin. Browsers send
  `Sec-Fetch-Site: same-origin` automatically; scripted clients must set it (or a
  matching `Origin`) or receive `403 Cross-origin request refused`. `flask-cors`
  is no longer a dependency — `requirements-web.txt` is now Flask only.
- **Rejected rebound hosts.** The origin guard checked how a request related to
  the host but never the host itself, so a DNS name rebound to `127.0.0.1` was
  legitimately same-origin. The `Host` header is now checked first, on every
  method, against `localhost`, `127.0.0.1`, `[::1]` and the host:port actually
  bound; anything else is `403 Bad host`.
- **Confined every desktop path** to `$HOME`, `/media`, `/mnt` and
  `/run/media` — browsing, folder creation, and the `desktop_path` stored on a
  rule. Rules previously stored the path unchecked, which made the browse
  confinement decorative, since the runner writes to that path later. All three
  callers now share one resolver: refusals are `403 Path is outside the allowed
  directories`, and an embedded NUL is a `400` instead of a `500` traceback.
- **Stopped injecting untrusted strings into the DOM.** File names, paths and
  error text from a run are set as text, not parsed as HTML.
- **Percent-encode every path segment** appended to an MTP URI, so a file named
  with a `#`, a space or a `?` addresses the file it names.
- **`gio` is invoked by absolute path** (`/usr/bin/gio`) rather than resolved
  through `PATH`.

### Data safety

- **Move never deletes without a verified copy.** A file is removed from the
  phone only after the desktop copy exists and its size matches the source. If
  the source size cannot be read, the copy is kept and the original is left on
  the phone.
- **Sync refuses to delete on an incomplete picture.** With
  `delete_extraneous: true`, deletion is skipped — with a warning, while copying
  still proceeds — when the desktop scan hit an unreadable entry, when the scan
  found no files at all, or when the rule's phone path is the storage root.
  Separately, a `desktop_path` that is not a directory now fails the rule
  outright: nothing is copied and nothing is deleted.
- **`gio` failures are now loud.** A failed directory listing raises instead of
  being read as "the directory is empty", which previously let a transient MTP
  error look like a folder full of extraneous files.
- **Backup defaults to skip-on-conflict.** A plain `--run` no longer flips
  existing backup rules into rename-and-copy, which would have duplicated the
  whole archive on every run. Move and copy still rename by default. Note this
  is the CLI default only: the dashboard's "Rename on Conflict" toggle ships
  **on**, so a backup rule started from the web UI renames unless it is
  unticked.
- **Backup overwrites its own stale output.** On resume, a desktop file this
  rule wrote earlier whose size no longer matches the phone's copy is replaced;
  the phone is the source. Files this rule did not write are never overwritten.
- **Resume state is keyed per profile**, `"<profile>:<rule id>"`, so two phones
  with a rule `r-0001` each no longer share one backup state.
- **Config and state are written atomically.** An interrupted write no longer
  leaves a truncated `config.json`, and a corrupt state file is renamed
  `state.json.corrupt` with a warning rather than silently reset.
- **A phone with no MTP serial cannot be registered** — a serial-less profile
  would match every serial-less phone. `--add-device` now fails with
  `Device exposes no serial number; cannot register it reliably`.
- **A volume and its own mount are treated as one phone**, so a single connected
  device is no longer reported as two.
- **An empty `desktop_path` is rejected** instead of silently resolving to the
  current working directory.
- **Sync guards against symlink loops.** A symlinked desktop directory that leads
  back into a directory the scan already walked is detected by inode and not
  followed again, and the scan is marked incomplete so no phone-side deletion
  follows from it.
- **`state.json` is locked.** Every read-modify-write happens under an exclusive
  `fcntl` lock on `~/.local/share/phone-migration/state.lock`, so concurrent runs
  cannot drop each other's backup progress.

### Dry run

- **Dry run is side-effect free.** No directories are created, no state file is
  written, and no `gio` mutation is issued while previewing.
- **Dry run is no longer sticky.** The flag is assigned per run, so a preview
  followed by an execute in the same process actually executes.
- **`--run` previews by default; `-y` (or `--yes` / `--execute`) transfers.**
  The `--dry-run` flag never existed and has been removed from the docs.

### CLI

- **One theme module.** All colors and icons live in `phone_migration/theme.py`;
  no other module defines a palette or an ANSI literal. Three competing palettes
  used to ship in one CLI.
- **No emoji in output.** Icons are Nerd Font glyphs with single-width unicode
  fallbacks, switchable with `NERD_FONT=1` and `PHONE_SYNC_PLAIN_ICONS=1`.
  `NO_COLOR` (or a non-TTY stdout) disables color.
- **XDG paths.** Config moved to `~/.config/phone-migration/config.json`, resume
  state to `~/.local/share/phone-migration/state.json`, and the web UI's pid file
  and log to `~/.local/state/phone-migration/`. A config left in the old
  in-checkout location is copied to the XDG path once, with a printed note; the
  original is not deleted.
- **`--web --background` and `--web --stop`** manage the server through a pid
  file. `--stop` now exits `1` and keeps the pid file when the process survives,
  instead of reporting success and discarding the only handle on it. Starting
  refuses to proceed when port 8080 is already held, including by a bound but
  non-accepting listener.
- **`--notify`** sends a desktop notification on completion, and is skipped for
  dry runs.

### Web UI

- **The UI no longer parses CLI text.** Runs return a structured result — stats,
  per-rule outcomes and per-file actions — and the dashboard renders that. Log
  lines are display-only, so rewording an output line can no longer break the UI.
- **"Backed up" counts copies only.** Files that were already backed up are
  reported separately as resumed, instead of being added into the copied total.
- **"Include manual rules"** replaces the old "run manual rules" wording: the
  option runs every rule, not only the manual ones.
- **Run history** lives at `~/.config/phone-migration/history.json`, capped at
  the 100 most recent runs, written atomically, and now stores the structured
  per-rule file lists alongside the log lines.
- **A failed run no longer wedges the UI.** The worker clears its `running` flag
  under the lock before persisting history, so an error while saving no longer
  left the flag set and every later run stuck behind a permanent `409`.
- **Alerts show on every page.** The alert container moved to the base template;
  it previously existed only on the dashboard and rules pages, so errors raised
  on Profiles and History were silently swallowed.
- **`POST /api/device/register` is gone.** Registering the connected phone from
  the web UI is `POST /api/profiles {"name", "device_id"}`, with `device_id` the
  `mtp_id` from `GET /api/device/detect`. A phone with no MTP serial is listed
  but refused with `400 Device exposes no serial number; cannot register it
  reliably`, matching the CLI.
- **Folder bookmarks** moved to `~/.config/phone-migration/bookmarks.json` —
  the same default path as before, now derived from `XDG_CONFIG_HOME` and written
  atomically. Saving a desktop bookmark is path-confined like every other desktop
  path.
- **Backup rules are visible on the Rules page.** They previously did not render,
  which also made them undeletable from the UI.
- **The DRY RUN badge is a fact, not a guess.** It comes from the run's own
  result instead of a substring match on the log text.
- **`POST /api/tests/run`** starts the hardware edge-case script against the
  connected phone. It performs real file operations, so it sits behind the same
  host and same-origin guards as every other mutating route, refuses to start
  without a device (`400`) or while already running (`409`).

### Docs

- Every documented command that transfers now shows `-y`, and the fact that a
  bare `--run` only previews is stated up front.
- Removed the nonexistent `--dry-run` and `--no-rename` flags, the nonexistent
  per-rule rename setting, and the dead `"overwrite"` sync-rule field.
- Documented the previously undocumented `--check`, `--copy`, `--backup`,
  `--browse-phone`, `-r/--rule-id`, `--manual`/`--no-manual`, `--notify`,
  `--web --background`/`--stop`, and the `NO_COLOR`, `NERD_FONT` and
  `PHONE_SYNC_PLAIN_ICONS` environment variables.
- Stated that the CLI is standard library only and that `--web` needs
  `pip install -r requirements-web.txt` (Flask alone).
- `docs/DESIGN_SYSTEM.md` now derives its palette table from `theme.py`, with
  contrast ratios recomputed against the `#0D0E16` background, and documents the
  icon set in both its Nerd Font and plain forms. `MUTED` was lightened to
  `#7C8399` to clear WCAG AA, which it previously did not.
- Sample outputs are captured from the real CLI.
- `warp.md` lost its fabricated example session, its `--dry-run` examples and its
  wrong repository paths, and moved to `docs/warp.md`.
- `tests/README_TESTS.md` no longer documents a `tests/test_e2e_operations.py`
  that does not exist; it now names the three suites that do.

### Tests

- Added `pyproject.toml` with pytest configuration, replacing a `sys.path` hack.
- Tests are isolated from the real config and state files.
- Added a source scan that fails when any `Colors.X` or `Icons.X` referenced
  anywhere does not exist, a WCAG contrast assertion for every text color, and an
  emoji sweep over the CLI, web UI, templates and JS.

### Repository

- **Test videos are no longer in the repository.** `tests/videos/` was removed
  and is gitignored; the hardware test script expects you to drop your own files
  there. Nothing in the pytest suite needs them.
- **Documentation moved under `docs/`.** `CHANGELOG.md`, `TODO.md`,
  `CLEANUP_SUMMARY.md` and `warp.md` left the repository root; `README.md`
  stayed. `docs/RULE_MODES.md` is now `docs/OPERATIONS.md`.

---

# Web UI generation

This section predates the Smart Copy to Backup rename and refers to backup rules
by their old name.

### Added
- **Web UI - Operation Details Modal**: Click "Expand" on any operation card to view detailed file-level information
  - **Command View**: Shows the exact command that was/will be executed with color-coded syntax
  - **Detail View** (for Move/Copy/Smart Copy): Lists individual files being copied, deleted, or skipped
  - **Sync Summary**: Displays sync operation statistics (files synced, skipped, cleaned)
- **Per-Operation Expand Buttons**: Each operation card now has an individual expand button for detailed inspection
- **Verbose Mode in Web UI**: Web UI now runs with `verbose=True` by default to show file-level details
  - Enables detailed file listings in operation modals
  - CLI remains unchanged (defaults to `verbose=False` for clean output)
- **Tab-Based Detail View**: Two-tab interface for detailed operation inspection
  - Tab A: Command View - Shows formatted command with color-coded flags and parameters
  - Tab B: Detail View - Lists files by category (Copying, Deleting, Skipped, Folders)
- **Modal Dialogs**: Full-screen modal for detailed operation inspection
  - Click outside or press Escape to close
  - Close button (X) in top-right corner

### Changed
- **Color Palette Update**: Replaced harsh colors with soft pastel tones
  - Accent: `#8B5CF6` → `#C8A2E0` (soft lavender)
  - Info: `#60A5FA` → `#9DD4FF` (soft sky blue)
  - Success: `#10B981` → `#8FD6B5` (soft mint green)
  - Warning: `#F59E0B` → `#FFD699` (soft peachy-gold)
  - Danger: `#EF4444` → `#FF9898` (soft coral red)
  - Overall theme: More pleasant and easier on the eyes
- **Run Page Removed**: Run Operations moved from separate `/run` page to dashboard (home page)
  - Streamlined navigation with single-page operation interface
  - Command preview and operations displayed in one place

### Removed
- **run.html**: Removed separate Run page template
- **run.js**: Consolidated functionality into dashboard.js
- **run.css**: Migrated styles to dashboard.css

### Technical Details
- **File Operation Parsing**: Improved parsing of CLI output to extract file-level details
  - Supports Move, Copy, Smart Copy, and Sync operations
  - Parses file paths with arrow symbols (→, ->, =>)
  - Extracts deletion markers (×) and skip indicators (⊙)
  - Shows folder operations with a folder marker
- **Log Storage**: Each operation stores its associated log lines for detailed inspection
- **Modal Management**: Modals use data attributes to store operation data and logs for inspection

### Web UI Improvements
- **Dashboard Consolidation**: All run operations now on the main dashboard
- **Enhanced Command Preview**: 
  - Shows exact command that will execute
  - Color-coded syntax highlighting
  - Warning indicator for execute mode vs. dry-run
- **Operation Cards**: Each rule execution shows in a separate, expandable card
- **Responsive Design**: Modal adapts to screen size

### User Experience
- Users can now preview exactly what files will be affected before running operations
- Detailed file lists help verify sync/move/copy operations are correct
- Soft color palette reduces eye strain during extended use
- Cleaner UI with removed Run page

## [Previous versions]

See the git history.
