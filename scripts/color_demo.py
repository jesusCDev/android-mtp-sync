#!/usr/bin/env python3
"""Print the phone-sync palette and icon set, so a terminal can be eyeballed.

    python3 scripts/color_demo.py
    PHONE_SYNC_PLAIN_ICONS=1 python3 scripts/color_demo.py
    NERD_FONT=1 python3 scripts/color_demo.py
"""

import sys
from pathlib import Path

# runnable straight from a checkout: python3 scripts/color_demo.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phone_migration.theme import NERD, Colors, Icons

SWATCHES = [
    ("Semantic", ["ERROR", "SUCCESS", "WARNING", "INFO", "ACCENT", "MUTED"]),
    ("Actions", ["MOVED", "BACKED_UP", "SYNCED", "DELETED", "SKIPPED", "RENAMED"]),
    ("UI", ["HEADER", "SEPARATOR", "DEVICE_NAME", "RULE_ID", "PATH"]),
]

ICON_NAMES = [
    "OK", "FAIL", "WARN", "INFO", "BULLET", "ARROW", "PHONE", "FOLDER", "FILE",
    "MOVE", "COPY", "SYNC", "DELETE", "SKIP", "RENAME", "BOLT", "SEARCH", "STATS",
]


def rule():
    print(f"{Colors.SEPARATOR}{'-' * 62}{Colors.RESET}")


def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}{Icons.PHONE}  Deep Twilight Pastels{Colors.RESET}")
    rule()

    for section, names in SWATCHES:
        print(f"\n{Colors.BOLD}{Colors.INFO}{section}{Colors.RESET}")
        for name in names:
            color = getattr(Colors, name)
            print(f"  {color}{'#' * 8}{Colors.RESET} {color}{name}{Colors.RESET}")

    mode = "nerd font" if NERD else "plain"
    print(f"\n{Colors.BOLD}{Colors.INFO}Icons{Colors.RESET} {Colors.DIM}({mode}){Colors.RESET}")
    for name in ICON_NAMES:
        print(f"  {Colors.ACCENT}{getattr(Icons, name)}{Colors.RESET}  {Colors.DIM}{name}{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.INFO}Example output{Colors.RESET}")
    print(f"  {Colors.SUCCESS}{Icons.OK}{Colors.RESET} copied {Colors.PATH}~/Pictures/Camera/IMG_0042.jpg{Colors.RESET}")
    print(f"  {Colors.WARNING}{Icons.WARN}{Colors.RESET} conflict, not copied {Colors.DIM}IMG_0043.jpg{Colors.RESET}")
    print(f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} IMG_0044.jpg: {Colors.MUTED}gio: connection lost{Colors.RESET}")
    rule()
    print()


if __name__ == "__main__":
    main()
