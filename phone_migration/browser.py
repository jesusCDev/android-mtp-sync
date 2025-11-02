"""Interactive phone directory browser."""

from typing import Dict, Any, List
from . import gio_utils, paths

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright foreground colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


def list_phone_directory(activation_uri: str, phone_path: str = "/") -> List[Dict[str, Any]]:
    """
    List contents of a phone directory.
    
    Args:
        activation_uri: MTP activation URI
        phone_path: Path on phone to list
    
    Returns:
        List of entries with name, type, and size info
    """
    # Ensure device is mounted
    try:
        gio_utils.run(["gio", "mount", activation_uri], check=False)
    except:
        pass  # Already mounted or can't mount
    
    # Build full URI
    full_uri = paths.build_phone_uri(activation_uri, phone_path)
    
    # List entries
    entries = gio_utils.gio_list(full_uri)
    
    result = []
    for entry in entries:
        entry_uri = f"{full_uri}/{entry}"
        info = gio_utils.gio_info(entry_uri)
        
        entry_type = info.get("standard::type", "")
        # Check multiple indicators for directories
        is_dir = (
            "directory" in entry_type.lower() or 
            entry_type == "2" or  # Type 2 is directory
            info.get("standard::is-directory", "").lower() == "true"
        )
        
        size = info.get("standard::size", "0")
        
        result.append({
            "name": entry,
            "is_directory": is_dir,
            "size": int(size) if size.isdigit() else 0,
            "path": f"{phone_path}/{entry}" if phone_path != "/" else f"/{entry}"
        })
    
    # Sort: directories first, then files
    result.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
    
    return result


def browse_phone_interactive(device_info: Dict[str, Any], start_path: str = "/") -> None:
    """
    Interactive browser for phone directories.
    
    Args:
        device_info: Device info with activation_uri
        start_path: Starting path on phone
    """
    activation_uri = device_info.get("activation_uri", "")
    display_name = device_info.get("display_name", "Phone")
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}📱 Browsing: {display_name}{Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 60}{Colors.RESET}")
    
    # First, show storage roots
    print(f"\n{Colors.BOLD}Available Storage:{Colors.RESET}")
    print(f"  {Colors.GREEN}[1]{Colors.RESET} Internal storage")
    print(f"  {Colors.YELLOW}[2]{Colors.RESET} SD Card (if available)")
    print(f"  {Colors.RED}[0]{Colors.RESET} Cancel")
    
    try:
        choice = input("\nSelect storage [1]: ").strip() or "1"
        
        if choice == "0":
            return
        elif choice == "1":
            storage = "Internal storage"
        elif choice == "2":
            storage = "SD Card"
        else:
            print("Invalid choice")
            return
        
        # Browse from storage root
        browse_path_recursive(activation_uri, storage, "/")
        
    except (KeyboardInterrupt, EOFError):
        print("\n\nBrowsing cancelled")


def browse_path_recursive(activation_uri: str, storage: str, current_path: str) -> None:
    """
    Recursively browse a path on phone.
    
    Args:
        activation_uri: MTP URI
        storage: Storage label (Internal storage or SD Card)
        current_path: Current path being browsed
    """
    while True:
        full_path = current_path if current_path.startswith(f"{storage}/") else f"{storage}{current_path}"
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}📁 {full_path}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * 60}{Colors.RESET}")
        
        try:
            entries = list_phone_directory(activation_uri, current_path)
        except Exception as e:
            print(f"Error listing directory: {e}")
            return
        
        # Show directories first
        dirs = [e for e in entries if e["is_directory"]]
        files = [e for e in entries if not e["is_directory"]]
        
        if not entries:
            print("  (empty directory)")
        else:
            if dirs:
                print(f"\n{Colors.BOLD}{Colors.CYAN}Directories ({len(dirs)}):{Colors.RESET}")
                for i, entry in enumerate(dirs, 1):
                    print(f"  {Colors.GREEN}[{i}]{Colors.RESET} {Colors.BOLD}📁 {entry['name']}/{Colors.RESET}")
            
            if files:
                print(f"\n{Colors.DIM}Files ({len(files)}):{Colors.RESET}")
                for entry in files[:10]:  # Show first 10 files
                    size_mb = entry['size'] / (1024 * 1024)
                    if size_mb > 1:
                        size_str = f"{size_mb:.1f} MB"
                    else:
                        size_str = f"{entry['size'] / 1024:.1f} KB"
                    print(f"      {Colors.DIM}📄 {entry['name']} ({size_str}){Colors.RESET}")
                
                if len(files) > 10:
                    print(f"      {Colors.DIM}... and {len(files) - 10} more files{Colors.RESET}")
        
        # Menu
        print(f"\n{Colors.BOLD}Options:{Colors.RESET}")
        if dirs:
            print(f"  {Colors.GREEN}1-{len(dirs)}{Colors.RESET}: Enter directory")
        print(f"  {Colors.YELLOW}[u]{Colors.RESET}: Go up one level")
        print(f"  {Colors.CYAN}[c]{Colors.RESET}: Use current path")
        print(f"  {Colors.RED}[q]{Colors.RESET}: Quit")
        
        try:
            choice = input("\nChoice: ").strip().lower()
            
            if choice == 'q':
                return
            elif choice == 'u':
                # Go up one level
                if current_path == "/":
                    print("Already at root")
                else:
                    parts = current_path.rstrip("/").split("/")
                    current_path = "/".join(parts[:-1]) or "/"
            elif choice == 'c':
                print(f"\n{Colors.BOLD}{Colors.GREEN}✓ Selected path:{Colors.RESET} {Colors.CYAN}{current_path}{Colors.RESET}")
                print(f"\n{Colors.BOLD}To use this in a rule:{Colors.RESET}")
                print(f"  {Colors.YELLOW}--phone-path{Colors.RESET} {current_path}")
                return
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(dirs):
                    selected = dirs[idx]
                    new_path = selected['path']
                    if not new_path.startswith("/"):
                        new_path = "/" + new_path
                    current_path = new_path
                else:
                    print("Invalid number")
            else:
                print("Invalid choice")
        
        except (KeyboardInterrupt, EOFError):
            print("\n\nBrowsing cancelled")
            return


def list_phone_root(device_info: Dict[str, Any]) -> None:
    """
    List root directories on phone (non-interactive).
    
    Args:
        device_info: Device info with activation_uri
    """
    activation_uri = device_info.get("activation_uri", "")
    display_name = device_info.get("display_name", "Phone")
    
    print(f"\n{display_name} - Root Directories:\n")
    
    # Check Internal storage
    print("📱 Internal storage:")
    try:
        entries = list_phone_directory(activation_uri, "/")
        for entry in entries:
            if entry["is_directory"]:
                print(f"  /{entry['name']}/")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Check SD Card if available
    print("\n💾 SD Card:")
    try:
        entries = list_phone_directory(activation_uri, "SD Card/")
        if entries:
            for entry in entries:
                if entry["is_directory"]:
                    print(f"  SD Card/{entry['name']}/")
        else:
            print("  (not available or empty)")
    except Exception:
        print("  (not available)")
    
    print("\nCommon paths:")
    print("  /DCIM/Camera          - Photos")
    print("  /DCIM/Screenshots     - Screenshots")
    print("  /Download             - Downloads")
    print("  /Movies               - Movies")
    print("  /Music                - Music")
    print("  /Documents            - Documents")
