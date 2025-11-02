# Phone Migration - TODO

Future enhancements and features to implement after core functionality is complete.

## High Priority

### Auto-run on Device Connect
- **Goal**: Automatically execute sync when phone is connected
- **Implementation**:
  - Create systemd user service to watch for MTP device events
  - Create udev rule to trigger service when Android device connects
  - Service runs `main.py --run` automatically
  - Add `--daemon` mode for background operation
- **Files needed**:
  - `~/.config/systemd/user/phone-migration.service`
  - `/etc/udev/rules.d/99-android-mtp.rules`
- **Considerations**:
  - Should notify user when sync starts/completes
  - Need to handle multiple devices gracefully
  - Ensure phone is fully mounted before starting

### Desktop Notifications
- **Goal**: Show notifications for sync start, completion, and errors
- **Implementation**:
  - Use `notify-send` command (available on most Linux desktops)
  - Notify on: device connect, sync start, sync complete, errors
  - Include summary stats in completion notification
- **Example**: "Phone Sync Complete: 25 files copied, 10 deleted"

## Medium Priority

### Progress Indicators
- **Goal**: Show progress during long operations
- **Implementation**:
  - Count total files before starting
  - Show progress bar or percentage
  - Estimate time remaining based on current speed
  - Use `tqdm` library or custom progress display
- **Benefit**: Better UX for large transfers (hundreds of photos)

### Smart Sync with Checksums
- **Goal**: Only copy files that actually changed
- **Implementation**:
  - Calculate MD5/SHA256 hash of files before copying
  - Skip files with matching hashes
  - Store hash cache in config or separate file
  - Much faster for large files that haven't changed
- **Trade-off**: Hash calculation takes time vs. always copying

### Hash-based Duplicate Detection for Move
- **Goal**: Detect and skip files that already exist on desktop (even with different names)
- **Implementation**:
  - Build hash index of desktop destination
  - Check each phone file's hash against index
  - Skip copy if hash exists
  - Delete duplicate from phone or move to archive folder
- **Benefit**: Save space, avoid true duplicates

## Low Priority

### EXIF Date-based Organization
- **Goal**: Organize photos by date from EXIF metadata
- **Implementation**:
  - Read EXIF date from photos using `PIL` or `exiftool`
  - Create destination folders like `~/Photos/2025/01/`
  - Fall back to file modification date if no EXIF
  - Add `--organize-by-date` flag
- **Use case**: Better photo organization than flat folders

### File Filtering Patterns
- **Goal**: Include/exclude files by pattern
- **Implementation**:
  - Add `include_patterns` and `exclude_patterns` to rules
  - Support glob patterns like `*.jpg`, `IMG_*.png`
  - Support regex for advanced filtering
- **Use cases**:
  - Only sync specific file types
  - Exclude temporary files
  - Process only recent files

### SD Card Support
- **Goal**: Explicit support for SD card storage
- **Implementation**:
  - Detect "SD Card" storage label automatically
  - Add `--storage` flag to specify storage location
  - Allow rules to target different storage locations
- **Current status**: Should work with path `SD Card/...` but untested

### Parallel Transfers
- **Goal**: Copy multiple files simultaneously for speed
- **Implementation**:
  - Use thread pool or asyncio
  - Copy N files concurrently (configurable)
  - Show progress for all concurrent transfers
- **Trade-off**: MTP might not benefit much from parallel transfers
- **Risk**: Could overwhelm phone or cause connection issues

### Rate Limiting
- **Goal**: Throttle transfer speed to avoid phone overheating
- **Implementation**:
  - Add `--max-speed` flag (e.g., `--max-speed 5MB/s`)
  - Sleep between operations or chunks
  - Monitor transfer rate and adjust
- **Use case**: Long running syncs that might heat up phone

### Bi-directional Sync
- **Goal**: True bi-directional sync (not just desktop → phone)
- **Implementation**:
  - Track modification times on both sides
  - Newest version wins
  - Detect conflicts and prompt user
  - Similar to rsync behavior
- **Complexity**: High - need conflict resolution strategy
- **Alternative**: Keep current unidirectional model for simplicity

### Incremental Sync with State
- **Goal**: Remember what was synced last time
- **Implementation**:
  - Store state file with last sync time per rule
  - Only process files newer than last sync
  - Much faster for frequent syncs
- **File**: `~/.local/share/phone-migration/state.json`

### File Compression
- **Goal**: Compress files before transfer to save time
- **Implementation**:
  - Compress on phone before copying (requires phone app)
  - Or accept compressed archives from phone
  - Uncompress on desktop automatically
- **Complexity**: High - MTP doesn't support this natively

### Multiple Device Simultaneous Support
- **Goal**: Handle multiple phones connected at once
- **Implementation**:
  - Detect all connected devices
  - Match each to a profile
  - Run syncs in parallel or sequentially
  - Add `--device PROFILE` flag to target specific device
- **Current limitation**: Tool errors if multiple devices detected

### Web UI
- **Goal**: Browser-based configuration interface
- **Implementation**:
  - Simple Flask or FastAPI server
  - Configure profiles and rules via web form
  - Show sync history and logs
  - Start/stop syncs from browser
- **Complexity**: High
- **Benefit**: Easier for non-technical users

### Scheduled Syncs (Cron)
- **Goal**: Run syncs on a schedule even if phone not connected
- **Implementation**:
  - Add to crontab: `0 * * * * phone-sync --run`
  - Tool checks if device connected, exits quietly if not
  - Useful if phone is always charging at desk
- **Current support**: Can already do this manually

## Documentation

### Video Tutorial
- Record screen demo showing:
  - First time setup
  - Adding rules
  - Running sync
  - Troubleshooting
- Upload to YouTube or host locally

### FAQ Document
- Collect common questions and answers
- Add to README or separate FAQ.md

## Testing

### Unit Tests
- Test path normalization
- Test config loading/saving
- Test device fingerprinting
- Mock gio commands for testing

### Integration Tests
- Test with actual MTP device (if available)
- Test edge cases:
  - Empty directories
  - Special characters in filenames
  - Very large files
  - Disconnection during transfer

### CI/CD
- GitHub Actions for linting
- Run unit tests on commit
- Test on multiple Python versions

## Performance

### Profiling
- Profile slow operations
- Optimize gio command invocations
- Cache repeated gio info calls

### Benchmarking
- Measure transfer speeds
- Compare with manual copy via file manager
- Document performance characteristics

## Notes

- Keep core features simple and reliable
- Only add features that provide real value
- Test thoroughly before marking as complete
- Consider user feedback before implementing low-priority items
- Maintain backward compatibility with config file format
