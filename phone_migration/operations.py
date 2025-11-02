"""File operations for move and sync rules."""

import os
from pathlib import Path
from typing import Any, Dict, Set
from . import gio_utils, paths

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    WHITE = '\033[97m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97;1m'

def shorten_path(path_str: str) -> str:
    """Replace home directory with ~ for readability."""
    home = str(Path.home())
    if isinstance(path_str, Path):
        path_str = str(path_str)
    if path_str.startswith(home):
        return path_str.replace(home, '~', 1)
    return path_str


def run_copy_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False) -> Dict[str, int]:
    """
    Execute a copy rule: copy from phone to desktop without deleting from phone.

    Args:
        rule: Rule dictionary with phone_path, desktop_path
        device: Device dictionary with activation_uri
        verbose: Print verbose output

    Returns:
        Dictionary with counts: copied, renamed, errors
    """
    activation_uri = device.get("activation_uri", "")
    phone_path = rule.get("phone_path", "")
    desktop_path_str = rule.get("desktop_path", "")

    # Build URIs and paths
    source_uri = paths.build_phone_uri(activation_uri, phone_path)
    dest_dir = paths.expand_desktop(desktop_path_str)

    print(f"\n{Colors.BOLD}{Colors.BRIGHT_BLUE}📋 Copy:{Colors.RESET} {Colors.CYAN}{phone_path}{Colors.RESET} {Colors.DIM}→{Colors.RESET} {Colors.GREEN}{shorten_path(dest_dir)}{Colors.RESET}\n")

    # Create destination directory
    paths.ensure_dir(dest_dir)

    # Track statistics
    stats = {"copied": 0, "renamed": 0, "errors": 0, "folders": 0}

    # Recursively process phone directory (no deletion)
    _process_copy_directory(source_uri, dest_dir, stats, verbose)

    # Align based on longest label "Renamed:" (8 chars including emoji/symbol)
    print(f"\n  {Colors.GREEN}✓ Copied:{Colors.RESET}   {stats['copied']} files")
    if stats["folders"] > 0:
        print(f" {Colors.BRIGHT_WHITE}📁 Folders:{Colors.RESET}  {stats['folders']}")
    if stats["renamed"] > 0:
        print(f"  {Colors.YELLOW}↻ Renamed:{Colors.RESET}  {stats['renamed']} (duplicates)")
    if stats["errors"] > 0:
        print(f"  {Colors.YELLOW}⨠ Errors:{Colors.RESET}   {stats['errors']}")

    return stats


def _process_copy_directory(source_uri: str, dest_dir: Path, 
                            stats: Dict[str, int], verbose: bool, in_subfolder: bool = False) -> None:
    """Recursively process a directory for copy operation (no deletion).

    Args:
        in_subfolder: True if we're inside a subfolder (to hide individual file output)
    """
    # List entries in source directory
    entries = gio_utils.gio_list(source_uri)

    for entry in entries:
        entry_uri = f"{source_uri}/{entry}" if source_uri.endswith('/') else f"{source_uri}/{entry}"

        # Get entry info to determine if it's a file or directory
        info = gio_utils.gio_info(entry_uri)
        entry_type = info.get("standard::type", "")

        # Check multiple indicators for directories
        is_dir = (
            "directory" in entry_type.lower() or
            entry_type == "2" or
            info.get("standard::is-directory", "").lower() == "true"
        )

        if is_dir:
            # Create corresponding subdirectory on desktop
            sub_dest_dir = dest_dir / entry
            sub_dest_short = shorten_path(sub_dest_dir)
            paths.ensure_dir(sub_dest_dir)
            stats["folders"] += 1
            print(f"  {Colors.BRIGHT_WHITE}📦{Colors.RESET} {Colors.BOLD}{entry}/{Colors.RESET} {Colors.DIM}→ {sub_dest_short}{Colors.RESET}")

            # Recurse into subdirectory (track file count, mark as in_subfolder)
            folder_stats_before = stats["copied"]
            _process_copy_directory(entry_uri, sub_dest_dir, stats, verbose, in_subfolder=True)
            files_in_folder = stats["copied"] - folder_stats_before
            if files_in_folder > 0 and not verbose:
                print(f"     {Colors.DIM}({files_in_folder} files){Colors.RESET}")

        elif "regular" in entry_type.lower() or entry_type == "1":  # Type 1 is regular file
            # Determine destination file path
            dest_file = paths.next_available_name(dest_dir, entry)

            # Check if needs rename due to duplicate
            will_rename = dest_file.name != entry
            if will_rename:
                stats["renamed"] += 1
                # Show rename with full destination path (only if not in subfolder or verbose)
                if (gio_utils.DRY_RUN or verbose) and not in_subfolder:
                    dest_short = shorten_path(dest_file)
                    print(f"  {Colors.YELLOW}↻{Colors.RESET} {Colors.DIM}{entry}{Colors.RESET} → {Colors.YELLOW}{dest_file.name}{Colors.RESET} {Colors.DIM}(duplicate → {dest_short}){Colors.RESET}")

            # Copy file - show root level files (not in subfolder), but not if already shown via rename
            show_copy = (not will_rename and not in_subfolder) or verbose
            if gio_utils.gio_copy(entry_uri, str(dest_file), recursive=False, overwrite=False, verbose=show_copy):
                # Verify copy succeeded (skip verification in dry-run mode)
                if gio_utils.DRY_RUN:
                    # In dry-run, just count it as successful
                    stats["copied"] += 1
                elif dest_file.exists() and dest_file.stat().st_size > 0:
                    stats["copied"] += 1
                else:
                    stats["errors"] += 1
                    if verbose:
                        print(f"  Warning: Copy verification failed for {entry}")
            else:
                stats["errors"] += 1


def run_move_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False) -> Dict[str, int]:
    """
    Execute a move rule: copy from phone to desktop, then delete from phone.

    Args:
        rule: Rule dictionary with phone_path, desktop_path
        device: Device dictionary with activation_uri
        verbose: Print verbose output

    Returns:
        Dictionary with counts: copied, renamed, deleted, errors
    """
    activation_uri = device.get("activation_uri", "")
    phone_path = rule.get("phone_path", "")
    desktop_path_str = rule.get("desktop_path", "")

    # Build URIs and paths
    source_uri = paths.build_phone_uri(activation_uri, phone_path)
    dest_dir = paths.expand_desktop(desktop_path_str)

    print(f"\n{Colors.BOLD}{Colors.BRIGHT_BLUE}→{Colors.RESET} {Colors.BOLD}Move:{Colors.RESET} {Colors.CYAN}{phone_path}{Colors.RESET} {Colors.DIM}→{Colors.RESET} {Colors.GREEN}{shorten_path(dest_dir)}{Colors.RESET}\n")

    # Create destination directory
    paths.ensure_dir(dest_dir)

    # Track statistics
    stats = {"copied": 0, "renamed": 0, "deleted": 0, "errors": 0, "folders": 0}

    # Files to delete after successful copy
    files_to_delete = []

    # Recursively process phone directory
    _process_move_directory(source_uri, dest_dir, files_to_delete, stats, verbose)

    # Delete files from phone after successful copy
    # Don't list individual files - just count them
    if files_to_delete:
        if verbose:
            print(f"\n{Colors.DIM}Cleaning up phone:{Colors.RESET}")
        for file_uri in files_to_delete:
            if gio_utils.gio_remove(file_uri, verbose=verbose):
                stats["deleted"] += 1
            else:
                stats["errors"] += 1
                if verbose:
                    print(f"  Warning: Failed to delete {file_uri}")

    # Try to remove empty directories
    _cleanup_empty_dirs(source_uri, verbose)

    # Align based on longest label "Renamed:" (8 chars including emoji/symbol)
    print(f"\n  {Colors.GREEN}✓ Copied:{Colors.RESET}   {stats['copied']} files")
    if stats["folders"] > 0:
        print(f" {Colors.BRIGHT_WHITE}📁 Folders:{Colors.RESET}  {stats['folders']}")
    if stats["renamed"] > 0:
        print(f"  {Colors.YELLOW}↻ Renamed:{Colors.RESET}  {stats['renamed']} (duplicates)")
    if stats["deleted"] > 0:
        print(f" {Colors.RED}🗑️  Deleted:{Colors.RESET}  {stats['deleted']}")
    if stats["errors"] > 0:
        print(f"  {Colors.YELLOW}⨠ Errors:{Colors.RESET}   {stats['errors']}")

    return stats


def _process_move_directory(source_uri: str, dest_dir: Path, files_to_delete: list,
                            stats: Dict[str, int], verbose: bool, in_subfolder: bool = False) -> None:
    """Recursively process a directory for move operation.

    Args:
        in_subfolder: True if we're inside a subfolder (to hide individual file output)
    """
    # List entries in source directory
    entries = gio_utils.gio_list(source_uri)

    for entry in entries:
        entry_uri = f"{source_uri}/{entry}" if source_uri.endswith('/') else f"{source_uri}/{entry}"

        # Get entry info to determine if it's a file or directory
        info = gio_utils.gio_info(entry_uri)
        entry_type = info.get("standard::type", "")

        # Check multiple indicators for directories
        is_dir = (
            "directory" in entry_type.lower() or
            entry_type == "2" or
            info.get("standard::is-directory", "").lower() == "true"
        )

        if is_dir:
            # Create corresponding subdirectory on desktop
            sub_dest_dir = dest_dir / entry
            sub_dest_short = shorten_path(sub_dest_dir)
            paths.ensure_dir(sub_dest_dir)
            stats["folders"] += 1
            print(f"  {Colors.BRIGHT_WHITE}📦{Colors.RESET} {Colors.BOLD}{entry}/{Colors.RESET} {Colors.DIM}→ {sub_dest_short}{Colors.RESET}")

            # Recurse into subdirectory (track file count, mark as in_subfolder)
            folder_stats_before = stats["copied"]
            _process_move_directory(entry_uri, sub_dest_dir, files_to_delete, stats, verbose, in_subfolder=True)
            files_in_folder = stats["copied"] - folder_stats_before
            if files_in_folder > 0 and not verbose:
                print(f"     {Colors.DIM}({files_in_folder} files){Colors.RESET}")

        elif "regular" in entry_type.lower() or entry_type == "1":  # Type 1 is regular file
            # Determine destination file path
            dest_file = paths.next_available_name(dest_dir, entry)

            # Check if needs rename due to duplicate
            will_rename = dest_file.name != entry
            if will_rename:
                stats["renamed"] += 1
                # Show rename with full destination path (only if not in subfolder or verbose)
                if (gio_utils.DRY_RUN or verbose) and not in_subfolder:
                    dest_short = shorten_path(dest_file)
                    print(f"  {Colors.YELLOW}↻{Colors.RESET} {Colors.DIM}{entry}{Colors.RESET} → {Colors.YELLOW}{dest_file.name}{Colors.RESET} {Colors.DIM}(duplicate → {dest_short}){Colors.RESET}")

            # Copy file - show root level files (not in subfolder), but not if already shown via rename
            show_copy = (not will_rename and not in_subfolder) or verbose
            if gio_utils.gio_copy(entry_uri, str(dest_file), recursive=False, overwrite=False, verbose=show_copy):
                # Verify copy succeeded (skip verification in dry-run mode)
                if gio_utils.DRY_RUN:
                    # In dry-run, just count it as successful
                    stats["copied"] += 1
                    files_to_delete.append(entry_uri)
                elif dest_file.exists() and dest_file.stat().st_size > 0:
                    stats["copied"] += 1
                    files_to_delete.append(entry_uri)
                else:
                    stats["errors"] += 1
                    if verbose:
                        print(f"  Warning: Copy verification failed for {entry}")
            else:
                stats["errors"] += 1


def _cleanup_empty_dirs(dir_uri: str, verbose: bool, skip_root: bool = True) -> None:
    """Try to remove empty directories (best effort).

    Args:
        dir_uri: Directory URI to clean up
        verbose: Print verbose output
        skip_root: If True, don't delete the root directory itself (only subdirectories)
    """
    if skip_root:
        # Only clean up subdirectories, not the root move directory
        entries = gio_utils.gio_list(dir_uri)
        for entry in entries:
            entry_uri = f"{dir_uri}/{entry}" if dir_uri.endswith('/') else f"{dir_uri}/{entry}"
            info = gio_utils.gio_info(entry_uri)
            entry_type = info.get("standard::type", "")
            is_dir = (
                "directory" in entry_type.lower() or
                entry_type == "2" or
                info.get("standard::is-directory", "").lower() == "true"
            )
            if is_dir:
                try:
                    gio_utils.gio_remove(entry_uri, verbose=False)
                except:
                    pass  # Ignore errors - directory might not be empty
    else:
        try:
            gio_utils.gio_remove(dir_uri, verbose=False)
        except:
            pass  # Ignore errors - directory might not be empty


def run_sync_rule(rule: Dict[str, Any], device: Dict[str, Any], verbose: bool = False) -> Dict[str, int]:
    """
    Execute a sync rule: mirror desktop to phone (desktop is source of truth).

    Args:
        rule: Rule dictionary with desktop_path, phone_path
        device: Device dictionary with activation_uri
        verbose: Print verbose output

    Returns:
        Dictionary with counts: copied, deleted, errors
    """
    activation_uri = device.get("activation_uri", "")
    desktop_path_str = rule.get("desktop_path", "")
    phone_path = rule.get("phone_path", "")

    # Build paths and URIs
    src_dir = paths.expand_desktop(desktop_path_str)
    dest_uri = paths.build_phone_uri(activation_uri, phone_path)

    print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}🔄 Sync:{Colors.RESET} {Colors.GREEN}{shorten_path(src_dir)}{Colors.RESET} → {Colors.CYAN}{phone_path}{Colors.RESET}")

    if not src_dir.exists():
        print(f"  Warning: Desktop source does not exist: {src_dir}")
        return {"copied": 0, "deleted": 0, "errors": 1}

    # Ensure destination exists on phone
    gio_utils.gio_mkdir(dest_uri, parents=True)

    # Track statistics
    stats = {"copied": 0, "skipped": 0, "deleted": 0, "errors": 0}

    # Track all files that should exist on phone
    expected_phone_files: Set[str] = set()

    # Copy/update files from desktop to phone
    _sync_desktop_to_phone(src_dir, dest_uri, "", expected_phone_files, stats, verbose)

    # Delete extraneous files on phone
    if rule.get("delete_extraneous", True):
        _delete_extraneous_on_phone(dest_uri, "", expected_phone_files, stats, verbose)

    # Print summary with all relevant stats
    summary_parts = []
    if stats["copied"] > 0:
        summary_parts.append(f"{Colors.GREEN}✓ Synced:{Colors.RESET} {stats['copied']}")
    if stats["skipped"] > 0:
        summary_parts.append(f"{Colors.CYAN}⊙ Skipped:{Colors.RESET} {stats['skipped']}")
    if stats["deleted"] > 0:
        summary_parts.append(f"{Colors.DIM}Cleaned:{Colors.RESET} {stats['deleted']}")
    
    if summary_parts:
        print(f"  {', '.join(summary_parts)}")
    else:
        print(f"  {Colors.DIM}No changes{Colors.RESET}")
    
    if stats["errors"] > 0:
        print(f"  {Colors.YELLOW}⚠ Errors:{Colors.RESET} {stats['errors']}")

    return stats


def _sync_desktop_to_phone(src_dir: Path, dest_uri: str, rel_path: str,
                           expected_files: Set[str], stats: Dict[str, int], verbose: bool) -> None:
    """Recursively sync desktop directory to phone (smart sync: skip unchanged files)."""
    if not src_dir.is_dir():
        return

    for entry in src_dir.iterdir():
        entry_rel_path = f"{rel_path}/{entry.name}" if rel_path else entry.name

        if entry.is_dir():
            # Create directory on phone
            sub_dest_uri = f"{dest_uri}/{entry.name}"
            gio_utils.gio_mkdir(sub_dest_uri, parents=True)

            # Recurse
            _sync_desktop_to_phone(entry, sub_dest_uri, entry_rel_path, expected_files, stats, verbose)

        elif entry.is_file():
            # Track this file as expected
            expected_files.add(entry_rel_path)

            # Destination file URI on phone
            dest_file_uri = f"{dest_uri}/{entry.name}"
            
            # Smart sync: check if file already exists with same size
            dest_info = gio_utils.gio_info(dest_file_uri)
            if dest_info:
                # File exists on phone - compare sizes
                dest_size = gio_utils.get_file_size(dest_info)
                src_size = entry.stat().st_size
                
                if dest_size is not None and dest_size == src_size:
                    # File unchanged - skip copy
                    stats["skipped"] += 1
                    if verbose:
                        print(f"  {Colors.CYAN}⊙{Colors.RESET} {Colors.DIM}{entry.name}{Colors.RESET} {Colors.DIM}(unchanged){Colors.RESET}")
                    continue
            
            # File is new or changed - copy it
            if gio_utils.gio_copy(str(entry), dest_file_uri, recursive=False, overwrite=True, verbose=verbose):
                stats["copied"] += 1
            else:
                stats["errors"] += 1


def _delete_extraneous_on_phone(dest_uri: str, rel_path: str,
                                expected_files: Set[str], stats: Dict[str, int], verbose: bool) -> None:
    """Delete files on phone that don't exist on desktop."""
    entries = gio_utils.gio_list(dest_uri)

    for entry in entries:
        entry_rel_path = f"{rel_path}/{entry}" if rel_path else entry
        entry_uri = f"{dest_uri}/{entry}"

        # Get entry info
        info = gio_utils.gio_info(entry_uri)
        entry_type = info.get("standard::type", "")

        if "directory" in entry_type.lower():
            # Recurse into directory
            _delete_extraneous_on_phone(entry_uri, entry_rel_path, expected_files, stats, verbose)

            # Try to remove directory if empty
            if not gio_utils.gio_list(entry_uri):
                if gio_utils.gio_remove(entry_uri, verbose=verbose):
                    stats["deleted"] += 1

        elif "regular" in entry_type.lower() or entry_type == "1":
            # Check if file should exist
            if entry_rel_path not in expected_files:
                if gio_utils.gio_remove(entry_uri, verbose=verbose):
                    stats["deleted"] += 1
                else:
                    stats["errors"] += 1
