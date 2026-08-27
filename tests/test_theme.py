"""Tests for phone_migration.theme, the single source of CLI colors and icons."""

import ast
import importlib
import io
import re
import sys
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import pytest

from phone_migration import theme

REPO_ROOT = Path(__file__).resolve().parent.parent

# Terminal background the palette is designed for.
BACKGROUND = (0x0D, 0x0E, 0x16)

# Colors used for text (SEPARATOR is a divider rule, not text, so it is exempt).
TEXT_COLORS = [
    "ERROR", "SUCCESS", "WARNING", "INFO", "ACCENT", "MUTED",
    "DEVICE_NAME", "RULE_ID", "PATH", "HEADER",
]

ICON_NAMES = [
    "OK", "FAIL", "WARN", "INFO", "BULLET", "ARROW", "PHONE", "FOLDER", "FILE",
    "MOVE", "COPY", "SYNC", "DELETE", "SKIP", "RENAME", "BOLT", "SEARCH", "STATS",
]

# Environment theme reads once, at import time.
THEME_ENV = ("NO_COLOR", "PHONE_SYNC_PLAIN_ICONS", "NERD_FONT", "WEZTERM_PANE")

PRIVATE_USE = range(0xE000, 0xF900)


class _FakeTTY(io.StringIO):
    def isatty(self):
        return True


@contextmanager
def theme_env(monkeypatch, tty=True, **env):
    """Re-import theme under a controlled environment, then restore the ambient module."""
    with monkeypatch.context() as m:
        for key in THEME_ENV:
            m.delenv(key, raising=False)
        for key, value in env.items():
            m.setenv(key, value)
        m.setattr(sys, "stdout", _FakeTTY() if tty else io.StringIO())
        yield importlib.reload(theme)
    importlib.reload(theme)


def color_names():
    return [name for name in vars(theme.Colors) if name.isupper()]


def rgb(ansi):
    """Extract (r, g, b) from a 24-bit SGR foreground sequence."""
    match = re.fullmatch(r"\033\[38;2;(\d+);(\d+);(\d+)m", ansi)
    assert match, f"not a 24-bit color escape: {ansi!r}"
    return tuple(int(part) for part in match.groups())


def relative_luminance(color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = color
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg, bg):
    light, dark = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# --- source scan -------------------------------------------------------------
# This is the test that would have caught the Colors.RED crash: every Colors.X /
# Icons.X spelled in the source has to resolve.
#
# A file that still carries its own legacy `class Colors:` is checked against
# that class; every other file is checked against theme.Colors. So the scan
# covers the whole tree today and tightens automatically as each module drops
# its private palette and imports the theme instead.

THEME_REFERENCE = re.compile(r"\b(Colors|Icons)\.([A-Z_][A-Z0-9_]*)\b")


def source_files():
    return [
        *sorted(REPO_ROOT.glob("phone_migration/*.py")),
        *sorted(REPO_ROOT.glob("scripts/*.py")),
        REPO_ROOT / "main.py",
    ]


def local_color_names(source):
    """Attribute names of a file's own `class Colors:`, or None if it defines none."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == "Colors":
            return {
                target.id
                for statement in node.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
    return None


def test_source_files_are_found():
    """Guard against the scan below silently degrading into a no-op."""
    assert len(source_files()) > 5


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_referenced_color_and_icon_attributes_exist(path):
    source = path.read_text()
    colors = local_color_names(source)
    if colors is None:
        colors = set(color_names())
    icons = {name for name in vars(theme.Icons) if name.isupper()}
    for class_name, attribute in THEME_REFERENCE.findall(source):
        defined = colors if class_name == "Colors" else icons
        assert attribute in defined, f"{path.name} uses {class_name}.{attribute}, which does not exist"


# --- colors ------------------------------------------------------------------

def test_text_colors_are_readable_on_the_terminal_background(monkeypatch):
    with theme_env(monkeypatch) as t:
        for name in TEXT_COLORS:
            ratio = contrast_ratio(rgb(getattr(t.Colors, name)), BACKGROUND)
            assert ratio >= 4.5, f"Colors.{name} contrast is {ratio:.2f}:1, WCAG AA needs 4.5:1"


def test_no_color_blanks_every_color(monkeypatch):
    with theme_env(monkeypatch, NO_COLOR="1") as t:
        assert color_names()
        for name in color_names():
            assert getattr(t.Colors, name) == "", f"Colors.{name} is set despite NO_COLOR"


def test_piped_output_blanks_every_color(monkeypatch):
    with theme_env(monkeypatch, tty=False) as t:
        for name in color_names():
            assert getattr(t.Colors, name) == "", f"Colors.{name} is set despite a non-TTY stdout"


# --- icons -------------------------------------------------------------------

def icon_values(t):
    return {name: getattr(t.Icons, name) for name in ICON_NAMES}


def test_plain_icons_when_requested(monkeypatch):
    with theme_env(monkeypatch, PHONE_SYNC_PLAIN_ICONS="1") as t:
        assert not t.NERD
        icons = icon_values(t)
        assert icons["OK"] == "✓"
        assert icons["FAIL"] == "✗"
        assert icons["ARROW"] == "→"
        for name, glyph in icons.items():
            assert ord(glyph) not in PRIVATE_USE, f"Icons.{name} is a nerd-font glyph in plain mode"


def test_nerd_icons_when_a_nerd_font_is_detected(monkeypatch):
    for env in ({"NERD_FONT": "1"}, {"WEZTERM_PANE": "0"}):
        with theme_env(monkeypatch, **env) as t:
            assert t.NERD
            icons = icon_values(t)
            assert icons["OK"] == "\uf00c"     # nf-fa-check
            assert icons["FAIL"] == "\uf00d"   # nf-fa-close
            assert icons["ARROW"] == "\uf061"  # nf-fa-arrow_right
            for name, glyph in icons.items():
                assert ord(glyph) in PRIVATE_USE, f"Icons.{name} is not a nerd-font glyph in nerd mode"


def test_plain_icons_win_over_nerd_font_detection(monkeypatch):
    with theme_env(monkeypatch, PHONE_SYNC_PLAIN_ICONS="1", NERD_FONT="1") as t:
        assert not t.NERD
        assert t.Icons.OK == "✓"


@pytest.mark.parametrize("plain", [True, False])
def test_icons_are_single_width_and_never_emoji(monkeypatch, plain):
    env = {"PHONE_SYNC_PLAIN_ICONS": "1"} if plain else {"NERD_FONT": "1"}
    with theme_env(monkeypatch, **env) as t:
        for name, glyph in icon_values(t).items():
            assert len(glyph) == 1, f"Icons.{name} is not a single codepoint"
            width = unicodedata.east_asian_width(glyph)
            assert width not in ("W", "F"), f"Icons.{name} is double-width ({width})"


def test_raw_ansi_escapes_live_only_in_the_theme():
    offenders = [p.name for p in source_files()
                 if p.name != "theme.py" and "\\033[" in p.read_text()]
    assert not offenders, f"raw ANSI escapes outside theme.py: {offenders}"
