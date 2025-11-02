"""Web UI for Phone Migration Tool using Flask."""

import json
import threading
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

from . import config as cfg, device, runner, operations


app = Flask(__name__, 
            template_folder='web_templates',
            static_folder='web_static')
CORS(app)  # Enable CORS for API requests

# Global state
current_run_status = {
    "running": False,
    "progress": 0,
    "current_rule": None,
    "stats": {},
    "logs": []
}


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


@app.route('/run')
def run_page():
    """Run operations page."""
    return render_template('run.html')


@app.route('/history')
def history():
    """History/logs page."""
    return render_template('history.html')


# === API Routes ===

@app.route('/api/status')
def api_status():
    """Get current system status."""
    config = cfg.load_config()
    
    # Detect connected device
    profile = runner.detect_connected_device(config, verbose=False)
    
    if profile:
        device_info = profile.get("device", {})
        return jsonify({
            "connected": True,
            "device_name": device_info.get("display_name", "Unknown"),
            "profile_name": profile.get("name", "unknown"),
            "rule_count": len(profile.get("rules", []))
        })
    else:
        return jsonify({
            "connected": False,
            "device_name": None,
            "profile_name": None,
            "rule_count": 0
        })


@app.route('/api/profiles')
def api_profiles():
    """Get all profiles."""
    config = cfg.load_config()
    profiles = config.get("profiles", [])
    
    return jsonify({
        "profiles": profiles
    })


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
        elif mode == "smart_copy":
            cfg.add_smart_copy_rule(config, profile_name, phone_path, desktop_path, manual_only)
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
    
    data = request.json
    rule_ids = data.get("rule_ids")  # Optional: specific rules to run
    notify = data.get("notify", False)
    
    # Start run in background thread
    def run_sync():
        global current_run_status
        current_run_status["running"] = True
        current_run_status["progress"] = 0
        current_run_status["logs"] = []
        
        try:
            config = cfg.load_config()
            # Note: This runs synchronously in the thread
            # TODO: Capture output and update status in real-time
            runner.run_for_connected_device(
                config, 
                verbose=False, 
                dry_run=False, 
                rule_ids=rule_ids,
                notify=notify
            )
            
            current_run_status["progress"] = 100
            current_run_status["logs"].append("✓ All operations completed")
        except Exception as e:
            current_run_status["logs"].append(f"❌ Error: {str(e)}")
        finally:
            current_run_status["running"] = False
    
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Run started"})


@app.route('/api/run/status')
def api_run_status():
    """Get current run status."""
    return jsonify(current_run_status)


@app.route('/api/device/detect')
def api_device_detect():
    """Detect connected MTP devices."""
    devices = device.enumerate_mtp_mounts()
    
    return jsonify({
        "devices": [
            {
                "display_name": d.get("display_name", "Unknown"),
                "activation_uri": d.get("activation_uri", ""),
                "default_location": d.get("default_location", "")
            }
            for d in devices
        ]
    })


@app.route('/api/device/register', methods=['POST'])
def api_device_register():
    """Register a new device."""
    data = request.json
    profile_name = data.get("name", "default")
    
    config = cfg.load_config()
    
    try:
        device.register_current_device(config, profile_name, verbose=False)
        cfg.save_config(config)
        return jsonify({"success": True, "message": f"Device registered as '{profile_name}'"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def start_web_ui(host='127.0.0.1', port=8080, debug=False):
    """Start the web UI server."""
    print(f"\n{'='*60}")
    print(f"📱 Phone Migration Tool - Web UI")
    print(f"{'='*60}\n")
    print(f"🌐 Server starting on http://{host}:{port}")
    print(f"   Open this URL in your browser to access the interface\n")
    print(f"   Press Ctrl+C to stop the server\n")
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    start_web_ui(debug=True)
