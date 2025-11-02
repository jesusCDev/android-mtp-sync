#!/usr/bin/env python3
"""Phone Migration Tool - Automate MTP file transfers between Android and Linux desktop."""

import argparse
import sys
from phone_migration import config as cfg, device, runner, browser


def build_parser():
    """Build the argument parser with all commands."""
    p = argparse.ArgumentParser(
        prog="phone-migration",
        description="Automate file transfers between Android phone (MTP) and Linux desktop"
    )
    
    # Mutually exclusive commands
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--add-device", action="store_true", 
                   help="Register a connected MTP device")
    g.add_argument("--move", action="store_true",
                   help="Add a move rule (phone → desktop, delete from phone)")
    g.add_argument("--sync", action="store_true",
                   help="Add a sync rule (desktop → phone, desktop is source of truth)")
    g.add_argument("--run", action="store_true",
                   help="Execute sync/move operations for connected device")
    g.add_argument("--list-profiles", action="store_true",
                   help="List all configured profiles")
    g.add_argument("--list-rules", action="store_true",
                   help="List rules for a profile")
    g.add_argument("--remove-rule", action="store_true",
                   help="Remove a specific rule from a profile")
    g.add_argument("--edit-rule", action="store_true",
                   help="Edit an existing rule")
    g.add_argument("--browse-phone", action="store_true",
                   help="Browse phone directories to find paths")
    g.add_argument("--check", action="store_true",
                   help="Check if phone is connected and recognized")
    
    # Optional arguments
    p.add_argument("-n", "--name", help="Profile name (for --add-device, default: 'default')")
    p.add_argument("-p", "--profile", help="Profile name to operate on")
    p.add_argument("-pp", "--phone-path", help="Path on phone (e.g., /DCIM/Camera)")
    p.add_argument("-dp", "--desktop-path", help="Path on desktop (e.g., ~/Videos/phone_images/Camera)")
    p.add_argument("-i", "--id", help="Rule ID (for --remove-rule, --edit-rule)")
    p.add_argument("-m", "--mode", choices=["move", "sync"], help="Rule mode (for --edit-rule)")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    p.add_argument("-y", "--yes", "--execute", action="store_true", dest="execute",
                   help="Execute operations (default is dry-run)")
    
    return p


def main():
    """Main entry point."""
    args = build_parser().parse_args()
    
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
            cfg.add_move_rule(config, args.profile, args.phone_path, args.desktop_path)
            cfg.save_config(config)
            print(f"✓ Move rule added to profile '{args.profile}'")
            return 0
        
        if args.sync:
            if not all([args.profile, args.phone_path, args.desktop_path]):
                print("Error: --profile, --phone-path, and --desktop-path are required for --sync",
                      file=sys.stderr)
                return 1
            cfg.add_sync_rule(config, args.profile, args.desktop_path, args.phone_path)
            cfg.save_config(config)
            print(f"✓ Sync rule added to profile '{args.profile}'")
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
            cfg.edit_rule(config, args.profile, args.id, 
                         mode=args.mode, 
                         phone_path=args.phone_path, 
                         desktop_path=args.desktop_path)
            cfg.save_config(config)
            print(f"✓ Rule '{args.id}' updated in profile '{args.profile}'")
            return 0
        
        if args.run:
            # Dry-run by default, require --yes to execute
            dry_run = not args.execute
            runner.run_for_connected_device(config, verbose=args.verbose, dry_run=dry_run)
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
