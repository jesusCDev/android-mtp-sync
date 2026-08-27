# Handoff — written 2026-08-27 00:25 EDT

## TASK

phone-migration (`phone-sync`): the 2026-08-26 full validation review (spec `tasks/review-2026-08-26.md`, ~130 findings) was fixed, ported onto the upstream line, merged, and pushed. Follow-ups the user then asked for are also done. **No work is open.** This file exists so a fresh session does not redo anything.

User constraints not recorded elsewhere:
- Never bypass the subagent routing hook (`ROUTE_ENFORCE`); if the tier drops to `haiku`, pause rather than run high-risk work on it. `~/.claude/skills/route/agent-routing.sh` does not exist; the hook's denial message names the current tier.
- Never run `--run -y`, `--add-device`, or a real `--web` on port 8080 during verification; the user's real config (profile `s25-ultra`) lives at `~/.config/phone-migration/config.json` (migrated once from the repo-dir copy, which still exists and is gitignored).
- Deletions of user files/history only with explicit consent (all consents given so far are listed under DONE).

## DONE (verified; `python3 -m pytest -q -W error` → 475 passed on `main`)

- Review fixes (data safety, dry-run purity, GioError model, XDG config + state, serial-only device matching, web security: host allow-list + same-origin guard, path confinement, XSS escaping, structured `RunResult`, one run lock, log scrubbing; preflight made real; docs regenerated; theme/icons module) — merged into `main`, pushed. Plan `tasks/port-plan.md` (all ticked); v1 plan `tasks/plan-v1.md`; xreview ledger `tasks/reviews.md` (3 sections, every box checked).
- 2026-08-26 22:33–23:56: pushed; untracked junk deleted; v1 branch deleted; `tests/videos/` (153 MB) and `tests/res/` (PNGs) purged from history with `git filter-repo`, force-pushed (tree verified identical apart from purged paths; pack 165 → 3.2 MiB); `chore/static-refactor` untouched.
- 2026-08-27 00:12–00:22: `--web` opens a browser tab once the server answers (`--no-browser` opt-out; stdlib `webbrowser`); `--run` exits 2 with no device, 1 if any rule errored; deferred review minors carried into `docs/TODO.md`; `.superpowers/` scratch + pre-rewrite bundles deleted (commits d9dcf83, 0e17773, fc476a9, dcd0567). xreview on the feature: no findings.

## IN PROGRESS

Nothing. No subagents, monitors, or background jobs.

## REMAINING (user-only, optional)

1. GitHub may still serve the purged SHAs until its garbage collection — open a GitHub Support ticket to force a GC if immediate unreachability matters. Any other clone must be re-cloned (history was rewritten twice).
2. Six idle Claude sessions from 2026-08-25 (`claude-codex-3c`, `p90xtracker-c4`, `laptop-fixes-86`, `all-workout-07`, `adhd-recall-a0`, `bluetooth-panel-widget`) still hold memory — close from their terminals.
3. Restore `~/.claude/skills/route/agent-routing.sh` if `/route` is wanted.
4. Optional follow-ups are enumerated in `docs/TODO.md` ("Deferred review minors"): e.g. vendor Font Awesome + add a CSP, shrink the 1 MiB `static/img/logo.png`, `DELETE /api/rules/<unknown-profile>` returns 500 not 404, IPv6 host form.

## STATE

- Branch `main` at dcd0567 (plus this handoff commit) == `origin/main`. Working tree clean (no untracked files). Other local branch: `chore/static-refactor` (old, matches origin).
- No uncommitted files. Nothing must-not-commit remains (the junk was deleted).
- No scratch directories left in the repo; the session scratchpad under `/tmp/claude-1000/...` is disposable.
- Memory notes: `~/.claude/projects/-home-jesuscdev-Programming-project-cli-phone-migration/memory/` (`fix-review-findings-branch.md`, `route-script-missing.md`).

## GOTCHAS

- `tasks/todo.md` does not exist; the plans are `tasks/port-plan.md` (current) and `tasks/plan-v1.md` (reference). Do not re-run them.
- Bare `--run` previews; `-y` executes. Backup skips on conflict under plain `--run` (runner `rename_duplicates` is tri-state) but the dashboard's Rename-on-Conflict toggle ships ON. Sync is one-way desktop → phone and refuses `delete_extraneous` at the storage root, on an empty/incomplete desktop scan (incl. broken/looping symlinks), or after any copy failure.
- Phones without an MTP serial are refused at registration; `config.find_profile_by_device_id` refuses empty ids.
- `tests/test_edge_cases.py` is a hardware script (not collected by pytest) that expects user-supplied videos under the gitignored `tests/videos/` — out of scope, do not "fix".
- `tests/conftest.py` isolates config/state/lock/history/bookmarks paths; if you add a module-level user path anywhere, add it there or tests will touch real files.
- xreview: `xreview.sh` only diffs the working tree vs HEAD; to review committed branch work use `git reset --soft <base>` → run → `git reset --soft ORIG_HEAD`. A Stop hook blocks ending a turn while `tasks/reviews.md` has unchecked boxes.
