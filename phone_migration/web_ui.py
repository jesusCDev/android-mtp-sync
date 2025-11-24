"""Web UI for Phone Migration Tool using Flask."""

import json
import sys
import io
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

from . import config as cfg, device, runner, operations, browser


app = Flask(__name__, 
            template_folder='web_templates',
            static_folder='static',
            static_url_path='/static')
CORS(app)  # Enable CORS for API requests

# Disable aggressive caching during development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['CACHE_TYPE'] = 'null'

# Disable Flask's caching for templates
@app.after_request
def add_no_cache_headers(response):
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.must_revalidate = True
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Global state
current_run_status = {
    "running": False,
    "progress": 0,
    "current_rule": None,
    "stats": {},
    "logs": []
}

# History storage file path
HISTORY_FILE = Path.home() / ".config" / "phone-migration" / "history.json"

# History storage (persisted to disk)
run_history = []


def load_history():
    """Load history from disk."""
    global run_history
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r') as f:
                run_history = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load history: {e}")
        run_history = []


def save_history():
    """Save history to disk."""
    try:
        # Ensure directory exists
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Write history to file
        with open(HISTORY_FILE, 'w') as f:
            json.dump(run_history, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save history: {e}")


@app.route('/')
def index():
    """Dashboard page."""
    return render_template('dashboard.html')


@app.route('/profiles')
def profiles():
    """Profiles management page."""
    return render_template('profiles.html')


@app.route('/rules')
def rules():
    """Rules management page."""
    return render_template('rules.html')


@app.route('/history')
def history():
    """History/logs page."""
    return render_template('history.html')


@app.route('/documentation')
def documentation():
    """Documentation page."""
    return render_template('documentation.html')


# === API Routes ===

@app.route('/api/status')
def api_status():
    """Get current system status."""
    from . import gio_utils, paths
    config = cfg.load_config()
    
    # Detect connected device
    profile = runner.detect_connected_device(config, verbose=False)
    
    if profile:
        device_info = profile.get("device", {})
        activation_uri = device_info.get("activation_uri", "")
        
        # Check device accessibility with a quick check
        # Use gio_info on the device root - faster than mounting
        accessible = False
        if activation_uri:
            try:
                from . import gio_utils
                # Quick check: try to get info on device root
                # This is faster and more reliable than gio mount
                info = gio_utils.gio_info(activation_uri, timeout=2)
                # If we get any info back, device is accessible
                accessible = bool(info)
            except Exception:
                # Any error = not accessible right now
                accessible = False
        
        return jsonify({
            "connected": True,
            "accessible": accessible,
            "device_name": device_info.get("display_name", "Unknown"),
            "profile_name": profile.get("name", "unknown"),
            "rule_count": len(profile.get("rules", []))
        })
    else:
        return jsonify({
            "connected": False,
            "accessible": False,
            "device_name": None,
            "profile_name": None,
            "rule_count": 0
        })


@app.route('/api/profiles', methods=['GET', 'POST'])
def api_profiles():
    """Get all profiles or create a new profile."""
    if request.method == 'POST':
        # Create a new profile
        data = request.json
        profile_name = data.get("name")
        device_id = data.get("device_id")
        
        if not profile_name or not device_id:
            return jsonify({"error": "Profile name and device_id are required"}), 400
        
        config = cfg.load_config()
        
        # Check if profile already exists
        if cfg.find_profile(config, profile_name):
            return jsonify({"error": f"Profile '{profile_name}' already exists"}), 409
        
        try:
            # Get connected devices to find the one matching device_id
            devices = device.enumerate_mtp_mounts()
            matching_device = None
            
            for d in devices:
                import re
                activation_uri = d.get("activation_uri", "")
                mtp_match = re.search(r'mtp://\[([^\]]+)\]', activation_uri)
                mtp_id = mtp_match.group(1) if mtp_match else activation_uri
                
                if mtp_id == device_id:
                    matching_device = d
                    break
            
            if not matching_device:
                return jsonify({"error": "Device not found or not connected"}), 404
            
            # Get device fingerprint for unique identification
            id_type, id_value = device.device_fingerprint(matching_device, verbose=False)
            
            # Create profile
            profile = {
                "name": profile_name,
                "device": {
                    "display_name": matching_device.get("display_name", "Unknown Device"),
                    "id_type": id_type,
                    "id_value": id_value,
                    "activation_uri": matching_device.get("activation_uri", "")
                },
                "rules": []
            }
            
            cfg.add_profile(config, profile)
            cfg.save_config(config)
            
            return jsonify({"success": True, "message": f"Profile '{profile_name}' created"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # GET: Return all profiles
    config = cfg.load_config()
    profiles = config.get("profiles", [])
    
    # Enrich profiles with rule counts
    result = []
    for profile in profiles:
        result.append({
            "profile_name": profile.get("name", "unknown"),
            "device_name": profile.get("device", {}).get("display_name", "Unknown"),
            "mtp_id": profile.get("device", {}).get("mtp_id", "unknown"),
            "rules_count": len(profile.get("rules", []))
        })
    
    return jsonify(result)


@app.route('/api/profiles/<profile_name>/rules')
def api_profile_rules(profile_name):
    """Get rules for a specific profile."""
    config = cfg.load_config()
    profile = cfg.find_profile(config, profile_name)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    
    return jsonify({
        "profile": profile_name,
        "rules": profile.get("rules", [])
    })


@app.route('/api/rules', methods=['POST'])
def api_add_rule():
    """Add a new rule."""
    data = request.json
    config = cfg.load_config()
    
    profile_name = data.get("profile")
    mode = data.get("mode")
    phone_path = data.get("phone_path")
    desktop_path = data.get("desktop_path")
    manual_only = data.get("manual_only", False)
    
    if not all([profile_name, mode, phone_path, desktop_path]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        if mode == "move":
            cfg.add_move_rule(config, profile_name, phone_path, desktop_path, manual_only)
        elif mode == "copy":
            cfg.add_copy_rule(config, profile_name, phone_path, desktop_path, manual_only)
        elif mode in ["backup", "smart_copy"]:
            cfg.add_backup_rule(config, profile_name, phone_path, desktop_path, manual_only)
        elif mode == "sync":
            cfg.add_sync_rule(config, profile_name, desktop_path, phone_path, manual_only)
        else:
            return jsonify({"error": f"Invalid mode: {mode}"}), 400
        
        cfg.save_config(config)
        return jsonify({"success": True, "message": f"{mode.title()} rule added"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/rules/<profile_name>/<rule_id>', methods=['DELETE'])
def api_delete_rule(profile_name, rule_id):
    """Delete a rule."""
    config = cfg.load_config()
    
    try:
        cfg.remove_rule(config, profile_name, rule_id)
        cfg.save_config(config)
        return jsonify({"success": True, "message": "Rule deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/run', methods=['POST'])
def api_run():
    """Execute configured rules."""
    if current_run_status["running"]:
        return jsonify({"error": "A run is already in progress"}), 409
    
    data = request.json or {}
    rule_ids = data.get("rule_ids")  # Optional: specific rules to run
    dry_run = data.get("dry_run", False)
    include_manual = data.get("include_manual", False)
    notify = data.get("notify", False)
    rename_duplicates = data.get("rename_duplicates", True)  # Default to True for backward compatibility
    
    # Start run in background thread
    def run_sync():
        global current_run_status, run_history
        current_run_status["running"] = True
        current_run_status["progress"] = 0
        current_run_status["logs"] = []
        current_run_status["stats"] = {"moved": 0, "backed_up": 0, "synced": 0, "errors": 0}
        
        start_time = datetime.now()
        profile_name = "Unknown"
        rules_count = 0
        
        # Capture stdout to get CLI output
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            config = cfg.load_config()
            profile = runner.detect_connected_device(config, verbose=False)
            
            if profile:
                profile_name = profile.get("name", "Unknown")
                # Count rules (exclude manual if not included)
                all_rules = profile.get("rules", [])
                if not include_manual:
                    rules_count = len([r for r in all_rules if not r.get("manual_only", False)])
                else:
                    rules_count = len(all_rules)
            
            # Run with captured output (verbose=True for detailed file info in web UI)
            runner.run_for_connected_device(
                config, 
                verbose=True, 
                dry_run=dry_run, 
                rule_ids=rule_ids,
                notify=notify,
                include_manual=include_manual,
                rename_duplicates=rename_duplicates
            )
            
            # Get captured output and strip ANSI codes
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            
            # Strip ANSI color codes for web display
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_output = ansi_escape.sub('', output)
            
            # Split into lines and add to logs
            for line in clean_output.split('\n'):
                if line.strip():
                    current_run_status["logs"].append(line)
            
            current_run_status["progress"] = 100
            status = "success"
        except Exception as e:
            sys.stdout = old_stdout
            current_run_status["logs"].append(f"❌ Error: {str(e)}")
            current_run_status["stats"]["errors"] = current_run_status["stats"].get("errors", 0) + 1
            status = "error"
        finally:
            # Ensure stdout is restored
            if sys.stdout != old_stdout:
                sys.stdout = old_stdout
            current_run_status["running"] = False
            
            # Save to history
            run_history.insert(0, {
                "timestamp": start_time.isoformat(),
                "profile": profile_name,
                "rules_count": rules_count,
                "status": status,
                "stats": dict(current_run_status["stats"]),
                "logs": list(current_run_status["logs"])
            })
            
            # Keep only last 100 runs
            if len(run_history) > 100:
                run_history.pop()
            
            # Persist to disk
            save_history()
    
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Run started"})


@app.route('/api/run/status')
def api_run_status():
    """Get current run status."""
    # Parse stats from logs
    stats = {"copied": 0, "skipped": 0, "deleted": 0, "errors": 0, "synced": 0}
    
    for log_line in current_run_status.get("logs", []):
        import re
        
        # Parse Copied: X
        copied_match = re.search(r'Copied:\s*(\d+)', log_line)
        if copied_match:
            stats["copied"] = max(stats["copied"], int(copied_match.group(1)))
        
        # Parse Skipped: X or Exists: X
        skipped_match = re.search(r'(?:Skipped|Exists):\s*(\d+)', log_line)
        if skipped_match:
            stats["skipped"] = max(stats["skipped"], int(skipped_match.group(1)))
        
        # Parse Deleted: X
        deleted_match = re.search(r'Deleted:\s*(\d+)', log_line)
        if deleted_match:
            stats["deleted"] = max(stats["deleted"], int(deleted_match.group(1)))
        
        # Parse Synced: X
        synced_match = re.search(r'Synced:\s*(\d+)', log_line)
        if synced_match:
            stats["synced"] = max(stats["synced"], int(synced_match.group(1)))
        
        # Parse smart-copy progress
        progress_match = re.search(r'\[(\d+)/(\d+)\s*-\s*([\d.]+)%\]', log_line)
        if progress_match:
            current_run_status["stats"]["smart_copy_current"] = int(progress_match.group(1))
            current_run_status["stats"]["smart_copy_total"] = int(progress_match.group(2))
    
    # Parse errors from logs
    for log_line in current_run_status.get("logs", []):
        import re
        errors_match = re.search(r'(?:Errors|Error):\s*(\d+)', log_line)
        if errors_match:
            stats["errors"] = max(stats["errors"], int(errors_match.group(1)))
    
    # Return status with parsed stats
    result = dict(current_run_status)
    result["stats"] = stats
    return jsonify(result)


@app.route('/api/device/detect')
def api_device_detect():
    """Detect connected MTP devices."""
    devices = device.enumerate_mtp_mounts()
    
    result = []
    for d in devices:
        activation_uri = d.get("activation_uri", "")
        # Extract MTP ID from URI (e.g., "mtp://[usb:003,009]/" -> "usb:003,009")
        import re
        mtp_match = re.search(r'mtp://\[([^\]]+)\]', activation_uri)
        mtp_id = mtp_match.group(1) if mtp_match else activation_uri
        
        result.append({
            "device_name": d.get("display_name", "Unknown"),
            "mtp_id": mtp_id,
            "activation_uri": activation_uri,
            "default_location": d.get("default_location", "")
        })
    
    return jsonify(result)


@app.route('/api/device/unregistered')
def api_device_unregistered():
    """Detect connected MTP devices that don't have a matching profile."""
    import re
    config = cfg.load_config()
    devices = device.enumerate_mtp_mounts()
    
    unregistered = []
    for d in devices:
        # Get device fingerprint
        id_type, id_value = device.device_fingerprint(d, verbose=False)
        
        # Check if profile exists for this device
        profile = cfg.find_profile_by_device_id(config, id_type, id_value)
        if not profile:
            # Device not registered
            activation_uri = d.get("activation_uri", "")
            mtp_match = re.search(r'mtp://\[([^\]]+)\]', activation_uri)
            mtp_id = mtp_match.group(1) if mtp_match else activation_uri
            
            unregistered.append({
                "device_name": d.get("display_name", "Unknown"),
                "mtp_id": mtp_id,
                "activation_uri": activation_uri,
                "id_type": id_type,
                "id_value": id_value
            })
    
    return jsonify(unregistered)


@app.route('/api/device/register', methods=['POST'])
def api_device_register():
    """Register a new device."""
    data = request.json
    profile_name = data.get("profile_name")
    device_name = data.get("device_name")
    mtp_id = data.get("mtp_id")
    
    if not all([profile_name, device_name, mtp_id]):
        return jsonify({"error": "Missing required fields"}), 400
    
    config = cfg.load_config()
    
    # Check if profile already exists
    if cfg.find_profile(config, profile_name):
        return jsonify({"error": f"Profile '{profile_name}' already exists"}), 409
    
    try:
        # Add profile directly
        cfg.add_profile(
            config,
            profile_name=profile_name,
            device_name=device_name,
            mtp_id=mtp_id
        )
        cfg.save_config(config)
        return jsonify({"success": True, "message": f"Device registered as '{profile_name}'"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/profiles/<profile_name>', methods=['PUT'])
def api_update_profile(profile_name):
    """Update a profile (e.g., rename)."""
    data = request.json
    new_name = data.get("name")
    
    if not new_name:
        return jsonify({"error": "Profile name is required"}), 400
    
    config = cfg.load_config()
    profile = cfg.find_profile(config, profile_name)
    
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    
    # Check if new name already exists (if different from current)
    if new_name != profile_name:
        if cfg.find_profile(config, new_name):
            return jsonify({"error": f"Profile '{new_name}' already exists"}), 409
    
    try:
        profile["name"] = new_name
        cfg.save_config(config)
        return jsonify({"success": True, "message": "Profile updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/profiles/<profile_name>', methods=['DELETE'])
def api_delete_profile(profile_name):
    """Delete a profile."""
    config = cfg.load_config()
    
    profile = cfg.find_profile(config, profile_name)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    
    try:
        config["profiles"] = [p for p in config.get("profiles", []) if p.get("name") != profile_name]
        cfg.save_config(config)
        return jsonify({"success": True, "message": "Profile deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/history')
def api_history():
    """Get operation history."""
    limit = request.args.get('limit', 10, type=int)
    
    # Return the requested number of history items
    return jsonify(run_history[:limit])


@app.route('/api/browse/phone')
def api_browse_phone():
    """Browse phone directories."""
    phone_path = request.args.get('path', '/')
    
    # Detect connected device
    config = cfg.load_config()
    profile = runner.detect_connected_device(config, verbose=False)
    
    if not profile:
        return jsonify({"error": "No device connected"}), 409
    
    device_info = profile.get("device", {})
    activation_uri = device_info.get("activation_uri", "")
    
    if not activation_uri:
        return jsonify({"error": "Device activation URI not found"}), 500
    
    try:
        # Use browser.list_phone_directory to get contents
        entries_raw = browser.list_phone_directory(activation_uri, phone_path)
        
        # Transform to API format
        entries = []
        for entry in entries_raw:
            entries.append({
                "name": entry["name"],
                "path": entry["path"],
                "type": "dir" if entry["is_directory"] else "file",
                "size": entry.get("size", 0)
            })
        
        return jsonify({
            "path": phone_path,
            "entries": entries,
            "deviceConnected": True
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/folder/create', methods=['POST'])
def api_create_folder():
    """Create a new folder on desktop."""
    import os
    
    data = request.json
    folder_path = data.get('path')
    
    if not folder_path:
        return jsonify({"error": "Path is required"}), 400
    
    try:
        # Normalize and expand path
        resolved_path = os.path.abspath(os.path.expanduser(folder_path))
        
        # Check if already exists
        if os.path.exists(resolved_path):
            return jsonify({"error": "Folder already exists"}), 409
        
        # Create the folder
        os.makedirs(resolved_path, exist_ok=False)
        
        return jsonify({"success": True, "path": resolved_path})
    
    except PermissionError:
        return jsonify({"error": "Permission denied"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/browse/desktop')
def api_browse_desktop():
    """Browse desktop directories."""
    import os
    from pathlib import Path
    
    desktop_path = request.args.get('path', str(Path.home()))
    
    # Normalize and resolve path
    try:
        resolved_path = os.path.abspath(os.path.expanduser(desktop_path))
        
        if not os.path.exists(resolved_path):
            return jsonify({"error": "Directory not found"}), 404
        
        if not os.path.isdir(resolved_path):
            return jsonify({"error": "Path is not a directory"}), 400
        
        # List directory contents
        entries = []
        try:
            with os.scandir(resolved_path) as it:
                for entry in it:
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        entries.append({
                            "name": entry.name,
                            "path": entry.path,
                            "type": "dir" if is_dir else "file"
                        })
                    except (PermissionError, OSError):
                        # Skip entries we can't access
                        continue
        except PermissionError:
            return jsonify({"error": "Permission denied"}), 403
        
        # Sort: directories first, then alphabetically
        entries.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
        
        # Check if we can go up
        can_go_up = resolved_path != '/'
        
        return jsonify({
            "path": resolved_path,
            "entries": entries,
            "canGoUp": can_go_up
        })
    
    except PermissionError:
        return jsonify({"error": "Permission denied"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def start_web_ui(host='127.0.0.1', port=8080, debug=False):
    """Start the web UI server."""
    # Load history from disk on startup
    load_history()
    
    print(f"\n{'='*60}")
    print(f"📱 Phone Migration Tool - Web UI")
    print(f"{'='*60}\n")
    print(f"🌐 Server starting on http://{host}:{port}")
    print(f"   Open this URL in your browser to access the interface\n")
    print(f"   Press Ctrl+C to stop the server\n")
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    start_web_ui(debug=True)
