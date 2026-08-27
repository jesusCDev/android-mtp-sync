# Plan: port the review fixes onto upstream main

Spec: `tasks/review-2026-08-26.md` (binding). Reference implementation: branch `fix/review-findings` (v1; plan `tasks/plan-v1.md` — its **Global Constraints** and **Shared Interfaces** sections apply verbatim here). Upstream maps: `.superpowers/sdd/port-map-core.md`, `.superpowers/sdd/port-map-web.md`.
Branch: `fix/review-findings-v2`, cut from upstream `main` 4a98196; first commit acd5ab4 removes `tests/videos/`.

## Port-specific constraints (in addition to plan-v1's Global Constraints)

- **Preserve upstream features.** Everything upstream added since 63d813c stays working: `preflight.py`, `progress.py`, `dry_run_analyzer.py`, `rule_validator.py`, runner's auto-validation / `skip_validation` / device-accessibility probe, symlink-loop guard in sync, fcntl state lock, `FailureInjector` in gio_utils, `gio_info(..., timeout=)` override, web UI Ocean Noir design, `StreamingOutput` live logs, progress card, command preview, sessionStorage persistence, nav-disable, bookmarks/quick mounts/symlink browsing, branding assets, cache-busting, `/api/tests/run`.
- **Reuse v1 verbatim where the upstream file is byte-identical to 63d813c** (`main.py`, `paths.py`, `config.py`, `device.py`, `browser.py`, `notifications.py`, `transfer_stats.py`, `history.js`, `history.css`, `profiles.css`): `git checkout fix/review-findings -- <path>` then re-verify against the new neighbours. Tests from v1 (`git show fix/review-findings:tests/<file>`) are the starting point everywhere; adapt, don't rewrite.
- **The v1 rulings stand** (ledger in `git show fix/review-findings:tasks/reviews.md` and the session summary): serial-only device matching; sync ignores `rename_duplicates`; runtime `delete_extraneous` default False; tri-state `rename_duplicates` in runner; web confinement roots; dashboard rename toggle ships ON; `copy` counts as backed_up.
- Every task: `python3 -m pytest -q -W error` green before commit; commit message conventional, body ends `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Never commit `COLOR_REFERENCE.txt`, `phone_migration/resources/`, `.superpowers/`.
- Known-broken, out of scope, do not fix or delete: `tests/test_edge_cases.py` (hardware script, not collected by pytest, needs user-supplied videos), `tests/helpers/`, `tests/docs/`.

---

## Task 1: theme + test infrastructure + emoji sweep of upstream modules

Files: `phone_migration/theme.py`, `pyproject.toml`, `tests/conftest.py`, `tests/test_theme.py`, `scripts/color_demo.py` (all taken from v1 — the final v1 versions, i.e. including the fix-wave `requires-python` table), `phone_migration/{dry_run_analyzer,preflight,progress,rule_validator}.py` (ANSI/emoji → theme), `tests/test_operations.py` (drift fixes only), `tests/test_dry_run_safety.py` (one message-drift fix).

- [x] Copy the five v1 files. `tests/conftest.py`'s fixture must also cover `web_ui.HISTORY_FILE`/bookmarks paths if they exist upstream (check `web_ui.py` for module-level file paths; patch them too, import-guarded).
- [x] `dry_run_analyzer.py:215` `from .operations import Colors` → `from .theme import Colors`. Replace every raw ANSI literal and emoji in the four upstream modules with `theme.Colors`/`theme.Icons` names (no other module may define ANSI literals). `tests/test_theme.py`'s scan then covers them.
- [x] `tests/test_operations.py`: the same three drift fixes as v1 Task 1 (patch target, delete the sync rename test, `total_files` in the mock; also `failed: {}`). `tests/test_dry_run_safety.py::test_mass_deletion_warning`: align the expected message with the current analyzer text (test-only change).
- [x] Verify: suite fully green; `python3 scripts/color_demo.py` runs; no emoji left in `phone_migration/*.py` (the v1 `tests/test_web_ui.py` sweep is not in yet — add a small `tests/test_no_emoji.py` that scans `phone_migration/**/*.py`, `main.py`, `scripts/` for emoji/variation selectors/wide glyphs now; Task 7 extends it to JS/HTML).

## Task 2: gio_utils + paths

Files: `phone_migration/gio_utils.py`, `phone_migration/paths.py`, `tests/test_gio_utils.py`, `tests/test_paths.py`, call-site kwarg edits in `operations.py`/`browser.py`/`runner.py`/`rule_validator.py` only.

- [x] Apply the v1 `gio_utils` design (`GioError`, `GIO`, timeouts, `child_uri`, `gio_list` raises, `gio_list_detailed`, `gio_info` `{}`-only-when-absent, `is_dir`, `gio_copy` without `overwrite`, `gio_mkdir` idempotent and timeout-safe, `gio_mount`) **on top of** upstream's file: keep `FailureInjector` (test-only hook) and keep an optional `timeout` override on `gio_info` (`rule_validator.py:76` passes `timeout=1`); route it through the shared `run()`.
- [x] `paths.py` is byte-identical to the v1 base → take v1's file verbatim.
- [x] Tests: v1's `test_gio_utils.py`/`test_paths.py`, plus one test that `FailureInjector` still works and one that `gio_info(uri, timeout=1)` is accepted.

## Task 3: state + config

Files: `phone_migration/state.py`, `phone_migration/config.py`, `tests/test_state.py`, `tests/test_config.py`, `runner.py:~123` debug-hint line only.

- [x] `state.py`: v1 design (`state_key`, `failed: dict`, corrupt → `.corrupt`, atomic tmp+fsync+`os.replace`, `rename_profile`) **inside upstream's fcntl `_acquire_lock()`** — do not drop the lock. Keep `mark_file_copied`/`mark_file_failed` as deprecated wrappers until Task 4 (as v1 did).
- [x] `config.py` byte-identical to v1 base → v1 file verbatim (XDG + migration, atomic write, `setdefault`, no `overwrite` key, theme colors, XDG `or` fix).
- [x] Tests from v1 plus: two processes/threads saving state concurrently do not corrupt (exercise the lock path once).

## Task 4: operations.py

Files: `phone_migration/operations.py`, `tests/test_operations.py` (replace with v1's), `tests/fake_gio.py` (v1), `phone_migration/state.py` (delete wrappers last).

- [x] Port v1's rewrite (all P0/P2 fixes, `files` list, `profile_name`, batched state, sync guards incl. storage-root/incomplete-scan/`OSError`, `run_smart_copy_rule` alias, sync without `rename_duplicates`) onto upstream's `operations.py`, preserving upstream's symlink-loop guard in sync and any hooks into `progress.py` (see port-map-core §2). Delete the state wrappers.
- [x] `dry_run_analyzer` consumes `(rule, stats)` tuples with `stats.get(...)` — confirm the new stats keys are a superset; add a test in `tests/test_dry_run_safety.py` style that feeds a real `run_move_rule` stats dict into `analyze_dry_run_results` without error.

## Task 5: device + browser + notifications

Files: byte-identical upstream → take v1's final files verbatim (`device.py` with the digit-requiring serial regex, `browser.py`, `notifications.py`) and v1's tests verbatim. Verify `web_ui.py`'s callers of `browser.list_phone_directory` (upstream added bookmarks/symlink browsing — check the keys it reads) still get what they read; if upstream's browser.py gained functions since 63d813c the map says it did not — confirm with `git diff 63d813c..4a98196 -- phone_migration/browser.py`.

## Task 6: runner + main

Files: `phone_migration/runner.py`, `main.py`, `tests/test_runner.py`, `tests/test_main.py`.

- [x] `runner.py` is a redesign on upstream's version: return the v1 `RunResult` (Shared Interfaces in `tasks/plan-v1.md`), tri-state `rename_duplicates`, `include_manual` = all rules, unknown-mode/exception handling, `profile_name` to backup, `failed`→errors, `resumed` separate, `("", "")` fingerprint skip, `gio_utils.gio_mount`, theme colors/icons, **while keeping** upstream's preflight call, `progress.RuleProgress`/`OperationProgress` usage, auto-validation + `skip_validation`, device-accessibility probe via `gio_info`, and the dry-run analyzer call (adapter: `[(r, r["stats"]) for r in result["rules"]]`). Notification via `result["stats"]`.
- [x] `main.py` byte-identical upstream → v1's final file verbatim (pid file, `--no-manual`, `-y` hints, XDG `or`), then reconcile with upstream runner's signature (`skip_validation` flag: expose `--skip-validation` if upstream's CLI had it — it did not; leave the runner default).
- [x] Tests: v1's `test_runner.py`/`test_main.py` adapted — monkeypatch `preflight`, `progress`, `dry_run_analyzer`, `rule_validator` where they would touch the filesystem or the device.

## Task 7: web UI

Files: `phone_migration/web_ui.py`, `phone_migration/static/js/*.js`, `static/css/*.css`, `web_templates/*.html`, `requirements-web.txt`, `tests/test_web_ui.py`, `tests/test_no_emoji.py` (extend to JS/HTML/CSS).

Follow port-map-web §6 exactly:
- [x] Guard: `@app.before_request` with `ALLOWED_HOSTS` (populated by `start_web_ui`) + same-origin rule for all non-GET/HEAD/OPTIONS; remove `CORS(app)`/`flask_cors`; `requirements-web.txt` = `Flask>=3.0.0`. Must cover all 26 routes incl. `/api/tests/run` and `/api/bookmarks/*`.
- [x] Confinement: `_resolve_desktop_path` (v1 fix-wave version: `ValueError`/`RuntimeError` → 400, `PermissionError` → 403, `ALLOWED_ROOTS`) on `/api/browse/desktop`, `/api/folder/create` (keep upstream's single-path JSON schema; reject `.`/`..` segments), `POST /api/rules` `desktop_path`, and bookmarks if they store paths.
- [x] Run lock: `running=True` under a `threading.Lock` in the handler before `thread.start()`; keep `StreamingOutput`. After `run_for_connected_device` returns, store `current_run_status["result"]`; `/api/run/status` returns it; delete the regex stat parsing; history entries carry `dry_run`, `stats`, `rules` from the result; `status="error"` when `stats["errors"] > 0`; `_tri_state` for `rename_duplicates`; `save_history`/`save_bookmarks` via `cfg._atomic_write_json`; `running` cleared before persist; `/api/history` limit clamp; `debug=False`; `HISTORY_FILE` beside the XDG config.
- [x] JS: fix `escapeHtml` (add `"`/`'`), hoist to `main.js`, convert every interpolation site in port-map-web §3 and every inline `onclick` with interpolation to `dataset`+listeners; `dashboard.js`/`history.js` build cards/modal/file lists from `result.rules[].files` (delete sentinel/log parsing); DRY RUN badge from `result.dry_run`; `backup` mode in both `getModeIcon`/`getModeLabel` copies and both CSS files; `encodeURIComponent` on `profiles.js` PUT caller; delete the dead `/api/device/register` route (registration stays on `/api/profiles` POST); remove the undefined-handler Escape listener if still present.
- [x] Tests: v1's `tests/test_web_ui.py` as the base, extended to the 26-route surface (every mutating route 403s without same-origin; `/api/tests/run` included), `node --check` over `static/js/*.js`, old-format `history.json` entries (no `rules`/`dry_run`) still render (unit-test `load_history` + a JS smoke via node if feasible).

## Task 8: docs

Files: `README.md`, `docs/OPERATIONS.md` (upstream's rename of RULE_MODES), `docs/archive/QUICKSTART.md`, `docs/CHANGELOG.md` (merge v1's entries with upstream's), `docs/DESIGN_SYSTEM.md` (v1 final), `docs/warp.md` + root `warp.md` (root: `git rm`; docs copy: fix stale flags), `docs/README.md`, `docs/TODO.md`, `tests/README_TESTS.md` (points at a missing file and at `tests/videos/` — say videos are user-supplied and gitignored).

- [x] Port v1's Task 8 content onto the upstream layout; every command verified against the ported `--help`; samples regenerated (`PHONE_SYNC_PLAIN_ICONS=1 NO_COLOR=1`); document upstream's new features (preflight, dry-run analyzer, progress card, bookmarks, test runner) where v1's docs did not know them — read the modules, one paragraph each; no emoji; CHANGELOG `[Unreleased]` = union.

---

## Review

(filled in at the end)
