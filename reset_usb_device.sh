#!/bin/bash
# USB device reset script - requires sudo
# Used by cleanup_mtp_nuclear.sh to reset USB devices

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run with sudo"
    exit 1
fi

DEVICE_NAME="$1"

if [[ -z "$DEVICE_NAME" ]]; then
    echo "Usage: $0 <device_name>"
    echo "Example: $0 1-6"
    exit 1
fi

echo "Resetting USB device: $DEVICE_NAME"

# Try unbind/bind method
if [[ -f /sys/bus/usb/drivers/usb/unbind ]]; then
    echo "Unbinding device..."
    echo "$DEVICE_NAME" > /sys/bus/usb/drivers/usb/unbind
    sleep 2
    
    echo "Rebinding device..."
    echo "$DEVICE_NAME" > /sys/bus/usb/drivers/usb/bind
    sleep 2
    
    echo "✓ USB device reset successful"
    exit 0
fi

exit 1
