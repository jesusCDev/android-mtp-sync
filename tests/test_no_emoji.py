"""Guard against emoji, variation selectors, and wide glyphs in CLI-facing source.

phone_migration/theme.py is exempt: it is the one place glyphs are defined (and
it has its own width/emoji checks in tests/test_theme.py). Every other module
must reference Icons.X / Colors.X by name instead of a literal glyph.

Files the port hasn't reached yet are allow-listed below (see tasks/port-plan.md
for which task lands each one); delete an entry as its task migrates the file.
Task 7 extends this scan to JS/HTML/CSS.
"""

import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The single authorized source of literal glyphs; covered by test_theme.py instead.
EXEMPT = {"phone_migration/theme.py"}

# Not yet migrated off raw ANSI/emoji -- tracked in tasks/port-plan.md.
NOT_YET_MIGRATED = {
    "phone_migration/operations.py",     # Task 4
    "phone_migration/runner.py",         # Task 6
    "main.py",                           # Task 6
    "phone_migration/web_ui.py",         # Task 7
}


def source_files():
    candidates = [
        *sorted(REPO_ROOT.glob("phone_migration/*.py")),
        *sorted(REPO_ROOT.glob("scripts/*.py")),
        REPO_ROOT / "main.py",
    ]
    skip = EXEMPT | NOT_YET_MIGRATED
    return [p for p in candidates if p.relative_to(REPO_ROOT).as_posix() not in skip]


def test_source_files_are_found():
    """Guard against the scan below silently degrading into a no-op."""
    assert len(source_files()) >= 4


def _is_disallowed_glyph(ch: str) -> bool:
    cp = ord(ch)
    if cp < 0x2000:                          # ASCII / Latin-1 / general punctuation
        return False
    if 0xFE00 <= cp <= 0xFE0F:               # variation selectors (e.g. the VS16 in "⚠️")
        return True
    if cp == 0x200D:                         # zero-width joiner (emoji ZWJ sequences)
        return True
    if 0x1F1E6 <= cp <= 0x1F1FF:             # regional indicators (flag emoji)
        return True
    if 0x1F3FB <= cp <= 0x1F3FF:             # emoji skin-tone modifiers
        return True
    if 0x1F000 <= cp <= 0x1FFFF:             # modern emoji / pictograph blocks
        return True
    return unicodedata.east_asian_width(ch) in ("W", "F")


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_no_emoji_variation_selectors_or_wide_glyphs(path):
    text = path.read_text(encoding="utf-8")
    for ch in text:
        assert not _is_disallowed_glyph(ch), (
            f"{path.name} contains {ch!r} (U+{ord(ch):04X}); "
            "use phone_migration.theme.Icons instead of a literal glyph"
        )
