# Plan: fix all review findings

Spec: `tasks/review-2026-08-26.md` (binding authority; finding numbers below refer to it).
Branch: `fix/review-findings`. Base commit: the "wip: palette rewrite" commit.

## Global Constraints

- **TDD.** Every behavior change gets a failing test first (`pytest tests/`), then the fix. Report RED/GREEN evidence.
- **Python 3.10+**, stdlib only for the CLI. Web UI: Flask only (`flask-cors` is removed).
- **No emoji anywhere** in CLI output, notifications, docs code samples, or JS. Icons come only from `phone_migration.theme.Icons`; colors only from `phone_migration.theme.Colors`. No other module defines a `Colors` class or ANSI literal.
- **Nothing parses CLI text.** Web UI and JS consume the structured `RunResult` (below). Log lines are display-only.
- **Dry run is side-effect free.** Under `gio_utils.DRY_RUN`, no directory creation, no state file writes, no gio mutation. `DRY_RUN` is assigned unconditionally per run (`gio_utils.DRY_RUN = dry_run`).
- **URIs:** every path segment appended to an MTP URI is `urllib.parse.quote(name, safe="")`-encoded via `gio_utils.child_uri(parent, name)`.
- **gio failures raise `gio_utils.GioError`**; callers never treat a failed listing as "empty".
- **Minimal diffs.** Root-cause fixes at the shared function, not per caller. Mark deliberate ceilings with `# ponytail: <ceiling>, <upgrade path>`.
- **Deletions of untracked files are NOT done by implementers** (`COLOR_REFERENCE.txt`, `phone_migration/resources/`). Moving with `mv`/`git mv` is fine.
- Commit per task with a conventional message (`fix:`, `feat:`, `refactor:`, `test:`, `docs:`), body ending `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Shared Interfaces (all tasks build against these)

### `phone_migration/theme.py` (Task 1)

```python
class Colors:            # ANSI 24-bit "Deep Twilight Pastels"; all attrs are str
    RESET, BOLD, DIM, ITALIC, UNDERLINE
    ERROR, SUCCESS, WARNING, INFO, ACCENT, MUTED        # MUTED must be >= 4.5:1 on #0D0E16 (use #7C8399 or lighter)
    MOVED, BACKED_UP, SYNCED, DELETED, SKIPPED, RENAMED
    HEADER, SEPARATOR, DEVICE_NAME, RULE_ID, PATH
    # every attribute is "" when NO_COLOR is set or stdout is not a TTY at import time

class Icons:             # single-width glyphs; nerd-font variant when NERD_FONT=1 or WEZTERM_PANE set,
                         # plain fallback when PHONE_SYNC_PLAIN_ICONS=1 or no nerd font detected
    OK, FAIL, WARN, INFO, BULLET, ARROW, PHONE, FOLDER, FILE,
    MOVE, COPY, SYNC, DELETE, SKIP, RENAME, BOLT, SEARCH, STATS
```

Nerd-font codepoints (Font Awesome range, stable across Nerd Fonts v2/v3) and plain fallbacks:

| name | nerd | plain |
|---|---|---|
| OK | `` | `✓` |
| FAIL | `` | `✗` |
| WARN | `` | `⚠` |
| INFO | `` | `▸` |
| BULLET | `` | `•` |
| ARROW | `` | `→` |
| PHONE | `` | `▪` |
| FOLDER | `` | `▸` |
| FILE | `` | `•` |
| MOVE | `` | `↑` |
| COPY | `` | `+` |
| SYNC | `` | `⇄` |
| DELETE | `` | `✗` |
| SKIP | `` | `-` |
| RENAME | `` | `~` |
| BOLT | `` | `!` |
| SEARCH | `` | `?` |
| STATS | `` | `#` |

Numbered steps in help text use plain `1.` `2.` `3.` — never `①`.

### `phone_migration/gio_utils.py` (Task 2)

```python
class GioError(RuntimeError): ...          # message = first non-empty stderr line (or "timeout after Ns")
GIO = "/usr/bin/gio"                        # never bare "gio"
TIMEOUT_SHORT = 60                          # list/info/remove/mkdir/mount
TIMEOUT_COPY = 3600                         # copy
DRY_RUN = False

def run(args, check=True, timeout=TIMEOUT_SHORT) -> CompletedProcess   # TimeoutExpired -> GioError
def child_uri(parent_uri: str, name: str) -> str                       # rstrip("/") + "/" + quote(name, safe="")
def gio_list(uri) -> list[str]                                         # raises GioError on failure (incl. missing dir)
def gio_list_detailed(uri) -> list[dict]                               # one `gio list -a standard::type,standard::size`;
                                                                        # [{"name": str, "is_dir": bool, "size": int|None}]
def gio_info(uri, attributes=None) -> dict                             # {} only when gio says the file does not exist;
                                                                        # any other failure raises GioError
def is_dir(info: dict) -> bool                                         # standard::type in ("directory", "2")
def get_file_size(info) -> int | None
def gio_copy(src, dst, recursive=False, verbose=False) -> bool         # NO overwrite param (gio copy already overwrites);
                                                                        # on failure prints "{Icons.FAIL} name: <stderr>" and returns False
def gio_remove(uri, verbose=False) -> bool
def gio_mkdir(uri, parents=True) -> bool
def gio_mount(activation_uri) -> None                                  # best-effort, swallows GioError
```

### `phone_migration/state.py` (Task 3)

All functions take `state_key: str` (callers pass `f"{profile_name}:{rule_id}"`). Existing API names kept: `load_rule_state`, `save_rule_state`, `mark_rule_complete`, `has_resume_state`, `get_state_summary`, `get_remaining_files`. `mark_file_copied`/`mark_file_failed` are removed; Task 4 batches via `save_rule_state` (called every 25 files and at the end). `failed` is a `dict[str, str]` (path -> last error) on disk and in memory. Corrupt state file is renamed `state.json.corrupt` with a warning; never silently reset.

### `RunResult` (Task 6 produces, Task 7 consumes)

`runner.run_for_connected_device(...) -> dict`:

```python
{
  "dry_run": bool,
  "profile": str | None,            # None => no device / no profile matched
  "device": str | None,             # display_name
  "stats": {"copied", "renamed", "deleted", "errors", "skipped", "moved", "synced", "backed_up", "resumed", "folders"},   # ints
  "transfer": {"size_bytes": int, "seconds": float} | None,
  "rules": [
    {"id": str, "mode": str, "phone_path": str, "desktop_path": str,
     "stats": {...same keys as the op returns...},
     "error": str | None,
     "files": [ {"action": "copied|moved|synced|deleted|skipped|renamed|failed|folder", "src": str, "dst": str | None, "error": str | None} ]}
  ]
}
```

Each `operations.run_*_rule` returns its stats dict **plus** `"files": list` in the same per-file shape (Task 4). `src`/`dst` are display strings (phone path relative to the rule root, desktop path as `~/...`).

### `operations.run_*_rule` signatures (Task 4)

```python
run_copy_rule(rule, device, verbose=False, transfer_tracker=None, rename_duplicates=True) -> dict
run_move_rule(rule, device, verbose=False, transfer_tracker=None, rename_duplicates=True) -> dict
run_backup_rule(rule, device, verbose=False, transfer_tracker=None, rename_duplicates=False, profile_name="") -> dict
run_smart_copy_rule = run_backup_rule        # alias, forwards every argument
run_sync_rule(rule, device, verbose=False, transfer_tracker=None) -> dict      # rename_duplicates removed (sync source of truth = desktop)
```

---

## Task 1: Test infrastructure + theme module

Files: `pyproject.toml` (new), `tests/test_operations.py` (3 drift fixes only), `phone_migration/theme.py` (new), `tests/test_theme.py` (new), `scripts/color_demo.py` (moved from root `test_colors.py` via `mv`, then rewritten to import `theme`).

- [x] `pyproject.toml`: `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`. Delete the `sys.path` hack in `tests/test_operations.py:13-14`.
- [x] Fix the three drifted tests so the suite is green **without touching production code**:
  - `@patch('phone_migration.gio_info')` → `@patch('phone_migration.gio_utils.gio_info')`.
  - `test_sync_with_rename_duplicates_false_skips_conflicts`: delete it (Task 4 removes the flag from sync and writes real sync tests).
  - `test_smart_copy_tracks_progress`: mocked `load_rule_state` must return `{"copied": set(), "failed": [], "total_files": 0}`.
- [x] `theme.py` per the Shared Interfaces table. Detection at import: `PLAIN = os.environ.get("PHONE_SYNC_PLAIN_ICONS") == "1"`; `NERD = not PLAIN and (os.environ.get("NERD_FONT") == "1" or "WEZTERM_PANE" in os.environ)`; colors blank when `"NO_COLOR" in os.environ or not sys.stdout.isatty()`.
- [x] `tests/test_theme.py` (TDD):
  - every `Colors.X` / `Icons.X` referenced anywhere under `phone_migration/` and `main.py` exists on the class (regex scan of source files — this is the test that would have caught the `Colors.RED` crash);
  - every text color (`ERROR SUCCESS WARNING INFO ACCENT MUTED DEVICE_NAME RULE_ID PATH HEADER`) has WCAG contrast >= 4.5:1 against `#0D0E16` (compute from the `38;2;r;g;b` triple);
  - `PHONE_SYNC_PLAIN_ICONS=1` yields the plain set; `NERD_FONT=1` yields the nerd set (reload the module under `monkeypatch.setenv`);
  - `NO_COLOR=1` blanks every color.
- [x] `scripts/color_demo.py`: `from phone_migration.theme import Colors, Icons`; prints the palette. No `Colors` class of its own. Not collected by pytest.

Verify: `python3 -m pytest -q` green, `python3 scripts/color_demo.py` runs.

## Task 2: gio_utils + paths

Files: `phone_migration/gio_utils.py`, `phone_migration/paths.py`, `tests/test_gio_utils.py` (new), `tests/test_paths.py` (new), plus the mechanical call-site updates in `operations.py` / `browser.py` / `runner.py` needed to keep the suite green (`gio_copy(..., overwrite=...)` → drop the kwarg; nothing else in those files).

Findings: #6 #7 #8, gio_utils.py:49,98,175,182,184, paths.py:23,60,103,110,132,155, operations.py:92 (helper only), browser.py:46, runner.py:209 (bare `gio`).

- [x] Implement the `gio_utils` interface above. `run()` uses `subprocess.run([...], capture_output=True, text=True, timeout=timeout)`; `TimeoutExpired` → `GioError(f"timeout after {timeout}s: {' '.join(args[:3])}")`.
- [x] `gio_list` raises `GioError` on non-zero rc. `gio_info` returns `{}` only if stderr contains `No such file or directory` / `not found` (case-insensitive); otherwise raises.
- [x] `gio_copy`: remove `overwrite` (and the `--backup=none` flag). Print the success line **after** `run()` succeeds. On failure print `f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} {name}: {err}"` and return False.
- [x] `gio_list_detailed` parses `gio list -a standard::type,standard::size <uri>` output (`name\t<size>\t(<type>)\tstandard::type=2 standard::size=123`) — read the real format with a local dir first; write the parser test from a captured sample.
- [x] Remove the `Colors` class from `gio_utils.py`; import from `theme`.
- [x] `paths.expand_desktop("")` / whitespace-only → `ValueError("desktop_path is empty")`.
- [x] `paths.normalize_phone_path`: drop `.`/`..`/empty segments; storage-label prefix match is separator-aware (`"Internal storage"` alone == label, no double label); `build_phone_uri` quotes the storage label too.
- [x] `paths.next_available_name` → `Optional[Path]`; returns `None` after 1000 candidates (no `RuntimeError`); uses `Path.stem`/`Path.suffix` so `.bashrc` → `.bashrc (1)`.
- [x] Tests (TDD, real subprocess where cheap — `gio` exists on this box and works on `file://` URIs of a `tmp_path`): `gio_list` on a missing dir raises; `gio_info` on a missing file returns `{}`; `child_uri("mtp://x/a", "b c#d.jpg") == "mtp://x/a/b%20c%23d.jpg"`; `gio_list_detailed` on a tmp dir with a file and a subdir; timeout path via a monkeypatched `subprocess.run` raising `TimeoutExpired`; every `paths` fix above.

## Task 3: state + config

Files: `phone_migration/state.py`, `phone_migration/config.py`, `tests/test_state.py` (new), `tests/test_config.py` (new). Also `phone_migration/runner.py:123` debug-hint path string only.

Findings: #9 #26 #27, state.py:37,40,100,127,134, config.py:10,33,65,85,217-225,273-284.

- [x] `state.py`: per Shared Interfaces. `_save_state_file`: `tempfile.NamedTemporaryFile(dir=STATE_DIR, prefix="state.", suffix=".tmp", delete=False)` → write → `flush()` + `os.fsync()` → `os.replace()`. `_load_state_file`: on `json.JSONDecodeError`, rename to `state.json.corrupt` (overwrite an older `.corrupt`), print a `Colors.WARNING` line, return `{}`. Failed entries: `dict[path, error]`, `save_rule_state(state_key, copied: set, failed: dict, total_files: int)`. All reads use `.get`.
- [x] `config.py`: `CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "phone-migration"`. `LEGACY_CONFIG_FILE = Path.home() / "Programming" / "project-cli" / "phone-migration" / "config.json"`. `load_config()`: if `CONFIG_FILE` missing and `LEGACY_CONFIG_FILE` exists → copy it to `CONFIG_FILE` once and print one `Colors.INFO` line saying so. `save_config` uses the same tmp+fsync+`os.replace` pattern (extract a shared `_atomic_write_json(path, data)` in `state.py`? No — put it in `config.py` and have `state.py` import it; one copy). `add_profile`: `config.setdefault("profiles", []).append(profile)`.
- [x] `config.py`: delete both private color palettes; import `Colors`, `Icons` from `theme`; replace the emoji in `list_profiles`/`list_rules` with `Icons.*`.
- [x] `runner.py:123` debug hint prints `cfg.CONFIG_FILE` instead of the hardcoded `~/.config/...` string (one-line change; the rest of runner is Task 6).
- [x] Sync rules: `add_sync_rule` keeps writing `delete_extraneous: True` explicitly (existing behaviour); nothing else in config changes semantics.
- [x] Tests (TDD, `tmp_path` + `monkeypatch.setattr(state, "STATE_FILE", ...)` / `monkeypatch.setattr(cfg, "CONFIG_FILE", ...)`): corrupt state file → renamed + `{}`; save is atomic (no `.tmp` left, content round-trips); two state keys don't clobber; failed dict dedupes by path; legacy config migration copies once; `save_config` leaves no tmp file; `add_profile` on `{}` works; `find_profile_by_device_id` still works; `edit_rule` can set `manual_only` False.

## Task 4: operations.py

Files: `phone_migration/operations.py`, `tests/test_operations.py` (rewrite).

Findings: #2 #3 #4 #5 #6 #29, operations.py:58,92,109,120,193,234-302,249,323,408,538,543,570,587,621,632,649,679,690, runner.py:292 (semantic).

Design: one fake gio layer for tests — `tests/fake_gio.py` with an in-memory tree `{uri: bytes | dict}` and functions matching `gio_utils.gio_list/gio_list_detailed/gio_info/gio_copy/gio_remove/gio_mkdir` that operate on it; tests `monkeypatch.setattr(gio_utils, name, fake)`. Desktop side uses real `tmp_path`. No `MagicMock` return-value soup; assert on the tree and the filesystem.

- [x] Delete the `Colors` class and `shorten_path` duplicate; import from `theme` / `gio_utils`.
- [x] Every URI join goes through `gio_utils.child_uri`. Directory check goes through `gio_utils.is_dir(info)`.
- [x] Dry-run gating: `paths.ensure_dir` and every `state.*` write only when `not gio_utils.DRY_RUN`. Under dry run count what *would* happen and append `files` entries the same way.
- [x] **Move:** verify `dest.exists() and dest.stat().st_size == source_size` (source size from the listing/info) before appending to `files_to_delete`. A 0-byte source verifies against a 0-byte dest. `_cleanup_empty_dirs` lists each subdir first and deletes only when `gio_list` returns `[]` (a `GioError` aborts that subdir, counted as error). No bare `except:` anywhere; catch `gio_utils.GioError`.
- [x] **Copy/Move:** an entry that is neither dir nor regular file (info `{}` after a failed lookup) increments `errors` and appends `{"action": "failed", ...}` — never silent.
- [x] **Backup:** `profile_name` param; `state_key = f"{profile_name}:{rule_id}"`. Keep `copied: set` and `failed: dict` in memory; `save_rule_state` every 25 files and once at the end (`# ponytail: flush every 25 files, per-file writes were O(n^2)`). Resume check compares `dest.stat().st_size == source_size`, not existence. Completion: `stats["failed"] == 0 and copied + skipped >= total_files` → `mark_rule_complete`; otherwise state persists and the run prints how many failed. Honour `rename_duplicates` as passed (default False); `run_smart_copy_rule = run_backup_rule`. Summary label for backup skips is "conflict, not copied", not "exist".
- [x] **Sync:** `src_dir.is_dir()` required (else `GioError`-style error counted, rule aborted). `delete_extraneous = rule.get("delete_extraneous", False)`. Refuse deletion (print a `Colors.WARNING` line, count nothing) when the desktop scan produced zero expected files. Copy when phone file missing **or** size differs (no `rename_duplicates`). Expected/actual names compared after `unicodedata.normalize("NFC", ...)`. Recurse into subdirs using `is_dir`.
- [x] Every op appends to `stats["files"]` per the `RunResult` shape.
- [x] Tests (TDD) — at minimum: copy single file lands with correct bytes; copy conflict with `rename_duplicates=False` skips and never calls copy; conflict with True writes ` (1)`; move deletes source only after size-verified copy; move with a truncated copy (fake copy writes fewer bytes) does NOT delete and counts an error; move 0-byte file verifies and deletes; names with `#`, `%`, spaces, parentheses round-trip; dry-run move/copy/backup creates no dirs, no state file, no deletes; backup resume skips previously-copied files by size; backup with all copies failing keeps state and reports failed; backup completes when `copied + skipped == total`; sync copies new + size-changed files; sync deletes extraneous only when enabled and the desktop scan is non-empty; sync refuses when desktop path is a file; sync recurses into phone subdirs; listing failure (`GioError`) counts an error rather than treating the dir as empty.

## Task 5: device + browser + notifications

Files: `phone_migration/device.py`, `phone_migration/browser.py`, `phone_migration/notifications.py`, `tests/test_device.py`, `tests/test_notifications.py`, `tests/test_browser.py` (new).

Findings: #14, device.py:33,52,127, browser.py:46,57,74, notifications.py:41,59,84.

- [x] `device.enumerate_mtp_mounts`: one device per `Mount(` line whose block/URI is `mtp://`; do not merge sibling mounts; capture `identifier`/`activation_uri` per mount.
- [x] `device.device_fingerprint`: serial from `gio info` attributes, else regex `r'mtp://[^/]+_([A-Za-z0-9-]+)/'`. **No** `identifier`/`usb_address`/`activation_uri` fallbacks: return `("", "")` when no serial. `register_current_device` raises `RuntimeError("Device exposes no serial number; cannot register it reliably")` in that case. `runner.detect_connected_device` (Task 6) skips such devices. Ruling recorded in ledger: phones without a serial are unsupported rather than mis-matched.
- [x] `browser.list_phone_directory`: one `gio_utils.gio_list_detailed` call, no per-entry `gio info`, no bare `except`, no bare `"gio"`. Remove its `Colors` class; use `theme`.
- [x] `notifications`: `notify-send` args gain `"--"` before title; narrow `except (FileNotFoundError, subprocess.SubprocessError)`; titles/bodies use words, no emoji.
- [x] Tests (TDD): `enumerate_mtp_mounts` parses a captured two-mount `gio mount -li` sample (write the sample into the test) into two devices; lowercase serial extracted; no-serial device → `("", "")` and `register_current_device` raises; `list_phone_directory` builds entries from a fake `gio_list_detailed`; `notify-send` argv contains `--` before a title starting with `-`.

## Task 6: runner + main

Files: `phone_migration/runner.py`, `main.py`, `tests/test_runner.py` (new), `tests/test_main.py` (new).

Findings: #1 #15 #16 #25, runner.py:96,101,102,175-265,203,209,248,252,292,316, main.py:91-119,157,174,208,221,233,239,289-311,339,353,367,405.

- [x] `runner.py`: delete the `Colors` class, import `Colors`, `Icons` from `theme`; no `Colors.RED/YELLOW/CYAN`; no emoji; no `'='*60` leftover.
- [x] `gio_utils.DRY_RUN = dry_run` unconditionally at the top of `run_for_connected_device`.
- [x] Rule filter: `rule_ids` → those ids; `include_manual=True` → all rules; else non-manual only. Docstring matches.
- [x] Per rule: build the `RunResult.rules[]` entry; unknown mode → `error = f"unknown mode {mode}"`, `errors += 1`, continue; exception → `error = str(e)`, `errors += 1`, continue (print with `Colors.ERROR`). Pass `profile_name` to backup; pass `rename_duplicates` through to backup (no hardcoded False); sync gets no `rename_duplicates`.
- [x] Totals: `backed_up += copied` only; `resumed` is its own key and its own summary line.
- [x] `detect_connected_device` skips devices whose fingerprint is `("", "")` with a `Colors.WARNING` line.
- [x] Mount via `gio_utils.gio_mount`.
- [x] Return `RunResult`. Summary printing unchanged in spirit but driven by the same dict; `notifications.notify_completion(result["stats"], dry_run)`.
- [x] `main.py`: help text uses `1.`/`2.` and `Icons`; `--run` passes `include_manual=args.manual`; `--edit-rule` accepts `--manual/--no-manual` (`argparse.BooleanOptionalAction`, `default=None`); `--backup` and `--smart-copy` share one block, `--smart-copy` prints a one-line deprecation warning; delete the dead `return 0`.
- [x] Web process management: PID file `Path(os.environ.get("XDG_STATE_HOME", Path.home()/".local"/"state")) / "phone-migration" / "web.pid"`. `--stop`: read pid, verify `/proc/<pid>/cmdline` contains `main.py` and `--web`, SIGTERM, wait up to 5 s for exit, remove pid file; no `pgrep`. `--web` (foreground or background): if the pid file points at a live matching process, stop it first and wait for the port to free (poll `socket.connect_ex` up to 5 s). `--background`: after `Popen`, poll the port up to 5 s; print the URL on success, else exit 1 with the child's stderr tail (capture stderr to `~/.local/state/phone-migration/web.log` instead of DEVNULL). Foreground writes the pid file itself and removes it on exit.
- [x] Tests (TDD): `run_for_connected_device` with monkeypatched `detect_connected_device` + fake `operations.run_*` returning canned stats → returns a `RunResult` with correct totals; `DRY_RUN` is reset to False on a non-dry run after a dry run; `include_manual` semantics; unknown mode counted as error; an op raising is counted and does not abort later rules; parser tests: `--run --dry-run` exits 2, `--edit-rule --no-manual` parses, `--run --manual` reaches runner with `include_manual=True` (mock runner); `--stop` with a pid file pointing at a non-matching cmdline does not signal (mock `os.kill`).

## Task 7: web UI (Flask + JS)

Files: `phone_migration/web_ui.py`, `phone_migration/static/js/{main,dashboard,history,profiles,rules}.js`, `phone_migration/web_templates/*.html` as needed, `requirements-web.txt`, `tests/test_web_ui.py` (new).

Findings: #10 #11 #12 #13 #17 #18 #19 #20 #21 #22 #23 #24, web_ui.py:19,46,218,241,269,350,356,361,401,433,442,494,521,581, dashboard.js:290,299,419,628,683,763,794, history.js:82, profiles.js:19,107, rules.js:40,64,93,100,123,133.

- [x] Remove `flask_cors` import/usage and drop it from `requirements-web.txt`. Add `@app.before_request` that, for methods other than GET/HEAD/OPTIONS, returns 403 unless `Sec-Fetch-Site` is `same-origin`/`none` or the `Origin` header's host equals `request.host` (and 403 when neither header is present).
- [x] `ALLOWED_ROOTS = [Path.home(), Path("/media"), Path("/mnt"), Path("/run/media")]`; `_safe_desktop_path(p) -> Path` resolves (`expanduser` + `realpath`) and raises `PermissionError` unless it is relative to one root. Used by `/api/browse/desktop` and `/api/folder/create` (which also rejects names containing `/` or equal to `.`/`..`). `/api/history` clamps `limit` to `1..100`.
- [x] `/api/run`: `_run_lock = threading.Lock()`; the handler sets `running=True` under the lock (409 if already running) **before** starting the thread. The thread wraps the run in `contextlib.redirect_stdout(_LineWriter(current_run_status["logs"]))` where `_LineWriter.write` appends completed lines (ANSI stripped) live. On exception the partial logs are kept. `current_run_status["result"] = RunResult` (or `None`). Status endpoint returns `{"running", "progress", "logs": list(copy), "result"}`; **no regex parsing**. History entries store `stats = result["stats"]`, `dry_run`, `status` (`"error"` if exception or `stats["errors"] > 0`), `logs`, `rules` (the `RunResult.rules` list).
- [x] `/api/device/register` calls `device.register_current_device(config, profile_name)` and saves. Add `PUT /api/profiles/<name>` accepting `{"name": new_name}` (rename; 409 on collision). Point `profiles.js` at `POST /api/device/register` for Add and the PUT for Edit; use `encodeURIComponent` on every path parameter (`rules.js:40`, `profiles.js:53,107`).
- [x] `if __name__ == "__main__": start_web_ui()` with `debug=False`.
- [x] `main.js`: `function escapeHtml(s)` (move from `rules.js:464`). Every interpolation of server data into `innerHTML` in dashboard/history/profiles/rules goes through it, or uses `textContent`. No inline `onclick="...'${name}'..."` — use `dataset` + `addEventListener`.
- [x] `dashboard.js`: build operation cards and the detail modal from `result.rules[].files` — delete `parseOperationLog` and all emoji/`[DRY RUN MODE` sentinel matching. DRY RUN badge from `result.dry_run`. Errors from `result.stats.errors`. Remove the undefined `isResultsExpanded`/`toggleResultsExpanded` handler.
- [x] `rules.js`: `modeOrder`, `getModeIcon`, `getModeLabel` include `backup` (label "Backup"); `smart_copy` renders as Backup too.
- [x] `history.js`: log preview via `textContent`; the file list from `entry.rules[].files`.
- [x] Tests (TDD, `app.test_client()`, config/history paths monkeypatched to `tmp_path`): POST without Origin/Sec-Fetch-Site → 403; POST with `Sec-Fetch-Site: same-origin` → not 403; `/api/browse/desktop?path=/etc` → 403; `?path=<tmp under home>` → 200 (monkeypatch `Path.home`); `/api/folder/create` with `..` in name → 400; second concurrent `/api/run` → 409 (monkeypatch runner to block on an `Event`); status after a fake runner returns → `result.stats` present, logs contain the printed line; `/api/history?limit=-1` → 1 entry max/clamped; `/api/device/register` with a monkeypatched `device.register_current_device` → 200 and profile saved; `PUT /api/profiles/x` renames. A JS smoke: `node --check` on every `static/js/*.js`.

## Task 8: docs

Files: `README.md`, `QUICKSTART.md`, `docs/RULE_MODES.md`, `CHANGELOG.md`, `docs/DESIGN_SYSTEM.md` (moved from root with `mv`), `warp.md` (`git rm`), `requirements-web.txt` mention. **Do not delete** `COLOR_REFERENCE.txt` or `phone_migration/resources/` — fold `COLOR_REFERENCE.txt`'s useful content into `docs/DESIGN_SYSTEM.md` and leave the file for the user to remove.

Findings: README.md:46,110,160,189,339,407,418,440,536,549; QUICKSTART.md:66,82,122,128,129,151; RULE_MODES.md:30,65,71,95,104,107,114,153,263; CHANGELOG; warp.md; DESIGN_SYSTEM.md:1,23,149,254,306; COLOR_REFERENCE.txt:103,137,144.

- [x] Every documented run command that is meant to transfer uses `-y`; state once, prominently, that bare `--run` previews. Remove every `--dry-run` and `--no-rename`. Document `--check`, `--copy`, `--backup` (and that `--smart-copy` is a deprecated alias), `--browse-phone`, `-r/--rule-id`, `--manual`/`--no-manual`, `--notify`, `--web --background/--stop`, `NO_COLOR`, `NERD_FONT=1`, `PHONE_SYNC_PLAIN_ICONS=1`.
- [x] Requirements: stdlib for CLI; `pip install -r requirements-web.txt` (Flask only) for `--web`. Config path `~/.config/phone-migration/config.json` (XDG), state `~/.local/share/phone-migration/state.json`, pid/log `~/.local/state/phone-migration/`. One-shot migration from the old path mentioned.
- [x] Remove `docs/TODO.md` links. "Smart Copy" → "Backup" everywhere except the alias note. Sample outputs regenerated from the real CLI (`PHONE_SYNC_PLAIN_ICONS=1 NO_COLOR=1 python3 main.py --list-rules` etc.) — no emoji in samples. RULE_MODES: backup "skips files already recorded in its state file or already present at the destination with the same size" — no "smart comparison" claim; conflict handling per mode stated exactly as implemented in Task 4.
- [x] `CHANGELOG.md`: add an `[Unreleased]` section listing the fixes by area (security, data safety, dry-run, CLI, web UI, docs) and the Smart Copy → Backup rename.
- [x] `docs/DESIGN_SYSTEM.md`: hex values match `theme.py` exactly (regenerate the table from the module), contrast column recomputed (WCAG formula, on `#0D0E16`), migration checklist reflects reality, icon table (nerd + plain) added, `COLOR_REFERENCE.txt` content merged.
- [x] `git rm warp.md`.

Verify: every command in README/QUICKSTART that is not device-dependent runs (`--help`, `--list-profiles`, `--list-rules`, `--run` on a config with no device prints the no-device message and exits 0).

---

## Review

(filled in at the end)
