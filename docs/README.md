# Documentation

Start at the root [README.md](../README.md); everything here is a deeper cut on
one topic.

| File | What it covers |
|---|---|
| [OPERATIONS.md](OPERATIONS.md) | The four rule modes — move, copy, backup, sync — and exactly what each does to your files, including conflict handling and every case where sync refuses to delete. |
| [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | The CLI palette and icon set, derived from `phone_migration/theme.py`, with WCAG contrast figures and the `NO_COLOR` / `NERD_FONT` / `PHONE_SYNC_PLAIN_ICONS` switches. |
| [warp.md](warp.md) | Quick reference and saved-workflow snippets for Warp Terminal users. |
| [CHANGELOG.md](CHANGELOG.md) | Version history. |
| [TODO.md](TODO.md) | Known gaps and planned work, chiefly the rule-validation timeout that keeps `rule_validator.py` switched off. |
| [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) | Historical record of the 2025-11-24 repository reorganization. |

Test documentation lives with the tests: [tests/README_TESTS.md](../tests/README_TESTS.md).

## Archive

[archive/](archive/) holds documents that are superseded but still worth
keeping:

- [QUICKSTART.md](archive/QUICKSTART.md) — the five-minute onboarding path, now
  duplicated in the root README. Still accurate.
- [DIAGNOSTIC_REPORT.md](archive/DIAGNOSTIC_REPORT.md) — a point-in-time MTP
  debugging write-up.
- [TESTING_SAFETY.md](archive/TESTING_SAFETY.md) — an earlier safety analysis,
  superseded by the Safety section of the root README and by
  [OPERATIONS.md](OPERATIONS.md).
