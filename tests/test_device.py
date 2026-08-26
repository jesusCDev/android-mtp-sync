"""Tests for phone_migration.device: mount parsing and device fingerprints.

The sample below is the shape `gio mount -li` really prints (gvfs
programs/gvfs-mount.c): drives contain volumes contain mounts, a mount line is
``Mount(n): <name> -> <uri>``, and volume ids are indented under ``ids:``.
It holds two distinct MTP phones plus one ordinary disk mount.
"""

import pytest

from phone_migration import device, gio_utils


GIO_MOUNT_LI = """\
Drive(0): KXG8AZNV1T02 LA KIOXIA
  Type: GProxyDrive (GProxyVolumeMonitorUDisks2)
  ids:
   unix-device: '/dev/nvme0n1'
  is_removable=0
  can_eject=0
  sort_key=00coldplug/00fixed/nvme0
  Volume(0): Data
    Type: GProxyVolume (GProxyVolumeMonitorUDisks2)
    ids:
     unix-device: '/dev/nvme0n1p3'
     label: 'Data'
    uuid=8f0e4c31-3d5b-4a6e-9d0a-2f7c1b8e4a90
    can_mount=1
    should_automount=1
    Mount(0): Data -> file:///run/media/jesus/Data
      Type: GProxyShadowMount (GProxyVolumeMonitorUDisks2)
      user_visible=1
      can_unmount=1
      default_location=file:///run/media/jesus/Data

Volume(0): Galaxy S21
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/003/009'
   class: 'device'
  uuid=
  activation_root=mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
  can_mount=1
  can_eject=0
  should_automount=0
  sort_key=gproxyvolume-mtp
  Mount(0): Galaxy S21 -> mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
    Type: GDaemonMount
    themed icons:  [multimedia-player]  [phone]
    user_visible=1
    can_unmount=1
    can_eject=0
    is_shadowed=0
    default_location=mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
Volume(1): Pixel 7
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/003/011'
   class: 'device'
  uuid=
  activation_root=mtp://Google_Pixel_7_2b9c-41ad/
  can_mount=1
  can_eject=0
  should_automount=0
  sort_key=gproxyvolume-mtp
  Mount(1): Pixel 7 -> mtp://Google_Pixel_7_2b9c-41ad/
    Type: GDaemonMount
    user_visible=1
    can_unmount=1
    is_shadowed=0
    default_location=mtp://Google_Pixel_7_2b9c-41ad/
"""

# A phone gvfs could not name: the URI carries only the USB port, which is
# reassigned to whatever is plugged in next.
NO_SERIAL_MOUNT_LI = """\
Volume(0): Android
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/003/014'
  activation_root=mtp://[usb:003,014]/
  can_mount=1
  Mount(0): Android -> mtp://[usb:003,014]/
    Type: GDaemonMount
    user_visible=1
"""


# A phone gvfs knows about but has not mounted (should_automount=0): there is no
# Mount( line at all, only the volume's activation root.
UNMOUNTED_MOUNT_LI = """\
Volume(0): Android
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/003/009'
   class: 'device'
  uuid=
  activation_root=mtp://[usb:003,009]/
  can_mount=1
  can_eject=0
  should_automount=0
  sort_key=gproxyvolume-mtp
"""

# One phone, two spellings: gvfs advertises the volume by USB port and then
# mounts it under its named URI.
MIXED_FORM_MOUNT_LI = """\
Volume(0): Galaxy S21
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/003/009'
   class: 'device'
  activation_root=mtp://[usb:003,009]/
  can_mount=1
  should_automount=0
  Mount(0): Galaxy S21 -> mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
    Type: GDaemonMount
    user_visible=1
    can_unmount=1
    default_location=mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/
"""


@pytest.fixture
def mount_list(monkeypatch):
    """Feed enumerate_mtp_mounts a canned `gio mount -li`."""
    def use(output):
        monkeypatch.setattr(gio_utils, "gio_mount_list", lambda: output)
    return use


@pytest.fixture
def gio_info(monkeypatch):
    """Control what `gio info` reports for the device root."""
    def use(result):
        def fake(location, attributes=None):
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr(gio_utils, "gio_info", fake)
    return use


# --- enumerate_mtp_mounts ----------------------------------------------------

def test_two_phones_are_two_devices(mount_list):
    mount_list(GIO_MOUNT_LI)

    devices = device.enumerate_mtp_mounts()

    assert [d["display_name"] for d in devices] == ["Galaxy S21", "Pixel 7"]
    assert [d["activation_uri"] for d in devices] == [
        "mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/",
        "mtp://Google_Pixel_7_2b9c-41ad/",
    ]


def test_non_mtp_mounts_are_ignored(mount_list):
    mount_list(GIO_MOUNT_LI)

    for dev in device.enumerate_mtp_mounts():
        assert dev["activation_uri"].startswith("mtp://")


def test_each_device_keeps_its_own_identifier(mount_list):
    mount_list(GIO_MOUNT_LI)

    devices = device.enumerate_mtp_mounts()

    assert devices[0]["identifier"] == "/dev/bus/usb/003/009"
    assert devices[1]["identifier"] == "/dev/bus/usb/003/011"


def test_no_devices_when_nothing_is_plugged_in(mount_list):
    mount_list("")

    assert device.enumerate_mtp_mounts() == []


# --- device_fingerprint ------------------------------------------------------

def test_serial_comes_from_gio_info_when_available(mount_list, gio_info):
    mount_list(GIO_MOUNT_LI)
    gio_info({"mtp::serial": "SERIALFROMINFO"})

    assert device.device_fingerprint(device.enumerate_mtp_mounts()[0]) == (
        "mtp_serial", "SERIALFROMINFO")


def test_uppercase_serial_is_read_from_the_uri(mount_list, gio_info):
    mount_list(GIO_MOUNT_LI)
    gio_info({})

    assert device.device_fingerprint(device.enumerate_mtp_mounts()[0]) == (
        "mtp_serial", "R5CY43CZ5AR")


def test_lowercase_hyphenated_serial_is_read_from_the_uri(mount_list, gio_info):
    """Finding #14: this used to fall back to the USB port address."""
    mount_list(GIO_MOUNT_LI)
    gio_info({})

    assert device.device_fingerprint(device.enumerate_mtp_mounts()[1]) == (
        "mtp_serial", "2b9c-41ad")


def test_a_device_without_a_serial_has_no_fingerprint(mount_list, gio_info):
    """No usb_address / identifier / activation_uri fallback: those match the
    wrong phone after a reconnect."""
    mount_list(NO_SERIAL_MOUNT_LI)
    gio_info({})

    assert device.device_fingerprint(device.enumerate_mtp_mounts()[0]) == ("", "")


def test_a_model_word_with_no_digit_is_not_mistaken_for_a_serial(gio_info):
    """mtp://SAMSUNG_SAMSUNG_Android/ has no serial segment at all - the last
    underscore-separated word is just the model, and two serial-less phones
    of this model must not collide on it."""
    gio_info({})

    assert device.device_fingerprint(
        {"activation_uri": "mtp://SAMSUNG_SAMSUNG_Android/"}) == ("", "")


def test_enrich_returns_nothing_when_gio_fails(gio_info):
    gio_info(gio_utils.GioError("Failed to open file: device busy"))

    assert device.enrich_mtp_attributes("mtp://whatever/") == {}


# --- register_current_device -------------------------------------------------

def test_registering_writes_the_serial_fingerprint(mount_list, gio_info):
    mount_list(NO_SERIAL_MOUNT_LI.replace("[usb:003,014]", "Google_Pixel_7_2b9c-41ad"))
    gio_info({})
    config = {"profiles": []}

    device.register_current_device(config, "pixel")

    assert config["profiles"][0]["device"]["id_type"] == "mtp_serial"
    assert config["profiles"][0]["device"]["id_value"] == "2b9c-41ad"


def test_registering_keeps_existing_rules(mount_list, gio_info):
    mount_list(NO_SERIAL_MOUNT_LI.replace("[usb:003,014]", "Google_Pixel_7_2b9c-41ad"))
    gio_info({})
    config = {"profiles": [{"name": "pixel", "device": {}, "rules": [{"id": "r-0001"}]}]}

    device.register_current_device(config, "pixel")

    assert config["profiles"][0]["rules"] == [{"id": "r-0001"}]


def test_registering_a_device_without_a_serial_refuses(mount_list, gio_info):
    mount_list(NO_SERIAL_MOUNT_LI)
    gio_info({})
    config = {"profiles": []}

    with pytest.raises(RuntimeError, match="no serial number"):
        device.register_current_device(config, "mystery")

    assert config["profiles"] == []


def test_registering_with_no_device_connected_refuses(mount_list):
    mount_list("")

    with pytest.raises(RuntimeError, match="No MTP devices"):
        device.register_current_device({"profiles": []}, "nothing")


def test_registering_with_two_devices_connected_refuses(mount_list, gio_info):
    mount_list(GIO_MOUNT_LI)
    gio_info({})

    with pytest.raises(RuntimeError, match="disconnect"):
        device.register_current_device({"profiles": []}, "ambiguous")


def test_a_connected_but_unmounted_phone_is_still_found(mount_list):
    """should_automount=0 means no Mount( line until something touches the URI;
    the phone is plugged in all the same."""
    mount_list(UNMOUNTED_MOUNT_LI)

    devices = device.enumerate_mtp_mounts()

    assert [d["activation_uri"] for d in devices] == ["mtp://[usb:003,009]/"]


def test_a_volume_and_its_own_mount_are_one_phone(mount_list):
    """The volume advertises the USB-port URI, its mount the named one. Two
    spellings of one phone must not become two devices - register_current_device
    would refuse with "Multiple MTP devices found (2)"."""
    mount_list(MIXED_FORM_MOUNT_LI)

    devices = device.enumerate_mtp_mounts()

    assert [d["activation_uri"] for d in devices] == [
        "mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/"]
    assert devices[0]["identifier"] == "/dev/bus/usb/003/009"
