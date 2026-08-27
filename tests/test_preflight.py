"""Preflight tests: the phone-side size estimate and the desktop free-space probe.

gio never runs here - `gio_list_detailed` is faked, so the estimate walk is
exercised without a phone attached.
"""

import shutil

import pytest

from phone_migration import gio_utils, paths, preflight

DEVICE = {"display_name": "Pixel 7", "activation_uri": "mtp://Pixel/"}


def _rule(desktop="~/Pictures", phone="/DCIM/Camera"):
    return {"id": "r-1", "mode": "copy", "phone_path": phone, "desktop_path": desktop}


def _root(phone="/DCIM/Camera"):
    return paths.build_phone_uri(DEVICE["activation_uri"], phone)


def _lister(tree, calls=None):
    """A gio_list_detailed stand-in; a URI outside the tree raises like gio does."""
    def gio_list_detailed(uri):
        if calls is not None:
            calls.append(uri)
        if uri not in tree:
            raise gio_utils.GioError(f"No such file or directory: {uri}")
        return tree[uri]
    return gio_list_detailed


def _file(name, size):
    return {"name": name, "is_dir": False, "size": size}


def _dir(name):
    return {"name": name, "is_dir": True, "size": None}


# --- free space --------------------------------------------------------------

def test_free_space_falls_back_to_the_nearest_existing_ancestor(tmp_path):
    """The destination is created by the operation itself, moments after this check."""
    missing = tmp_path / "Phone" / "Camera" / "2026"
    assert preflight.query_free_space_desktop(str(missing)) > 0


def test_free_space_expands_a_home_relative_path():
    assert preflight.query_free_space_desktop("~/") > 0


# --- estimate ----------------------------------------------------------------

def test_the_estimate_sums_a_nested_phone_tree(monkeypatch):
    root = _root()
    sub = gio_utils.child_uri(root, "Sub dir")
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({
        root: [_file("a.jpg", 100), _dir("Sub dir")],
        sub: [_file("b.mp4", 250), _file("unknown.bin", None)],
    }))

    assert preflight.estimate_phone_size(_rule(), DEVICE) == 350


def test_the_estimate_stops_at_max_entries(monkeypatch):
    root = _root()
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({
        root: [_file(f"f{i}.jpg", 10) for i in range(50)],
    }))

    assert preflight.estimate_phone_size(_rule(), DEVICE, max_entries=5) == 50


def test_a_subtree_that_will_not_list_is_skipped_not_fatal(monkeypatch):
    root = _root()
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({
        root: [_file("a.jpg", 100), _dir("Locked")],
    }))

    assert preflight.estimate_phone_size(_rule(), DEVICE) == 100


def test_an_unreachable_phone_path_estimates_zero(monkeypatch):
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({}))

    assert preflight.estimate_phone_size(_rule(), DEVICE) == 0


# --- the checks that use it --------------------------------------------------

def test_a_rule_bigger_than_the_free_space_fails_preflight(monkeypatch, tmp_path):
    free = shutil.disk_usage(tmp_path).free
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({
        _root(): [_file("huge.mp4", free * 2)],
    }))

    with pytest.raises(preflight.PreflightError, match="Deficit"):
        preflight.preflight_copy(_rule(desktop=str(tmp_path / "new")), DEVICE)


@pytest.mark.parametrize("check", ["preflight_copy", "preflight_move", "preflight_backup"])
def test_a_rule_that_fits_passes(monkeypatch, tmp_path, check):
    monkeypatch.setattr(gio_utils, "gio_list_detailed", _lister({
        _root(): [_file("small.jpg", 1024)],
    }))

    getattr(preflight, check)(_rule(desktop=str(tmp_path / "new")), DEVICE)
