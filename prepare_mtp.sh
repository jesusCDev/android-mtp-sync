#!/bin/bash
# Prepare MTP connection for Phone Migration Tool
# This script closes all file managers and restarts GVFS to release the MTP lock

echo "=========================================="
echo "Preparing MTP for Phone Migration Tool"
echo "=========================================="
echo ""

echo "1. Closing file managers..."
killall nemo dolphin nautilus pcmanfm thunar 2>/dev/null
sleep 1
echo "   ✓ File managers closed"
echo ""

echo "2. Restarting GVFS daemon..."
systemctl --user restart gvfs-daemon
sleep 2
echo "   ✓ GVFS restarted"
echo ""

echo "3. Verifying phone connection..."
if gio mount -l | grep -q -i "SAMSUNG\|mtp"; then
    echo "   ✓ Phone detected"
    echo ""
    echo "=========================================="
    echo "✓ MTP is ready!"
    echo "=========================================="
    echo ""
    echo "You can now run:"
    echo "  phone-sync --web"
    echo ""
else
    echo "   ✗ Phone not detected"
    echo ""
    echo "Try:"
    echo "  1. Unlock your phone"
    echo "  2. Ensure File Transfer mode is enabled"
    echo "  3. Reconnect the USB cable"
    echo "  4. Run this script again"
fi
