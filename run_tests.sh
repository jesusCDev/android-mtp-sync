#!/bin/bash
# Single command to safely run the test suite
# Usage: ./run_tests.sh

set -e

echo "========================================================================"
echo "Phone Migration Tool - Test Suite Runner"
echo "========================================================================"
echo ""

# Check if phone is connected
echo "📱 Checking device connection..."
DEVICES=$(gio mount -li 2>/dev/null | grep -i "SAMSUNG\|Android" || true)
if [ -z "$DEVICES" ]; then
    echo "❌ ERROR: No Android device connected"
    echo "   Please connect your phone via USB and enable File Transfer mode"
    exit 1
fi
echo "✓ Device found"
echo ""

# Run the test suite
echo "🧪 Starting test suite..."
echo "   This will create a test-android-mtp folder on your phone"
echo "   and run all operation tests (copy, move, sync, backup)"
echo ""
python3 "$(dirname "$0")/tests/test_e2e_operations_safe.py"
exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed"
fi

exit $exit_code
