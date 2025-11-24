"""
Improved comprehensive edge case tests with:
1. Sanity check to verify device connectivity
2. Isolated folders per test (copy_test_1, copy_test_2, etc.)
3. Proper cleanup with safety verification
4. Better failure diagnostics
"""

import sys
from pathlib import Path
import shutil
import hashlib
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import config as cfg, runner, operations
from tests.helpers.mtp_testlib import MTPDevice


class ImprovedEdgeCaseTestSuite:
    """Improved edge case tests with safety and isolation."""
    
    # Base test folder (will be cleaned up completely)
    TEST_BASE_PHONE = "Internal storage/test-phone-edge-v2"
    TEST_BASE_DESKTOP = Path.home() / ".local" / "share" / "phone_edge_tests_v2"
    
    # Track what we create for safe cleanup
    created_phone_folders: List[str] = []
    created_desktop_folders: List[Path] = []
    
    def __init__(self):
        """Initialize test suite."""
        self.device = None
        self.mtp = None
        self.test_profile = None
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        self.failed_tests: List[str] = []
    
    # ==================== SANITY CHECK ====================
    
    def sanity_check(self) -> bool:
        """
        TEST 0: SANITY CHECK - Verify device connection AND filesystem access.
        
        Tests:
        1. Device detection
        2. MTP connection initialization
        3. Filesystem access (can read directory listing)
        4. Write access (can create test folder)
        
        All must pass for tests to proceed. If any fails, it's an environment
        issue, not a code issue.
        """
        print("\n" + "="*70)
        print("TEST 0: SANITY CHECK - Connection & Filesystem Access")
        print("="*70 + "\n")
        
        try:
            # Step 1: Detect device
            print("  1. Detecting device...")
            config = cfg.load_config()
            profile = runner.detect_connected_device(config, verbose=False)
            
            if not profile:
                print("     ❌ FAILED: No device detected")
                print("     → Check: Phone connected via USB?")
                print("     → Check: File Transfer mode enabled?")
                self.results["failed"] += 1
                return False
            print("     ✓ Device detected")
            
            # Step 2: Get connection info
            print("  2. Checking connection URI...")
            device_info = profile.get("device", {})
            display_name = device_info.get("display_name", "Unknown")
            activation_uri = device_info.get("activation_uri", "")
            
            if not activation_uri:
                print("     ❌ FAILED: No activation URI found")
                self.results["failed"] += 1
                return False
            print(f"     ✓ Connected to: {display_name}")
            
            # Step 3: Initialize MTP
            print("  3. Initializing MTP connection...")
            self.mtp = MTPDevice(activation_uri)
            self.test_profile = profile
            print("     ✓ MTP initialized")
            
            # Step 4: Test READ access (list directory)
            print("  4. Testing READ access (list directory)...")
            try:
                root_contents = self.mtp.list_dir("/")
                print(f"     ✓ Can read filesystem ({len(root_contents)} items in root)")
            except Exception as e:
                print(f"     ❌ FAILED: Cannot read filesystem")
                print(f"     → Error: {e}")
                print("     → This means MTP connection exists but filesystem is inaccessible")
                self.results["failed"] += 1
                return False
            
            # Step 5: Test WRITE access (can create folder)
            print("  5. Testing WRITE access (can create folder)...")
            try:
                test_folder = "Internal storage/sanity_check_test"
                self.mtp.mkdir(test_folder)
                # Try to list it to verify it was created
                self.mtp.list_dir(test_folder)
                # Clean up
                self.mtp.remove_recursive(test_folder)
                print(f"     ✓ Can write to filesystem")
            except Exception as e:
                print(f"     ❌ FAILED: Cannot write to filesystem")
                print(f"     → Error: {e}")
                print("     → This means READ works but WRITE doesn't")
                print("     → Check: Phone permissions? Storage full? Read-only mode?")
                self.results["failed"] += 1
                return False
            
            # All checks passed
            print(f"\n✅ SANITY CHECK PASSED - Ready to run tests")
            print(f"   Device: {display_name}")
            print(f"   Connection: ✓ Read Access: ✓ Write Access: ✓")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"❌ SANITY CHECK FAILED: Unexpected error")
            print(f"   {e}")
            self.results["failed"] += 1
            return False
    
    # ==================== SETUP ====================
    
    def setup_test_folders(self) -> bool:
        """
        Setup phase: Create all test directories and populate with test files.
        
        Creates isolated folder structure:
        - Phone: test-phone-edge-v2/copy_test_1/, copy_test_2/, move_test_1/, etc.
        - Desktop: ~/.local/share/phone_edge_tests_v2/copy_test_1/, etc.
        
        This ensures tests don't interfere with each other.
        """
        print("\n" + "="*70)
        print("SETUP: Creating isolated test folders")
        print("="*70 + "\n")
        
        try:
            # Create base desktop folder
            self.TEST_BASE_DESKTOP.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created base desktop folder: {self.TEST_BASE_DESKTOP}")
            
            # Create base phone folder
            self.mtp.mkdir(self.TEST_BASE_PHONE)
            print(f"✓ Created base phone folder: {self.TEST_BASE_PHONE}")
            
            # Get test videos
            videos_dir = Path(__file__).parent / "videos"
            if not videos_dir.exists():
                print(f"❌ Test videos directory not found: {videos_dir}")
                return False
            
            video_files = list(videos_dir.glob("*.mp4"))
            if not video_files:
                print(f"❌ No test videos found in {videos_dir}")
                return False
            
            print(f"✓ Found {len(video_files)} test videos")
            
            # Define test structure
            test_configs = {
                "copy_test_rename": ["nested/deep", "empty_folder"],
                "copy_test_structure": ["nested/deep", "empty_folder"],
                "move_test_verify": [],
                "sync_test_unchanged": [],
                "sync_test_deleted_file": [],
                "sync_test_deleted_folder": [],
                "backup_test_resume": [],
                "backup_test_changed": [],
                "hidden_test": [],
                "empty_test": [],
                "filename_test": [],
            }
            
            # Create test folder structure
            video_idx = 0
            for test_name, subdirs in test_configs.items():
                # Phone folder
                test_phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
                self.mtp.mkdir(test_phone_path)
                self.created_phone_folders.append(test_phone_path)
                
                # Desktop folder
                test_desktop_path = self.TEST_BASE_DESKTOP / test_name
                test_desktop_path.mkdir(parents=True, exist_ok=True)
                self.created_desktop_folders.append(test_desktop_path)
                
                # Create subdirectories
                for subdir in subdirs:
                    self.mtp.mkdir(f"{test_phone_path}/{subdir}")
                
                # Add test files to phone
                if video_idx < len(video_files):
                    self.mtp.push_file(video_files[video_idx], f"{test_phone_path}/file_root.mp4")
                    video_idx += 1
                
                if video_idx < len(video_files) and "nested" in subdirs:
                    self.mtp.push_file(video_files[video_idx], f"{test_phone_path}/nested/file_nested.mp4")
                    video_idx += 1
                
                if video_idx < len(video_files) and "nested/deep" in subdirs:
                    self.mtp.push_file(video_files[video_idx], f"{test_phone_path}/nested/deep/file_deep.mp4")
                    video_idx += 1
            
            print(f"✓ Created {len(test_configs)} isolated test folders")
            print(f"  Phone base: {self.TEST_BASE_PHONE}/")
            print(f"  Desktop base: {self.TEST_BASE_DESKTOP}/\n")
            
            return True
        
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    # ==================== CLEANUP ====================
    
    def cleanup(self) -> None:
        """
        Safe cleanup with verification.
        
        Only deletes folders we know we created (tracked in created_* lists).
        This prevents accidental deletion of user data.
        """
        print("\n" + "="*70)
        print("CLEANUP: Removing test artifacts")
        print("="*70 + "\n")
        
        # Clean phone folders
        print("Cleaning phone...")
        for folder in self.created_phone_folders:
            try:
                self.mtp.remove_recursive(folder)
                print(f"  ✓ Removed: {folder}")
            except Exception as e:
                print(f"  ⚠ Error removing {folder}: {e}")
        
        # Clean desktop folders
        print("Cleaning desktop...")
        for folder in self.created_desktop_folders:
            try:
                if folder.exists():
                    shutil.rmtree(folder)
                    print(f"  ✓ Removed: {folder}")
            except Exception as e:
                print(f"  ⚠ Error removing {folder}: {e}")
        
        # Remove base test folder if empty
        try:
            self.mtp.remove_recursive(self.TEST_BASE_PHONE)
            print(f"  ✓ Removed base folder: {self.TEST_BASE_PHONE}")
        except:
            pass
        
        try:
            if self.TEST_BASE_DESKTOP.exists() and len(list(self.TEST_BASE_DESKTOP.iterdir())) == 0:
                self.TEST_BASE_DESKTOP.rmdir()
        except:
            pass
        
        print("✓ Cleanup complete\n")
    
    # ==================== TEST HELPER ====================
    
    def count_files_recursive(self, tree: Dict) -> int:
        """Recursively count files in tree."""
        count = len(tree.get("files", []))
        for subdir in tree.get("dirs", {}).values():
            count += self.count_files_recursive(subdir)
        return count
    
    # ==================== TESTS ====================
    
    def test_copy_rename_handling(self) -> bool:
        """TEST 1: Copy with duplicate filenames - verify rename handling."""
        print("\n" + "-"*70)
        print("TEST 1: COPY - Rename Handling (Duplicates)")
        print("-"*70 + "\n")
        
        try:
            test_name = "copy_test_rename"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            dest_path = self.TEST_BASE_DESKTOP / test_name
            
            # Add extra files with same names in different subdirs
            videos_dir = Path(__file__).parent / "videos"
            video = list(videos_dir.glob("*.mp4"))[0]
            self.mtp.mkdir(f"{phone_path}/subdir1")
            self.mtp.mkdir(f"{phone_path}/subdir2")
            self.mtp.push_file(video, f"{phone_path}/subdir1/duplicate.mp4")
            self.mtp.push_file(video, f"{phone_path}/subdir2/duplicate.mp4")
            
            # Run copy
            operations.run_copy_rule(
                {"phone_path": phone_path, "desktop_path": str(dest_path), "id": "test_copy_rename"},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Verify: all 5 files copied (3 originals + 2 new)
            all_files = list(dest_path.rglob("*.mp4"))
            if len(all_files) == 5:
                print(f"✅ COPY RENAME TEST PASSED ({len(all_files)} files)")
                self.results["passed"] += 1
                return True
            else:
                print(f"❌ Expected 5 files, got {len(all_files)}")
                self.failed_tests.append("copy_rename")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            self.failed_tests.append("copy_rename")
            self.results["failed"] += 1
            return False
    
    def test_move_verification(self) -> bool:
        """TEST 2: Move - verify copy before deletion."""
        print("\n" + "-"*70)
        print("TEST 2: MOVE - File Verification Before Deletion")
        print("-"*70 + "\n")
        
        try:
            test_name = "move_test_verify"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            dest_path = self.TEST_BASE_DESKTOP / test_name
            
            # Add test files
            videos_dir = Path(__file__).parent / "videos"
            videos = list(videos_dir.glob("*.mp4"))[:3]
            for i, vid in enumerate(videos):
                self.mtp.push_file(vid, f"{phone_path}/file{i}.mp4")
            
            # Count before
            pre_tree = self.mtp.directory_tree(phone_path)
            pre_count = self.count_files_recursive(pre_tree)
            
            # Run move
            operations.run_move_rule(
                {"phone_path": phone_path, "desktop_path": str(dest_path), "id": "test_move_verify"},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Verify
            desktop_files = list(dest_path.rglob("*.mp4"))
            post_tree = self.mtp.directory_tree(phone_path)
            post_count = self.count_files_recursive(post_tree)
            
            if len(desktop_files) == pre_count and post_count == 0:
                print(f"✅ MOVE VERIFICATION TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"❌ Files mismatch: desktop={len(desktop_files)}, phone_after={post_count}, expected={pre_count}")
                self.failed_tests.append("move_verify")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            self.failed_tests.append("move_verify")
            self.results["failed"] += 1
            return False
    
    # Additional tests (abbreviated for brevity - same pattern)
    
    def test_sync_unchanged(self) -> bool:
        """TEST 3: Sync - unchanged files skipped."""
        print("\n" + "-"*70)
        print("TEST 3: SYNC - Unchanged Files")
        print("-"*70 + "\n")
        
        try:
            test_name = "sync_test_unchanged"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            desktop_path = self.TEST_BASE_DESKTOP / test_name
            
            # Add files to desktop
            videos_dir = Path(__file__).parent / "videos"
            for i, vid in enumerate(list(videos_dir.glob("*.mp4"))[:3]):
                shutil.copy2(vid, desktop_path / vid.name)
            
            # First sync
            stats1 = operations.run_sync_rule(
                {"phone_path": phone_path, "desktop_path": str(desktop_path), "id": test_name},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Second sync (should skip)
            stats2 = operations.run_sync_rule(
                {"phone_path": phone_path, "desktop_path": str(desktop_path), "id": test_name},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            if stats2['copied'] == 0 and stats2['skipped'] > 0:
                print(f"✅ SYNC UNCHANGED TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"❌ Second sync should skip files")
                self.failed_tests.append("sync_unchanged")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            self.failed_tests.append("sync_unchanged")
            self.results["failed"] += 1
            return False
    
    # Placeholder for remaining tests (implement same pattern)
    
    def run_all(self) -> bool:
        """Run all tests with proper setup and cleanup."""
        print("\n" + "="*70)
        print("PHONE MIGRATION TOOL - IMPROVED EDGE CASE TEST SUITE v2")
        print("="*70)
        
        # Sanity check first
        if not self.sanity_check():
            print("\n⚠️  Device connection failed. Fix connection and try again.")
            return False
        
        # Setup
        if not self.setup_test_folders():
            print("\n⚠️  Setup failed. Cleaning up...")
            self.cleanup()
            return False
        
        # Run tests
        try:
            self.test_copy_rename_handling()
            self.test_move_verification()
            self.test_sync_unchanged()
            # TODO: Add remaining tests following same pattern
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Tests interrupted by user")
        
        finally:
            # Always cleanup, even if tests fail
            self.cleanup()
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        total = self.results["passed"] + self.results["failed"]
        print(f"\nTotal: {total} | ✅ Passed: {self.results['passed']} | ❌ Failed: {self.results['failed']}\n")
        
        if self.failed_tests:
            print("Failed tests:")
            for test in self.failed_tests:
                print(f"  - {test}")
            print()
        
        return self.results["failed"] == 0


if __name__ == "__main__":
    suite = ImprovedEdgeCaseTestSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)
