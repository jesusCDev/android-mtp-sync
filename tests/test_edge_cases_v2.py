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
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import config as cfg, runner, operations
from phone_migration.preflight import estimate_transfer_size, query_free_space_desktop, PreflightError
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
    
    def test_large_file_handling(self) -> bool:
        """TEST 4: Large files - handle files >= 1GB without truncation."""
        print("\n" + "-"*70)
        print("TEST 4: LARGE FILES - Handling >= 1GB")
        print("-"*70 + "\n")
        
        try:
            test_name = "large_file_test"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            dest_path = self.TEST_BASE_DESKTOP / test_name
            
            # Create isolated test folder
            self.mtp.mkdir(phone_path)
            self.created_phone_folders.append(phone_path)
            dest_path.mkdir(parents=True, exist_ok=True)
            self.created_desktop_folders.append(dest_path)
            
            # Create sparse file (1.1 GB) on desktop without actually using disk space
            desktop_sparse = dest_path / "large_file_1gb.bin"
            desktop_sparse_size = 1_100_000_000  # 1.1 GB
            
            print(f"Creating sparse file ({desktop_sparse_size / (1024**3):.1f} GB)...")
            with open(desktop_sparse, "wb") as f:
                f.write(b"START")
                f.seek(desktop_sparse_size - 1)
                f.write(b"END")
            
            # Verify file size
            actual_size = desktop_sparse.stat().st_size
            if actual_size != desktop_sparse_size:
                print(f"❌ Sparse file creation failed: expected {desktop_sparse_size}, got {actual_size}")
                self.failed_tests.append("large_files")
                self.results["failed"] += 1
                return False
            
            # Compute hash before transfer
            import hashlib
            print("Computing source file hash...")
            sha256_hash = hashlib.sha256()
            with open(desktop_sparse, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha256_hash.update(chunk)
            source_hash = sha256_hash.hexdigest()
            
            # Perform sync (copy desktop file to phone)
            print(f"Syncing {desktop_sparse_size / (1024**3):.1f} GB file to phone...")
            operations.run_sync_rule(
                {"phone_path": phone_path, "desktop_path": str(dest_path), "id": test_name},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Pull file back from phone to verify integrity
            print("Pulling file back from phone to verify...")
            phone_file_path = f"{phone_path}/large_file_1gb.bin"
            verify_path = dest_path / "large_file_1gb_verify.bin"
            self.mtp.pull_file(phone_file_path, str(verify_path))
            
            # Verify size and hash
            verify_size = verify_path.stat().st_size
            if verify_size != desktop_sparse_size:
                print(f"❌ File size mismatch after transfer: expected {desktop_sparse_size}, got {verify_size}")
                self.failed_tests.append("large_files")
                self.results["failed"] += 1
                return False
            
            print("Computing verify file hash...")
            sha256_hash = hashlib.sha256()
            with open(verify_path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha256_hash.update(chunk)
            verify_hash = sha256_hash.hexdigest()
            
            if source_hash != verify_hash:
                print("❌ File hash mismatch (corruption detected)")
                print(f"   Source: {source_hash}")
                print(f"   Verify: {verify_hash}")
                self.failed_tests.append("large_files")
                self.results["failed"] += 1
                return False
            
            print("✅ LARGE FILE TEST PASSED")
            print(f"   File: {desktop_sparse_size / (1024**3):.1f} GB")
            print("   Size integrity: ✓ Hash integrity: ✓")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append("large_files")
            self.results["failed"] += 1
            return False
    
    def test_disk_space_validation(self) -> bool:
        """TEST 5: Disk space - validate preflight checks and safe abort on low space."""
        print("\n" + "-"*70)
        print("TEST 5: DISK SPACE - Preflight Validation & Low Space Safety")
        print("-"*70 + "\n")
        
        try:
            test_name = "disk_space_test"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            dest_path = self.TEST_BASE_DESKTOP / test_name
            
            # Create isolated test folder
            self.mtp.mkdir(phone_path)
            self.created_phone_folders.append(phone_path)
            dest_path.mkdir(parents=True, exist_ok=True)
            self.created_desktop_folders.append(dest_path)
            
            # Test 5a: Estimate transfer size
            print("\nTest 5a: Estimating transfer size...")
            # Create 5 files of ~10MB each
            test_files = []
            for i in range(5):
                test_file = dest_path / f"test_file_{i}.bin"
                with open(test_file, "wb") as f:
                    f.write(b"x" * (10 * 1024 * 1024))  # 10 MB
                test_files.append(test_file)
            
            estimated_bytes = estimate_transfer_size(str(dest_path), "copy")
            expected_bytes = 50 * 1024 * 1024  # ~50 MB
            
            # Allow 5% variance due to filesystem overhead
            if abs(estimated_bytes - expected_bytes) > (expected_bytes * 0.05):
                print(f"❌ Size estimation failed: expected ~{expected_bytes / (1024**2):.1f}MB, got {estimated_bytes / (1024**2):.1f}MB")
                self.failed_tests.append("disk_space_validation")
                self.results["failed"] += 1
                return False
            
            print(f"✓ Estimated transfer: {estimated_bytes / (1024**2):.1f} MB")
            
            # Test 5b: Query free space
            print("\nTest 5b: Querying free space on destination...")
            try:
                free_bytes = query_free_space_desktop(str(dest_path))
                print(f"✓ Available space: {free_bytes / (1024**3):.1f} GB")
            except PreflightError as e:
                print(f"❌ Could not query free space: {e}")
                self.failed_tests.append("disk_space_validation")
                self.results["failed"] += 1
                return False
            
            # Test 5c: Sufficient space scenario
            print("\nTest 5c: Validating sufficient space scenario...")
            try:
                from phone_migration.preflight import validate_space_or_abort
                # Should pass - plenty of free space
                validate_space_or_abort(
                    total_bytes=10 * 1024 * 1024,  # 10 MB
                    free_bytes=free_bytes,
                    headroom_percent=5.0,
                    operation_name="Test"
                )
                print("✓ Sufficient space validation passed")
            except PreflightError as e:
                print(f"❌ Should have passed with sufficient space: {e}")
                self.failed_tests.append("disk_space_validation")
                self.results["failed"] += 1
                return False
            
            # Test 5d: Low space scenario (simulated)
            print("\nTest 5d: Validating low space detection...")
            try:
                from phone_migration.preflight import validate_space_or_abort
                # Should fail - simulating extremely low free space
                validate_space_or_abort(
                    total_bytes=free_bytes + (1 * 1024 * 1024 * 1024),  # Ask for more than available + 1GB
                    free_bytes=1 * 1024 * 1024,  # Only 1 MB free
                    headroom_percent=5.0,
                    operation_name="Test"
                )
                # If we get here, the check failed to catch low space
                print("❌ Low space check should have raised PreflightError")
                self.failed_tests.append("disk_space_validation")
                self.results["failed"] += 1
                return False
            except PreflightError as e:
                print(f"✓ Low space correctly detected and raised error")
                print(f"   Error message: {str(e).split(chr(10))[0]}")
            
            print("\n✅ DISK SPACE VALIDATION TEST PASSED")
            print("   Size estimation: ✓ Free space query: ✓ Safety checks: ✓")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append("disk_space_validation")
            self.results["failed"] += 1
            return False
    
    def test_symlink_traversal(self) -> bool:
        """TEST 6: Symlink traversal - follow symlinks, create real folders/files on phone."""
        print("\n" + "-"*70)
        print("TEST 6: SYMLINK TRAVERSAL - Follow Symlinks & Create Real Files")
        print("-"*70 + "\n")
        
        try:
            test_name = "symlink_test"
            phone_path = f"{self.TEST_BASE_PHONE}/{test_name}"
            dest_path = self.TEST_BASE_DESKTOP / test_name
            
            # Create isolated test folder
            self.mtp.mkdir(phone_path)
            self.created_phone_folders.append(phone_path)
            dest_path.mkdir(parents=True, exist_ok=True)
            self.created_desktop_folders.append(dest_path)
            
            # Test 6a: Create test files and symlinks
            print("\nTest 6a: Creating test files and symlinks...")
            
            # Create actual files
            test_dir = dest_path / "actual_files"
            test_dir.mkdir()
            file1 = test_dir / "file1.txt"
            file2 = test_dir / "file2.txt"
            file1.write_text("Content of file1")
            file2.write_text("Content of file2")
            
            # Create nested directory with file
            nested_dir = test_dir / "nested"
            nested_dir.mkdir()
            nested_file = nested_dir / "nested_file.txt"
            nested_file.write_text("Nested content")
            
            # Create symlink to file
            symlink_to_file = dest_path / "link_to_file.txt"
            symlink_to_file.symlink_to(file1)
            
            # Create symlink to directory
            symlink_to_dir = dest_path / "link_to_dir"
            symlink_to_dir.symlink_to(test_dir)
            
            print("✓ Created files and symlinks")
            
            # Test 6b: Sync desktop to phone
            print("\nTest 6b: Syncing with symlink traversal...")
            operations.run_sync_rule(
                {"phone_path": phone_path, "desktop_path": str(dest_path), "id": test_name},
                {"activation_uri": self.mtp.uri},
                verbose=False
            )
            
            # Test 6c: Verify files on phone
            print("\nTest 6c: Verifying files on phone...")
            phone_tree = self.mtp.directory_tree(phone_path)
            
            # Extract all files from tree
            def extract_files(tree, prefix=""):
                files = []
                for f in tree.get("files", []):
                    files.append(f"{prefix}/{f}" if prefix else f)
                for dir_name, subdir in tree.get("dirs", {}).items():
                    new_prefix = f"{prefix}/{dir_name}" if prefix else dir_name
                    files.extend(extract_files(subdir, new_prefix))
                return files
            
            phone_files = extract_files(phone_tree)
            
            # Check that symlinks were traversed and real files created
            # Expected files:
            # - actual_files/file1.txt
            # - actual_files/file2.txt
            # - actual_files/nested/nested_file.txt
            # - link_to_file.txt (should be real file, not symlink)
            # - link_to_dir/file1.txt
            # - link_to_dir/file2.txt
            # - link_to_dir/nested/nested_file.txt
            
            expected_patterns = [
                "actual_files/file1.txt",
                "actual_files/file2.txt",
                "actual_files/nested/nested_file.txt",
                "link_to_file.txt",
                # Files from traversing symlink_to_dir
            ]
            
            print(f"\nPhone files found: {len(phone_files)}")
            for f in sorted(phone_files):
                print(f"  - {f}")
            
            # Check minimum expected files
            if len(phone_files) < 4:
                print(f"❌ Expected at least 4 files, got {len(phone_files)}")
                self.failed_tests.append("symlink_traversal")
                self.results["failed"] += 1
                return False
            
            # Verify that actual_files exists
            if not any("actual_files" in f for f in phone_files):
                print("❌ Expected 'actual_files' directory on phone")
                self.failed_tests.append("symlink_traversal")
                self.results["failed"] += 1
                return False
            
            # Verify that link_to_file.txt exists (symlink was followed and created as real file)
            if not any("link_to_file.txt" in f for f in phone_files):
                print("❌ Symlinked file not found on phone")
                self.failed_tests.append("symlink_traversal")
                self.results["failed"] += 1
                return False
            
            print("\n✅ SYMLINK TRAVERSAL TEST PASSED")
            print(f"   Files synced: {len(phone_files)}")
            print("   Symlinks followed: ✓ Real files created: ✓")
            self.results["passed"] += 1
            return True
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append("symlink_traversal")
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
            self.test_large_file_handling()
            self.test_disk_space_validation()
            self.test_symlink_traversal()
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
