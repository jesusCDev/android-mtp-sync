# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Web UI - Operation Details Modal**: Click "Expand" on any operation card to view detailed file-level information
  - **Command View**: Shows the exact command that was/will be executed with color-coded syntax
  - **Detail View** (for Move/Copy/Smart Copy): Lists individual files being copied, deleted, or skipped
  - **Sync Summary**: Displays sync operation statistics (files synced, skipped, cleaned)
- **Per-Operation Expand Buttons**: Each operation card now has an individual expand button for detailed inspection
- **Verbose Mode in Web UI**: Web UI now runs with `verbose=True` by default to show file-level details
  - Enables detailed file listings in operation modals
  - CLI remains unchanged (defaults to `verbose=False` for clean output)
- **Tab-Based Detail View**: Two-tab interface for detailed operation inspection
  - Tab A: Command View - Shows formatted command with color-coded flags and parameters
  - Tab B: Detail View - Lists files by category (Copying, Deleting, Skipped, Folders)
- **Modal Dialogs**: Full-screen modal for detailed operation inspection
  - Click outside or press Escape to close
  - Close button (X) in top-right corner

### Changed
- **Color Palette Update**: Replaced harsh colors with soft pastel tones
  - Accent: `#8B5CF6` → `#C8A2E0` (soft lavender)
  - Info: `#60A5FA` → `#9DD4FF` (soft sky blue)
  - Success: `#10B981` → `#8FD6B5` (soft mint green)
  - Warning: `#F59E0B` → `#FFD699` (soft peachy-gold)
  - Danger: `#EF4444` → `#FF9898` (soft coral red)
  - Overall theme: More pleasant and easier on the eyes
- **Run Page Removed**: Run Operations moved from separate `/run` page to dashboard (home page)
  - Streamlined navigation with single-page operation interface
  - Command preview and operations displayed in one place

### Removed
- **run.html**: Removed separate Run page template
- **run.js**: Consolidated functionality into dashboard.js
- **run.css**: Migrated styles to dashboard.css

### Technical Details
- **File Operation Parsing**: Improved parsing of CLI output to extract file-level details
  - Supports Move, Copy, Smart Copy, and Sync operations
  - Parses file paths with arrow symbols (→, ->, =>)
  - Extracts deletion markers (×) and skip indicators (⊙)
  - Shows folder operations with 📦 symbol
- **Log Storage**: Each operation stores its associated log lines for detailed inspection
- **Modal Management**: Modals use data attributes to store operation data and logs for inspection

### Web UI Improvements
- **Dashboard Consolidation**: All run operations now on the main dashboard
- **Enhanced Command Preview**: 
  - Shows exact command that will execute
  - Color-coded syntax highlighting
  - Warning indicator for execute mode vs. dry-run
- **Operation Cards**: Each rule execution shows in a separate, expandable card
- **Responsive Design**: Modal adapts to screen size

### User Experience
- Users can now preview exactly what files will be affected before running operations
- Detailed file lists help verify sync/move/copy operations are correct
- Soft color palette reduces eye strain during extended use
- Cleaner UI with removed Run page

## [Previous Versions]

See git history for earlier versions.
