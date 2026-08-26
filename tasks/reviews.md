
## 2026-08-26 16:40 — Review-fix series: phone-migration data safety, dry-run, web security, docs
reviewer: gpt-5.6-terra · 50 files changed, 8195 insertions(+), 4279 deletions(-)
- [x] phone_migration/operations.py:67 — CLI and pre-existing config rules bypass the web-only desktop-path confinement, allowing runners to read/write arbitrary filesystem paths — enforce the shared allowed-root resolver when saving and executing every rule.
  - dismissed: the CLI runs as the local user against their own config, so confining it protects nothing; the allowed-root confinement exists for browser-reachable input (web browse/add-rule), which is already enforced at save time. A pre-existing out-of-root rule can only exist if the local user wrote it.
- [x] phone_migration/web_ui.py:417 — Renaming a profile changes the backup resume-state key (`<profile>:<rule id>`), orphaning progress and causing partial prior outputs to be skipped as conflicts — key state by an immutable device identifier or migrate state keys during rename.
  - fixed in 2b8c927: `state.rename_profile(old, new)` re-keys `old:*` → `new:*` atomically; called from `PUT /api/profiles/<name>`; tests in test_state.py + test_web_ui.py.
