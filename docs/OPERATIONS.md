# Operations Guide

There are four rule modes. This document says exactly what each one does to your
files, so you can pick the right one before you pass `-y`.

> Every example below previews when run as written and transfers when you add
> `-y`. `phone-sync --run` never modifies anything.

## Before every real run

Two checks bracket a run, and neither is configurable:

- **Preflight (real runs only).** Before each rule executes, the transfer size is
  estimated by walking the rule's phone folder — a lower bound, since the walk
  stops after 2000 entries — and compared against the free space on the
  destination filesystem, measured on the nearest existing ancestor because the
  destination itself is created moments later; the transfer must fit with 5% of
  the free space still left over. If it does not, that rule is skipped with a `Preflight check failed`
  message naming the deficit, and the run continues with the other rules. Sync is
  the exception: MTP does not report the phone's free space, so a sync rule's
  check is logged as skipped rather than enforced.
- **Dry-run analysis (previews only).** After a preview, its own statistics are
  re-read and checked for results that should be impossible — a copy that
  deleted, a move whose deletions do not equal its copies, a backup that deleted
  anything. Those are blockers, and the preview then ends with `OPERATION
  BLOCKED` instead of the usual "execute with -y" hint. Lopsided or very large
  deletions are warnings; a rule that would change nothing is an info note. A
  preview with no findings prints `All safety checks passed!`.

## Overview

| Mode | Direction | Source files kept? | Deletes anything? | Use case |
|---|---|---|---|---|
| **Move** | Phone to desktop | No, removed from the phone | Yes, on the phone | Free up phone storage |
| **Copy** | Phone to desktop | Yes | No | Keep a second copy on the desktop |
| **Backup** | Phone to desktop | Yes | No | Large or interruptible transfers |
| **Sync** | Desktop to phone | Yes, desktop is never touched | Yes, on the phone | Mirror a desktop folder onto the phone |

---

## Move mode

**Direction:** phone to desktop.

**What happens**

1. The phone directory is listed.
2. Each file is copied to the desktop.
3. The desktop copy is verified: it must exist, and its size must equal the
   source size.
4. Only then is the original deleted from the phone.
5. Directories left empty by the move are removed, best effort.

If the source size cannot be read, the desktop copy is kept but **the original
stays on the phone** and the run reports an error. Nothing is ever deleted on
the strength of a copy that could not be verified.

**Conflict handling.** A plain `--run` renames: `photo.jpg` becomes
`photo (1).jpg`, `photo (2).jpg`, and so on, up to 1000 attempts. In the web UI
you can turn the "Rename on conflict" toggle off, in which case a name that is
already taken on the desktop is skipped and the phone's copy is left alone.
There is no CLI flag for this.

**Example**

```bash
phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
phone-sync --run -y
```

---

## Copy mode

**Direction:** phone to desktop.

Identical to move, minus steps 4 and 5: nothing is deleted from either side.
The same size verification runs, but a mismatch just reports the file as failed.

**Conflict handling.** Same as move — rename by default, skip when the web UI's
rename toggle is off.

**Example**

```bash
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Pictures/Camera
phone-sync --run -y
```

---

## Backup mode

**Direction:** phone to desktop. Never deletes anything, on either side.

Backup is copy plus a resume record. It exists for transfers big enough that
being interrupted matters.

**What happens**

1. The whole phone subtree is scanned first, so the run knows its total.
2. Each file is copied, with a `[142/1000 - 14.2%]` progress line.
3. Progress is written to
   `~/.local/share/phone-migration/state.json` every 25 files, at the end of the
   run, and on Ctrl+C. It is keyed `"<profile>:<rule id>"`, so two phones with a
   rule `r-0001` each keep separate state.
4. When the run finishes with no failures and every file accounted for, the
   resume record is cleared.

Re-running the same rule picks up where the previous run stopped.

**What counts as "already backed up"**

Backup does **not** hash files, read timestamps, or do any other content
comparison, and it does **not** consult the state file to decide this. A file is
left alone on one condition only: the desktop already holds a file at that
relative path whose size equals the phone's. It is then counted under "Already
backed up" and nothing is transferred for it.

The state file decides something narrower — see below. It is what makes the
"Resuming: N files copied by an earlier run" line possible and what tells
backup's own output apart from a file you put there yourself, but a file listed
in it is still re-examined by size on every run.

Because the check is path plus size, a file edited on the phone without changing
its size will not be picked up again.

**Resuming over a changed desktop file.** If the desktop copy was written by an
earlier run of this same rule (it is in the state file) and its size no longer
matches the phone's copy — a truncated transfer, typically — it is overwritten.
The phone is treated as the source. A file that this rule did not write is never
overwritten; it goes through the conflict handling below.

**Conflict handling.** Backup **skips** by default, unlike move and copy: a
name that is already taken and that this rule did not write is left alone and
counted under "Skipped (conflict, not copied)". Renaming would duplicate the
entire archive on every run.

**This default applies to a plain CLI `--run` only.** The dashboard's "Rename on
Conflict" toggle ships **on**, so a backup rule started from the web UI renames
on conflict unless you untick it first.

**Example**

```bash
phone-sync --backup -p default -pp /DCIM -dp ~/Backups/Phone/DCIM
phone-sync --run -y
# interrupted? run it again, it resumes
```

`--smart-copy` is a deprecated alias for `--backup`, and rules stored with
`"mode": "smart_copy"` still run as backups.

---

## Sync mode

**Direction:** desktop to phone. The desktop is the source of truth and is
**never modified**.

**What happens**

1. The desktop directory is walked.
2. A file is copied to the phone when the phone has no copy of it, or has one of
   a different size. Sync always overwrites a size-mismatched phone file; there
   is no flag for that and no `"overwrite"` field in the rule.
3. A phone file whose size already matches is left alone and counted as
   unchanged.
4. If the rule sets `delete_extraneous: true`, phone files and directories that
   do not exist on the desktop are deleted.

**When `delete_extraneous` refuses to delete**

Deleting the phone's side of a mirror is the most destructive thing this tool
does, so it is skipped entirely — with a warning, while the copying half still
runs — in any of these cases:

- the desktop scan hit an entry it could not read, so the file list is
  incomplete. Two cases are worth naming: a **broken symlink** is skipped, and a
  **symlink loop** — a symlinked directory that leads back to a directory the
  scan already walked, directly or through a chain — is detected by inode and not
  followed again. Either one marks the scan incomplete, so the phone keeps its
  copy of everything;
- the desktop scan found no files at all;
- the rule's phone path is the storage root rather than a folder inside it.

The rule behind all three: a partial or empty picture of the desktop must never
turn into a mass deletion on the phone.

Separately, a `desktop_path` that is not a directory is an outright error: the
rule stops before step 1, so nothing is copied and nothing is deleted.

**Example**

```bash
phone-sync --sync -p default -dp ~/Music/Playlists -pp /Music/playlists
phone-sync --run -y
```

---

## Conflict resolution summary

| Mode | Destination name already taken | Default | Web UI toggle |
|---|---|---|---|
| Move | Desktop has that name | Rename to `name (N).ext` | Skip |
| Copy | Desktop has that name | Rename to `name (N).ext` | Skip |
| Backup | Desktop has that name, not written by this rule | **Skip** | Rename |
| Sync | Phone has a differently sized copy | Overwrite | Not configurable |

The "Default" column is what a plain CLI `--run` does; the CLI has no flag to
change it. The rename/skip choice is a run-time toggle in the web UI, not
something stored on the rule — and it ships **on**, so a backup rule run from
the dashboard renames on conflict rather than skipping unless you untick it.

### Worked examples

Move or copy, name already taken (default: rename):

```
Desktop already has: photo.jpg
Copying from phone:  photo.jpg
Result:              written as photo (1).jpg
```

Backup, name already taken (default: skip):

```
Desktop already has: photo.jpg   (not recorded in this rule's state)
Backing up:          photo.jpg
Result:              left alone, counted as "Skipped (conflict, not copied)"
```

Backup, same file, same size:

```
Desktop already has: photo.jpg   (2,481,003 bytes)
Phone has:           photo.jpg   (2,481,003 bytes)
Result:              nothing transferred, counted as "Already backed up"
```

Sync, extraneous phone file:

```
Desktop has: song1.mp3, song2.mp3
Phone has:   song1.mp3, song2.mp3, old_song.mp3
Result:      old_song.mp3 deleted from the phone
```

---

## Choosing a mode

| You want to... | Use |
|---|---|
| Free up space on the phone | **Move** |
| Keep a desktop copy, keep the phone copy too | **Copy** |
| Transfer thousands of files over a flaky connection | **Backup** |
| Push a desktop folder onto the phone and keep it matching | **Sync** |
| Take no risk of losing anything anywhere | **Copy** or **Backup** |

---

## Manual vs auto rules

Rules run automatically by default. Tag a rule `--manual` and a plain `--run`
skips it:

```bash
# Auto: runs with a plain --run
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Pictures

# Manual only
phone-sync --copy -p default -pp /DCIM/Screenshots -dp ~/Pictures --manual
```

Run manual rules by including them all, or by id:

```bash
phone-sync --run --manual -y       # every rule, auto and manual
phone-sync --run -r r-0003 -y      # just this one
```

`--edit-rule --no-manual` clears the flag on an existing rule.

In the web UI, the button labelled "Run All Rules" behaves like a plain `--run`
and therefore skips manual-only rules, despite the label; "Run Manual Rules" runs
the ones you tick.

---

## What gets copied and deleted

| Situation | Move | Copy | Backup | Sync |
|---|---|---|---|---|
| File on phone, not on desktop | Copy, then delete from phone | Copy | Copy | n/a |
| Name taken on desktop | Rename (or skip), then delete original | Rename (or skip) | Skip (or rename) | n/a |
| Same name and size on both sides | Copy, then delete from phone | Copy | Already backed up, nothing transferred | n/a |
| File on desktop, not on phone | n/a | n/a | n/a | Copy to phone |
| File on desktop, phone copy differs in size | n/a | n/a | n/a | Overwrite phone copy |
| File on desktop, phone copy same size | n/a | n/a | n/a | Unchanged, skipped |
| File on phone, not on desktop | Delete from phone | Kept | Kept | Deleted if `delete_extraneous` |

Move's copy-then-delete is always size-verified first; see the move section.
