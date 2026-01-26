# BigVods - Twitch VOD to YouTube Archiver

Automatically downloads Twitch VODs and uploads them to YouTube.

## Project Structure

```
BigVods/
├── main.py                 # Main archiver script
├── twitch_api.py           # Twitch API client
├── downloader.py           # VOD downloader
├── youtube_upload.py       # YouTube uploader
├── requirements.txt        # Python dependencies
├── config.json            # Configuration (not in git)
├── processed_vods.json    # Tracked VODs
├── archiver.log           # Log file
│
├── scripts/                # Utility scripts
│   ├── sync_playlist_links.py  # Sync YouTube playlist to VODs
│   ├── check_status.py         # Check archiver status
│   └── windows/                # Windows automation
│       ├── run_archiver.bat    # Launcher script
│       ├── run_hidden.vbs      # Hidden launcher
│       └── setup_task.ps1      # Task Scheduler setup
│
└── web/                    # Dashboard
    ├── dashboard.html      # Web dashboard
    └── dashboard_server.py # Dashboard HTTP server
```

## Setup

1. Install Python 3.11+
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Configure `config.json` with your credentials
6. Set up OAuth credentials (see below)

## Configuration

Create `config.json`:
```json
{
    "twitch": {
        "client_id": "your_twitch_client_id",
        "client_secret": "your_twitch_client_secret",
        "channel_name": "channel_name"
    },
    "youtube": {
        "client_secrets_file": "client_secrets.json",
        "credentials_file": "youtube_credentials.json",
        "privacy_status": "unlisted"
    },
    "settings": {
        "download_dir": "downloads",
        "poll_interval_minutes": 15,
        "delete_after_upload": true,
        "dashboard_port": 8000
    }
}
```

## Running

### Manual
```bash
python main.py
```

### Windows Auto-Start
1. Run `scripts\windows\setup_task.ps1` as Administrator
2. The archiver will start automatically on boot

## Dashboard

The dashboard runs automatically when the archiver starts. Access it at:
```
http://localhost:8000/web/dashboard.html
```

## Utilities

- `scripts/sync_playlist_links.py` - Sync YouTube playlist video IDs to processed VODs
- `scripts/check_status.py` - Check archiver status from command line

## Notes

- Credentials files are excluded from git (see `.gitignore`)
- Logs rotate automatically (max 5MB, 3 backups)
- Dashboard auto-refreshes every 30 seconds
