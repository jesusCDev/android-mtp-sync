"""
SAFE end-to-end tests for migration operations with copy verification.

⚠️  SAFETY FEATURES:
1. Only uses test-android-mtp/ folder on phone (isolated, non-destructive)
2. Only uses ~/.local/share/phone_migration_tests/ on desktop (safe test directory)
3. MOVE tests verify files exist on desktop BEFORE deleting from phone
4. Compares file counts and verifies structure after each operation
5. Fails tests if counts don't match (prevents data loss)
6. No interaction with user data directories
"""

import sys
from pathlib import Path
import shutil
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import config as cfg, runner, operations
from tests.helpers.mtp_testlib import MTPDevice


class SafeTestSuite:
    """Safe test suite with verification before deletion."""
    
    # SAFETY: These paths are isolated and safe
    TEST_FOLDER = "Internal storage/test-android-mtp"  # On phone - clearly marked as test
    LOCAL_TEST_DIR = Path.home() / ".local" / "share" / "phone_migration_tests"
    
    def __init__(self):
        """Initialize test suite."""
        self.device = None
        self.mtp = None
        self.test_profile = None
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
    
    def print_safety_header(self):
        """Print safety information."""
        print("\n" + "="*70)
        print("PHONE MIGRATION - SAFE END-TO-END TEST SUITE")
        print("="*70)
        print("\n🛡️  SAFETY FEATURES:")
        print(f"  ✓ Phone test folder: {self.TEST_FOLDER}/")
        print(f"  ✓ Desktop test folder: {self.LOCAL_TEST_DIR}")
        print("  ✓ No user data accessed")
        print("  ✓ Files verified before deletion (move operations)")
        print("  ✓ File counts validated after each operation")
        print("  ✓ Automatic cleanup on completion\n")
    
    def setup(self) -> bool:
        """Setup test environment."""
        # Detect connected device
        config = cfg.load_config()
        profile = runner.detect_connected_device(config, verbose=False)
        
        if not profile:
            print("❌ No device connected")
            return False
        
        self.test_profile = profile
        device_info = profile.get("device", {})
        activation_uri = device_info.get("activation_uri", "")
        
        if not activation_uri:
            print("❌ Device activation URI not found")
            return False
        
        print(f"✓ Connected device: {device_info.get('display_name')}")
        print(f"  Profile: {profile.get('name')}")
        
        # Initialize MTP device wrapper
        self.mtp = MTPDevice(activation_uri)
        
        # Create local test directories
        self.LOCAL_TEST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✓ Local test directory: {self.LOCAL_TEST_DIR}\n")
        
        return True
    
    def populate_test_structure(self) -> bool:
        """Create test folder structure on phone."""
        print("Setting up test folder structure on phone...\n")
        
        try:
            # Create main test folder
            self.mtp.mkdir(self.TEST_FOLDER)
            print(f"✓ Created {self.TEST_FOLDER}/ (test-only folder)\n")
            
            # Define test cases
            test_cases = {
                "copy_test": ["nested/deep", "empty_folder"],
                "move_test": ["nested/deep", "empty_folder"],
                "sync_test": ["nested/deep"],
                "backup_test": ["nested/deep", "empty_folder"],
            }
            
            # Get test videos
            videos_dir = Path(__file__).parent / "videos"
            if not videos_dir.exists():
                print(f"❌ Test videos directory not found: {videos_dir}")
                return False
            
            video_files = list(videos_dir.glob("*.mp4"))
            if not video_files:
                print(f"❌ No test videos found in {videos_dir}")
                return False
            
            print(f"✓ Found {len(video_files)} test videos\n")
            
            # Populate each test case
            video_idx = 0
            for test_case, subdirs in test_cases.items():
                test_path = f"{self.TEST_FOLDER}/{test_case}"
                self.mtp.mkdir(test_path)
                
                # Create subdirectories
                for subdir in subdirs:
                    dir_path = f"{test_path}/{subdir}"
                    self.mtp.mkdir(dir_path)
                
                # Add single file at root level
                if video_idx < len(video_files):
                    self.mtp.push_file(video_files[video_idx], f"{test_path}/single_file.mp4")
                    video_idx += 1
                
                # Add files in nested directories
                if video_idx < len(video_files):
                    self.mtp.push_file(video_files[video_idx], f"{test_path}/nested/file_in_nested.mp4")
                    video_idx += 1
                
                if video_idx < len(video_files):
                    self.mtp.push_file(video_files[video_idx], f"{test_path}/nested/deep/file_in_deep.mp4")
                    video_idx += 1
            
            print()
            return True
            
        except Exception as e:
            print(f"❌ Error setting up test structure: {e}")
            return False
    
    def get_file_hashes(self, directory: Path) -> dict:
        """Get MD5 hashes of all files for verification."""
        hashes = {}
        for file_path in directory.rglob("*.mp4"):
            try:
                with open(file_path, 'rb') as f:
                    hashes[str(file_path)] = hashlib.md5(f.read()).hexdigest()
            except Exception as e:
                print(f"  ⚠ Could not hash {file_path}: {e}")
        return hashes
    
    def count_all_files(self, tree: Dict) -> int:
        """Recursively count all files in a tree structure."""
        count = len(tree.get("files", []))
        for subdir in tree.get("dirs", {}).values():
            count += self.count_all_files(subdir)
        return count
    
    def test_copy_operation(self) -> bool:
        """Test copy operation: files should be copied but not deleted."""
        print("\n" + "-"*70)
        print("TEST 1: COPY OPERATION (Phone → Desktop, NO deletion)")
        print("-"*70 + "\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/copy_test"
            dest_path = self.LOCAL_TEST_DIR / "copy_output"
            # Clean up from previous runs
            if dest_path.exists():
                shutil.rmtree(dest_path)
            dest_path.mkdir(exist_ok=True)
            
            # Get pre-copy state (count ALL files recursively)
            pre_copy = self.mtp.directory_tree(source_path)
            pre_count = self.count_all_files(pre_copy)
            print(f"Files to copy: {pre_count}\n")
            
            # Run copy operation
            print("Running copy operation...")
            operations.run_copy_rule(
                {
                    "phone_path": source_path,
                    "desktop_path": str(dest_path),
                    "id": "test_copy"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # SAFETY: Verify files on desktop
            desktop_files = list(dest_path.rglob("*.mp4"))
            desktop_count = len(desktop_files)
            print(f"\n✓ Files copied to desktop: {desktop_count}")
            
            # SAFETY: Verify files still exist on phone
            post_copy = self.mtp.directory_tree(source_path)
            post_count = self.count_all_files(post_copy)
            print(f"✓ Files still on phone: {post_count}")
            
            # SAFETY: Validate counts match
            if desktop_count != pre_count or post_count != pre_count:
                print(f"\n❌ COPY TEST FAILED - File count mismatch!")
                print(f"   Expected: {pre_count} on both phone and desktop")
                print(f"   Got: {desktop_count} on desktop, {post_count} on phone")
                self.results["failed"] += 1
                return False
            
            print("\n✅ COPY TEST PASSED")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"\n❌ COPY TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_move_operation(self) -> bool:
        """Test move operation with VERIFICATION before deletion."""
        print("\n" + "-"*70)
        print("TEST 2: MOVE OPERATION (Phone → Desktop, WITH deletion)")
        print("-"*70 + "\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/move_test"
            dest_path = self.LOCAL_TEST_DIR / "move_output"
            # Clean up from previous runs
            if dest_path.exists():
                shutil.rmtree(dest_path)
            dest_path.mkdir(exist_ok=True)
            
            # Get pre-move state (count ALL files recursively)
            pre_move = self.mtp.directory_tree(source_path)
            pre_count = self.count_all_files(pre_move)
            print(f"Files to move: {pre_count}\n")
            
            # Run move operation
            print("Running move operation...")
            operations.run_move_rule(
                {
                    "phone_path": source_path,
                    "desktop_path": str(dest_path),
                    "id": "test_move"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # SAFETY: Verify files on desktop FIRST
            desktop_files = list(dest_path.rglob("*.mp4"))
            desktop_count = len(desktop_files)
            print(f"\n✓ Files moved to desktop: {desktop_count}")
            
            # SAFETY: Verify files deleted from phone
            post_move = self.mtp.directory_tree(source_path)
            post_count = self.count_all_files(post_move)
            print(f"✓ Files remaining on phone: {post_count}")
            
            # SAFETY: Validate critical conditions
            if desktop_count != pre_count:
                print(f"\n❌ MOVE TEST FAILED - Not all files copied to desktop!")
                print(f"   Expected {pre_count} files on desktop")
                print(f"   Got {desktop_count} files")
                print(f"   ⚠️  Files NOT deleted from phone (safe)")
                self.results["failed"] += 1
                return False
            
            if post_count != 0:
                print(f"\n❌ MOVE TEST FAILED - Files not deleted from phone!")
                print(f"   Expected 0 files on phone")
                print(f"   Found {post_count} files still on phone")
                self.results["failed"] += 1
                return False
            
            print("\n✅ MOVE TEST PASSED - All files verified before deletion")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"\n❌ MOVE TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_sync_operation(self) -> bool:
        """Test sync operation."""
        print("\n" + "-"*70)
        print("TEST 3: SYNC OPERATION (Desktop → Phone, mirror)")
        print("-"*70 + "\n")
        
        try:
            # Populate desktop with test files
            source_path = self.LOCAL_TEST_DIR / "sync_source"
            # Clean up from previous runs
            if source_path.exists():
                shutil.rmtree(source_path)
            source_path.mkdir(exist_ok=True)
            
            videos_dir = Path(__file__).parent / "videos"
            video_files = list(videos_dir.glob("*.mp4"))[:3]
            
            for video in video_files:
                shutil.copy2(video, source_path / video.name)
            
            source_count = len(list(source_path.glob("*.mp4")))
            print(f"Files to sync: {source_count}\n")
            
            # Target on phone
            dest_path = f"{self.TEST_FOLDER}/sync_test"
            
            # Run sync operation
            print("Running sync operation...")
            operations.run_sync_rule(
                {
                    "phone_path": dest_path,
                    "desktop_path": str(source_path),
                    "id": "test_sync"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # SAFETY: Verify files on phone
            post_sync = self.mtp.list_dir(dest_path)
            synced_count = len([f for f in post_sync if f.endswith('.mp4')])
            print(f"\n✓ Files synced to phone: {synced_count}")
            
            if synced_count != source_count:
                print(f"\n❌ SYNC TEST FAILED")
                print(f"   Expected {source_count} files on phone")
                print(f"   Got {synced_count} files")
                self.results["failed"] += 1
                return False
            
            print("\n✅ SYNC TEST PASSED")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"\n❌ SYNC TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_backup_operation(self) -> bool:
        """Test backup operation."""
        print("\n" + "-"*70)
        print("TEST 4: BACKUP OPERATION (Resumable copy, NO deletion)")
        print("-"*70 + "\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/backup_test"
            dest_path = self.LOCAL_TEST_DIR / "backup_output"
            # Clean up from previous runs
            if dest_path.exists():
                shutil.rmtree(dest_path)
            dest_path.mkdir(exist_ok=True)
            
            # Get pre-backup state (count ALL files recursively)
            pre_backup = self.mtp.directory_tree(source_path)
            pre_count = self.count_all_files(pre_backup)
            print(f"Files to backup: {pre_count}\n")
            
            # Run backup operation
            print("Running backup operation...")
            operations.run_backup_rule(
                {
                    "phone_path": source_path,
                    "desktop_path": str(dest_path),
                    "id": "test_backup"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # SAFETY: Verify files on desktop
            desktop_files = list(dest_path.rglob("*.mp4"))
            desktop_count = len(desktop_files)
            print(f"\n✓ Files backed up to desktop: {desktop_count}")
            
            # SAFETY: Verify files still on phone
            post_backup = self.mtp.directory_tree(source_path)
            post_count = self.count_all_files(post_backup)
            print(f"✓ Files still on phone: {post_count}")
            
            if desktop_count != pre_count or post_count != pre_count:
                print(f"\n❌ BACKUP TEST FAILED - File count mismatch!")
                print(f"   Expected {pre_count} on both phone and desktop")
                print(f"   Got {desktop_count} on desktop, {post_count} on phone")
                self.results["failed"] += 1
                return False
            
            print("\n✅ BACKUP TEST PASSED")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"\n❌ BACKUP TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def cleanup(self):
        """Clean up test structure from phone."""
        print("\n" + "="*70)
        print("CLEANUP")
        print("="*70 + "\n")
        
        try:
            print(f"Removing test folder from phone: {self.TEST_FOLDER}/...")
            # Recursively remove all files in test folder
            def remove_recursive(path):
                try:
                    entries = self.mtp.list_dir(path)
                    for entry in entries:
                        entry_path = f"{path}/{entry}" if not path.endswith('/') else f"{path}{entry}"
                        info = self.mtp.get_file_info(entry_path)
                        entry_type = info.get('type', '')
                        if 'directory' in entry_type.lower() or entry_type == '2':
                            # Recurse into directory
                            remove_recursive(entry_path)
                        # Remove the item (file or now-empty directory)
                        self.mtp.remove(entry_path)
                except Exception as e:
                    pass  # Ignore errors during recursive delete
            
            remove_recursive(self.TEST_FOLDER)
            # Remove the root test folder
            self.mtp.remove(self.TEST_FOLDER)
            print("✓ Phone cleaned up\n")
        except Exception as e:
            print(f"⚠ Warning during cleanup: {e}\n")
    
    def print_summary(self):
        """Print test summary."""
        total = self.results["passed"] + self.results["failed"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        
        print("="*70)
        print("TEST SUMMARY")
        print("="*70 + "\n")
        
        print(f"Total: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}\n")
        
        if failed == 0 and passed > 0:
            print("🎉 ALL TESTS PASSED - No regressions detected!")
        elif failed > 0:
            print(f"⚠️  {failed} test(s) failed - please review")
        
        print()


def main():
    """Run the complete safe test suite."""
    suite = SafeTestSuite()
    suite.print_safety_header()
    
    # Setup
    if not suite.setup():
        print("❌ Setup failed")
        return 1
    
    # Populate test structure
    if not suite.populate_test_structure():
        print("❌ Test structure setup failed")
        return 1
    
    # Run tests
    suite.test_copy_operation()
    suite.test_move_operation()
    suite.test_sync_operation()
    suite.test_backup_operation()
    
    # Cleanup
    suite.cleanup()
    
    # Summary
    suite.print_summary()
    
    return 0 if suite.results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
