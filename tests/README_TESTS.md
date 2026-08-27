# Test Suite

There are three separate things in this directory, and they are run in different
ways.

| What | How to run | Needs a phone? |
|---|---|---|
| The pytest suite (`tests/test_*.py`) | `python3 -m pytest -q` | No |
| The dry-run analyzer tests (`tests/test_dry_run_safety.py`) | included in the above | No |
| The hardware edge-case script (`tests/test_edge_cases.py`) | `python3 tests/test_edge_cases.py` | **Yes** |

## The pytest suite

```bash
# From the project root
python3 -m pytest -q

# One module
python3 -m pytest -q tests/test_operations.py

# Treat warnings as errors, which is what the port runs before each commit
python3 -m pytest -q -W error
```

Everything under `tests/test_*.py` is collected by pytest except
`test_edge_cases.py` (see below). No phone, no network and no real
`~/.config` or `~/.local` access is involved: `tests/conftest.py` redirects the
config, state and history paths into a temporary directory for every test, and
`tests/fake_gio.py` stands in for the `gio` subprocess calls.

| Module | Covers |
|---|---|
| `test_operations.py` | move, copy, backup and sync rule execution, conflict handling, deletion refusals |
| `test_runner.py` | rule selection, the `RunResult` shape, preflight wiring, dry-run analysis output |
| `test_state.py` | the resume state file, its lock, corrupt-file recovery |
| `test_config.py` | profile and rule storage, atomic writes, the XDG migration copy |
| `test_device.py` | MTP device detection and serial-based profile matching |
| `test_paths.py` | phone-path normalization, MTP URI building, duplicate renaming |
| `test_gio_utils.py` | the `gio` command wrappers, timeouts, failure propagation |
| `test_browser.py` | the interactive phone browser |
| `test_notifications.py` | `notify-send` integration |
| `test_main.py` | argument parsing and the CLI entry points |
| `test_theme.py` | palette contrast, icon widths, and that no module references a `Colors.X` / `Icons.X` that does not exist |
| `test_no_emoji.py` | an emoji and wide-glyph sweep over the CLI-facing modules |
| `test_dry_run_safety.py` | `dry_run_analyzer.analyze_dry_run_results` against synthetic rule/stats pairs |
| `test_web_ui.py` | the web UI's routes, its host and same-origin guards, desktop path confinement, and the structured run result the dashboard renders (98 tests) |

`test_dry_run_safety.py` is plain pytest functions rather than a class, and it
touches nothing outside the analyzer: it feeds it `(rule, stats)` tuples and
asserts on the blockers, warnings and info notes that come back.

## The hardware edge-case script

`tests/test_edge_cases.py` is **not** collected by pytest — its class is named
`ImprovedEdgeCaseTestSuite`, which does not match pytest's `Test*` pattern, and
it runs from its own `__main__` block:

```bash
python3 tests/test_edge_cases.py
```

It is a standalone integration script that drives a real phone through
`tests/helpers/mtp_testlib.py`. It is **known to be out of date and is not run by
CI**; treat it as a starting point rather than a passing suite.

The web UI's `POST /api/tests/run` starts **this** script, not the pytest suite,
so everything below about what it touches applies there too.

### What it needs

- An Android phone connected over USB in File Transfer mode, unlocked, and left
  unlocked for the whole run.
- Roughly 2 GB free on the phone and on the desktop.
- **Video files that you supply yourself** in `tests/videos/`. That directory was
  removed from the repository and is gitignored — test media does not belong in
  git. Drop three to five files of your own in, or generate placeholders:

```bash
mkdir -p tests/videos
dd if=/dev/zero of=tests/videos/test1.mp4 bs=1M count=10
```

Without those files the script fails at its first video lookup.

### What it touches

Unlike the pytest suite, this script is **not** isolated. It writes to
`Internal storage/test-phone-edge-v2/` on the phone and to
`~/.local/share/phone_edge_tests_v2/` on the desktop, and it reads, backs up and
restores your **real** `~/.local/share/phone-migration/state.json`. Do not run it
in the middle of a backup you care about resuming.

### What it checks

Connection sanity, copy rename and skip-on-conflict handling, move's
copy-then-verify-then-delete ordering, sync skipping unchanged files, large file
transfers, the preflight disk-space check, symlink traversal and loop guarding,
device disconnection, concurrent state access, corrupt-state recovery, and
read-only file permissions. `tests/docs/TESTING.md` has the long form.

## Test helpers

`tests/helpers/mtp_testlib.py` wraps bare `gio` subprocess calls for the
hardware script:

```python
from tests.helpers.mtp_testlib import MTPDevice, compare_trees

device = MTPDevice("mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/")

device.mkdir("/path/to/dir")
device.list_dir("/path/to/dir")
device.remove("/path/to/item")

device.push_file(Path("local.mp4"), "/phone/path/file.mp4")
device.push_file_recursive(Path("local_dir"), "/phone/dir")

device.path_exists("/phone/path")
device.get_file_info("/phone/path")

differences = compare_trees(device.directory_tree("/a"), device.directory_tree("/b"))
```

It is used by `test_edge_cases.py` only; the pytest suite uses
`tests/fake_gio.py` instead.

## Troubleshooting

**"No device connected"** (hardware script only)
Check the phone is in File Transfer mode and unlocked, then
`gio mount -li | grep -i mtp`.

**"Device activation URI not found"**
The device is not registered yet. Run `python3 main.py --add-device --name test`.

**The script hangs on a file copy**
The phone locked or slept. Unlock it and keep it awake.

**Only one application at a time**
Linux MTP is exclusive. Close any file manager holding the phone, then
`systemctl --user restart gvfs-daemon`.

## Further reading

- [tests/docs/TESTING.md](docs/TESTING.md) — the hardware script in detail
- [tests/docs/EDGE_CASES_PRIORITY.md](docs/EDGE_CASES_PRIORITY.md) — the edge
  cases and why each one matters
- [docs/OPERATIONS.md](../docs/OPERATIONS.md) — the behavior the tests assert
