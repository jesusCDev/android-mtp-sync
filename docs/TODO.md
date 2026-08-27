# TODO List - Android MTP Sync

## High Priority

### Fix Rule Validation Timeout Issue
**Status**: Wired end to end, but held behind a deliberate `if False and
accessible:` switch in `phone_migration/web_ui.py`. `phone_migration/rule_validator.py`
itself is complete and unused by the CLI runner.
**Problem**: `gio_info()` with timeout parameter hangs on some systems/MTP connections, causing validation to never complete
**Impact**: Validation feature currently disabled to prevent UI blocking

**Root Cause**:
- `gio_utils.gio_info(phone_uri, timeout=1)` doesn't properly respect timeout on all systems
- MTP connections can be slow, causing the subprocess call to hang indefinitely
- Thread-based timeout doesn't interrupt the underlying `gio info` subprocess

**Potential Solutions**:
1. Use `subprocess.Popen` with proper timeout handling instead of relying on gio's built-in timeout
2. Add a wrapper with `signal.alarm()` (Unix-only) or `threading.Timer` to forcefully kill the subprocess
3. Make validation completely optional with a user toggle in settings
4. Use a process pool with timeout enforcement
5. Skip phone path validation entirely and only validate desktop paths (which are fast)

**Files to Modify**:
- `phone_migration/gio_utils.py` - Fix `gio_info()` timeout implementation
- `phone_migration/rule_validator.py` - Add better error handling for timeouts
- `phone_migration/web_ui.py` - Re-enable validation (change the `if False and accessible:` switch back to `if accessible:`)

**Test Plan**:
1. Connect device with slow MTP connection
2. Verify validation completes within 2-3 seconds max
3. Verify timeout doesn't hang the entire thread
4. Test with multiple rules (2-5) to ensure it scales

**Priority**: High - This is a UX blocker that prevents users from seeing path validation warnings

---

## Medium Priority

### Add Validation Toggle in Settings
- Allow users to enable/disable automatic validation
- Store preference in config file
- Show manual "Validate Now" button when auto-validation is off

### Improve gio_utils Timeout Mechanism
- Implement universal timeout wrapper for all gio commands
- Use process-level timeout enforcement
- Add retry logic with exponential backoff

---

## Low Priority

### Add Validation Cache
- Cache validation results for 5 minutes to avoid repeated checks
- Invalidate cache when rules change or device reconnects
- Show "Last validated: X minutes ago" in UI

### Validation Performance Metrics
- Log how long each validation takes
- Show timing in verbose mode
- Alert if validation takes >3 seconds

---

## Notes
- Test runner works correctly - uses subprocess with proper timeout
- Validation is non-critical feature - tool works fine without it
- Consider making phone path validation optional since desktop path validation is fast and reliable

## Deferred review minors (2026-08-26 review-fix series)

Triaged "leave" by the final whole-branch review; none blocks anything. Kept here so they are not lost with the review scratch workspace.

- NOT_YET_MIGRATED has no stale-entry assertion (add "every entry still holds a disallowed glyph" before Task 7)
- test_theme scan does not catch raw \033[ literals bypassing Colors
- ponytail markers inside docstrings
- report test-count off by one
- review Approved (a9ee8ce93d637a724). Important: handoff claim "transfer None only when no device" false (also no-rules/no-match) — corrected by message to Task 7 implementer. minor (deferred): stats post-processing outside per-rule try (runner.py:379-397)
- probe except narrowed to GioError (FileNotFoundError escapes
- unreachable)
- analyzer adapter feeds errored rules → misleading INFO line
- unknown-mode skips overall_progress.update
- no test pins the spinner-stop fix
- RED evidence reasoned not captured
- main.py --run returns 0 when stats["errors"]>0 (v1 verbatim — final-wave candidate)
- complete (commits 308a045, 9ae5060, b69f980
- review clean). minor (deferred): DESIGN_SYSTEM.md:130 recipe uses `-p default` (placeholder, not a real profile → use PROFILE). Final wave: delete dead RuleProgress.update/update_counts
- fix round 1 re-review: all addressed
- carve-out → final wave: PUA scrub bypassed at web_ui.py:463, :817, :830/832/835 (add _scrub() at every append)
- stripping deletes Icons.ARROW in Nerd mode → main.py --web sets PHONE_SYNC_PLAIN_ICONS=1 before importing phone_migration (plain → arrow preserved). minor (deferred): pre-probe _busy() outside lock (commented)
- test_indentation_survives_glyph_stripping only tests leading whitespace
- tests/test_edge_cases.py prints emoji (out of scope by plan)
- running cleared before history insert (deliberate)
- With fixes — I-1 dashboard.js:294/304 Command Preview emits --dry-run/--rename-duplicates (CLI rejects)
- I-2 (x or "").strip() on non-string fields → 500 on bookmarks/profiles/rules routes
- I-3 StreamingOutput never collapses \r (spinner blob persisted to history)
- I-4 test_no_emoji misses PUA range. Backward compat (history/bookmarks/sessionStorage) clean. Ruling REVERSED: DESIGN_SYSTEM.md:130 `-p default` stays (real default profile name). Ruling: (a) implement `_scrub()` at every append incl. :817 subprocess stream
- skip the main.py env-var half (arrow loss in Nerd-mode web logs accepted). minor (deferred): cross-site Sec-Fetch-Site falls to Origin check
- prototype-reachable lookups
- Register Device prefill lost across navigation (pre-existing)
- cache-busting inconsistency
- CDN fonts no CSP; 1 MiB logo
- dead rule-progress-bar markup
- restored-run card empty until rules load
- DELETE unknown profile 500
- MUTATING_ROUTES hand-maintained
- tests/test_theme.py theme_env reload not in finally
- theme.py:19 sys.stdout.isatty() unguarded
- scripts/color_demo.py getattr lists unchecked (add a subprocess smoke test)
- gio_mkdir lets timeout GioError escape (wrap run in try/except → False)
- gio_mkdir returns True on existing regular file
- `_ABSENT` includes broad "not found" (consider "no such file or directory" only)
- RED/GREEN counts differ by one test
- gio_utils.shorten_path str() coercion has no caller
- DEFAULT_STORAGE_LABEL duplicated in STORAGE_LABELS[0]
- gio_list_detailed compares type == "directory" only while is_dir accepts "2"
- _load_state_file quarantine misses UnicodeDecodeError / non-dict JSON
- has_resume_state vs get_state_summary disagree when only failed populated
- no test for the failed-write path of _atomic_write_json
- no parent-dir fsync
- NamedTemporaryFile drops config perms to 0600
- importlib.reload in test_config brittle
- test_config importlib.reload defeats isolation within that one test (read-only, harmless)
- STATE_DIR patch vestigial
- fake_gio._rel does not reject raw `#`/bad `%` (odd-name tests weaker than claimed)
- no test for refused delete paths (:143-146, :676)
- conflict written into failed_paths without distinct marker (:435)
- backup overwrites user-edited desktop file on size mismatch (:421, needs docs note)
- cleanup double-counts subdir listing failure (:274/:292); "No files found" wording after failed root listing (:356). Also ⚠ state._load_state_file renames a corrupt file on *load* even in dry-run (Task 3 file) — deferred to final review
- Path.is_dir/is_file can raise EACCES on Python ≤3.12 (fold trio into the OSError guard
- add requires-python to pyproject)
- stray broken symlink permanently refuses deletion for that rule (by design, noisy)
- desktop symlink to ancestor recurses without loop guard (pre-existing)
- spec regex mints a model word as serial for a host like mtp://SAMSUNG_SAMSUNG_Android/ (finding #14 harm class — consider requiring a digit)
- browser/interactive paths traceback on FileNotFoundError when /usr/bin/gio absent (fix belongs in gio_utils.run)
- notify-send resolved via PATH; "1 errors" pluralization
- a volume-less top-level MTP `Mount(` line following an unmounted volume block pops that volume's phone (pending_key cleared only on headings
- fix = only pop when the Mount line is indented under the heading)
- identifier inherited across blocks
- same-host storages merge into one device (base design)
- `str | None` annotation on inner def (needs requires-python>=3.10 in pyproject)
- two-unmounted-phones case untested
- loose "main.py" substring cmdline match (use split("\0") + exact tokens)
- stat aggregation outside the per-rule try (runner.py:293-303); --smart-copy deprecation line prints before validation
- unreachable AssertionError runner.py:126 + redundant .get guard :301
- unused `signal` import in tests
- XDG_STATE_HOME="" yields relative path (use `or`)
- port-probe test one-sided (`is True` both ways) + adds ~0.6s; --stop double _web_pid TOCTOU; --background success uses loosened probe (marked ceiling)
- ACTION_ICONS[file.action]/groups[action] prototype-reachable lookups (Object.create(null))
- progress only 0→100 (decorative bar)
- ALLOWED_ROOTS import-time construction untested
- PUT rename orphans profile:rule_id backup state
- redirect_stdout process-global (marked)
- `~nosuchuser/x` desktop path → RuntimeError 500 on browse/folder-create/add-rule (catch RuntimeError in _resolve_desktop_path)
- dashboard.js:5 sends rename_duplicates:true by default so backup rules from the dashboard still rename (consider toggle default unselected → null)
- ALLOWED_HOSTS fails closed for non-8080 hosts (no --host/--port flags exist)
- web-added rules stored realpath-resolved
- history ordering race cosmetic
- minor (deferred) / final-wave code items: runner.py:187 no-device hint says "Execute: phone-sync --run" (should be `--run -y`)
- config.py still writes inert "recursive": True (consider dropping)
- COLOR_REFERENCE.txt stale pointer (user deletes)
