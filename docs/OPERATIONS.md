# Rule Modes Guide

This document explains the four rule modes and what happens to your files with each mode.

## Overview

| Mode | Source (Phone) | Files Copied? | Files Kept? | Files Deleted? | Use Case |
|------|---|---|---|---|---|
| **Move** | Phone → Desktop | ✅ Yes | ❌ No | ✅ Yes (on phone) | Archive: Backup and clean phone |
| **Copy** | Phone → Desktop | ✅ Yes | ✅ Yes | ❌ No | Backup: Keep on phone + desktop |
| **Backup** | Phone → Desktop | ✅ Yes | ✅ Yes | ❌ No | Safe backup: Resumable, skips duplicates |
| **Sync** | Desktop ↔ Phone | ✅ Yes | ✅ Yes | ✅ Yes (mismatches) | Mirror: Keep desktop & phone in sync |

---

## 1. MOVE Mode 📤

**Direction:** Phone → Desktop

**What happens:**
- Copies files FROM phone TO desktop
- Deletes the files FROM phone (after successful copy)
- Keeps files on desktop

**Files on Desktop:** ✅ Present
**Files on Phone:** ❌ Deleted after copy

**Conflict handling:**
- By default: Renames duplicates (e.g., `photo.jpg` → `photo (1).jpg`)
- If you set `--no-rename`: Skips files that already exist

**Summary output:**
```
✓ Copied:   15 files
↻ Renamed:  2 (duplicates)
🗑️  Deleted:  15
```

**Best for:**
- Archiving: Moving photos off your phone to free up storage
- One-time backups: Transfer and clean
- Recovering storage space on phone

**Example:**
```bash
phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures
```

---

## 2. COPY Mode 📋

**Direction:** Phone → Desktop

**What happens:**
- Copies files FROM phone TO desktop
- Keeps files on both phone and desktop
- Does NOT delete anything

**Files on Desktop:** ✅ Present
**Files on Phone:** ✅ Still there

**Conflict handling:**
- By default: Renames duplicates (e.g., `photo.jpg` → `photo (1).jpg`)
- If you set `--no-rename`: Skips files that already exist

**Summary output:**
```
✓ Copied:   15 files
↻ Renamed:  2 (duplicates)
📋 Files backed up from phone: 17
```

**Best for:**
- Regular backups: Keep copies on desktop
- Sharing: Files stay on phone for access
- Safety: Never loses data from either location

**Example:**
```bash
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Pictures
```

---

## 3. BACKUP Mode 💾

**Direction:** Phone → Desktop

**What happens:**
- Copies files FROM phone TO desktop (resumable)
- Keeps files on both phone and desktop
- Does NOT delete anything
- **Tracks progress**: Can resume if interrupted
- **Skips unchanged files**: Uses smart comparison to skip already-copied files

**Files on Desktop:** ✅ Present
**Files on Phone:** ✅ Still there

**Conflict handling:**
- By default: **Skips** duplicates (do nothing on conflict)
- Rename duplicates: OFF by default (unlike Copy and Move)
- If you want renaming: Can be configured per rule

**Key differences from Copy:**
- ✅ Can resume if interrupted (saves progress)
- ✅ Smarter: Only copies files that changed
- ✅ Safer default: Skips duplicates instead of renaming

**Summary output:**
```
✓ Copied:   8 files (this run)
↻ Resumed:  152 files (previous runs)
⊙ Exists:   5 files (already backed up)
📋 Files backed up from phone: 165
```

**Best for:**
- Large backups: 1000+ files that might be interrupted
- External drives: Unreliable connections that need resumability
- Daily backups: Skip files that haven't changed

**Example:**
```bash
phone-sync --backup -p default -pp /DCIM/Camera -dp ~/Backups/Phone
```

---

## 4. SYNC Mode 🔄

**Direction:** Desktop ↔ Phone (Desktop is source of truth)

**What happens:**
- Copies files FROM desktop TO phone
- **Deletes files from phone that don't exist on desktop**
- **Keeps files on desktop unchanged**
- Creates a mirror copy on phone

**Files on Desktop:** ✅ Present (always)
**Files on Phone:** 
- ✅ Files that exist on desktop → copied
- ❌ Files that ONLY exist on phone → **deleted**

**Conflict handling:**
- Always overwrites phone files with desktop versions
- Files only on phone are considered "extraneous" and deleted

**Summary output:**
```
✓ Copied:   8 files to phone
🗑️  Deleted:  3 files from phone (no longer on desktop)
📥 Files synced to phone: 8
```

**Best for:**
- Keeping playlists in sync: Desktop playlist → phone
- Keeping documents in sync: Desktop folder → phone
- Mirror operations: Desktop is "source of truth"

**Example:**
```bash
phone-sync --sync -p default -dp ~/Music/Playlists -pp /Music/phone-sync
```

---

## Conflict Resolution Summary

| Mode | File Already Exists | Default Behavior | Alternative |
|------|---|---|---|
| Move | Duplicate exists | Rename to `name (N).ext` | Skip file |
| Copy | Duplicate exists | Rename to `name (N).ext` | Skip file |
| Backup | Duplicate exists | **Skip file** | Rename (configurable) |
| Sync | File on phone only | Delete from phone | N/A (always deletes) |

---

## Conflict Resolution Examples

### Move/Copy with Duplicate (default = rename)
```
Desktop already has: photo.jpg
Attempting to copy: photo.jpg

Result: Renamed to photo (1).jpg
Output: "↻ Renamed: 1 (duplicates)"
```

### Backup with Duplicate (default = skip)
```
Desktop already has: photo.jpg
Attempting to backup: photo.jpg

Result: File skipped, left alone
Output: "⊙ Exists: 1 files (already backed up)"
```

### Sync with Extraneous File
```
Desktop has: song1.mp3, song2.mp3
Phone has: song1.mp3, song2.mp3, old_song.mp3

Result: old_song.mp3 deleted from phone
Output: "🗑️  Deleted: 1 files from phone"
```

---

## Choosing the Right Mode

### "I want to back up my photos"
→ Use **COPY** (safe, keeps everything) or **BACKUP** (resumable, smarter)

### "I want to free up phone storage"
→ Use **MOVE** (copies then deletes from phone)

### "I want to keep my playlists in sync"
→ Use **SYNC** (desktop is source of truth)

### "I have a huge folder with unstable connection"
→ Use **BACKUP** (resumable, can pick up where it left off)

### "I want maximum safety"
→ Use **COPY** (never deletes anything)

---

## Manual vs Auto Rules

By default, all rules run automatically. You can mark rules as "Manual only" to require explicit execution.

```bash
# Add auto rule (runs with --run)
phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Pictures

# Add manual-only rule (must run with --run -r rule-id)
phone-sync --copy -p default -pp /DCIM/Screenshot -dp ~/Pictures --manual
```

When using the web UI, you can select which manual rules to run via the "Run Manual Rules" button.

---

## Progress Tracking

### Backup Mode Features
- **Resumable**: If connection drops, rerun the same command to continue
- **Smart comparison**: Only copies files that have changed
- **Progress indicator**: Shows `[15/1000 - 1.5%]` during operation
- **Verbose mode**: See detailed file-by-file progress in web UI

---

## Summary Table: What Gets Copied/Deleted

| Scenario | Move | Copy | Backup | Sync |
|----------|------|------|--------|------|
| New file on phone | Copy & delete from phone | Copy only | Copy only | N/A |
| File exists on both | Rename/skip & delete original | Rename/skip | Skip | Overwrite phone |
| File only on desktop | N/A | N/A | N/A | Copy to phone |
| File only on phone | Delete from phone | Keep on phone | Keep on phone | Delete from phone |
| Unchanged file | Copy & delete | Copy | Skip (smart) | Skip if unchanged |

