"""
Status checker for VOD Archiver
Shows if it's running, recent activity, and next check time.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess


def is_running() -> bool:
    """Check if the archiver process is running."""
    try:
        # Check for scheduled task
        result = subprocess.run(
            ["powershell", "-Command", 
             "Get-ScheduledTask -TaskName 'TwitchVODArchiver' | Select-Object -ExpandProperty State"],
            capture_output=True,
            text=True,
            timeout=5
        )
        state = result.stdout.strip()
        return state == "Running"
    except:
        # Fallback: check for python process with our script
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Check if any python process has our script path
            script_dir = Path(__file__).parent.absolute()
            return str(script_dir) in result.stdout
        except:
            return False


def get_recent_logs(log_file: str = "archiver.log", lines: int = 20) -> list[str]:
    """Get recent log entries."""
    if not os.path.exists(log_file):
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:] if line.strip()]
    except Exception as e:
        return [f"Error reading log: {e}"]


def get_processed_vods() -> list[dict]:
    """Get list of processed VODs with metadata."""
    processed_file = "processed_vods.json"
    if not os.path.exists(processed_file):
        return []
    
    try:
        with open(processed_file, 'r') as f:
            vod_ids = json.load(f)
            return [{"id": vid, "processed": True} for vid in vod_ids]
    except:
        return []


def get_config() -> dict:
    """Load config to get poll interval."""
    try:
        with open("config.json", 'r') as f:
            return json.load(f)
    except:
        return {"settings": {"poll_interval_minutes": 15}}


def parse_log_for_activity(log_lines: list[str]) -> dict:
    """Parse log lines to extract key activity."""
    activity = {
        "last_check": None,
        "last_vod_processed": None,
        "last_error": None,
        "vods_found_today": 0,
        "vods_uploaded_today": 0,
    }
    
    today = datetime.now().date()
    
    for line in log_lines:
        if "Starting check cycle" in line:
            # Extract timestamp
            try:
                parts = line.split(" | ")
                if len(parts) >= 1:
                    timestamp_str = parts[0]
                    activity["last_check"] = timestamp_str
            except:
                pass
        
        if "Found" in line and "new VOD" in line:
            activity["vods_found_today"] += 1
        
        if "Successfully archived VOD" in line:
            activity["vods_uploaded_today"] += 1
            activity["last_vod_processed"] = line
        
        if "ERROR" in line or "Failed" in line:
            activity["last_error"] = line
    
    return activity


def main():
    """Print status information."""
    print("=" * 60)
    print("  VOD Archiver Status")
    print("=" * 60)
    print()
    
    # Check if running
    running = is_running()
    status_icon = "✓" if running else "✗"
    status_text = "RUNNING" if running else "NOT RUNNING"
    print(f"Status: {status_text} {status_icon}")
    print()
    
    # Get config
    config = get_config()
    poll_interval = config.get("settings", {}).get("poll_interval_minutes", 15)
    channel = config.get("twitch", {}).get("channel_name", "unknown")
    
    print(f"Channel: {channel}")
    print(f"Poll interval: {poll_interval} minutes")
    print()
    
    # Get recent activity
    log_lines = get_recent_logs()
    if log_lines:
        activity = parse_log_for_activity(log_lines)
        
        if activity["last_check"]:
            print(f"Last check: {activity['last_check']}")
        
        if activity["vods_found_today"] > 0:
            print(f"VODs found today: {activity['vods_found_today']}")
        
        if activity["vods_uploaded_today"] > 0:
            print(f"VODs uploaded today: {activity['vods_uploaded_today']}")
        
        if activity["last_vod_processed"]:
            print(f"Last processed: {activity['last_vod_processed']}")
        
        if activity["last_error"]:
            print(f"Last error: {activity['last_error']}")
        
        print()
        print("Recent log entries:")
        print("-" * 60)
        for line in log_lines[-10:]:
            print(line)
    else:
        print("No log file found or log is empty.")
    
    print()
    print("=" * 60)
    
    # Show processed VODs count
    processed = get_processed_vods()
    if processed:
        print(f"Total VODs processed: {len(processed)}")
    
    print()
    print("Commands:")
    print("  Stop:  Stop-ScheduledTask -TaskName 'TwitchVODArchiver'")
    print("  Start: Start-ScheduledTask -TaskName 'TwitchVODArchiver'")
    print("  View:  Open dashboard.html in your browser")


if __name__ == "__main__":
    main()
