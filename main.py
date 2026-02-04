"""
Twitch VOD to YouTube Archiver
Main orchestration script that monitors for new VODs, downloads, and uploads them.
"""

import json
import time
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from twitch_api import TwitchAPI
from downloader import VODDownloader
from youtube_upload import YouTubeUploader
from web.dashboard_server import DashboardServer


def setup_logging(log_file: str = "archiver.log") -> logging.Logger:
    """Set up logging to both file and console."""
    logger = logging.getLogger("VODArchiver")
    logger.setLevel(logging.INFO)
    
    # File handler with rotation (max 5MB, keep 3 backups)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    file_handler.setFormatter(file_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Global logger
log = setup_logging()


class VODArchiver:
    """Main orchestrator for archiving Twitch VODs to YouTube."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.processed_file = "processed_vods.json"
        
        # Initialize components
        self.twitch = TwitchAPI(
            self.config["twitch"]["client_id"],
            self.config["twitch"]["client_secret"]
        )
        self.downloader = VODDownloader(
            self.config["settings"]["download_dir"]
        )
        self.uploader = YouTubeUploader(
            self.config["youtube"]["client_secrets_file"],
            self.config["youtube"]["credentials_file"]
        )
        
        # Load processed VODs
        self.processed_vods = self._load_processed()
        
        # Migrate old format to new format if needed
        self._migrate_processed_format()
        
        # Initialize playlist (will be created on first use)
        self.playlist_id = None
    


    
    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        with open(self.config_path) as f:
            return json.load(f)
    
    def _load_processed(self) -> dict:
        """Load dictionary of processed VODs with metadata."""
        try:
            with open(self.processed_file) as f:
                data = json.load(f)
                # Handle old format (list of IDs) for backward compatibility
                if isinstance(data, list):
                    # Convert old format to new format
                    return {vod_id: {"twitch_id": vod_id} for vod_id in data}
                # New format (dict mapping VOD ID to metadata)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_processed(self):
        """Save processed VODs to file."""
        with open(self.processed_file, "w") as f:
            json.dump(self.processed_vods, f, indent=2)
    
    def _migrate_processed_format(self):
        """Migrate old format (list) to new format (dict) if needed and save immediately."""
        # Check if file needs migration by reading it directly
        try:
            with open(self.processed_file) as f:
                raw_data = json.load(f)
                # If it's still in old format (list), migrate it
                if isinstance(raw_data, list):
                    log.info(f"Migrating {len(raw_data)} VODs from old format to new format...")
                    # Convert to new format
                    self.processed_vods = {
                        vod_id: {
                            "twitch_id": vod_id,
                            "youtube_id": None,  # Can't retroactively get this
                            "title": None,
                            "uploaded_at": None
                        }
                        for vod_id in raw_data
                    }
                    # Save immediately
                    self._save_processed()
                    log.info("Migration complete. Old VODs won't have YouTube links.")
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # File doesn't exist or is already in new format
    
    def _mark_processed(self, vod_id: str, youtube_id: str = None, title: str = None, stream_date: str = None):
        """Mark a VOD as processed and save with metadata."""
        self.processed_vods[vod_id] = {
            "twitch_id": vod_id,
            "youtube_id": youtube_id,
            "title": title,
            "stream_date": stream_date,  # When the Twitch stream happened
            "uploaded_at": datetime.now().isoformat()  # When we uploaded to YouTube
        }
        self._save_processed()
    
    def _format_description(self, vod: dict) -> str:
        """Create YouTube description from VOD metadata."""
        return f"""Archived from Twitch: {vod['url']}

Original stream date: {vod['created_at']}
Duration: {vod['duration']}

{vod.get('description', '')}

---
Automatically archived from Twitch VOD.
"""
    
    def process_vod(self, vod: dict) -> bool:
        """
        Process a single VOD: download and upload.
        
        Returns True if successful, False otherwise.
        """
        vod_id = vod["id"]
        title = vod["title"]
        
        log.info("=" * 60)
        log.info(f"Processing VOD: {title}")
        log.info(f"ID: {vod_id}")
        log.info(f"Duration: {vod['duration']}")
        log.info("=" * 60)
        
        # Download
        file_path = self.downloader.download(
            vod["url"], 
            vod_id, 
            title,
            channel_name=self.config["twitch"]["channel_name"],
            created_at=vod["created_at"]
        )
        if not file_path:
            log.error(f"Failed to download VOD {vod_id}")
            # Clean up any partial downloads
            self._cleanup_partial_downloads(vod_id)
            return False
        
        # Upload to YouTube
        video_id = self.uploader.upload(
            video_path=file_path,
            title=title,
            description=self._format_description(vod),
            privacy_status=self.config["youtube"]["privacy_status"],
            tags=["Twitch", "VOD", "Archive", self.config["twitch"]["channel_name"]],
            playlist_id=self.playlist_id
        )
        
        if not video_id:
            log.error(f"Failed to upload VOD {vod_id}")
            # Keep the downloaded file for retry
            return False
        
        # Success - clean up and mark as processed
        if self.config["settings"]["delete_after_upload"]:
            self.downloader.delete(file_path)
        
        self._mark_processed(vod_id, youtube_id=video_id, title=title, stream_date=vod.get("created_at"))
        log.info(f"Successfully archived VOD {vod_id} -> YouTube: {video_id}")
        return True
    
    def _cleanup_partial_downloads(self, vod_id: str):
        """Clean up partial download files for a VOD."""
        downloads_dir = Path(self.config["settings"]["download_dir"])
        if not downloads_dir.exists():
            return
        
        # Find all files related to this VOD
        for file_path in downloads_dir.iterdir():
            if file_path.name.startswith(f"{vod_id}_"):
                try:
                    # Only delete partial files (not completed downloads)
                    if file_path.suffix in ['.part', '.ytdl'] or '.part-Frag' in file_path.name:
                        file_path.unlink()
                        log.info(f"Cleaned up partial download: {file_path.name}")
                except Exception as e:
                    log.warning(f"Failed to clean up {file_path.name}: {e}")
    
    def check_for_new_vods(self) -> list[dict]:
        """Check for new VODs that haven't been processed yet."""
        channel = self.config["twitch"]["channel_name"]
        log.info(f"Checking for new VODs from {channel}...")
        
        vods = self.twitch.get_channel_vods(channel, limit=10)
        
        new_vods = []
        for vod in vods:
            vod_id = vod["id"]
            if vod_id not in self.processed_vods:
                new_vods.append(vod)
            else:
                # Log why it's being skipped
                processed_info = self.processed_vods[vod_id]
                youtube_id = processed_info.get("youtube_id")
                if youtube_id:
                    log.info(f"Skipping VOD {vod_id} - already uploaded to YouTube: {youtube_id}")
                else:
                    log.info(f"Skipping VOD {vod_id} - already marked as processed")
        
        if new_vods:
            log.info(f"Found {len(new_vods)} new VOD(s)")
        else:
            log.info("No new VODs found")
        
        return new_vods
    
    def run_once(self) -> int:
        """
        Run a single check and process cycle.
        
        Returns number of VODs successfully processed.
        """
        new_vods = self.check_for_new_vods()
        
        if not new_vods:
            return 0
        
        # Authenticate YouTube upfront
        if not self.uploader.authenticate():
            log.error("YouTube authentication failed, skipping this cycle")
            return 0
        
        # Get or create playlist for this channel
        if not self.playlist_id:
            channel_name = self.config["twitch"]["channel_name"]
            playlist_title = f"{channel_name} VOD Archive"
            playlist_description = f"Automatically archived Twitch VODs from {channel_name}"
            self.playlist_id = self.uploader.get_or_create_playlist(playlist_title, playlist_description)
            if not self.playlist_id:
                log.warning("Could not create/get playlist, videos will still be uploaded")
        
        success_count = 0
        for vod in new_vods:
            if self.process_vod(vod):
                success_count += 1
            else:
                log.warning("Stopping due to failure. Will retry next cycle.")
                break
        
        return success_count
    
    def run_loop(self):
        """Run the archiver in a continuous loop."""
        poll_interval = self.config["settings"]["poll_interval_minutes"]
        dashboard_port = self.config.get("settings", {}).get("dashboard_port", 8000)
        
        log.info("#" * 60)
        log.info("  Twitch VOD Archiver")
        log.info(f"  Channel: {self.config['twitch']['channel_name']}")
        log.info(f"  Poll interval: {poll_interval} minutes")
        log.info("#" * 60)
        
        # Start dashboard server
        dashboard = DashboardServer(port=dashboard_port)
        dashboard.start()
        log.info(f"Dashboard available at: http://localhost:{dashboard_port}/web/dashboard.html")
        
        # Authenticate YouTube at startup (non-blocking - will retry in first cycle)
        log.info("YouTube authentication will be attempted during first check cycle")
        
        while True:
            try:
                log.info("Starting check cycle...")
                
                processed = self.run_once()
                
                if processed > 0:
                    log.info(f"Processed {processed} VOD(s) this cycle")
                
                log.info(f"Sleeping for {poll_interval} minutes...")
                time.sleep(poll_interval * 60)
                
            except KeyboardInterrupt:
                log.info("Shutting down...")
                break
            except Exception as e:
                log.exception(f"Error in main loop: {e}")
                log.info(f"Retrying in {poll_interval} minutes...")
                time.sleep(poll_interval * 60)


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Twitch VOD to YouTube Archiver")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't loop)"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config file (default: config.json)"
    )
    args = parser.parse_args()
    
    archiver = VODArchiver(config_path=args.config)
    
    if args.once:
        count = archiver.run_once()
        log.info(f"Processed {count} VOD(s)")
    else:
        archiver.run_loop()


if __name__ == "__main__":
    main()


