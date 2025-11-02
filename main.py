#!/usr/bin/env python3
"""Phone Migration Tool - Automate MTP file transfers between Android and Linux desktop."""

import argparse
import sys
from phone_migration import config as cfg, device, runner, browser


def build_parser():
    """Build the argument parser with all commands."""
    
    # ANSI colors for help text
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97;1m'
    
    description = f"""
{BOLD}{BRIGHT_WHITE}Phone Migration Tool{RESET}
{DIM}{'─' * 70}{RESET}

Automate file transfers between Android phone (MTP) and Linux desktop.

{BOLD}Common Workflows:{RESET}
  {CYAN}1. First time setup:{RESET}
     phone-sync --add-device --name default
     phone-sync --move -p default -pp /DCIM/Camera -dp ~/Pictures
     
  {CYAN}2. Daily sync:{RESET}
     phone-sync --run -y
     
  {CYAN}3. Manual backup:{RESET}
     phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Backup --manual
     phone-sync --run -r r-0003 -y

{DIM}Default behavior: Dry-run mode (preview only). Use -y to execute.{RESET}
    """
    
    p = argparse.ArgumentParser(
        prog="phone-sync",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{BOLD}Examples:{RESET}
  {DIM}# Register your phone{RESET}
  phone-sync --add-device
  
  {DIM}# Move screenshots daily{RESET}
  phone-sync --move -p default -pp /DCIM/Screenshots -dp ~/Pictures/Screenshots
  
  {DIM}# Backup camera folder monthly (manual){RESET}
  phone-sync --copy -p default -pp /DCIM/Camera -dp ~/Backup --manual
  
  {DIM}# List all rules{RESET}
  phone-sync --list-rules -p default
  
  {DIM}# Run auto rules (preview){RESET}
  phone-sync --run
  
  {DIM}# Run auto rules (execute){RESET}
  phone-sync --run -y
  
  {DIM}# Run specific manual rule{RESET}
  phone-sync --run -r r-0003 -y

{DIM}For more information, see README.md{RESET}
        """
    )
    
    # Command groups for better organization
    commands = p.add_argument_group('COMMANDS (choose one)')
    g = commands.add_mutually_exclusive_group(required=True)
    
    # Device setup
    g.add_argument("--add-device", action="store_true", 
                   help="Register a connected MTP device")
    g.add_argument("--check", action="store_true",
                   help="Check if phone is connected and recognized")
    
    # Rule management
    g.add_argument("--move", action="store_true",
                   help="📤 Add move rule (phone → desktop, delete from phone)")
    g.add_argument("--copy", action="store_true",
                   help="📋 Add copy rule (phone → desktop, keep on phone)")
    g.add_argument("--smart-copy", action="store_true",
                   help="💡 Add smart copy rule (resumable, tracks progress)")
    g.add_argument("--sync", action="store_true",
                   help="🔄 Add sync rule (desktop → phone, mirror)")
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
                   help="▶️  Execute configured rules (dry-run by default)")
    
    # Web UI
    g.add_argument("--web", action="store_true",
                   help="🌐 Start web UI server (http://localhost:8080)")
    
    # Device options
    device_opts = p.add_argument_group('Device options (for --add-device)')
    device_opts.add_argument("-n", "--name", metavar="NAME",
                             help="Profile name (default: 'default')")
    
    # Rule options
    rule_opts = p.add_argument_group('Rule options (for --move, --copy, --sync, --remove-rule, --edit-rule, --list-rules)')
    rule_opts.add_argument("-p", "--profile", metavar="PROFILE",
                           help="Profile name to operate on (required)")
    rule_opts.add_argument("-pp", "--phone-path", metavar="PATH",
                           help="Path on phone (e.g., /DCIM/Camera)")
    rule_opts.add_argument("-dp", "--desktop-path", metavar="PATH",
                           help="Path on desktop (e.g., ~/Pictures)")
    rule_opts.add_argument("-i", "--id", metavar="ID",
                           help="Rule ID (for --remove-rule, --edit-rule)")
    rule_opts.add_argument("-m", "--mode", choices=["move", "copy", "smart_copy", "sync"],
                           help="Rule mode (for --edit-rule)")
    rule_opts.add_argument("--manual", action="store_true",
                           help="Mark rule as manual-only (for --move, --copy, --sync)")
    
    # Execution options
    exec_opts = p.add_argument_group('Execution options (for --run)')
    exec_opts.add_argument("-r", "--rule-id", action="append", metavar="ID",
                           help="Run specific rule(s) by ID (can use multiple times)")
    exec_opts.add_argument("-y", "--yes", "--execute", action="store_true", dest="execute",
                           help="Execute operations (default is dry-run preview)")
    exec_opts.add_argument("-v", "--verbose", action="store_true",
                           help="Show detailed output (file-by-file)")
    exec_opts.add_argument("--notify", action="store_true",
                           help="🔔 Send desktop notifications on completion")
    
    return p


def main():
    """Main entry point."""
    args = build_parser().parse_args()
    
    # Handle web UI separately (doesn't need config loading)
    if args.web:
        from phone_migration import web_ui
        web_ui.start_web_ui(host='127.0.0.1', port=8080, debug=False)
        return 0
    
    try:
        config = cfg.load_config()
        
        if args.add_device:
            device.register_current_device(config, args.name or "default", args.verbose)
            cfg.save_config(config)
            print(f"✓ Device registered to profile '{args.name or 'default'}'")
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
            cfg.add_move_rule(config, args.profile, args.phone_path, args.desktop_path, manual_only=args.manual)
            cfg.save_config(config)
            manual_suffix = " [MANUAL]" if args.manual else ""
            print(f"✓ Move rule added to profile '{args.profile}'{manual_suffix}")
            return 0
        
        if args.copy:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --copy", 
                      file=sys.stderr)
                return 1
            cfg.add_copy_rule(config, args.profile, args.phone_path, args.desktop_path, manual_only=args.manual)
            cfg.save_config(config)
            manual_suffix = " [MANUAL]" if args.manual else ""
            print(f"✓ Copy rule added to profile '{args.profile}'{manual_suffix}")
            return 0
        
        if args.smart_copy:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --smart-copy", 
                      file=sys.stderr)
                return 1
            cfg.add_smart_copy_rule(config, args.profile, args.phone_path, args.desktop_path, manual_only=args.manual)
            cfg.save_config(config)
            manual_suffix = " [MANUAL]" if args.manual else ""
            print(f"✓ Smart copy rule added to profile '{args.profile}'{manual_suffix}")
            print(f"  💡 Resumable copy with progress tracking")
            return 0
        
        if args.sync:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --sync",
                      file=sys.stderr)
                return 1
            cfg.add_sync_rule(config, args.profile, args.desktop_path, args.phone_path, manual_only=args.manual)
            cfg.save_config(config)
            manual_suffix = " [MANUAL]" if args.manual else ""
            print(f"✓ Sync rule added to profile '{args.profile}'{manual_suffix}")
            return 0
        
        if args.remove_rule:
            if not all([args.profile, args.id]):
                print("Error: --profile and --id are required for --remove-rule", file=sys.stderr)
                return 1
            cfg.remove_rule(config, args.profile, args.id)
            cfg.save_config(config)
            print(f"✓ Rule '{args.id}' removed from profile '{args.profile}'")
            return 0
        
        if args.edit_rule:
            if not args.profile or not args.id:
                print("Error: --profile and --id are required for --edit-rule", file=sys.stderr)
                return 1
            
            # Determine manual_only value (None if not specified, True if --manual flag given)
            manual_value = True if args.manual else None
            
            cfg.edit_rule(config, args.profile, args.id, 
                         mode=args.mode, 
                         phone_path=args.phone_path, 
                         desktop_path=args.desktop_path,
                         manual_only=manual_value)
            cfg.save_config(config)
            print(f"✓ Rule '{args.id}' updated in profile '{args.profile}'")
            return 0
        
        if args.run:
            # Dry-run by default, require --yes to execute
            dry_run = not args.execute
            runner.run_for_connected_device(config, verbose=args.verbose, dry_run=dry_run, rule_ids=args.rule_id, notify=args.notify)
            return 0
        
        if args.browse_phone:
            # Detect connected device
            profile = runner.detect_connected_device(config, args.verbose)
            if not profile:
                print("Error: No connected device found", file=sys.stderr)
                print("Connect your phone and make sure it's registered with --add-device")
                return 1
            
            device_info = profile.get("device", {})
            
            # Offer interactive or list mode
            if args.verbose:
                browser.list_phone_root(device_info)
            else:
                browser.browse_phone_interactive(device_info)
            
            return 0
        
        if args.check:
            # Check connection status
            print("Checking for connected devices...\n")
            profile = runner.detect_connected_device(config, args.verbose)
            
            if not profile:
                print("❌ No matching device found")
                print("\nMake sure:")
                print("  1. Phone is connected via USB")
                print("  2. File Transfer mode is enabled")
                print("  3. Phone is unlocked")
                print("  4. Device is registered (use --add-device)")
                return 1
            
            # Found device
            profile_name = profile.get("name", "unknown")
            device_info = profile.get("device", {})
            display_name = device_info.get("display_name", "Unknown")
            rule_count = len(profile.get("rules", []))
            
            print(f"✅ Connected: {display_name}")
            print(f"   Profile: {profile_name}")
            print(f"   Rules: {rule_count} configured")
            
            if rule_count == 0:
                print("\n💡 No rules configured yet. Add some with:")
                print(f"   phone-sync --move -p {profile_name} -pp /DCIM/Camera -dp ~/Pictures")
            else:
                print("\n✓ Ready to sync! Run: phone-sync --run")
            
            return 0
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
