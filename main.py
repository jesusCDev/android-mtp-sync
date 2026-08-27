#!/usr/bin/env python3
"""Phone Migration Tool - Automate MTP file transfers between Android and Linux desktop."""

import argparse
import errno
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from phone_migration import config as cfg, device, runner, browser
from phone_migration.theme import Colors, Icons

WEB_HOST = "127.0.0.1"
WEB_PORT = 8080
STOP_TIMEOUT = 5.0   # seconds to wait for a signalled web server to actually exit

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "phone-migration"
PID_FILE = STATE_DIR / "web.pid"
WEB_LOG = STATE_DIR / "web.log"

# Test hook: the foreground path's opener thread, so tests can join it.
_browser_thread: Optional[threading.Thread] = None


# ---------------------------------------------------------------------------
# web server process management
# ---------------------------------------------------------------------------

def _web_pid():
    """The pid recorded in the pid file, but only if it is still *our* web server.

    A pid is reused after a reboot, so the recorded number alone proves nothing.
    /proc/<pid>/cmdline has to still name this script and --web; a zombie reads
    back empty, which also fails the check. Returns None otherwise.
    """
    # ponytail: /proc-only, so this is Linux-bound; swap in psutil or
    # `ps -o args= -p <pid>` if the tool ever has to run off Linux.
    try:
        pid = int(PID_FILE.read_text().strip())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    return pid if "main.py" in cmdline and "--web" in cmdline else None


def _port_open(port: int) -> bool:
    """True unless the port actively refuses a connection.

    Only ECONNREFUSED proves nothing holds the port. A server that is bound but
    not accepting (shutting down, or with a full listen backlog) drops the SYN
    instead of refusing, so a plain `connect_ex(...) == 0` test reads it as free
    and lets the next start die on bind - the exact race this guards against.
    """
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((WEB_HOST, port)) != errno.ECONNREFUSED


def _wait_port(port: int, want_open: bool, timeout: float = 5.0) -> bool:
    """Poll until the port reaches the wanted state. False on timeout."""
    deadline = time.monotonic() + timeout
    while _port_open(port) != want_open:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
    return True


def _stop_web(timeout: float = STOP_TIMEOUT) -> Optional[int]:
    """SIGTERM the recorded web server and wait for it to go.

    Returns None once nothing is running any more, or the pid that outlived the
    wait. A survivor keeps its pid file: it is the only handle anyone has on
    that process, so throwing it away would strand a live server on the port.
    """
    pid = _web_pid()
    if pid is None:
        PID_FILE.unlink(missing_ok=True)
        return None

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return None
    except PermissionError as e:
        print(f"{Colors.WARNING}{Icons.WARN}{Colors.RESET} Cannot stop PID {pid}: {e}",
              file=sys.stderr)
        return pid

    deadline = time.monotonic() + timeout
    while _web_pid() == pid and time.monotonic() < deadline:
        time.sleep(0.1)

    if _web_pid() == pid:
        return pid

    PID_FILE.unlink(missing_ok=True)
    return None


def _log_tail(lines: int = 20) -> str:
    # ponytail: web.log is append-only and never rotated - one traceback per
    # failed start, so it grows slowly; hand it to RotatingFileHandler or
    # logrotate if it ever gets big enough to notice.
    try:
        return "\n".join(WEB_LOG.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log written)"


def _survivor_message(pid: int) -> None:
    print(f"{Colors.ERROR}{Icons.FAIL}{Colors.RESET} Error: web UI still running as pid {pid} "
          f"after {STOP_TIMEOUT:g}s; stop it by hand and retry", file=sys.stderr)


def _open_browser_tab() -> None:
    """Open the web UI in the user's default browser. Never raises."""
    url = f"http://{WEB_HOST}:{WEB_PORT}"
    print(f"{Colors.DIM}{Icons.INFO}{Colors.RESET} Opening {url} in your browser")
    try:
        webbrowser.open_new_tab(url)
    except Exception as e:
        print(f"{Colors.MUTED}Could not open a browser: {e}{Colors.RESET}")


def _wait_and_open_browser() -> None:
    """Foreground opener thread body: wait for the server, then open the tab."""
    if _wait_port(WEB_PORT, True):
        _open_browser_tab()


def _run_web(args) -> int:
    """--web, --web --background, --web --stop."""
    if args.stop:
        if _web_pid() is None:
            PID_FILE.unlink(missing_ok=True)
            print(f"{Colors.DIM}{Icons.INFO}{Colors.RESET} No running web UI instance found")
            return 0
        survivor = _stop_web(STOP_TIMEOUT)
        if survivor is not None:
            _survivor_message(survivor)
            return 1
        print(f"{Colors.SUCCESS}{Icons.OK}{Colors.RESET} Stopped web UI")
        return 0

    if _web_pid() is not None:
        survivor = _stop_web(STOP_TIMEOUT)
        if survivor is not None:
            _survivor_message(survivor)
            return 1
        print(f"{Colors.DIM}{Icons.INFO}{Colors.RESET} Stopped the previous web UI")

    # Binding is what actually fails, so refuse to start until the port is free -
    # that is the "Address already in use" crash this replaces.
    if not _wait_port(WEB_PORT, False):
        print(f"{Colors.ERROR}{Icons.FAIL}{Colors.RESET} Error: port {WEB_PORT} still in use; "
              f"nothing started", file=sys.stderr)
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.background:
        with open(WEB_LOG, "ab") as log:
            subprocess.Popen([sys.executable, __file__, "--web"],
                             stdout=log, stderr=log, start_new_session=True)
        # ponytail: "the port answers" is not proof it is *our* server - anything
        # that grabs :8080 first reads as success; probe a health endpoint
        # carrying a startup token if that ever bites.
        if _wait_port(WEB_PORT, True):
            print(f"{Colors.SUCCESS}{Icons.OK}{Colors.RESET} Web UI running at "
                  f"{Colors.PATH}http://{WEB_HOST}:{WEB_PORT}{Colors.RESET}")
            print(f"   {Colors.DIM}To stop: phone-sync --web --stop{Colors.RESET}")
            if not args.no_browser:
                _open_browser_tab()
            return 0
        print(f"{Colors.ERROR}{Icons.FAIL}{Colors.RESET} Web UI did not come up on port "
              f"{WEB_PORT}. Last lines of {WEB_LOG}:", file=sys.stderr)
        print(_log_tail(), file=sys.stderr)
        return 1

    # Foreground: this process is the server, so it owns the pid file.
    PID_FILE.write_text(str(os.getpid()))
    global _browser_thread
    _browser_thread = None
    if not args.no_browser:
        # start_web_ui() blocks, so the opener has to poll from its own thread.
        _browser_thread = threading.Thread(target=_wait_and_open_browser, daemon=True)
        _browser_thread.start()
    try:
        from phone_migration import web_ui
        web_ui.start_web_ui(host=WEB_HOST, port=WEB_PORT, debug=False)
    finally:
        PID_FILE.unlink(missing_ok=True)
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def build_parser():
    """Build the argument parser with all commands."""
    description = f"""
{Colors.BOLD}{Colors.HEADER}Phone Migration Tool{Colors.RESET}
{Colors.SEPARATOR}{'-' * 70}{Colors.RESET}

Automate file transfers between Android phone (MTP) and Linux desktop.

{Colors.BOLD}{Colors.INFO}Common Workflows:{Colors.RESET}
  {Colors.ACCENT}1. First time setup:{Colors.RESET}
     phone-sync --add-device --name default
     phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures

  {Colors.ACCENT}2. Daily sync:{Colors.RESET}
     phone-sync --run -y

  {Colors.ACCENT}3. Web UI (foreground):{Colors.RESET}
     phone-sync --web

  {Colors.ACCENT}4. Web UI (background):{Colors.RESET}
     phone-sync --web --background

  {Colors.ACCENT}5. Stop web UI:{Colors.RESET}
     phone-sync --web --stop

{Colors.DIM}Default: Dry-run mode (preview only). Use -y to execute.{Colors.RESET}
    """

    p = argparse.ArgumentParser(
        prog="phone-sync",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}Examples:{Colors.RESET}
  {Colors.DIM}# Register your phone{Colors.RESET}
  phone-sync --add-device

  {Colors.DIM}# Move screenshots daily{Colors.RESET}
  phone-sync --move -p default -pp /DCIM/Screenshots -dp ~/Pictures/Screenshots

  {Colors.DIM}# Backup camera folder monthly (manual){Colors.RESET}
  phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Backup --manual

  {Colors.DIM}# List all rules{Colors.RESET}
  phone-sync --list-rules -p default

  {Colors.DIM}# Run auto rules (preview){Colors.RESET}
  phone-sync --run

  {Colors.DIM}# Run auto rules (execute){Colors.RESET}
  phone-sync --run -y

  {Colors.DIM}# Run manual rules too{Colors.RESET}
  phone-sync --run --manual -y

  {Colors.DIM}# Run specific manual rule{Colors.RESET}
  phone-sync --run -r r-0003 -y

{Colors.DIM}For more information, see README.md{Colors.RESET}
        """
    )

    commands = p.add_argument_group('COMMANDS (choose one)')
    g = commands.add_mutually_exclusive_group(required=True)

    # Device setup
    g.add_argument("--add-device", action="store_true",
                   help="Register a connected MTP device")
    g.add_argument("--check", action="store_true",
                   help="Check if phone is connected and recognized")

    # Rule management
    g.add_argument("--move", action="store_true",
                   help=f"{Icons.MOVE} Add move rule (phone -> desktop, delete from phone)")
    g.add_argument("--copy", action="store_true",
                   help=f"{Icons.COPY} Add copy rule (phone -> desktop, keep on phone)")
    g.add_argument("--backup", action="store_true",
                   help=f"{Icons.FILE} Add backup rule (resumable copy, no deletions)")
    g.add_argument("--smart-copy", action="store_true",
                   help="Deprecated alias for --backup")
    g.add_argument("--sync", action="store_true",
                   help=f"{Icons.SYNC} Add sync rule (desktop -> phone, mirror)")
    g.add_argument("--remove-rule", action="store_true",
                   help="Remove a rule from a profile")
    g.add_argument("--edit-rule", action="store_true",
                   help="Edit an existing rule")

    # Information
    g.add_argument("--list-profiles", action="store_true",
                   help="List all configured profiles")
    g.add_argument("--list-rules", action="store_true",
                   help="List rules for a profile (with colors)")
    g.add_argument("--browse-phone", action="store_true",
                   help="Browse phone directories interactively")

    # Execution
    g.add_argument("--run", action="store_true",
                   help=f"{Icons.ARROW} Execute configured rules (dry-run by default)")

    # Web UI
    g.add_argument("--web", action="store_true",
                   help=f"{Icons.BOLT} Start web UI server (http://{WEB_HOST}:{WEB_PORT})")

    web_opts = p.add_argument_group('Web UI options (for --web)')
    web_opts.add_argument("--background", action="store_true",
                          help="Run as background daemon (survives terminal close)")
    web_opts.add_argument("--stop", action="store_true",
                          help="Stop any running web UI instance")
    web_opts.add_argument("--no-browser", action="store_true",
                          help="Do not open a browser tab")

    device_opts = p.add_argument_group('Device options (for --add-device)')
    device_opts.add_argument("-n", "--name", metavar="NAME",
                             help="Profile name (default: 'default')")

    rule_opts = p.add_argument_group(
        'Rule options (for --move, --copy, --backup, --sync, --remove-rule, --edit-rule, --list-rules)')
    rule_opts.add_argument("-p", "--profile", metavar="PROFILE",
                           help="Profile name to operate on (required)")
    rule_opts.add_argument("-pp", "--phone-path", metavar="PATH",
                           help="Path on phone (e.g., /DCIM/Camera)")
    rule_opts.add_argument("-dp", "--desktop-path", metavar="PATH",
                           help="Path on desktop (e.g., ~/Pictures)")
    rule_opts.add_argument("-i", "--id", metavar="ID",
                           help="Rule ID (for --remove-rule, --edit-rule)")
    rule_opts.add_argument("-m", "--mode", choices=["move", "copy", "backup", "smart_copy", "sync"],
                           help="Rule mode (for --edit-rule)")
    rule_opts.add_argument("--manual", action=argparse.BooleanOptionalAction, default=None,
                           help="Mark a new rule manual-only; with --edit-rule, --no-manual "
                                "clears the flag; with --run, include manual rules")

    exec_opts = p.add_argument_group('Execution options (for --run)')
    exec_opts.add_argument("-r", "--rule-id", action="append", metavar="ID",
                           help="Run specific rule(s) by ID (can use multiple times)")
    exec_opts.add_argument("-y", "--yes", "--execute", action="store_true", dest="execute",
                           help="Execute operations (default is dry-run preview)")
    exec_opts.add_argument("-v", "--verbose", action="store_true",
                           help="Show detailed output (file-by-file)")
    exec_opts.add_argument("--notify", action="store_true",
                           help=f"{Icons.INFO} Send desktop notifications on completion")

    return p


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    """Main entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)

    ok = f"{Colors.SUCCESS}{Icons.OK}{Colors.RESET}"
    fail = f"{Colors.ERROR}{Icons.FAIL}{Colors.RESET}"

    manual_flag = bool(args.manual)
    manual_suffix = " [MANUAL]" if manual_flag else ""

    try:
        # The web UI does not need the config loaded, but it does need the same
        # error handling - a failed start must not spill a traceback.
        if args.web:
            return _run_web(args)

        config = cfg.load_config()

        if args.add_device:
            device.register_current_device(config, args.name or "default", args.verbose)
            cfg.save_config(config)
            print(f"{ok} Device registered to profile '{args.name or 'default'}'")
            return 0

        if args.list_profiles:
            cfg.print_profiles(config)
            return 0

        if args.list_rules:
            if not args.profile:
                print("Error: --profile is required for --list-rules", file=sys.stderr)
                return 1
            cfg.print_rules(config, args.profile)
            return 0

        if args.move:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --move",
                      file=sys.stderr)
                return 1
            cfg.add_move_rule(config, args.profile, args.phone_path, args.desktop_path,
                              manual_only=manual_flag)
            cfg.save_config(config)
            print(f"{ok} Move rule added to profile '{args.profile}'{manual_suffix}")
            return 0

        if args.copy:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --copy",
                      file=sys.stderr)
                return 1
            cfg.add_copy_rule(config, args.profile, args.phone_path, args.desktop_path,
                              manual_only=manual_flag)
            cfg.save_config(config)
            print(f"{ok} Copy rule added to profile '{args.profile}'{manual_suffix}")
            return 0

        if args.backup or args.smart_copy:
            flag = "--smart-copy" if args.smart_copy else "--backup"
            if args.smart_copy:
                print(f"{Colors.WARNING}{Icons.WARN}{Colors.RESET} --smart-copy is deprecated; "
                      f"use --backup (this run added a backup rule)")
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print(f"Error: --profile, --phone-path, and --desktop-path are required for {flag}",
                      file=sys.stderr)
                return 1
            cfg.add_backup_rule(config, args.profile, args.phone_path, args.desktop_path,
                                manual_only=manual_flag)
            cfg.save_config(config)
            print(f"{ok} Backup rule added to profile '{args.profile}'{manual_suffix}")
            print(f"  {Colors.DIM}Resumable backup with progress tracking "
                  f"(no deletions){Colors.RESET}")
            return 0

        if args.sync:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --sync",
                      file=sys.stderr)
                return 1
            cfg.add_sync_rule(config, args.profile, args.desktop_path, args.phone_path,
                              manual_only=manual_flag)
            cfg.save_config(config)
            print(f"{ok} Sync rule added to profile '{args.profile}'{manual_suffix}")
            return 0

        if args.remove_rule:
            if not all([args.profile, args.id]):
                print("Error: --profile and --id are required for --remove-rule", file=sys.stderr)
                return 1
            cfg.remove_rule(config, args.profile, args.id)
            cfg.save_config(config)
            print(f"{ok} Rule '{args.id}' removed from profile '{args.profile}'")
            return 0

        if args.edit_rule:
            if not args.profile or not args.id:
                print("Error: --profile and --id are required for --edit-rule", file=sys.stderr)
                return 1
            # Tri-state: None leaves manual_only alone, True/False set it.
            cfg.edit_rule(config, args.profile, args.id,
                          mode=args.mode,
                          phone_path=args.phone_path,
                          desktop_path=args.desktop_path,
                          manual_only=args.manual)
            cfg.save_config(config)
            print(f"{ok} Rule '{args.id}' updated in profile '{args.profile}'")
            return 0

        if args.run:
            result = runner.run_for_connected_device(
                config,
                verbose=args.verbose,
                dry_run=not args.execute,      # dry-run unless -y
                rule_ids=args.rule_id,
                notify=args.notify,
                include_manual=manual_flag,
            )
            # A skipped rule, a failed copy or an unknown mode all land in
            # "errors"; scripts and the shell need to see that in $?.
            return 1 if result.get("stats", {}).get("errors", 0) else 0

        if args.browse_phone:
            profile = runner.detect_connected_device(config, args.verbose)
            if not profile:
                print("Error: No connected device found", file=sys.stderr)
                print("Connect your phone and make sure it's registered with --add-device")
                return 1

            device_info = profile.get("device", {})
            if args.verbose:
                browser.list_phone_root(device_info)
            else:
                browser.browse_phone_interactive(device_info)
            return 0

        if args.check:
            print("Checking for connected devices...\n")
            profile = runner.detect_connected_device(config, args.verbose)

            if not profile:
                print(f"{fail} No matching device found")
                print("\nMake sure:")
                print("  1. Phone is connected via USB")
                print("  2. File Transfer mode is enabled")
                print("  3. Phone is unlocked")
                print("  4. Device is registered (use --add-device)")
                return 1

            profile_name = profile.get("name", "unknown")
            device_info = profile.get("device", {})
            rule_count = len(profile.get("rules", []))

            print(f"{ok} Connected: {device_info.get('display_name', 'Unknown')}")
            print(f"   Profile: {profile_name}")
            print(f"   Rules: {rule_count} configured")

            if rule_count == 0:
                print(f"\n{Icons.INFO} No rules configured yet. Add some with:")
                print(f"   phone-sync --move -p {profile_name} -pp /DCIM/Camera -dp ~/Pictures")
            else:
                print(f"\n{ok} Ready to sync! Run: phone-sync --run -y")

            return 0

        return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
