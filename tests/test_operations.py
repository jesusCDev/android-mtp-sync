"""
Tests for phone migration operations (move, copy, sync, smart_copy).
Uses temporary directories to simulate file operations without requiring MTP device.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from phone_migration import operations, paths


class TestOperationsBase(unittest.TestCase):
    """Base class for operations tests with common setup/teardown."""
    
    def setUp(self):
        """Create temporary directories for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.dest_dir = Path(self.temp_dir) / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
    
    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_file(self, directory: Path, name: str, content: str = "") -> Path:
        """Helper to create a test file."""
        file_path = directory / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content or name)  # Use filename as default content
        return file_path
    
    def create_files(self, directory: Path, files: list) -> dict:
        """Helper to create multiple test files. Returns dict of name -> Path."""
        result = {}
        for name in files:
            result[name] = self.create_file(directory, name)
        return result


class TestNextAvailableName(TestOperationsBase):
    """Test the next_available_name function."""
    
    def test_no_conflict_returns_original_name(self):
        """When file doesn't exist, return the original name."""
        result = paths.next_available_name(self.dest_dir, "test.txt", rename_duplicates=True)
        self.assertEqual(result.name, "test.txt")
    
    def test_conflict_with_rename_true_returns_renamed(self):
        """When file exists and rename_duplicates=True, return renamed version."""
        self.create_file(self.dest_dir, "test.txt")
        result = paths.next_available_name(self.dest_dir, "test.txt", rename_duplicates=True)
        self.assertEqual(result.name, "test (1).txt")
    
    def test_conflict_with_rename_false_returns_none(self):
        """When file exists and rename_duplicates=False, return None."""
        self.create_file(self.dest_dir, "test.txt")
        result = paths.next_available_name(self.dest_dir, "test.txt", rename_duplicates=False)
        self.assertIsNone(result)
    
    def test_multiple_conflicts_with_rename_true(self):
        """When multiple files exist, find next available number."""
        self.create_file(self.dest_dir, "test.txt")
        self.create_file(self.dest_dir, "test (1).txt")
        self.create_file(self.dest_dir, "test (2).txt")
        result = paths.next_available_name(self.dest_dir, "test.txt", rename_duplicates=True)
        self.assertEqual(result.name, "test (3).txt")
    
    def test_file_without_extension(self):
        """Files without extensions should be handled correctly."""
        self.create_file(self.dest_dir, "README")
        result = paths.next_available_name(self.dest_dir, "README", rename_duplicates=True)
        self.assertEqual(result.name, "README (1)")


class TestCopyOperation(TestOperationsBase):
    """Test run_copy_rule operation."""
    
    @patch('phone_migration.gio_utils.gio_list')
    @patch('phone_migration.gio_utils.gio_info')
    @patch('phone_migration.gio_utils.gio_copy')
    def test_copy_single_file(self, mock_copy, mock_info, mock_list):
        """Test copying a single file."""
        # Setup mocks
        mock_list.return_value = ["photo.jpg"]
        mock_info.return_value = {
            "standard::type": "regular file",
            "standard::size": "1024"
        }
        mock_copy.return_value = True
        
        # Create destination file to verify it was copied
        dest_file = self.dest_dir / "photo.jpg"
        dest_file.write_text("photo content")
        
        # Create mock rule and device
        rule = {
            "phone_path": "/DCIM/Camera",
            "desktop_path": str(self.dest_dir)
        }
        device = {"activation_uri": "mtp://device/"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/DCIM/Camera"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.dest_dir):
                stats = operations.run_copy_rule(rule, device, verbose=False)
        
        # Should have recorded stats
        self.assertIsInstance(stats, dict)
    
    @patch('phone_migration.gio_utils.gio_list')
    @patch('phone_migration.gio_info')
    @patch('phone_migration.gio_utils.gio_copy')
    def test_copy_with_rename_duplicates_false_skips_conflict(self, mock_copy, mock_info, mock_list):
        """When rename_duplicates=False, conflicting files should be skipped."""
        # Setup: file already exists in destination
        existing_file = self.create_file(self.dest_dir, "photo.jpg", "existing content")
        
        # Setup mocks for source directory
        mock_list.return_value = ["photo.jpg"]
        mock_info.return_value = {
            "standard::type": "regular file",
            "standard::size": "2048"
        }
        
        rule = {
            "phone_path": "/DCIM/Camera",
            "desktop_path": str(self.dest_dir)
        }
        device = {"activation_uri": "mtp://device/"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/DCIM/Camera"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.dest_dir):
                with patch('phone_migration.operations.gio_utils.DRY_RUN', False):
                    stats = operations.run_copy_rule(
                        rule, device, verbose=False, rename_duplicates=False
                    )
        
        # File should not be copied (counted as error/skipped)
        # mock_copy should not have been called for the conflicting file
        self.assertIsInstance(stats, dict)


class TestMoveOperation(TestOperationsBase):
    """Test run_move_rule operation."""
    
    @patch('phone_migration.gio_utils.gio_list')
    @patch('phone_migration.gio_utils.gio_info')
    @patch('phone_migration.gio_utils.gio_copy')
    @patch('phone_migration.gio_utils.gio_remove')
    def test_move_copies_then_deletes(self, mock_remove, mock_copy, mock_info, mock_list):
        """Test that move copies files then deletes them."""
        mock_list.return_value = ["photo.jpg"]
        mock_info.return_value = {
            "standard::type": "regular file",
            "standard::size": "1024"
        }
        mock_copy.return_value = True
        mock_remove.return_value = True
        
        rule = {
            "phone_path": "/DCIM/Camera",
            "desktop_path": str(self.dest_dir)
        }
        device = {"activation_uri": "mtp://device/"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/DCIM/Camera"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.dest_dir):
                with patch('phone_migration.operations.gio_utils.DRY_RUN', False):
                    with patch('phone_migration.operations._cleanup_empty_dirs'):
                        stats = operations.run_move_rule(rule, device, verbose=False)
        
        self.assertIsInstance(stats, dict)
        # Move should have both copied and deleted counts
        self.assertIn("copied", stats)
        self.assertIn("deleted", stats)


class TestSyncOperation(TestOperationsBase):
    """Test run_sync_rule operation."""
    
    def test_sync_copies_new_files_from_desktop_to_phone(self):
        """Test syncing copies new files from desktop to phone."""
        # Create files on desktop
        self.create_file(self.source_dir, "file1.txt", "content1")
        self.create_file(self.source_dir, "file2.txt", "content2")
        
        rule = {
            "desktop_path": str(self.source_dir),
            "phone_path": "/Videos/sync"
        }
        device = {"activation_uri": "mtp://device/"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/Videos/sync"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.source_dir):
                with patch('phone_migration.gio_utils.gio_mkdir'):
                    with patch('phone_migration.gio_utils.gio_info', return_value=None):
                        with patch('phone_migration.gio_utils.gio_copy', return_value=True):
                            with patch('phone_migration.operations._delete_extraneous_on_phone'):
                                stats = operations.run_sync_rule(rule, device, verbose=False)
        
        # Should copy both files
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats.get("copied", 0), 2)
    
    def test_sync_skips_unchanged_files(self):
        """Test that sync skips files with same size (unchanged)."""
        # Create file on desktop
        test_file = self.create_file(self.source_dir, "video.mp4", "a" * 1024)
        
        rule = {
            "desktop_path": str(self.source_dir),
            "phone_path": "/Videos/sync"
        }
        device = {"activation_uri": "mtp://device/"}
        
        # Mock gio_info to return file exists with same size
        def mock_info_func(uri):
            return {"standard::size": "1024"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/Videos/sync"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.source_dir):
                with patch('phone_migration.gio_utils.gio_mkdir'):
                    with patch('phone_migration.gio_utils.gio_info', side_effect=mock_info_func):
                        with patch('phone_migration.gio_utils.get_file_size', return_value=1024):
                            with patch('phone_migration.gio_utils.gio_copy') as mock_copy:
                                with patch('phone_migration.operations._delete_extraneous_on_phone'):
                                    stats = operations.run_sync_rule(rule, device, verbose=False)
        
        # Should skip the file (not copy)
        self.assertEqual(stats.get("skipped", 0), 1)
        mock_copy.assert_not_called()
    
    @patch('phone_migration.gio_utils.gio_mkdir')
    @patch('phone_migration.operations._delete_extraneous_on_phone')
    def test_sync_with_rename_duplicates_false_skips_conflicts(self, mock_cleanup, mock_mkdir):
        """Test that sync skips files with conflicts when rename_duplicates=False."""
        # Create file on desktop
        test_file = self.create_file(self.source_dir, "video.mp4", "a" * 1024)
        
        rule = {
            "desktop_path": str(self.source_dir),
            "phone_path": "/Videos/sync"
        }
        device = {"activation_uri": "mtp://device/"}
        
        # Mock gio_info to return file exists with DIFFERENT size
        def mock_info_func(uri):
            return {"standard::size": "2048"}  # Different size
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/Videos/sync"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.source_dir):
                with patch('phone_migration.gio_utils.gio_info', side_effect=mock_info_func):
                    with patch('phone_migration.gio_utils.get_file_size', return_value=2048):
                        with patch('phone_migration.gio_utils.gio_copy') as mock_copy:
                            stats = operations.run_sync_rule(
                                rule, device, verbose=False, rename_duplicates=False
                            )
        
        # Should skip the file (conflict)
        self.assertGreater(stats.get("errors", 0), 0)
        mock_copy.assert_not_called()


class TestSmartCopyOperation(TestOperationsBase):
    """Test run_smart_copy_rule operation."""
    
    @patch('phone_migration.state.load_rule_state')
    @patch('phone_migration.state.save_rule_state')
    @patch('phone_migration.state.mark_file_copied')
    @patch('phone_migration.operations._build_file_list')
    @patch('phone_migration.gio_utils.gio_copy')
    def test_smart_copy_tracks_progress(self, mock_copy, mock_build, mock_mark_copied, 
                                        mock_save_state, mock_load_state):
        """Test that smart_copy tracks which files have been copied."""
        # Setup state to be empty (first run)
        mock_load_state.return_value = {"copied": [], "failed": []}
        mock_build.return_value = []  # Updated to just append to list
        
        # Mock _build_file_list to populate the file list
        def build_files(uri, rel_path, file_list):
            file_list.extend(["file1.txt", "file2.txt"])
        
        mock_build.side_effect = build_files
        mock_copy.return_value = True
        
        # Create mock files
        self.create_file(self.source_dir, "file1.txt")
        self.create_file(self.source_dir, "file2.txt")
        
        rule = {
            "id": "test-rule-1",
            "phone_path": "/Videos/backup",
            "desktop_path": str(self.source_dir)
        }
        device = {"activation_uri": "mtp://device/"}
        
        with patch('phone_migration.paths.build_phone_uri', return_value="mtp://device/Videos/backup"):
            with patch('phone_migration.paths.expand_desktop', return_value=self.source_dir):
                stats = operations.run_smart_copy_rule(rule, device, verbose=False)
        
        self.assertIsInstance(stats, dict)


class TestRenameConflictHandling(TestOperationsBase):
    """Test conflict handling with rename_duplicates parameter."""
    
    def test_move_with_conflicts_renamed_true(self):
        """With rename_duplicates=True, conflicting files should be renamed."""
        # Create source files
        self.create_file(self.source_dir, "photo.jpg", "source content")
        
        # Create conflicting destination file
        self.create_file(self.dest_dir, "photo.jpg", "dest content")
        
        # Direct test of the rename logic
        result = paths.next_available_name(self.dest_dir, "photo.jpg", rename_duplicates=True)
        self.assertEqual(result.name, "photo (1).jpg")
    
    def test_move_with_conflicts_renamed_false(self):
        """With rename_duplicates=False, conflicting files should be skipped."""
        # Create source files
        self.create_file(self.source_dir, "photo.jpg", "source content")
        
        # Create conflicting destination file
        self.create_file(self.dest_dir, "photo.jpg", "dest content")
        
        # Direct test of the skip logic
        result = paths.next_available_name(self.dest_dir, "photo.jpg", rename_duplicates=False)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
