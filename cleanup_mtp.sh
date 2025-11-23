#!/bin/bash
# Aggressive MTP cleanup script
# Kills all file managers and GVFS processes to release exclusive MTP access

set -e

echo "=========================================="
echo "Aggressive MTP Cleanup & Reset"
echo "=========================================="
echo ""

echo "Step 1: Killing all file managers..."
killall -9 nemo dolphin nautilus pcmanfm thunar 2>/dev/null || true
sleep 1
echo "✓ File managers killed"
echo ""

echo "Step 2: Killing all GVFS processes..."
killall -9 gvfsd gvfsd-mtp gvfs-mtp-volume-monitor 2>/dev/null || true
sleep 1
echo "✓ GVFS processes killed"
echo ""

echo "Step 3: Unmounting MTP device..."
gio mount -u mtp://SAMSUNG_SAMSUNG_Android_R5CY43CZ5AR/ 2>/dev/null || true
sleep 1
echo "✓ MTP unmounted"
echo ""

echo "Step 4: Restarting GVFS daemon..."
systemctl --user restart gvfs-daemon
sleep 3
echo "✓ GVFS restarted"
echo ""

echo "Step 5: Verifying phone connection..."
if gio mount -li 2>/dev/null | grep -q -i "SAMSUNG\|Android"; then
    echo "✓ Phone detected!"
    echo ""
    echo "=========================================="
    echo "✓ SUCCESS: Phone is ready!"
    echo "=========================================="
    echo ""
    echo "You can now run:"
    echo "  phone-sync --web"
    echo ""
else
    echo "⚠ Phone not detected"
    echo ""
    echo "Try:"
    echo "  1. Unlock your phone"
    echo "  2. Check File Transfer mode is enabled"
    echo "  3. Reconnect the USB cable"
    echo "  4. Run this script again"
fi
