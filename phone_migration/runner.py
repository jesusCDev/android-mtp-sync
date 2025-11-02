"""Runner to detect connected device and execute configured rules."""

from typing import Any, Dict, Optional
from . import device, config as cfg, operations, gio_utils

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


def run_for_connected_device(config: Dict[str, Any], verbose: bool = False, dry_run: bool = False) -> None:
    """
    Detect connected device and run all configured rules.
    
    Args:
        config: Configuration dictionary
        verbose: Print verbose output
        dry_run: Print actions without executing
    """
    # Set dry-run mode
    if dry_run:
        gio_utils.DRY_RUN = True
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}[DRY RUN MODE - Preview Only]{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}{'='*60}{Colors.RESET}\n")
    
    # Detect device
    print(f"{Colors.DIM}Detecting connected device...{Colors.RESET}")
    profile = detect_connected_device(config, verbose)
    
    if not profile:
        print(f"\n{Colors.RED}❌ No matching device found.{Colors.RESET}")
        print(f"\n{Colors.BOLD}Make sure:{Colors.RESET}")
        print(f"  {Colors.DIM}1.{Colors.RESET} Your phone is connected via USB")
        print(f"  {Colors.DIM}2.{Colors.RESET} File Transfer mode is enabled")
        print(f"  {Colors.DIM}3.{Colors.RESET} Your phone is unlocked")
        print(f"  {Colors.DIM}4.{Colors.RESET} You've registered the device with: {Colors.CYAN}phone-sync --add-device{Colors.RESET}")
        print(f"\n{Colors.DIM}Run 'gio mount -li' to see connected MTP devices{Colors.RESET}")
        return
    
    profile_name = profile.get("name", "unknown")
    device_info = profile.get("device", {})
    display_name = device_info.get("display_name", "Unknown")
    
    print(f"{Colors.BRIGHT_GREEN}✓ Found registered device:{Colors.RESET} {Colors.BOLD}{display_name}{Colors.RESET} {Colors.DIM}(profile: {profile_name}){Colors.RESET}\n")
    
    # Get rules
    rules = profile.get("rules", [])
    
    if not rules:
        print(f"{Colors.YELLOW}No rules configured for profile '{profile_name}'{Colors.RESET}")
        print(f"\n{Colors.BOLD}Add rules with:{Colors.RESET}")
        print(f"  {Colors.CYAN}phone-sync --move -p {profile_name} -pp /DCIM/Camera -dp ~/Pictures{Colors.RESET}")
        print(f"  {Colors.CYAN}phone-sync --sync -p {profile_name} -dp ~/Videos/motiv -pp /Videos/motiv{Colors.RESET}")
        return
    
    print(f"{Colors.BOLD}Executing {len(rules)} rule(s)...{Colors.RESET}\n")
    print(f"{Colors.DIM}{'='*60}{Colors.RESET}")
    
    # Ensure device is mounted
    activation_uri = device_info.get("activation_uri", "")
    if activation_uri:
        try:
            import subprocess
            subprocess.run(["gio", "mount", activation_uri], capture_output=True, check=False)
        except:
            pass  # Already mounted
    
    # Execute each rule
    total_stats = {"copied": 0, "renamed": 0, "deleted": 0, "errors": 0, "moved": 0, "synced": 0, "folders": 0}
    
    for i, rule in enumerate(rules, 1):
        rule_id = rule.get("id", f"rule-{i}")
        mode = rule.get("mode", "unknown")
        
        try:
            if mode == "move":
                stats = operations.run_move_rule(rule, device_info, verbose)
                total_stats["copied"] += stats.get("copied", 0)
                total_stats["renamed"] += stats.get("renamed", 0)
                total_stats["deleted"] += stats.get("deleted", 0)
                total_stats["errors"] += stats.get("errors", 0)
                total_stats["moved"] += stats.get("copied", 0)  # Moved = files copied from phone
                total_stats["folders"] += stats.get("folders", 0)
            
            elif mode == "sync":
                stats = operations.run_sync_rule(rule, device_info, verbose)
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
    
    # Calculate moved vs synced
    moved_count = total_stats.get('moved', 0)  # Files moved (copied then deleted)
    synced_count = total_stats.get('synced', 0)  # Files synced to phone
    
    if moved_count > 0:
        print(f"  {Colors.BRIGHT_GREEN}📤 Files moved from phone:{Colors.RESET}      {Colors.BOLD}{moved_count}{Colors.RESET}")
    if total_stats.get("folders", 0) > 0:
        print(f"  {Colors.BRIGHT_WHITE}📂 Folders processed:{Colors.RESET}           {Colors.BOLD}{total_stats['folders']}{Colors.RESET}")
    if synced_count > 0:
        print(f"  {Colors.BRIGHT_BLUE}📥 Files synced to phone:{Colors.RESET}       {Colors.BOLD}{synced_count}{Colors.RESET}")
    if total_stats["renamed"] > 0:
        print(f"  {Colors.YELLOW}🔄 Files renamed (duplicates):{Colors.RESET}  {Colors.BOLD}{total_stats['renamed']}{Colors.RESET}")
    if total_stats["deleted"] > 0:
        print(f"  {Colors.RED}🗑️  Files deleted from phone:{Colors.RESET}    {Colors.BOLD}{total_stats['deleted']}{Colors.RESET}")
    
    if total_stats["errors"] > 0:
        print(f"  {Colors.RED}⚠️  Errors:{Colors.RESET} {Colors.BOLD}{total_stats['errors']}{Colors.RESET}")
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Completed with errors{Colors.RESET}")
    else:
        if moved_count + synced_count + total_stats['deleted'] > 0:
            print(f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}✅ All operations completed successfully!{Colors.RESET}")
        else:
            print(f"\n{Colors.GREEN}✓ No changes needed{Colors.RESET}")
    
    if dry_run:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[DRY RUN]{Colors.RESET} {Colors.DIM}No actual changes were made{Colors.RESET}")
        print(f"   {Colors.DIM}Run with{Colors.RESET} {Colors.GREEN}--yes{Colors.RESET} {Colors.DIM}or{Colors.RESET} {Colors.GREEN}-y{Colors.RESET} {Colors.DIM}to execute operations{Colors.RESET}")
