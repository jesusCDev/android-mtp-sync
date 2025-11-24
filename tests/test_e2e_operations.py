"""End-to-end tests for migration operations (copy, move, sync, backup)."""

import sys
from pathlib import Path
import shutil
import subprocess

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import config as cfg, runner, operations, device as phone_device
from tests.helpers.mtp_testlib import MTPDevice, compare_trees


class TestSuite:
    """Main test suite for migration operations."""
    
    # Test configuration
    TEST_FOLDER = "test-android-mtp"
    LOCAL_TEST_DIR = Path.home() / ".local" / "share" / "phone_migration_tests"
    
    def __init__(self):
        """Initialize test suite."""
        self.device = None
        self.mtp = None
        self.test_profile = None
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
    
    def setup(self) -> bool:
        """Setup test environment."""
        print("\n" + "="*70)
        print("PHONE MIGRATION - END-TO-END TEST SUITE")
        print("="*70 + "\n")
        
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
        print(f"  URI: {activation_uri}\n")
        
        # Initialize MTP device wrapper
        self.mtp = MTPDevice(activation_uri)
        
        # Create local test directories
        self.LOCAL_TEST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✓ Local test directory: {self.LOCAL_TEST_DIR}\n")
        
        return True
    
    def populate_test_structure(self) -> bool:
        """Create test folder structure on phone and populate with files."""
        print("Setting up test folder structure on phone...\n")
        
        try:
            # Create main test folder
            self.mtp.mkdir(self.TEST_FOLDER)
            print(f"✓ Created {self.TEST_FOLDER}/")
            
            # Define test cases
            test_cases = {
                "copy_test": ["single_file", "nested/deep", "empty_folder"],
                "move_test": ["single_file", "nested/deep", "empty_folder"],
                "sync_test": ["single_file", "nested/deep"],
                "backup_test": ["single_file", "nested/deep", "empty_folder"],
            }
            
            # Get test videos
            videos_dir = Path(__file__).parent / "videos"
            if not videos_dir.exists():
                print(f"⚠ Test videos directory not found: {videos_dir}")
                return False
            
            video_files = list(videos_dir.glob("*.mp4"))
            if not video_files:
                print(f"⚠ No test videos found in {videos_dir}")
                return False
            
            print(f"✓ Found {len(video_files)} test videos\n")
            
            # Populate each test case
            video_idx = 0
            for test_case, subdirs in test_cases.items():
                test_path = f"{self.TEST_FOLDER}/{test_case}"
                self.mtp.mkdir(test_path)
                print(f"  {test_case}/")
                
                # Create subdirectories
                for subdir in subdirs:
                    dir_path = f"{test_path}/{subdir}"
                    self.mtp.mkdir(dir_path)
                    print(f"    └── {subdir}/")
                
                # Add single file at root level
                if video_idx < len(video_files):
                    self.mtp.push_file(video_files[video_idx], f"{test_path}/single_file.mp4")
                    print(f"      └── single_file.mp4")
                    video_idx += 1
                
                # Add files in nested directories
                for subdir in ["nested", "nested/deep"]:
                    if video_idx < len(video_files):
                        filename = f"file_in_{subdir.replace('/', '_')}.mp4"
                        self.mtp.push_file(video_files[video_idx], f"{test_path}/{subdir}/{filename}")
                        print(f"        └── {filename}")
                        video_idx += 1
            
            print()
            return True
            
        except Exception as e:
            print(f"❌ Error setting up test structure: {e}")
            return False
    
    def verify_file_exists(self, phone_path: str, description: str = "") -> bool:
        """Verify file exists on phone."""
        exists = self.mtp.path_exists(phone_path)
        status = "✓" if exists else "✗"
        desc = f" ({description})" if description else ""
        print(f"  {status} {phone_path}{desc}")
        return exists
    
    def test_copy_operation(self) -> bool:
        """Test copy operation: files should be copied but not deleted."""
        print("\n" + "-"*70)
        print("TEST 1: COPY OPERATION")
        print("-"*70)
        print("Expected: Files copied from phone to desktop, NOT deleted from phone\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/copy_test"
            dest_path = self.LOCAL_TEST_DIR / "copy_output"
            dest_path.mkdir(exist_ok=True)
            
            print(f"Source (phone): {source_path}")
            print(f"Destination (desktop): {dest_path}\n")
            
            # Get pre-copy state
            pre_copy = self.mtp.directory_tree(source_path)
            pre_files = pre_copy.get("files", [])
            pre_count = len(pre_files)
            
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
            
            # Verify files on desktop
            desktop_files = list(dest_path.rglob("*.mp4"))
            print(f"\n✓ Copied {len(desktop_files)} files to desktop")
            
            # Verify files still on phone
            post_copy = self.mtp.directory_tree(source_path)
            post_files = post_copy.get("files", [])
            post_count = len(post_files)
            
            print(f"✓ Files still on phone: {post_count}")
            
            # Check results
            if len(desktop_files) == pre_count and post_count == pre_count:
                print("\n✅ COPY TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"\n❌ COPY TEST FAILED")
                print(f"   Expected {pre_count} files on both phone and desktop")
                print(f"   Got {len(desktop_files)} on desktop, {post_count} on phone")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"\n❌ COPY TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_move_operation(self) -> bool:
        """Test move operation: files should be copied AND deleted."""
        print("\n" + "-"*70)
        print("TEST 2: MOVE OPERATION")
        print("-"*70)
        print("Expected: Files moved from phone to desktop, DELETED from phone\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/move_test"
            dest_path = self.LOCAL_TEST_DIR / "move_output"
            dest_path.mkdir(exist_ok=True)
            
            print(f"Source (phone): {source_path}")
            print(f"Destination (desktop): {dest_path}\n")
            
            # Get pre-move state
            pre_move = self.mtp.directory_tree(source_path)
            pre_count = len(pre_move.get("files", []))
            
            print(f"Files to move: {pre_count}\n")
            print("Running move operation...")
            
            # Run move operation
            operations.run_move_rule(
                {
                    "phone_path": source_path,
                    "desktop_path": str(dest_path),
                    "id": "test_move"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Verify files on desktop
            desktop_files = list(dest_path.rglob("*.mp4"))
            print(f"\n✓ Moved {len(desktop_files)} files to desktop")
            
            # Verify files deleted from phone
            post_move = self.mtp.directory_tree(source_path)
            post_count = len(post_move.get("files", []))
            
            print(f"✓ Files remaining on phone: {post_count}")
            
            # Check results
            if len(desktop_files) == pre_count and post_count == 0:
                print("\n✅ MOVE TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"\n❌ MOVE TEST FAILED")
                print(f"   Expected {pre_count} files on desktop, 0 on phone")
                print(f"   Got {len(desktop_files)} on desktop, {post_count} on phone")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"\n❌ MOVE TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_sync_operation(self) -> bool:
        """Test sync operation: mirrors desktop to phone."""
        print("\n" + "-"*70)
        print("TEST 3: SYNC OPERATION (Desktop → Phone)")
        print("-"*70)
        print("Expected: Files from desktop synced to phone\n")
        
        try:
            # First populate desktop with test files
            source_path = self.LOCAL_TEST_DIR / "sync_source"
            source_path.mkdir(exist_ok=True)
            
            # Copy some test videos to source
            videos_dir = Path(__file__).parent / "videos"
            video_files = list(videos_dir.glob("*.mp4"))[:3]
            
            for video in video_files:
                shutil.copy2(video, source_path / video.name)
            
            print(f"Source (desktop): {source_path}")
            print(f"Files to sync: {len(list(source_path.glob('*.mp4')))}\n")
            
            # Target on phone
            dest_path = f"{self.TEST_FOLDER}/sync_test"
            
            print("Running sync operation...")
            print(f"Target (phone): {dest_path}\n")
            
            # Run sync operation
            operations.run_sync_rule(
                {
                    "phone_path": dest_path,
                    "desktop_path": str(source_path),
                    "id": "test_sync"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Verify files on phone
            post_sync = self.mtp.list_dir(dest_path)
            synced_count = len([f for f in post_sync if f.endswith('.mp4')])
            
            print(f"\n✓ Synced {synced_count} files to phone")
            
            if synced_count == len(video_files):
                print("\n✅ SYNC TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"\n❌ SYNC TEST FAILED")
                print(f"   Expected {len(video_files)} files on phone")
                print(f"   Got {synced_count} files")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"\n❌ SYNC TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def test_backup_operation(self) -> bool:
        """Test backup operation: resumable copy."""
        print("\n" + "-"*70)
        print("TEST 4: BACKUP OPERATION (Resumable Copy)")
        print("-"*70)
        print("Expected: Files backed up from phone to desktop, resumable\n")
        
        try:
            source_path = f"{self.TEST_FOLDER}/backup_test"
            dest_path = self.LOCAL_TEST_DIR / "backup_output"
            dest_path.mkdir(exist_ok=True)
            
            print(f"Source (phone): {source_path}")
            print(f"Destination (desktop): {dest_path}\n")
            
            # Get files to backup
            pre_backup = self.mtp.directory_tree(source_path)
            pre_count = len(pre_backup.get("files", []))
            
            print(f"Files to backup: {pre_count}\n")
            print("Running backup operation...")
            
            # Run backup operation
            operations.run_backup_rule(
                {
                    "phone_path": source_path,
                    "desktop_path": str(dest_path),
                    "id": "test_backup"
                },
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Verify files on desktop
            desktop_files = list(dest_path.rglob("*.mp4"))
            print(f"\n✓ Backed up {len(desktop_files)} files")
            
            # Verify files still on phone (backup doesn't delete)
            post_backup = self.mtp.directory_tree(source_path)
            post_count = len(post_backup.get("files", []))
            
            print(f"✓ Files still on phone: {post_count}")
            
            if len(desktop_files) == pre_count and post_count == pre_count:
                print("\n✅ BACKUP TEST PASSED")
                self.results["passed"] += 1
                return True
            else:
                print(f"\n❌ BACKUP TEST FAILED")
                print(f"   Expected {pre_count} files on both")
                print(f"   Got {len(desktop_files)} on desktop, {post_count} on phone")
                self.results["failed"] += 1
                return False
        
        except Exception as e:
            print(f"\n❌ BACKUP TEST ERROR: {e}")
            self.results["failed"] += 1
            return False
    
    def cleanup(self):
        """Clean up test structure."""
        print("\n" + "="*70)
        print("CLEANUP")
        print("="*70 + "\n")
        
        try:
            print(f"Removing test folder from phone: {self.TEST_FOLDER}...")
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
        
        print(f"Total tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⊘ Skipped: {self.results['skipped']}\n")
        
        if failed == 0 and passed > 0:
            print("🎉 ALL TESTS PASSED!")
        elif failed > 0:
            print(f"⚠ {failed} test(s) failed")
        
        print()


def main():
    """Run the complete test suite."""
    suite = TestSuite()
    
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
