#!/usr/bin/env python3
"""
Quick diagnostic test for copy/move operations.

This bypasses actual MTP operations and tests the logic.
"""

import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import config as cfg, runner, gio_utils

def diagnose_copy_issue():
    """Diagnose why copy operations show 0 copied."""
    print("\n" + "=" * 60)
    print("DIAGNOSTIC TEST: Copy/Move Operations")
    print("=" * 60 + "\n")
    
    config = cfg.load_config()
    profile = runner.detect_connected_device(config, verbose=False)
    
    if not profile:
        print("✗ ERROR: No device connected\n")
        return
    
    device_info = profile.get("device", {})
    activation_uri = device_info.get("activation_uri", "")
    
    print(f"✓ Connected device: {device_info.get('display_name')}")
    print(f"✓ Activation URI: {activation_uri}\n")
    
    # Test 1: Check if gio can list files
    print("TEST 1: Can gio list files on phone?")
    print("-" * 60)
    try:
        from phone_migration import paths
        root_uri = paths.build_phone_uri(activation_uri, "/Videos/motivation")
        print(f"  Testing URI: {root_uri}")
        
        entries = gio_utils.gio_list(root_uri)
        print(f"  ✓ Success! Found {len(entries)} entries\n")
    except Exception as e:
        print(f"  ✗ FAILED: {e}\n")
        return
    
    # Test 2: Check if gio can get file info
    print("TEST 2: Can gio get file info?")
    print("-" * 60)
    try:
        if len(entries) > 0:
            entry_uri = f"{root_uri}/{entries[0]}"
            print(f"  Testing file: {entries[0]}")
            info = gio_utils.gio_info(entry_uri)
            is_dir = "directory" in info.get("standard::type", "").lower()
            print(f"  Type: {'📁 Directory' if is_dir else '📄 File'}")
            print(f"  ✓ Success!\n")
        else:
            print(f"  ⚠ No files to test\n")
    except Exception as e:
        print(f"  ✗ FAILED: {e}\n")
    
    # Test 3: Test copy to local temp folder
    print("TEST 3: Can gio copy MTP files to desktop?")
    print("-" * 60)
    temp_dir = tempfile.mkdtemp(prefix="copy_test_")
    try:
        # Try to copy ONE small entry
        if len(entries) > 0:
            entry_name = entries[0]
            entry_uri = f"{root_uri}/{entry_name}"
            dest_path = f"{temp_dir}/{entry_name}_test"
            
            print(f"  Source: {entry_name}")
            print(f"  Dest: {dest_path}")
            
            # Check if it's a file first
            info = gio_utils.gio_info(entry_uri)
            is_dir = "directory" in info.get("standard::type", "").lower()
            
            if is_dir:
                print(f"  ⚠ Entry is a directory, skipping\n")
            else:
                result = gio_utils.gio_copy(entry_uri, dest_path, recursive=False, overwrite=False, verbose=True)
                
                if result:
                    print(f"  gio_copy returned: True")
                    dest = Path(dest_path)
                    if dest.exists():
                        size = dest.stat().st_size
                        print(f"  ✓ File exists: YES ({size} bytes)")
                        print(f"  ✓ Success!\n")
                    else:
                        print(f"  ✗ PROBLEM: gio_copy returned True but file doesn't exist!")
                        print(f"  ✗ This explains why operations report success but nothing happens\n")
                else:
                    print(f"  ✗ gio_copy returned: False\n")
    except Exception as e:
        print(f"  ✗ FAILED: {e}\n")
    finally:
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
    
    # Test 4: Check DRY_RUN mode
    print("TEST 4: Verify DRY_RUN flag state")
    print("-" * 60)
    print(f"  DRY_RUN flag: {gio_utils.DRY_RUN}\n")
    
    print("=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    try:
        diagnose_copy_issue()
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
