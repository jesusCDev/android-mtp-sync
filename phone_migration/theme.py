"""The one place colors and icons are defined.

Palette: "Deep Twilight Pastels" - 24-bit ANSI, tuned for a #0D0E16 terminal
background (every text color clears WCAG AA, 4.5:1, against it).

Both switches are read once, at import time:

    NO_COLOR=<anything>       or a non-TTY stdout  -> every color is ""
    PHONE_SYNC_PLAIN_ICONS=1                       -> plain unicode icons
    NERD_FONT=1 or WEZTERM_PANE set                -> nerd-font icons
"""

import os
import sys

PLAIN = os.environ.get("PHONE_SYNC_PLAIN_ICONS") == "1"
NERD = not PLAIN and (os.environ.get("NERD_FONT") == "1" or "WEZTERM_PANE" in os.environ)

_COLOR = not ("NO_COLOR" in os.environ or not sys.stdout.isatty())


def _c(code: str) -> str:
    return code if _COLOR else ""


def _icon(nerd: str, plain: str) -> str:
    return nerd if NERD else plain


class Colors:
    RESET = _c('\033[0m')
    BOLD = _c('\033[1m')
    DIM = _c('\033[2m')
    ITALIC = _c('\033[3m')
    UNDERLINE = _c('\033[4m')

    # Core semantic colors
    ERROR = _c('\033[38;2;244;162;168m')      # Soft coral-pink: errors without aggression
    SUCCESS = _c('\033[38;2;181;232;160m')    # Mint cream: success feels fresh
    WARNING = _c('\033[38;2;245;215;161m')    # Warm cream: warnings with warmth, not alarm
    INFO = _c('\033[38;2;160;200;232m')       # Sky blue pastel: calm information
    ACCENT = _c('\033[38;2;212;181;232m')     # Lavender: special highlights
    MUTED = _c('\033[38;2;124;131;153m')      # Slate gray: de-emphasized but still legible

    # Action-specific colors (tells a story through color)
    MOVED = _c('\033[38;2;255;184;190m')      # Peachy rose: files leaving phone
    BACKED_UP = _c('\033[38;2;168;224;232m')  # Seafoam: preserved safely
    SYNCED = _c('\033[38;2;184;220;255m')     # Powder blue: bidirectional harmony
    DELETED = _c('\033[38;2;244;162;168m')    # Coral (same as error): deletion is serious
    SKIPPED = _c('\033[38;2;160;200;232m')    # Info blue: neutral skip
    RENAMED = _c('\033[38;2;245;215;161m')    # Cream: modified but okay

    # UI elements
    HEADER = _c('\033[38;2;245;215;161m')     # Warm cream glow
    SEPARATOR = _c('\033[38;2;42;46;64m')     # Deep indigo divider (rules only, never text)
    DEVICE_NAME = _c('\033[38;2;232;214;200m')  # Soft cream: important identifiers
    RULE_ID = _c('\033[38;2;181;232;160m')    # Mint: technical references
    PATH = _c('\033[38;2;184;220;255m')       # Powder blue: filesystem paths


class Icons:
    """Single-width glyphs. The nerd-font codepoints are Font Awesome range,
    stable across Nerd Fonts v2/v3; the plain column is the fallback."""

    OK     = _icon('\uf00c', '✓')      # nf-fa-check       / check mark
    FAIL   = _icon('\uf00d', '✗')      # nf-fa-close       / ballot x
    WARN   = _icon('\uf071', '⚠')      # nf-fa-warning     / warning sign
    INFO   = _icon('\uf05a', '▸')      # nf-fa-info_circle / small right triangle
    BULLET = _icon('\uf111', '•')      # nf-fa-circle      / bullet
    ARROW  = _icon('\uf061', '→')      # nf-fa-arrow_right / rightwards arrow
    PHONE  = _icon('\uf10b', '▪')      # nf-fa-mobile      / small square
    FOLDER = _icon('\uf07b', '▸')      # nf-fa-folder      / small right triangle
    FILE   = _icon('\uf15b', '•')      # nf-fa-file        / bullet
    MOVE   = _icon('\uf093', '↑')      # nf-fa-upload      / upwards arrow
    COPY   = _icon('\uf0c5', '+')      # nf-fa-copy        / plus
    SYNC   = _icon('\uf0ec', '⇄')      # nf-fa-exchange    / paired arrows
    DELETE = _icon('\uf1f8', '✗')      # nf-fa-trash       / ballot x
    SKIP   = _icon('\uf05e', '-')      # nf-fa-ban         / hyphen
    RENAME = _icon('\uf040', '~')      # nf-fa-pencil      / tilde
    BOLT   = _icon('\uf0e7', '!')      # nf-fa-bolt        / exclamation
    SEARCH = _icon('\uf002', '?')      # nf-fa-search      / question mark
    STATS  = _icon('\uf080', '#')      # nf-fa-bar_chart   / number sign
