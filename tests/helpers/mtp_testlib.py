"""Helpers for testing MTP operations on connected Android device."""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MTPDevice:
    """Wrapper for MTP device operations during testing."""
    
    def __init__(self, activation_uri: str):
        """Initialize with device activation URI."""
        self.uri = activation_uri
    
    def _run_gio(self, *args, check: bool = False) -> Tuple[int, str, str]:
        """Run a gio command and return (returncode, stdout, stderr)."""
        cmd = ["gio"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(f"GIO command failed: {' '.join(cmd)}\n{result.stderr}")
        return result.returncode, result.stdout, result.stderr
    
    def mkdir(self, path: str) -> None:
        """Create directory on phone."""
        full_uri = f"{self.uri}/{path.lstrip('/')}"
        rc, _, err = self._run_gio("mkdir", "-p", full_uri)
        if rc != 0:
            raise RuntimeError(f"Failed to create {path}: {err}")
    
    def push_file(self, local_path: Path, phone_path: str) -> None:
        """Copy file from desktop to phone."""
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        full_uri = f"{self.uri}/{phone_path.lstrip('/')}"
        rc, _, err = self._run_gio("copy", str(local_path), full_uri)
        if rc != 0:
            raise RuntimeError(f"Failed to push {phone_path}: {err}")
    
    def push_file_recursive(self, local_dir: Path, phone_path: str) -> None:
        """Recursively copy files from local directory to phone."""
        if not local_dir.is_dir():
            raise NotADirectoryError(f"{local_dir} is not a directory")
        
        for item in local_dir.rglob('*'):
            if item.is_file():
                # Calculate relative path
                rel_path = item.relative_to(local_dir)
                dest_phone_path = f"{phone_path}/{rel_path}".replace('\\', '/')
                
                # Create parent dir on phone if needed
                parent_path = str(Path(dest_phone_path).parent)
                if parent_path != phone_path:
                    try:
                        self.mkdir(parent_path)
                    except:
                        pass  # Dir might already exist
                
                # Push file
                self.push_file(item, dest_phone_path)
    
    def list_dir(self, path: str = "/") -> List[str]:
        """List directory contents on phone."""
        full_uri = f"{self.uri}/{path.lstrip('/')}"
        rc, stdout, err = self._run_gio("list", full_uri)
        if rc != 0:
            return []
        return [line.strip() for line in stdout.splitlines() if line.strip()]
    
    def get_file_info(self, path: str) -> Dict[str, str]:
        """Get file information from phone."""
        full_uri = f"{self.uri}/{path.lstrip('/')}"
        rc, stdout, err = self._run_gio("info", full_uri)
        if rc != 0:
            return {}
        
        info = {}
        for line in stdout.splitlines():
            if ': ' in line:
                key, value = line.split(': ', 1)
                info[key.strip()] = value.strip()
        return info
    
    def remove(self, path: str) -> None:
        """Remove file or directory from phone."""
        full_uri = f"{self.uri}/{path.lstrip('/')}"
        rc, _, err = self._run_gio("remove", full_uri)
        if rc != 0:
            raise RuntimeError(f"Failed to remove {path}: {err}")
    
    def path_exists(self, path: str) -> bool:
        """Check if path exists on phone."""
        info = self.get_file_info(path)
        return bool(info)
    
    def directory_tree(self, path: str = "/", prefix: str = "") -> Dict[str, any]:
        """Build a tree structure of phone directory."""
        try:
            entries = self.list_dir(path)
        except:
            return {}
        
        tree = {"files": [], "dirs": {}}
        
        for entry in entries:
            entry_path = f"{path}/{entry}".replace('//', '/')
            info = self.get_file_info(entry_path)
            entry_type = info.get('type', 'unknown')
            
            if 'directory' in entry_type.lower() or entry_type == '2':
                # Recurse into directory
                tree["dirs"][entry] = self.directory_tree(entry_path, prefix + "  ")
            else:
                # Add file
                size = info.get('size', '0')
                tree["files"].append({"name": entry, "size": size})
        
        return tree
    
    def count_files(self, path: str = "/") -> int:
        """Recursively count files in directory."""
        tree = self.directory_tree(path)
        count = len(tree.get("files", []))
        for subdir in tree.get("dirs", {}).values():
            # This is a simplified count - would need recursive call
            pass
        return count


def compare_trees(tree1: Dict, tree2: Dict, path: str = "") -> List[str]:
    """Compare two directory trees and return differences."""
    differences = []
    
    # Compare files
    files1 = {f['name']: f['size'] for f in tree1.get('files', [])}
    files2 = {f['name']: f['size'] for f in tree2.get('files', [])}
    
    for name in set(files1.keys()) | set(files2.keys()):
        if name not in files1:
            differences.append(f"Missing in source: {path}/{name}")
        elif name not in files2:
            differences.append(f"Extra in source: {path}/{name}")
        elif files1[name] != files2[name]:
            differences.append(f"Size mismatch: {path}/{name} ({files1[name]} vs {files2[name]})")
    
    # Compare directories
    dirs1 = tree1.get('dirs', {})
    dirs2 = tree2.get('dirs', {})
    
    for name in set(dirs1.keys()) | set(dirs2.keys()):
        if name not in dirs1:
            differences.append(f"Missing dir in source: {path}/{name}")
        elif name not in dirs2:
            differences.append(f"Extra dir in source: {path}/{name}")
        else:
            sub_diffs = compare_trees(dirs1[name], dirs2[name], f"{path}/{name}")
            differences.extend(sub_diffs)
    
    return differences
