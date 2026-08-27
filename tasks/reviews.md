
## 2026-08-26 16:40 — Review-fix series: phone-migration data safety, dry-run, web security, docs
reviewer: gpt-5.6-terra · 50 files changed, 8195 insertions(+), 4279 deletions(-)
- [x] phone_migration/operations.py:67 — CLI and pre-existing config rules bypass the web-only desktop-path confinement, allowing runners to read/write arbitrary filesystem paths — enforce the shared allowed-root resolver when saving and executing every rule.
  - dismissed: the CLI runs as the local user against their own config, so confining it protects nothing; the allowed-root confinement exists for browser-reachable input (web browse/add-rule), which is already enforced at save time. A pre-existing out-of-root rule can only exist if the local user wrote it.
- [x] phone_migration/web_ui.py:417 — Renaming a profile changes the backup resume-state key (`<profile>:<rule id>`), orphaning progress and causing partial prior outputs to be skipped as conflicts — key state by an immutable device identifier or migrate state keys during rename.
  - fixed in 2b8c927: `state.rename_profile(old, new)` re-keys `old:*` → `new:*` atomically; called from `PUT /api/profiles/<name>`; tests in test_state.py + test_web_ui.py.

## 2026-08-26 22:11 — Port of the review-fix series onto upstream main: data safety, dry-run, web security, preflight, docs
reviewer: gpt-5.6-terra · 86 files changed, 10882 insertions(+), 5332 deletions(-)
- [x] phone_migration/operations.py:672 — A failed sync copy does not mark the desktop scan incomplete, so `delete_extraneous` still deletes unrelated phone files after an MTP write failure — set `complete = False` on copy failure and skip all cleanup deletions.
  - fixed in 7aea3ea: a failed desktop→phone copy now sets `complete = False`, so the run refuses extraneous deletion (test: extraneous file survives when one copy fails).
- [x] phone_migration/gio_utils.py:290 — `gio copy` is invoked without `--overwrite`, so sync cannot replace changed phone files and backup cannot repair its own stale partial outputs — pass `--overwrite` for overwrite-required sync and resume-copy operations.
  - dismissed: verified on this machine — `/usr/bin/gio copy file://src file://dst` over an existing `dst` returns 0 and replaces the content without `--overwrite` (gio 2.88); `tests/test_gio_utils.py::test_gio_copy_overwrites_without_leaving_a_backup` pins it. The old `--backup=none` flag was the actual bug (parsed as `-b`, left `file~` copies) and is gone.
- [x] phone_migration/operations.py:287 — Empty-directory cleanup increments the move `deleted` counter, making nested move dry-runs report more deletions than copies and trigger the safety analyzer’s blocker — track directory removals separately or exclude them from the file-deletion counter.
  - fixed in 7aea3ea: directory removals now count in `folders_removed` and record action `folder`; `deleted` counts files only (tests: nested real move deleted==1/folders_removed==1; analyzer sees no blocker).
