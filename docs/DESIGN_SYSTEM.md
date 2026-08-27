# Deep Twilight Pastels - CLI Design System

The palette and icon set used by the command line output.

**`phone_migration/theme.py` is the source of truth.** Every color and every
icon in this project is defined there and imported from there; no other module
defines a palette or writes a raw ANSI escape. The tables below are derived from
that module — if you change a value, change it there and regenerate these.

## Philosophy

A dark base with soft pastel accents, tuned for long terminal sessions rather
than for maximum saturation.

1. **Atmosphere over sterility** — a deep indigo-black background (`#0D0E16`)
   instead of pure black.
2. **Pastel readability** — soft colors that still clear WCAG AA on that
   background.
3. **Semantic color** — a color means an action, not just a mood. Peachy rose is
   a file leaving the phone; seafoam is a file preserved.
4. **Icons carry the meaning too** — every state is distinguishable without
   color, which is what makes `NO_COLOR` output and colorblind viewing readable.

## Terminal base

These two are terminal settings, not part of `theme.py`. The palette is designed
against them:

| Role | Hex | Notes |
|---|---|---|
| Background | `#0D0E16` | Deep indigo-black. Every contrast figure below is measured against this. |
| Foreground | `#E8D6C8` | Soft cream. 13.6:1. |

## Palette

Contrast is the WCAG 2.x ratio against `#0D0E16`. AA body text needs 4.5:1, AAA
needs 7:1.

### Semantic

| Name | Hex | ANSI | Contrast | Meaning |
|---|---|---|---|---|
| `ERROR` | `#F4A2A8` | `38;2;244;162;168` | 9.7:1 | Soft coral-pink: errors without aggression |
| `SUCCESS` | `#B5E8A0` | `38;2;181;232;160` | 13.8:1 | Mint cream: success feels fresh |
| `WARNING` | `#F5D7A1` | `38;2;245;215;161` | 13.8:1 | Warm cream: warnings with warmth, not alarm |
| `INFO` | `#A0C8E8` | `38;2;160;200;232` | 10.9:1 | Sky blue pastel: calm information |
| `ACCENT` | `#D4B5E8` | `38;2;212;181;232` | 10.6:1 | Lavender: special highlights |
| `MUTED` | `#7C8399` | `38;2;124;131;153` | 5.1:1 | Slate gray: de-emphasized but still legible |

### Action-specific

| Name | Hex | ANSI | Contrast | Meaning |
|---|---|---|---|---|
| `MOVED` | `#FFB8BE` | `38;2;255;184;190` | 11.8:1 | Peachy rose: files leaving the phone |
| `BACKED_UP` | `#A8E0E8` | `38;2;168;224;232` | 13.3:1 | Seafoam: preserved safely |
| `SYNCED` | `#B8DCFF` | `38;2;184;220;255` | 13.5:1 | Powder blue: bidirectional harmony |
| `DELETED` | `#F4A2A8` | `38;2;244;162;168` | 9.7:1 | Coral, same as `ERROR`: deletion is serious |
| `SKIPPED` | `#A0C8E8` | `38;2;160;200;232` | 10.9:1 | Info blue: a neutral skip |
| `RENAMED` | `#F5D7A1` | `38;2;245;215;161` | 13.8:1 | Cream: modified but okay |

### UI elements

| Name | Hex | ANSI | Contrast | Meaning |
|---|---|---|---|---|
| `HEADER` | `#F5D7A1` | `38;2;245;215;161` | 13.8:1 | Warm cream glow for titles |
| `SEPARATOR` | `#2A2E40` | `38;2;42;46;64` | 1.4:1 | Deep indigo divider — **rules only, never text** |
| `DEVICE_NAME` | `#E8D6C8` | `38;2;232;214;200` | 13.6:1 | Soft cream: important identifiers |
| `RULE_ID` | `#B5E8A0` | `38;2;181;232;160` | 13.8:1 | Mint: technical references |
| `PATH` | `#B8DCFF` | `38;2;184;220;255` | 13.5:1 | Powder blue: filesystem paths |

`SEPARATOR` is the one value below 4.5:1, deliberately: it draws horizontal
rules, never text. `tests/test_theme.py` asserts the AA floor on every other
text color and exempts this one by name.

### Attributes

`RESET` (`\033[0m`), `BOLD` (`\033[1m`), `DIM` (`\033[2m`),
`ITALIC` (`\033[3m`), `UNDERLINE` (`\033[4m`).

Every attribute in `Colors` — including these — evaluates to the empty string
when `NO_COLOR` is set or stdout is not a TTY, so no output path needs to check.

## Icons

Two sets. Nerd Font codepoints are from the Font Awesome range, stable across
Nerd Fonts v2 and v3; the plain column is a single-width unicode fallback. The
Nerd glyphs are private-use codepoints - tofu in anything but a Nerd Font, so
they are not reproduced here; look one up by its codepoint instead.

| Name | Codepoint | Plain | Used for |
|---|---|---|---|
| `OK` | `U+F00C` | `✓` | Success confirmations |
| `FAIL` | `U+F00D` | `✗` | Errors, failures |
| `WARN` | `U+F071` | `⚠` | Warnings, refusals |
| `INFO` | `U+F05A` | `▸` | Informational notes |
| `BULLET` | `U+F111` | `•` | List items |
| `ARROW` | `U+F061` | `→` | Source to destination |
| `PHONE` | `U+F10B` | `▪` | Device lines, headers |
| `FOLDER` | `U+F07B` | `▸` | Directories |
| `FILE` | `U+F15B` | `•` | Files |
| `MOVE` | `U+F093` | `↑` | Move rules |
| `COPY` | `U+F0C5` | `+` | Copy and backup rules |
| `SYNC` | `U+F0EC` | `⇄` | Sync rules |
| `DELETE` | `U+F1F8` | `✗` | Deletions |
| `SKIP` | `U+F05E` | `-` | Skipped files |
| `RENAME` | `U+F040` | `~` | Renamed duplicates |
| `BOLT` | `U+F0E7` | `!` | Dry-run banner, web UI |
| `SEARCH` | `U+F002` | `?` | Scanning, in progress |
| `STATS` | `U+F080` | `#` | Summary blocks |

No emoji, anywhere. Emoji are double-width, carry invisible variation selectors
that break column alignment, and render inconsistently across terminals.
`tests/test_no_emoji.py` scans every module under `phone_migration/`, `scripts/`
and `main.py`, plus the web UI's `static/js`, `static/css` and `web_templates`,
and fails if one reappears; `tests/test_theme.py` separately asserts that every
glyph in both icon sets is single-width and not an emoji.

Numbered steps in help text use plain `1.` `2.` `3.`, never circled digits.

## Switching sets

All three switches are read once, at import time.

| Environment | Effect |
|---|---|
| `NO_COLOR` (any value) | Every `Colors` attribute becomes `""`. |
| stdout is not a TTY | Same as `NO_COLOR` — piped output is plain automatically. |
| `NERD_FONT=1` | Nerd Font icons. |
| `WEZTERM_PANE` set | Nerd Font icons, auto-detected. |
| `PHONE_SYNC_PLAIN_ICONS=1` | Plain icons. Wins over `NERD_FONT` and `WEZTERM_PANE`. |

```bash
# Reproducible, paste-safe output
PHONE_SYNC_PLAIN_ICONS=1 NO_COLOR=1 phone-sync --list-rules -p default
```

## Progress display

`phone_migration/progress.py` is the only module that animates. It holds three
pieces, all drawn from `Colors` and `Icons` like everything else:

- **`Spinner`** — a daemon thread cycling `| / - \\` at 10 Hz on a carriage
  return, in `INFO`. `stop()` erases the line and optionally prints one final
  line in its place.
- **`RuleProgress`** — wraps a `Spinner` per rule. The line is set once when the
  rule starts, reading `[2/5] SYNC (r-0003)`, and spins unchanged until the rule
  finishes; the spinner line is then replaced by a single settled line: `OK`/
  `FAIL` icon, the rule's summary, and the elapsed time, in `SUCCESS` or `ERROR`.
  (`update()` and `update_counts()` exist on the class and would rewrite the
  message with live file counts and a files/second rate, but nothing calls them —
  treat them as unused.)
- **`OperationProgress`** — one bar across all rules, in `ACCENT`, suffixed with
  an ETA extrapolated from the rules that have already finished.

Because the animation is written with carriage returns rather than newlines, a
redirected or piped run is best taken with `NO_COLOR=1`.

## Visual hierarchy

Real output, captured with `PHONE_SYNC_PLAIN_ICONS=1 NO_COLOR=1`.

Header and status:

```
────────────────────────────────────────────────────────────
▪  Phone Migration Tool
────────────────────────────────────────────────────────────

! DRY RUN MODE (preview only, no changes)

? Scanning for connected devices...

✗ No device found
```

Errors give reasons and numbered next steps rather than only a failure line:

```
Possible reasons:
  • Phone not connected via USB
  • File Transfer mode disabled
  • Phone is locked
  • Device not yet registered

Next steps:
  1. Connect phone & enable File Transfer
  2. Register: phone-sync --add-device --name default
  3. Execute: phone-sync --run -y
```

Rule listings pair a mode icon with the mode name and color:

```
Rules for profile 's25-ultra' (5 total)
──────────────────────────────────────────────────────────────────────

[r-0001] ↑ MOVE
  Phone:   /Download
  Desktop: ~/Downloads
  Action:  Copy to desktop, then delete from phone
  ····························································
…
[r-0003] ⇄ SYNC
  Desktop: ~/Videos/phone_videos/ck (source)
  Phone:   /Videos/ck
  Action:  Mirror desktop to phone (desktop is source of truth)
  ····························································
…
```

Conventions in use:

- Box-drawing rules (`─`, `·`) for section and record separators, in
  `SEPARATOR`.
- `HEADER` for titles, `PATH` for anything filesystem-shaped, `RULE_ID` for ids
  and copy-pasteable commands, `DIM` for labels.
- Action colors (`MOVED`, `BACKED_UP`, `SYNCED`, `DELETED`, `SKIPPED`,
  `RENAMED`) in summary lines, each with its matching icon.

## Accessibility

- **Contrast:** every text color clears WCAG AA (4.5:1) against `#0D0E16`, and
  all but `MUTED` clear AAA (7:1). This is asserted by
  `tests/test_theme.py::test_text_colors_are_readable_on_the_terminal_background`,
  so it cannot silently regress.
- **Colorblind readability:** `ERROR` (coral) and `SUCCESS` (mint) differ
  substantially in luminance, not only hue, and every state carries a distinct
  icon.
- **Monochrome:** the icon set alone distinguishes every action, so `NO_COLOR`
  output loses no information.
- **Width:** all icons in both sets are single-width, so columns stay aligned.

### Recomputing contrast

The WCAG formula, matching the helper in `tests/test_theme.py`:

```python
def relative_luminance(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg, bg):
    light, dark = sorted((relative_luminance(fg), relative_luminance(bg)),
                         reverse=True)
    return (light + 0.05) / (dark + 0.05)
```

## Terminal compatibility

Colors are 24-bit RGB (`\033[38;2;R;G;Bm`), which every modern terminal
emulator supports. There is no 256-color fallback and no light-background
variant; if you need either, `NO_COLOR=1` gives readable plain output on any
background.

### WezTerm

The palette as a WezTerm color scheme, for a terminal that matches the tool:

```lua
config.colors = {
    foreground = "#E8D6C8",
    background = "#0D0E16",

    ansi = {
        "#2E3440",  -- black
        "#F4A2A8",  -- red
        "#B5E8A0",  -- green
        "#F5D7A1",  -- yellow
        "#A0C8E8",  -- blue
        "#D4B5E8",  -- magenta
        "#A8E0E8",  -- cyan
        "#DAD1C8",  -- white
    },
    brights = {
        "#4A5366",  -- bright black
        "#FFB8BE",  -- bright red
        "#CEFAB5",  -- bright green
        "#FFE9B8",  -- bright yellow
        "#B8DCFF",  -- bright blue
        "#E8CFFF",  -- bright magenta
        "#BDFAFF",  -- bright cyan
        "#F5EDE5",  -- bright white
    },
}
```

Pair it with a Nerd Font (Hack Nerd Font Mono, JetBrains Mono Nerd Font, or
similar) so the icon set renders in its Nerd Font form; `WEZTERM_PANE` makes the
tool select that set automatically.

## Maintenance

### Adding a color

1. Add it to `Colors` in `phone_migration/theme.py`, with a comment saying what
   it means.
2. If it will carry text, check it against `#0D0E16` with the formula above; it
   must reach 4.5:1. Add it to `TEXT_COLORS` in `tests/test_theme.py`.
3. Regenerate the tables in this file.

### Adding an icon

1. Add it to `Icons` with both a Nerd Font codepoint and a single-width plain
   fallback.
2. Add the name to `ICON_NAMES` in `tests/test_theme.py`.
3. Add the row to the icon table here.

### Checking for drift

`tests/test_theme.py` scans every file under `phone_migration/`, `scripts/` and
`main.py` for `Colors.X` / `Icons.X` references and fails on any name the class
does not define. That test exists because a `Colors.RED` reference that no longer
existed used to crash every error path. Run the suite:

```bash
python3 -m pytest -q
```

Manual checks for hand-rolled color that bypassed the module:

```bash
grep -rn '\\033\[' --include='*.py' phone_migration main.py scripts
grep -rn 'class Colors' --include='*.py' phone_migration main.py scripts
```

Both should return only `phone_migration/theme.py`.

### Seeing the palette

```bash
python3 scripts/color_demo.py
```

## Status

| Item | State |
|---|---|
| One theme module, imported everywhere | Done |
| Legacy 16-color palettes removed from `operations.py`, `gio_utils.py`, `config.py` | Done |
| Emoji removed from CLI, web UI, templates and JS | Done |
| Nerd Font icons with a plain fallback | Done |
| `MUTED` raised to `#7C8399` to clear WCAG AA | Done |
| Contrast asserted by tests | Done |
| Undefined `Colors.X` / `Icons.X` caught by tests | Done |
| `--list-rules` styling | Done |
| Verbose file-by-file output | Done |
| Progress indicator for backups (`[142/1000 - 14.2%]`) | Done |
| Per-rule spinner and overall progress bar (`phone_migration/progress.py`) | Done |
| Progress bars for individual large transfers | Not planned — MTP gives no byte-level progress |
| Interactive confirmation prompt styling | Not planned — `-y` is the confirmation |
| Light-background palette variant | Not planned — use `NO_COLOR=1` |

## Inspiration

Nord, Tokyo Night, Catppuccin Mocha and Gruvbox, for muted tones over saturated
ones and warm color temperature on a dark base. What differs here is that the
colors are assigned by *action* rather than by syntax category: a file leaving
the phone and a file being preserved are told apart by color before you read the
word.
