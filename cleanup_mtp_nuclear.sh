#!/bin/bash
# Nuclear MTP cleanup - removes and reloads MTP kernel modules
# Only run this as a last resort before restarting

set -e

echo "=========================================="
echo "NUCLEAR MTP Cleanup"
echo "=========================================="
echo ""

echo "Step 1: Killing all file managers..."
killall -9 nemo dolphin nautilus pcmanfm thunar 2>/dev/null || true
sleep 1
echo "✓ File managers killed"
echo ""

echo "Step 2: Killing all GVFS processes..."
killall -9 gvfsd gvfsd-mtp gvfs-mtp-volume-monitor 2>/dev/null || true
sleep 2
echo "✓ GVFS processes killed"
echo ""

echo "Step 3: Stopping GVFS service completely..."
systemctl --user stop gvfs-daemon 2>/dev/null || true
sleep 2
echo "✓ GVFS service stopped"
echo ""

echo "Step 4: Killing any remaining gvfs processes..."
pkill -9 -f gvfs || true
sleep 1
echo "✓ Remaining GVFS processes killed"
echo ""

echo "Step 5: Checking USB devices..."
echo "USB devices connected:"
USB_DEVICE=$(lsusb | grep -i samsung)
echo "$USB_DEVICE"
if [[ -z "$USB_DEVICE" ]]; then
    echo "(Samsung device not found - may need to reconnect)"
else
    echo ""
    echo "Step 5b: Resetting USB device via sysfs..."
    # Extract bus:device from lsusb output (e.g., "Bus 001 Device 006")
    BUS=$(echo "$USB_DEVICE" | grep -oP 'Bus \K[0-9]+')
    DEVICE=$(echo "$USB_DEVICE" | grep -oP 'Device \K[0-9]+')
    
    if [[ -n "$BUS" ]] && [[ -n "$DEVICE" ]]; then
        # Try to find and reset the USB device using unbind/bind
        for usb_path in /sys/bus/usb/devices/*/; do
            if [[ -f "${usb_path}idVendor" ]]; then
                vendor=$(cat "${usb_path}idVendor")
                # Samsung vendor ID is 04e8
                if [[ "$vendor" == "04e8" ]]; then
                    device_name=$(basename "$usb_path")
                    echo "Found Samsung device: $device_name at ${usb_path}"
                    echo "Resetting USB device via unbind/bind..."
                    
                    # Get the directory where this script is located
                    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
                    RESET_SCRIPT="${SCRIPT_DIR}/reset_usb_device.sh"
                    
                    # Try using the sudo helper script
                    if [[ -f "$RESET_SCRIPT" ]]; then
                        if sudo "$RESET_SCRIPT" "$device_name" 2>/dev/null; then
                            echo "✓ USB device reset (unbind/bind via sudo)"
                        else
                            echo "⚠ Could not reset USB device - try running with sudo:"
                            echo "  sudo $0"
                        fi
                    else
                        echo "⚠ reset_usb_device.sh not found at $RESET_SCRIPT"
                        echo "  Try running: sudo $0"
                    fi
                    break
                fi
            fi
        done
    fi
fi
echo ""

echo "Step 6: Starting fresh GVFS daemon..."
systemctl --user start gvfs-daemon
sleep 4
echo "✓ Fresh GVFS daemon started"
echo ""

echo "Step 7: Listing mounts..."
gio mount -li 2>/dev/null | head -20 || true
echo ""

echo "Step 8: Final verification..."
if gio mount -li 2>/dev/null | grep -q -i "SAMSUNG\|Android"; then
    echo "✓ Phone detected!"
    echo ""
    echo "=========================================="
    echo "✓ SUCCESS: Phone is ready!"
    echo "=========================================="
else
    echo "⚠ Phone still not detected"
    echo ""
    echo "MTP access appears to be stuck at kernel/USB level."
    echo "This typically requires a full computer restart."
    echo ""
    echo "Before restarting, try:"
    echo "  1. Disconnect USB cable completely"
    echo "  2. Wait 5 seconds"
    echo "  3. Reconnect USB cable"
    echo "  4. Unlock phone and ensure File Transfer mode is on"
    echo "  5. Run this script again"
fi
