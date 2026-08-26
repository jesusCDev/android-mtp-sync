"""File operations for copy, move, backup and sync rules.

Every ``run_*_rule`` returns its counters plus ``"files"``: one entry per file
the rule touched, shaped ``{"action", "src", "dst", "error"}``. Task 6 feeds
those straight into ``RunResult`` - nothing parses the printed lines.

``action`` names the outcome: ``copied`` / ``moved`` / ``synced`` for a
transfer, ``renamed`` in place of those when a duplicate forced a new name,
plus ``skipped``, ``deleted``, ``folder`` and ``failed``. ``src`` is the phone
path relative to the rule root and ``dst`` the desktop path - swapped for sync,
whose source of truth is the desktop.

A rule never raises: an unusable desktop path or a failed listing is counted in
``errors``, recorded in ``files``, and the rule returns what it managed to do.

Two safety rules run through all of this:

* nothing is deleted from the phone that was not first copied **and verified
  byte-count-equal** to the source;
* under ``gio_utils.DRY_RUN`` nothing is created, written or removed - not the
  destination tree, not the resume state.
"""

import os
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from . import gio_utils, paths, state
from .gio_utils import GioError
from .theme import Colors, Icons

# ponytail: flush every 25 files, per-file writes were O(n^2)
SAVE_EVERY = 25


# --- shared plumbing ---------------------------------------------------------

def _display(path) -> str:
    """A desktop path as the user writes it: ``~/Pictures/a.jpg``."""
    return gio_utils.shorten_path(str(path))


def _record(stats: Dict[str, Any], action: str, src: str,
            dst: Optional[str] = None, error: Optional[str] = None) -> None:
    stats["files"].append({"action": action, "src": src, "dst": dst, "error": error})


def _fail(stats: Dict[str, Any], src: str, error, dst: Optional[str] = None) -> None:
    """Count an error, log it structurally, and say so on stdout."""
    stats["errors"] += 1
    _record(stats, "failed", src, dst, str(error))
    print(f"  {Colors.ERROR}{Icons.FAIL}{Colors.RESET} {src}: {Colors.DIM}{error}{Colors.RESET}")


def _endpoints(rule: Dict[str, Any], device: Dict[str, Any]) -> Tuple[str, Path]:
    """(phone URI, desktop dir). Raises ValueError on an empty desktop path."""
    source_uri = paths.build_phone_uri(device.get("activation_uri", ""),
                                       rule.get("phone_path", ""))
    return source_uri, paths.expand_desktop(rule.get("desktop_path", ""))


def _ensure_dir(path: Path) -> None:
    """Create a desktop directory - except in a dry run, which creates nothing."""
    if not gio_utils.DRY_RUN:
        paths.ensure_dir(path)


def _listing(uri: str, display: str, stats: Dict[str, Any]) -> Optional[List[str]]:
    """Entry names, or None when gio could not list them. A failed listing is
    never an empty directory - callers must not delete anything under it."""
    try:
        return gio_utils.gio_list(uri)
    except GioError as err:
        _fail(stats, display, err)
        return None


def _is_regular(info: Dict[str, str]) -> bool:
    entry_type = info.get("standard::type", "")
    return "regular" in entry_type.lower() or entry_type == "1"


def _new_stats(*names: str) -> Dict[str, Any]:
    stats: Dict[str, Any] = {name: 0 for name in names}
    stats["files"] = []
    return stats


# --- phone -> desktop (copy and move share one walk) -------------------------

def run_copy_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False,
                  transfer_tracker=None, rename_duplicates: bool = True) -> Dict[str, Any]:
    """Copy a phone directory to the desktop, leaving the phone untouched."""
    stats = _new_stats("copied", "renamed", "errors", "skipped", "folders")
    phone_path = rule.get("phone_path", "")

    try:
        source_uri, dest_dir = _endpoints(rule, device)
    except ValueError as err:
        _fail(stats, phone_path, err)
        return stats

    print(f"\n{Colors.BOLD}{Colors.INFO}{Icons.COPY} Copy:{Colors.RESET} "
          f"{Colors.PATH}{phone_path}{Colors.RESET} {Colors.DIM}{Icons.ARROW}{Colors.RESET} "
          f"{Colors.PATH}{_display(dest_dir)}{Colors.RESET}\n")

    _ensure_dir(dest_dir)
    _pull_directory(source_uri, dest_dir, "", stats, verbose,
                    rename_duplicates, transfer_tracker)
    _print_pull_summary(stats, "Copied")
    return stats


def run_move_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False,
                  transfer_tracker=None, rename_duplicates: bool = True) -> Dict[str, Any]:
    """Copy a phone directory to the desktop, then delete the originals.

    Only files whose desktop copy matches the source byte count are deleted;
    everything else stays on the phone and is counted as an error.
    """
    stats = _new_stats("copied", "renamed", "deleted", "errors", "skipped", "folders")
    phone_path = rule.get("phone_path", "")

    try:
        source_uri, dest_dir = _endpoints(rule, device)
    except ValueError as err:
        _fail(stats, phone_path, err)
        return stats

    print(f"\n{Colors.BOLD}{Colors.MOVED}{Icons.MOVE} Move:{Colors.RESET} "
          f"{Colors.PATH}{phone_path}{Colors.RESET} {Colors.DIM}{Icons.ARROW}{Colors.RESET} "
          f"{Colors.PATH}{_display(dest_dir)}{Colors.RESET}\n")

    _ensure_dir(dest_dir)
    verified: List[Tuple[str, str, str, str]] = []
    listed_everything = _pull_directory(source_uri, dest_dir, "", stats, verbose,
                                        rename_duplicates, transfer_tracker, verified)

    # SAFETY: `verified` holds only entries `_pull_file` appended after a
    # size-verified successful copy (dry-run: gio_copy reported success under
    # DRY_RUN; execute: dest_file exists and its byte count matches the
    # source). Nothing below this line is ever reached for an unverified copy.
    for entry_uri, entry_rel, dest_display, action in verified:
        if gio_utils.gio_remove(entry_uri, verbose=verbose):
            stats["deleted"] += 1
            _record(stats, action, entry_rel, dest_display)
        else:
            stats["errors"] += 1
            _record(stats, "copied", entry_rel, dest_display,
                    "copied to the desktop but not deleted from the phone")

    if listed_everything:
        _cleanup_empty_dirs(source_uri, "", stats, verbose)
    _print_pull_summary(stats, "Moved")
    return stats


def _pull_directory(source_uri: str, dest_dir: Path, rel_path: str,
                    stats: Dict[str, Any], verbose: bool, rename_duplicates: bool,
                    transfer_tracker, verified: Optional[list] = None) -> bool:
    """Walk one phone directory. ``verified`` is a move's delete queue: pass a
    list to have size-verified files appended to it, None to only copy.

    Returns False when any directory in the subtree could not be listed - a move
    must not try to tidy up a tree it could not read.

    ponytail: one `gio info` per entry (gio_list_detailed would be one call per
    directory) - only `gio info` tells a failed lookup apart from a plain file,
    and that difference is what stops an unreadable entry being skipped silently.
    """
    entries = _listing(source_uri, rel_path or ".", stats)
    if entries is None:
        return False

    complete = True
    for name in entries:
        entry_uri = gio_utils.child_uri(source_uri, name)
        entry_rel = f"{rel_path}/{name}" if rel_path else name

        try:
            info = gio_utils.gio_info(entry_uri)
        except GioError as err:
            _fail(stats, entry_rel, err)
            complete = False
            continue

        if gio_utils.is_dir(info):
            sub_dest = dest_dir / name
            stats["folders"] += 1
            _record(stats, "folder", entry_rel, _display(sub_dest))
            print(f"  {Colors.ACCENT}{Icons.FOLDER}{Colors.RESET} {Colors.BOLD}{name}/{Colors.RESET} "
                  f"{Colors.DIM}{Icons.ARROW} {_display(sub_dest)}{Colors.RESET}")
            _ensure_dir(sub_dest)
            complete &= _pull_directory(entry_uri, sub_dest, entry_rel, stats, verbose,
                                        rename_duplicates, transfer_tracker, verified)
            continue

        if not _is_regular(info):
            _fail(stats, entry_rel, "not a file or a directory - gio could not read it")
            continue

        _pull_file(entry_uri, entry_rel, name, info, dest_dir, stats, verbose,
                   rename_duplicates, transfer_tracker, verified)

    return complete


def _pull_file(entry_uri: str, entry_rel: str, name: str, info: Dict[str, str],
               dest_dir: Path, stats: Dict[str, Any], verbose: bool,
               rename_duplicates: bool, transfer_tracker,
               verified: Optional[list]) -> None:
    dest_file = paths.next_available_name(dest_dir, name,
                                          rename_duplicates=rename_duplicates)
    if dest_file is None:
        if rename_duplicates:
            _fail(stats, entry_rel,
                  f"no free name after {paths.MAX_DUPLICATES} attempts",
                  _display(dest_dir / name))
        else:
            stats["skipped"] += 1
            _record(stats, "skipped", entry_rel, _display(dest_dir / name),
                    "already on the desktop, not copied")
            if verbose:
                print(f"  {Colors.SKIPPED}{Icons.SKIP}{Colors.RESET} "
                      f"{Colors.DIM}{name} (already on the desktop){Colors.RESET}")
        return

    renamed = dest_file.name != name
    source_size = gio_utils.get_file_size(info)
    dest_display = _display(dest_file)

    if not gio_utils.gio_copy(entry_uri, str(dest_file), verbose=verbose or not renamed):
        _fail(stats, entry_rel, "copy failed", dest_display)
        return

    if gio_utils.DRY_RUN:
        copied_size = source_size          # nothing was written, nothing to stat
    elif not dest_file.exists():
        _fail(stats, entry_rel, "gio reported success but nothing arrived", dest_display)
        return
    else:
        copied_size = dest_file.stat().st_size
        if source_size is not None and copied_size != source_size:
            _fail(stats, entry_rel,
                  f"size mismatch: {copied_size} of {source_size} bytes arrived",
                  dest_display)
            return

    stats["copied"] += 1
    if renamed:
        stats["renamed"] += 1
        print(f"  {Colors.RENAMED}{Icons.RENAME}{Colors.RESET} {Colors.DIM}{name}{Colors.RESET} "
              f"{Icons.ARROW} {Colors.RENAMED}{dest_file.name}{Colors.RESET} "
              f"{Colors.DIM}(duplicate){Colors.RESET}")
    if transfer_tracker and copied_size:
        transfer_tracker.add_file(copied_size)

    action = "renamed" if renamed else ("moved" if verified is not None else "copied")
    if verified is None:
        _record(stats, action, entry_rel, dest_display)
        return

    if source_size is None and not gio_utils.DRY_RUN:
        # Unverifiable: the desktop copy stands, but the original stays put.
        stats["errors"] += 1
        _record(stats, "copied", entry_rel, dest_display,
                "source size unknown - original kept on the phone")
        return

    verified.append((entry_uri, entry_rel, dest_display, action))


def _cleanup_empty_dirs(dir_uri: str, rel_path: str, stats: Dict[str, Any],
                        verbose: bool) -> None:
    """Remove subdirectories a move emptied. A directory is removed only when
    its own listing comes back empty; a listing that fails aborts that subtree.
    The rule root itself is never removed."""
    entries = _listing(dir_uri, rel_path or ".", stats)
    if entries is None:
        return

    for name in entries:
        entry_uri = gio_utils.child_uri(dir_uri, name)
        entry_rel = f"{rel_path}/{name}" if rel_path else name

        try:
            info = gio_utils.gio_info(entry_uri)
        except GioError as err:
            _fail(stats, entry_rel, err)
            continue
        if not gio_utils.is_dir(info):
            continue

        _cleanup_empty_dirs(entry_uri, entry_rel, stats, verbose)

        remaining = _listing(entry_uri, entry_rel, stats)
        if remaining is None or remaining:
            continue
        # ponytail: best effort - a directory the phone refuses to drop is not
        # an error, the files are already safely off it.
        if gio_utils.gio_remove(entry_uri, verbose=verbose):
            stats["deleted"] += 1
            _record(stats, "deleted", entry_rel)


def _print_pull_summary(stats: Dict[str, Any], label: str) -> None:
    print(f"\n  {Colors.SUCCESS}{Icons.OK} {label}:{Colors.RESET} {stats['copied']} files")
    if stats["folders"]:
        print(f"  {Colors.ACCENT}{Icons.FOLDER} Folders:{Colors.RESET} {stats['folders']}")
    if stats["renamed"]:
        print(f"  {Colors.RENAMED}{Icons.RENAME} Renamed:{Colors.RESET} "
              f"{stats['renamed']} (duplicates)")
    if stats["skipped"]:
        print(f"  {Colors.SKIPPED}{Icons.SKIP} Skipped:{Colors.RESET} "
              f"{stats['skipped']} (already on the desktop)")
    if stats.get("deleted"):
        print(f"  {Colors.DELETED}{Icons.DELETE} Deleted from phone:{Colors.RESET} "
              f"{stats['deleted']}")
    if stats["errors"]:
        print(f"  {Colors.ERROR}{Icons.FAIL} Errors:{Colors.RESET} {stats['errors']}")


# --- backup (resumable copy) -------------------------------------------------

def run_backup_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False,
                    transfer_tracker=None, rename_duplicates: bool = False,
                    profile_name: str = "") -> Dict[str, Any]:
    """Resumable phone -> desktop copy.

    Progress is keyed ``"<profile>:<rule id>"`` and flushed in batches. State is
    cleared only when nothing failed and every file is accounted for, so an
    interrupted run always resumes instead of starting over.
    """
    stats = _new_stats("copied", "resumed", "skipped", "failed", "errors")
    phone_path = rule.get("phone_path", "")
    rule_id = rule.get("id", "unknown")
    state_key = f"{profile_name}:{rule_id}"

    try:
        source_uri, dest_dir = _endpoints(rule, device)
    except ValueError as err:
        _fail(stats, phone_path, err)
        return stats

    print(f"\n{Colors.BOLD}{Colors.BACKED_UP}{Icons.COPY} Backup:{Colors.RESET} "
          f"{Colors.PATH}{phone_path}{Colors.RESET} {Colors.DIM}{Icons.ARROW}{Colors.RESET} "
          f"{Colors.PATH}{_display(dest_dir)}{Colors.RESET}")

    rule_state = state.load_rule_state(state_key)
    copied_paths: Set[str] = rule_state["copied"]
    failed_paths: Dict[str, str] = rule_state["failed"]
    if copied_paths:
        print(f"  {Colors.INFO}{Icons.INFO} Resuming:{Colors.RESET} "
              f"{len(copied_paths)} files copied by an earlier run")

    print(f"  {Colors.DIM}Scanning source directory...{Colors.RESET}")
    all_files: List[Tuple[str, Optional[int], str]] = []
    _scan_files(source_uri, "", all_files, stats)
    total_files = len(all_files)
    if not total_files:
        print(f"  {Colors.WARNING}{Icons.WARN} No files found{Colors.RESET}")
        return stats
    print(f"  {Colors.DIM}Found:{Colors.RESET} {total_files} files\n")

    _ensure_dir(dest_dir)

    try:
        for index, (rel_path, source_size, entry_uri) in enumerate(all_files, 1):
            _backup_one(rel_path, source_size, entry_uri, dest_dir, stats,
                        copied_paths, failed_paths, verbose, rename_duplicates,
                        transfer_tracker, index, total_files)
            if index % SAVE_EVERY == 0:
                _save_progress(state_key, copied_paths, failed_paths, total_files)
    except KeyboardInterrupt:
        _save_progress(state_key, copied_paths, failed_paths, total_files)
        print(f"\n\n  {Colors.WARNING}{Icons.WARN} Interrupted.{Colors.RESET} Progress saved.")
        print(f"  {Colors.INFO}{Icons.INFO} Resume with:{Colors.RESET} "
              f"{Colors.RULE_ID}phone-sync --run -r {rule_id} -y{Colors.RESET}\n")
        raise

    complete = (stats["failed"] == 0 and stats["errors"] == 0
                and len(copied_paths) + stats["skipped"] >= total_files)
    if complete:
        print(f"\n  {Colors.SUCCESS}{Icons.OK} Backup complete.{Colors.RESET} "
              f"{Colors.DIM}Resume state cleared.{Colors.RESET}")
        if not gio_utils.DRY_RUN:
            state.mark_rule_complete(state_key)
    else:
        _save_progress(state_key, copied_paths, failed_paths, total_files)
        if stats["failed"]:
            print(f"\n  {Colors.WARNING}{Icons.WARN} {stats['failed']} files failed.{Colors.RESET} "
                  f"Run again to retry them.")

    print(f"\n  {Colors.SUCCESS}{Icons.OK} Copied:{Colors.RESET} {stats['copied']} files (this run)")
    if stats["resumed"]:
        print(f"  {Colors.INFO}{Icons.INFO} Already backed up:{Colors.RESET} {stats['resumed']} files")
    if stats["skipped"]:
        print(f"  {Colors.SKIPPED}{Icons.SKIP} Skipped:{Colors.RESET} "
              f"{stats['skipped']} files (conflict, not copied)")
    if stats["failed"]:
        print(f"  {Colors.ERROR}{Icons.FAIL} Failed:{Colors.RESET} {stats['failed']} files")
    if stats["errors"]:
        print(f"  {Colors.ERROR}{Icons.FAIL} Errors:{Colors.RESET} {stats['errors']}")

    return stats


def _backup_one(rel_path: str, source_size: Optional[int], entry_uri: str, dest_dir: Path,
                stats: Dict[str, Any], copied_paths: Set[str], failed_paths: Dict[str, str],
                verbose: bool, rename_duplicates: bool, transfer_tracker,
                index: int, total_files: int) -> None:
    dest_file = dest_dir / rel_path

    # Already there and the same size? Nothing to do - this is what makes a
    # resume cheap, and what stops a truncated file being skipped forever.
    if (source_size is not None and dest_file.exists()
            and dest_file.stat().st_size == source_size):
        stats["resumed"] += 1
        copied_paths.add(rel_path)
        failed_paths.pop(rel_path, None)
        _record(stats, "skipped", rel_path, _display(dest_file), "already backed up")
        return

    _ensure_dir(dest_file.parent)
    if dest_file.exists() and rel_path in copied_paths:
        # An earlier run of this rule wrote that file and it no longer matches
        # the phone: overwrite it, it is our own leftover, not someone's file.
        target = dest_file
    else:
        target = paths.next_available_name(dest_file.parent, dest_file.name,
                                           rename_duplicates=rename_duplicates)
    if target is None:
        if rename_duplicates:
            stats["failed"] += 1
            failed_paths[rel_path] = f"no free name after {paths.MAX_DUPLICATES} attempts"
            _record(stats, "failed", rel_path, _display(dest_file), failed_paths[rel_path])
        else:
            stats["skipped"] += 1
            failed_paths[rel_path] = "conflict, not copied"
            _record(stats, "skipped", rel_path, _display(dest_file), "conflict, not copied")
        return

    if verbose or index % 10 == 0:
        percent = index / total_files * 100
        print(f"  {Colors.DIM}[{index}/{total_files} - {percent:.1f}%]{Colors.RESET} {rel_path}")

    if not gio_utils.gio_copy(entry_uri, str(target), verbose=verbose):
        stats["failed"] += 1
        failed_paths[rel_path] = "copy failed"
        _record(stats, "failed", rel_path, _display(target), "copy failed")
        return

    if gio_utils.DRY_RUN:
        copied_size = source_size
    elif not target.exists():
        stats["failed"] += 1
        failed_paths[rel_path] = "gio reported success but nothing arrived"
        _record(stats, "failed", rel_path, _display(target), failed_paths[rel_path])
        return
    else:
        copied_size = target.stat().st_size
        if source_size is not None and copied_size != source_size:
            stats["failed"] += 1
            failed_paths[rel_path] = (f"size mismatch: {copied_size} of "
                                      f"{source_size} bytes arrived")
            _record(stats, "failed", rel_path, _display(target), failed_paths[rel_path])
            return

    stats["copied"] += 1
    copied_paths.add(rel_path)
    failed_paths.pop(rel_path, None)
    _record(stats, "copied", rel_path, _display(target))
    if transfer_tracker and copied_size:
        transfer_tracker.add_file(copied_size)


def _save_progress(state_key: str, copied: Set[str], failed: Dict[str, str],
                   total_files: int) -> None:
    if not gio_utils.DRY_RUN:
        state.save_rule_state(state_key, copied, failed, total_files)


def _scan_files(source_uri: str, rel_path: str,
               found: List[Tuple[str, Optional[int], str]], stats: Dict[str, Any]) -> None:
    """Collect (relative path, size, URI) for every regular file, depth first."""
    entries = _listing(source_uri, rel_path or ".", stats)
    if entries is None:
        return

    for name in entries:
        entry_uri = gio_utils.child_uri(source_uri, name)
        entry_rel = f"{rel_path}/{name}" if rel_path else name

        try:
            info = gio_utils.gio_info(entry_uri)
        except GioError as err:
            _fail(stats, entry_rel, err)
            continue

        if gio_utils.is_dir(info):
            _scan_files(entry_uri, entry_rel, found, stats)
        elif _is_regular(info):
            found.append((entry_rel, gio_utils.get_file_size(info), entry_uri))
        else:
            _fail(stats, entry_rel, "not a file or a directory - gio could not read it")


# Legacy name, same function - the CLI and saved configs still say "smart copy".
run_smart_copy_rule = run_backup_rule


# --- sync (desktop is the source of truth) -----------------------------------

def run_sync_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False,
                  transfer_tracker=None) -> Dict[str, Any]:
    """Mirror a desktop directory onto the phone.

    Files are copied when the phone has no copy or a differently sized one.
    Extraneous phone files are deleted only when the rule asks for it *and* the
    desktop scan actually produced a complete file list - an empty or partial
    scan means the phone keeps everything.
    """
    stats = _new_stats("copied", "skipped", "deleted", "errors")
    phone_path = rule.get("phone_path", "")

    try:
        src_dir = paths.expand_desktop(rule.get("desktop_path", ""))
    except ValueError as err:
        _fail(stats, rule.get("desktop_path", ""), err)
        return stats

    dest_uri = paths.build_phone_uri(device.get("activation_uri", ""), phone_path)
    print(f"\n{Colors.BOLD}{Colors.SYNCED}{Icons.SYNC} Sync:{Colors.RESET} "
          f"{Colors.PATH}{_display(src_dir)}{Colors.RESET} "
          f"{Colors.DIM}{Icons.ARROW}{Colors.RESET} {Colors.PATH}{phone_path}{Colors.RESET}")

    if not src_dir.is_dir():
        _fail(stats, _display(src_dir),
              "desktop source is not a directory - nothing to sync from")
        return stats

    gio_utils.gio_mkdir(dest_uri, parents=True)

    expected_files: Set[str] = set()
    expected_dirs: Set[str] = set()
    complete = _sync_desktop_to_phone(src_dir, dest_uri, "", expected_files,
                                      expected_dirs, stats, verbose, transfer_tracker)

    if rule.get("delete_extraneous", False):
        if not paths.normalize_phone_path(phone_path)[1]:
            print(f"  {Colors.WARNING}{Icons.WARN} Rule targets the storage root - "
                  f"refusing to delete anything on the phone{Colors.RESET}")
        elif not expected_files:
            print(f"  {Colors.WARNING}{Icons.WARN} Desktop side is empty - "
                  f"refusing to delete anything on the phone{Colors.RESET}")
        elif not complete:
            print(f"  {Colors.WARNING}{Icons.WARN} Desktop scan was incomplete - "
                  f"refusing to delete anything on the phone{Colors.RESET}")
        else:
            _delete_extraneous_on_phone(dest_uri, "", expected_files, expected_dirs,
                                        stats, verbose)

    parts = []
    if stats["copied"]:
        parts.append(f"{Colors.SUCCESS}{Icons.OK} Synced:{Colors.RESET} {stats['copied']}")
    if stats["skipped"]:
        parts.append(f"{Colors.SKIPPED}{Icons.SKIP} Unchanged:{Colors.RESET} {stats['skipped']}")
    if stats["deleted"]:
        parts.append(f"{Colors.DELETED}{Icons.DELETE} Removed:{Colors.RESET} {stats['deleted']}")
    print(f"  {', '.join(parts)}" if parts else f"  {Colors.DIM}No changes{Colors.RESET}")
    if stats["errors"]:
        print(f"  {Colors.ERROR}{Icons.FAIL} Errors:{Colors.RESET} {stats['errors']}")

    return stats


def _sync_desktop_to_phone(src_dir: Path, dest_uri: str, rel_path: str,
                           expected_files: Set[str], expected_dirs: Set[str],
                           stats: Dict[str, Any], verbose: bool,
                           transfer_tracker, visited_inodes: Optional[Set[int]] = None) -> bool:
    """Copy new and changed files onto the phone.

    Returns False if any part of the desktop tree could not be read - the caller
    must then not delete anything, because ``expected_files`` is incomplete.

    Follows symlinks but guards against loops with a visited-inode set: a
    symlinked directory that (directly or via a chain) points back at an
    ancestor is not re-walked a second time.
    """
    if visited_inodes is None:
        visited_inodes = set()

    try:
        inode = os.stat(src_dir).st_ino
    except OSError as err:
        _fail(stats, _display(src_dir), err)
        return False
    if inode in visited_inodes:
        # A symlink cycle (or two paths reaching the same real directory): it
        # is not re-walked, so its contents never reach expected_files. Like
        # any other unwalkable entry in this function, that makes the scan
        # incomplete - the phone's copy of anything under this name must not
        # be deleted on the strength of an enumeration that never happened.
        _fail(stats, rel_path or _display(src_dir),
              "already visited via another path - not scanned again, "
              "so the phone keeps whatever it has under this name")
        return False
    visited_inodes.add(inode)

    try:
        entries = sorted(src_dir.iterdir())
    except OSError as err:
        _fail(stats, _display(src_dir), err)
        return False

    complete = True
    for entry in entries:
        entry_rel = f"{rel_path}/{entry.name}" if rel_path else entry.name
        sub_uri = gio_utils.child_uri(dest_uri, entry.name)

        if entry.is_symlink():
            try:
                resolved = entry.resolve()
                broken = not resolved.exists()
            except (OSError, RuntimeError):
                resolved, broken = entry, True
            if broken:
                # Nothing to copy, and its name never reaches expected_files -
                # so the scan is incomplete and the phone's copy of that name
                # (if any) must not be deleted for it.
                _fail(stats, _display(entry),
                      "broken symlink - skipped, so the phone keeps its copy",
                      entry_rel)
                complete = False
                continue
        else:
            resolved = entry

        if resolved.is_dir():
            expected_dirs.add(unicodedata.normalize("NFC", entry_rel))
            gio_utils.gio_mkdir(sub_uri, parents=True)
            complete &= _sync_desktop_to_phone(resolved, sub_uri, entry_rel, expected_files,
                                               expected_dirs, stats, verbose, transfer_tracker,
                                               visited_inodes)
            continue
        if not resolved.is_file():
            # A fifo, a socket: nothing to copy, and its name never reaches
            # expected_files - so the scan is incomplete and the phone's copy
            # of that name must not be deleted for it.
            _fail(stats, _display(entry),
                  "not a file or a directory - skipped, so the phone keeps its copy",
                  entry_rel)
            complete = False
            continue

        expected_files.add(unicodedata.normalize("NFC", entry_rel))

        try:
            dest_info = gio_utils.gio_info(sub_uri)
        except GioError as err:
            _fail(stats, _display(entry), err, entry_rel)
            complete = False
            continue

        try:
            source_size = resolved.stat().st_size
        except OSError as err:
            # Raced: it was a file when iterdir saw it and is gone now.
            _fail(stats, _display(entry), err, entry_rel)
            complete = False
            continue
        if dest_info and gio_utils.get_file_size(dest_info) == source_size:
            stats["skipped"] += 1
            _record(stats, "skipped", _display(entry), entry_rel, "unchanged")
            if verbose:
                print(f"  {Colors.SKIPPED}{Icons.SKIP}{Colors.RESET} "
                      f"{Colors.DIM}{entry.name} (unchanged){Colors.RESET}")
            continue

        # ponytail: no post-copy size check on the phone side - a short write
        # differs in size and is re-copied next run, and nothing is deleted here.
        if gio_utils.gio_copy(str(resolved), sub_uri, verbose=verbose):
            stats["copied"] += 1
            _record(stats, "synced", _display(entry), entry_rel)
            if transfer_tracker:
                transfer_tracker.add_file(source_size)
        else:
            _fail(stats, _display(entry), "copy to phone failed", entry_rel)

    return complete


def _delete_extraneous_on_phone(dest_uri: str, rel_path: str, expected_files: Set[str],
                                expected_dirs: Set[str], stats: Dict[str, Any],
                                verbose: bool) -> None:
    """Remove phone files the desktop no longer has.

    Names are compared NFC-normalized: the phone may hand back the decomposed
    spelling of the same name, which would otherwise look extraneous every run.
    """
    entries = _listing(dest_uri, rel_path or ".", stats)
    if entries is None:
        return

    for name in entries:
        entry_uri = gio_utils.child_uri(dest_uri, name)
        entry_rel = f"{rel_path}/{name}" if rel_path else name
        key = unicodedata.normalize("NFC", entry_rel)

        try:
            info = gio_utils.gio_info(entry_uri)
        except GioError as err:
            _fail(stats, entry_rel, err)
            continue

        if gio_utils.is_dir(info):
            _delete_extraneous_on_phone(entry_uri, entry_rel, expected_files,
                                        expected_dirs, stats, verbose)
            if key in expected_dirs:
                continue
            remaining = _listing(entry_uri, entry_rel, stats)
            if remaining is None or remaining:
                continue
            if gio_utils.gio_remove(entry_uri, verbose=verbose):
                stats["deleted"] += 1
                _record(stats, "deleted", entry_rel)
            continue

        if not _is_regular(info):
            _fail(stats, entry_rel, "not a file or a directory - gio could not read it")
            continue

        if key in expected_files:
            continue
        if gio_utils.gio_remove(entry_uri, verbose=verbose):
            stats["deleted"] += 1
            _record(stats, "deleted", entry_rel)
        else:
            _fail(stats, entry_rel, "delete failed")
