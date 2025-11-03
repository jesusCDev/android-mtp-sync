"""Runner to detect connected device and execute configured rules."""

from typing import Any, Dict, Optional
from . import device, config as cfg, operations, gio_utils, paths, notifications
from .transfer_stats import TransferStats

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97;1m'


def detect_connected_device(config: Dict[str, Any], verbose: bool = False) -> Optional[Dict[str, Any]]:
    """
    Detect connected MTP device and find matching profile.
    
    Args:
        config: Configuration dictionary
        verbose: Print verbose output
    
    Returns:
        Tuple of (profile, device_info) or None if no match
    """
    devices = device.enumerate_mtp_mounts()
    
    if not devices:
        return None
    
    if verbose:
        print(f"Found {len(devices)} MTP device(s)")
    
    # Try to match each device to a profile
    for dev_info in devices:
        id_type, id_value = device.device_fingerprint(dev_info, verbose)
        
        if verbose:
            print(f"  Checking device: {dev_info.get('display_name', 'Unknown')}")
            print(f"    Fingerprint: {id_type}={id_value}")
        
        profile = cfg.find_profile_by_device_id(config, id_type, id_value)
        
        if profile:
            if verbose:
                print(f"    ✓ Matched profile: {profile.get('name', 'unknown')}")
            
            # Update activation URI in case it changed (USB port)
            profile["device"]["activation_uri"] = dev_info.get("activation_uri", "")
            
            return profile
    
    return None


def run_for_connected_device(config: Dict[str, Any], verbose: bool = False, dry_run: bool = False, rule_ids: Optional[list] = None, notify: bool = False, include_manual: bool = False, rename_duplicates: bool = True) -> None:
    """
    Detect connected device and run configured rules.
    
    Args:
        config: Configuration dictionary
        verbose: Print verbose output
        dry_run: Print actions without executing
        rule_ids: Optional list of specific rule IDs to run (ignores manual_only flag)
        notify: Send desktop notifications on completion
        include_manual: Include manual-only rules in execution
        rename_duplicates: When True, rename files on conflict; when False, skip them
    """
    # Print program header
    print(f"\n{Colors.BOLD}{Colors.BRIGHT_WHITE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_WHITE}📱 Phone Migration Tool{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_WHITE}{'='*60}{Colors.RESET}\n")
    
    # Set dry-run mode
    if dry_run:
        gio_utils.DRY_RUN = True
        print(f"{Colors.BOLD}{Colors.YELLOW}[DRY RUN MODE - Preview Only]{Colors.RESET}\n")
    
    # Detect device
    print(f"{Colors.DIM}Detecting connected device...{Colors.RESET}")
    profile = detect_connected_device(config, verbose)
    
    if not profile:
        print(f"\n{Colors.RED}❌ No device connected or profile not configured{Colors.RESET}")
        print(f"\n{Colors.BOLD}Common causes:{Colors.RESET}")
        print(f"  {Colors.DIM}•{Colors.RESET} Phone is not connected via USB")
        print(f"  {Colors.DIM}•{Colors.RESET} File Transfer mode is not enabled")
        print(f"  {Colors.DIM}•{Colors.RESET} Phone is locked or not visible")
        print(f"  {Colors.DIM}•{Colors.RESET} Device is not registered yet")
        
        print(f"\n{Colors.BOLD}What to do:{Colors.RESET}")
        print(f"  {Colors.CYAN}1. Connect your phone{Colors.RESET} and enable File Transfer mode")
        print(f"  {Colors.CYAN}2. Run:{Colors.RESET} phone-sync --add-device --name default")
        print(f"  {Colors.CYAN}3. Then run:{Colors.RESET} phone-sync --run")
        
        print(f"\n{Colors.BOLD}Debug:{Colors.RESET}")
        print(f"  {Colors.DIM}To see connected MTP devices:{Colors.RESET} gio mount -li | grep -i mtp")
        print(f"  {Colors.DIM}To check config:{Colors.RESET} cat ~/.config/phone-migration/config.json | jq .")
        
        # Send notification if enabled
        if notify:
            notifications.notify_device_not_found()
        
        return
    
    profile_name = profile.get("name", "unknown")
    device_info = profile.get("device", {})
    display_name = device_info.get("display_name", "Unknown")
    
    print(f"{Colors.BRIGHT_GREEN}✓ Found registered device:{Colors.RESET} {Colors.BOLD}{display_name}{Colors.RESET} {Colors.DIM}(profile: {profile_name}){Colors.RESET}")
    
    # Get activation URI
    activation_uri = device_info.get("activation_uri", "")
    
    # Test device accessibility
    if activation_uri:
        print(f"{Colors.DIM}Checking device accessibility...{Colors.RESET}")
        try:
            # Try to list the root storage to check if device is accessible
            test_uri = paths.build_phone_uri(activation_uri, "/")
            entries = gio_utils.gio_list(test_uri)
            if not entries:  # Empty list might indicate locked phone
                print(f"{Colors.YELLOW}⚠ Warning:{Colors.RESET} Device appears to be {Colors.YELLOW}locked{Colors.RESET} or files are not accessible")
                print(f"  {Colors.DIM}Unlock your phone and enable File Transfer mode for full access{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}✓ Device accessible{Colors.RESET}")
        except Exception as e:
            if verbose:
                print(f"{Colors.YELLOW}⚠ Warning:{Colors.RESET} Could not verify device accessibility: {e}")
            print(f"{Colors.DIM}If no files are found, make sure phone is unlocked{Colors.RESET}")
    
    print()  # Add spacing
    
    # Get rules
    all_rules = profile.get("rules", [])
    
    if not all_rules:
        print(f"{Colors.YELLOW}No rules configured for profile '{profile_name}'{Colors.RESET}")
        print(f"\n{Colors.BOLD}Add rules with:{Colors.RESET}")
        print(f"  {Colors.CYAN}phone-sync --move -p {profile_name} -pp /DCIM/Camera -dp ~/Pictures{Colors.RESET}")
        print(f"  {Colors.CYAN}phone-sync --copy -p {profile_name} -pp /DCIM/Camera -dp ~/Backup{Colors.RESET}")
        print(f"  {Colors.CYAN}phone-sync --sync -p {profile_name} -dp ~/Videos/motiv -pp /Videos/motiv{Colors.RESET}")
        return
    
    # Filter rules based on rule_ids, include_manual flag, or manual_only flag
    if rule_ids:
        # Run specific rules by ID (ignore manual_only)
        rules = [r for r in all_rules if r.get("id") in rule_ids]
        if not rules:
            print(f"{Colors.RED}Error: No rules found with specified IDs: {', '.join(rule_ids)}{Colors.RESET}")
            return
        print(f"{Colors.BOLD}Executing {len(rules)} specified rule(s)...{Colors.RESET}\n")
    elif include_manual:
        # Run only manual rules
        rules = [r for r in all_rules if r.get("manual_only", False)]
        auto_count = len(all_rules) - len(rules)
        if not rules:
            print(f"{Colors.YELLOW}No manual rules configured{Colors.RESET}")
            return
        print(f"{Colors.BOLD}Executing {len(rules)} manual rule(s)...", end="")
        if auto_count > 0:
            print(f" {Colors.DIM}({auto_count} auto rule(s) skipped){Colors.RESET}")
        else:
            print(f"{Colors.RESET}\n")
    else:
        # Run only non-manual rules
        rules = [r for r in all_rules if not r.get("manual_only", False)]
        manual_count = len(all_rules) - len(rules)
        if not rules:
            print(f"{Colors.YELLOW}All {len(all_rules)} rule(s) are marked as [MANUAL]{Colors.RESET}")
            print(f"\n{Colors.DIM}Run specific rules with:{Colors.RESET} {Colors.CYAN}--run -r <rule-id>{Colors.RESET}")
            return
        print(f"{Colors.BOLD}Executing {len(rules)} rule(s)...", end="")
        if manual_count > 0:
            print(f" {Colors.DIM}({manual_count} manual rule(s) skipped){Colors.RESET}")
        else:
            print(f"{Colors.RESET}\n")
    print(f"{Colors.DIM}{'='*60}{Colors.RESET}")
    
    # Ensure device is mounted
    if activation_uri:
        try:
            import subprocess
            subprocess.run(["gio", "mount", activation_uri], capture_output=True, check=False)
        except:
            pass  # Already mounted
    
    # Execute each rule
    total_stats = {"copied": 0, "renamed": 0, "deleted": 0, "errors": 0, "skipped": 0, "moved": 0, "synced": 0, "backed_up": 0, "folders": 0, "transfer_stats": None}
    
    # Start transfer statistics tracking
    transfer_tracker = TransferStats()
    transfer_tracker.start()
    total_stats["transfer_stats"] = transfer_tracker
    
    for i, rule in enumerate(rules, 1):
        rule_id = rule.get("id", f"rule-{i}")
        mode = rule.get("mode", "unknown")
        
        try:
            if mode == "move":
                stats = operations.run_move_rule(rule, device_info, verbose, transfer_tracker, rename_duplicates=rename_duplicates)
                total_stats["copied"] += stats.get("copied", 0)
                total_stats["renamed"] += stats.get("renamed", 0)
                total_stats["deleted"] += stats.get("deleted", 0)
                total_stats["errors"] += stats.get("errors", 0)
                total_stats["skipped"] += stats.get("skipped", 0)
                total_stats["moved"] += stats.get("copied", 0)  # Moved = files copied from phone
                total_stats["folders"] += stats.get("folders", 0)
            
            elif mode == "copy":
                stats = operations.run_copy_rule(rule, device_info, verbose, transfer_tracker, rename_duplicates=rename_duplicates)
                total_stats["copied"] += stats.get("copied", 0)
                total_stats["renamed"] += stats.get("renamed", 0)
                total_stats["errors"] += stats.get("errors", 0)
                total_stats["skipped"] += stats.get("skipped", 0)
                total_stats["backed_up"] += stats.get("copied", 0)  # Backed up = files copied without deletion
                total_stats["folders"] += stats.get("folders", 0)
            
            elif mode == "smart_copy":
                stats = operations.run_smart_copy_rule(rule, device_info, verbose, transfer_tracker, rename_duplicates=rename_duplicates)
                total_stats["copied"] += stats.get("copied", 0)
                total_stats["errors"] += stats.get("errors", 0)
                total_stats["skipped"] += stats.get("skipped", 0)
                total_stats["backed_up"] += stats.get("copied", 0) + stats.get("resumed", 0)  # Total including resumed
            
            elif mode == "sync":
                stats = operations.run_sync_rule(rule, device_info, verbose, transfer_tracker, rename_duplicates=rename_duplicates)
                total_stats["copied"] += stats.get("copied", 0)
                total_stats["deleted"] += stats.get("deleted", 0)
                total_stats["errors"] += stats.get("errors", 0)
                total_stats["synced"] += stats.get("copied", 0)  # Synced = files copied to phone
            
            else:
                print(f"\n{Colors.YELLOW}⚠ Unknown rule mode: {mode} (rule {rule_id}){Colors.RESET}")
        
        except Exception as e:
            print(f"\n{Colors.RED}❌ Error executing rule {rule_id}:{Colors.RESET} {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            total_stats["errors"] += 1
    
    # Print summary
    print(f"\n{Colors.DIM}{'='*60}{Colors.RESET}")
    print(f"\n📊 {Colors.BOLD}Summary:{Colors.RESET}")
    
    # Calculate moved vs synced vs backed_up
    moved_count = total_stats.get('moved', 0)  # Files moved (copied then deleted)
    backed_up_count = total_stats.get('backed_up', 0)  # Files copied (kept on phone)
    synced_count = total_stats.get('synced', 0)  # Files synced to phone
    
    if moved_count > 0:
        print(f"  {Colors.BRIGHT_GREEN}📤 Files moved from phone:{Colors.RESET}      {Colors.BOLD}{moved_count}{Colors.RESET}")
    if backed_up_count > 0:
        print(f"  {Colors.BRIGHT_CYAN}📋 Files backed up from phone:{Colors.RESET}  {Colors.BOLD}{backed_up_count}{Colors.RESET}")
    if total_stats.get("folders", 0) > 0:
        print(f"  {Colors.BRIGHT_WHITE}📂 Folders processed:{Colors.RESET}           {Colors.BOLD}{total_stats['folders']}{Colors.RESET}")
    if synced_count > 0:
        print(f"  {Colors.BRIGHT_BLUE}📥 Files synced to phone:{Colors.RESET}       {Colors.BOLD}{synced_count}{Colors.RESET}")
    if total_stats["renamed"] > 0:
        print(f"  {Colors.YELLOW}🔄 Files renamed (duplicates):{Colors.RESET}  {Colors.BOLD}{total_stats['renamed']}{Colors.RESET}")
    if total_stats["skipped"] > 0:
        print(f"  {Colors.CYAN}⊙ Files skipped (exist):{Colors.RESET}      {Colors.BOLD}{total_stats['skipped']}{Colors.RESET}")
    if total_stats["deleted"] > 0:
        print(f"  {Colors.RED}🗑️  Files deleted from phone:{Colors.RESET}    {Colors.BOLD}{total_stats['deleted']}{Colors.RESET}")
    
    if total_stats["errors"] > 0:
        print(f"  {Colors.RED}⚠️  Errors:{Colors.RESET} {Colors.BOLD}{total_stats['errors']}{Colors.RESET}")
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Completed with errors{Colors.RESET}")
    elif total_stats["skipped"] > 0 and (moved_count + backed_up_count + synced_count + total_stats['renamed'] > 0):
        print(f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}✅ Completed with {total_stats['skipped']} file(s) skipped{Colors.RESET}")
    else:
        if moved_count + backed_up_count + synced_count + total_stats['deleted'] > 0:
            print(f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}✅ All operations completed successfully!{Colors.RESET}")
        else:
            print(f"\n{Colors.GREEN}✓ No changes needed{Colors.RESET}")
    
    # Show transfer statistics if any files were transferred
    if transfer_tracker and (moved_count + backed_up_count + synced_count) > 0:
        stats_summary = transfer_tracker.get_summary()
        if stats_summary["size_bytes"] > 0:
            print(f"\n  {Colors.DIM}📊 Transfer: {Colors.RESET}{stats_summary['size']} in {stats_summary['time']}")
            if stats_summary["speed_mbps"] > 0.1:  # Only show speed if meaningful
                print(f"  {Colors.DIM}⚡ Speed: {Colors.RESET}{stats_summary['speed']}")
    
    if dry_run:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[DRY RUN]{Colors.RESET} {Colors.DIM}No actual changes were made{Colors.RESET}")
        print(f"   {Colors.DIM}Run with{Colors.RESET} {Colors.GREEN}--yes{Colors.RESET} {Colors.DIM}or{Colors.RESET} {Colors.GREEN}-y{Colors.RESET} {Colors.DIM}to execute operations{Colors.RESET}")
    
    # Send notification if enabled
    if notify:
        notifications.notify_completion(total_stats, dry_run)
