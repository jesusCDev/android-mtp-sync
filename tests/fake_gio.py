"""An in-memory phone, so operations tests never touch a real device.

The tree is keyed by the *decoded* path under the device root, exactly the way
gio sees it: ``gio_utils.child_uri`` percent-encodes every segment on the way
out and this fake unquotes it on the way in, so a name holding '#', '%' or a
space only round-trips if operations built the URI properly.

Failure injection: ``copy_failures`` / ``truncate`` (entry names) and
``list_errors`` (decoded directory paths). ``removed`` and ``copied`` record
what actually happened.
"""

from pathlib import Path
from urllib.parse import unquote

from phone_migration import gio_utils
from phone_migration.gio_utils import GioError


class FakePhone:
    def __init__(self, files=None, root="mtp://dev/"):
        self.root = root.rstrip("/")
        self.files = {}
        self.dirs = set()
        self.ghosts = set()         # listed, but gio info reports no type
        self.copy_failures = set()  # entry names whose copy fails
        self.truncate = set()       # entry names copied short, MTP style
        self.list_errors = set()    # decoded dir paths whose listing raises
        self.removed = []
        self.copied = []
        for path, data in (files or {}).items():
            self.add(path, data)

    # --- tree building -------------------------------------------------

    def add(self, path, data=b""):
        path = path.strip("/")
        self.files[path] = data
        self._add_parents(path)

    def mkdir(self, path):
        path = path.strip("/")
        if path:
            self.dirs.add(path)
            self._add_parents(path)

    def ghost(self, path):
        """An entry that a listing shows but `gio info` cannot describe."""
        path = path.strip("/")
        self.ghosts.add(path)
        self._add_parents(path)

    def _add_parents(self, path):
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            self.dirs.add(path)

    def _rel(self, uri):
        if not uri.startswith(self.root):
            raise GioError(f"not on this device: {uri}")
        return unquote(uri[len(self.root):]).strip("/")

    def _children(self, rel):
        prefix = f"{rel}/" if rel else ""
        return sorted({
            path[len(prefix):].split("/", 1)[0]
            for path in (*self.files, *self.dirs, *self.ghosts)
            if path.startswith(prefix) and len(path) > len(prefix)
        })

    def _is_dir(self, rel):
        return rel == "" or rel in self.dirs

    # --- the gio_utils surface -----------------------------------------

    def gio_list(self, location):
        rel = self._rel(location)
        if rel in self.list_errors:
            raise GioError(f"Error listing {location}: Device is busy")
        if not self._is_dir(rel):
            raise GioError(f"Error listing {location}: Not a directory")
        return self._children(rel)

    def gio_list_detailed(self, location):
        rel = self._rel(location)
        entries = []
        for name in self.gio_list(location):
            child = f"{rel}/{name}" if rel else name
            entries.append({
                "name": name,
                "is_dir": self._is_dir(child),
                "size": len(self.files[child]) if child in self.files else None,
            })
        return entries

    def gio_info(self, location, attributes=None):
        rel = self._rel(location)
        if rel in self.files:
            return {"standard::type": "regular",
                    "standard::size": str(len(self.files[rel]))}
        if self._is_dir(rel):
            return {"standard::type": "2"}  # gio's numeric type for a directory
        return {}

    def gio_copy(self, src, dst, recursive=False, verbose=False):
        if gio_utils.DRY_RUN:
            return True
        if src.startswith(self.root):                       # phone -> desktop
            rel = self._rel(src)
            data = self.files.get(rel)
            if data is None or self._basename(rel) in self.copy_failures:
                return False
            Path(dst).write_bytes(self._maybe_truncate(rel, data))
            self.copied.append((rel, dst))
            return True
        rel = self._rel(dst)                                # desktop -> phone
        if self._basename(rel) in self.copy_failures:
            return False
        self.add(rel, self._maybe_truncate(rel, Path(src).read_bytes()))
        self.copied.append((src, rel))
        return True

    def gio_remove(self, location, verbose=False):
        if gio_utils.DRY_RUN:
            return True
        rel = self._rel(location)
        if rel in self.files:
            del self.files[rel]
        elif rel in self.dirs:
            if self._children(rel):
                return False
            self.dirs.discard(rel)
        else:
            return False
        self.removed.append(rel)
        return True

    def gio_mkdir(self, location, parents=True):
        if gio_utils.DRY_RUN:
            return True
        self.mkdir(self._rel(location))
        return True

    # --- helpers --------------------------------------------------------

    def _basename(self, rel):
        return rel.rsplit("/", 1)[-1]

    def _maybe_truncate(self, rel, data):
        return data[: len(data) // 2] if self._basename(rel) in self.truncate else data

    def install(self, monkeypatch):
        for name in ("gio_list", "gio_list_detailed", "gio_info", "gio_copy",
                     "gio_remove", "gio_mkdir"):
            monkeypatch.setattr(gio_utils, name, getattr(self, name))
        return self
