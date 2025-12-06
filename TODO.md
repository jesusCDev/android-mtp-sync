# TODO List - Android MTP Sync

## High Priority

### Fix Rule Validation Timeout Issue
**Status**: Disabled (line 181 in web_ui.py)
**Problem**: `gio_info()` with timeout parameter hangs on some systems/MTP connections, causing validation to never complete
**Impact**: Validation feature currently disabled to prevent UI blocking

**Root Cause**:
- `gio_utils.gio_info(phone_uri, timeout=1)` doesn't properly respect timeout on all systems
- MTP connections can be slow, causing the subprocess call to hang indefinitely
- Thread-based timeout doesn't interrupt the underlying `gio info` subprocess

**Potential Solutions**:
1. Use `subprocess.Popen` with proper timeout handling instead of relying on gio's built-in timeout
2. Add a wrapper with `signal.alarm()` (Unix-only) or `threading.Timer` to forcefully kill the subprocess
3. Make validation completely optional with a user toggle in settings
4. Use a process pool with timeout enforcement
5. Skip phone path validation entirely and only validate desktop paths (which are fast)

**Files to Modify**:
- `phone_migration/gio_utils.py` - Fix `gio_info()` timeout implementation
- `phone_migration/rule_validator.py` - Add better error handling for timeouts
- `phone_migration/web_ui.py` - Re-enable validation (change `if False and accessible:` back to `if accessible:` on line 181)

**Test Plan**:
1. Connect device with slow MTP connection
2. Verify validation completes within 2-3 seconds max
3. Verify timeout doesn't hang the entire thread
4. Test with multiple rules (2-5) to ensure it scales

**Priority**: High - This is a UX blocker that prevents users from seeing path validation warnings

---

## Medium Priority

### Add Validation Toggle in Settings
- Allow users to enable/disable automatic validation
- Store preference in config file
- Show manual "Validate Now" button when auto-validation is off

### Improve gio_utils Timeout Mechanism
- Implement universal timeout wrapper for all gio commands
- Use process-level timeout enforcement
- Add retry logic with exponential backoff

---

## Low Priority

### Add Validation Cache
- Cache validation results for 5 minutes to avoid repeated checks
- Invalidate cache when rules change or device reconnects
- Show "Last validated: X minutes ago" in UI

### Validation Performance Metrics
- Log how long each validation takes
- Show timing in verbose mode
- Alert if validation takes >3 seconds

---

## Notes
- Test runner works correctly - uses subprocess with proper timeout
- Validation is non-critical feature - tool works fine without it
- Consider making phone path validation optional since desktop path validation is fast and reliable
