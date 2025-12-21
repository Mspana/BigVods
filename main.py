"""
Twitch VOD to YouTube Archiver
Main orchestration script that monitors for new VODs, downloads, and uploads them.
"""

import json
import time
import os
from datetime import datetime
from pathlib import Path

from twitch_api import TwitchAPI
from downloader import VODDownloader
from youtube_upload import YouTubeUploader


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
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        with open(self.config_path) as f:
            return json.load(f)
    
    def _load_processed(self) -> set:
        """Load set of already processed VOD IDs."""
        try:
            with open(self.processed_file) as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()
    
    def _save_processed(self):
        """Save processed VOD IDs to file."""
        with open(self.processed_file, "w") as f:
            json.dump(list(self.processed_vods), f, indent=2)
    
    def _mark_processed(self, vod_id: str):
        """Mark a VOD as processed and save."""
        self.processed_vods.add(vod_id)
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
        
        print(f"\n{'='*60}")
        print(f"Processing VOD: {title}")
        print(f"ID: {vod_id}")
        print(f"Duration: {vod['duration']}")
        print(f"{'='*60}\n")
        
        # Download
        file_path = self.downloader.download(vod["url"], vod_id, title)
        if not file_path:
            print(f"[Archiver] Failed to download VOD {vod_id}")
            return False
        
        # Upload to YouTube
        video_id = self.uploader.upload(
            video_path=file_path,
            title=title,
            description=self._format_description(vod),
            privacy_status=self.config["youtube"]["privacy_status"],
            tags=["Twitch", "VOD", "Archive", self.config["twitch"]["channel_name"]]
        )
        
        if not video_id:
            print(f"[Archiver] Failed to upload VOD {vod_id}")
            # Keep the downloaded file for retry
            return False
        
        # Success - clean up and mark as processed
        if self.config["settings"]["delete_after_upload"]:
            self.downloader.delete(file_path)
        
        self._mark_processed(vod_id)
        print(f"[Archiver] Successfully archived VOD {vod_id}")
        return True
    
    def check_for_new_vods(self) -> list[dict]:
        """Check for new VODs that haven't been processed yet."""
        channel = self.config["twitch"]["channel_name"]
        print(f"\n[Archiver] Checking for new VODs from {channel}...")
        
        vods = self.twitch.get_channel_vods(channel, limit=10)
        
        new_vods = [
            vod for vod in vods 
            if vod["id"] not in self.processed_vods
        ]
        
        if new_vods:
            print(f"[Archiver] Found {len(new_vods)} new VOD(s)")
        else:
            print("[Archiver] No new VODs found")
        
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
            print("[Archiver] YouTube authentication failed, skipping this cycle")
            return 0
        
        success_count = 0
        for vod in new_vods:
            if self.process_vod(vod):
                success_count += 1
            else:
                print(f"[Archiver] Stopping due to failure. Will retry next cycle.")
                break
        
        return success_count
    
    def run_loop(self):
        """Run the archiver in a continuous loop."""
        poll_interval = self.config["settings"]["poll_interval_minutes"]
        
        print(f"\n{'#'*60}")
        print(f"  Twitch VOD Archiver")
        print(f"  Channel: {self.config['twitch']['channel_name']}")
        print(f"  Poll interval: {poll_interval} minutes")
        print(f"{'#'*60}\n")
        
        # Authenticate YouTube at startup
        print("[Archiver] Authenticating with YouTube...")
        if not self.uploader.authenticate():
            print("[Archiver] Warning: YouTube auth failed. Will retry later.")
        
        while True:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] Starting check cycle...")
                
                processed = self.run_once()
                
                if processed > 0:
                    print(f"[Archiver] Processed {processed} VOD(s) this cycle")
                
                print(f"[Archiver] Sleeping for {poll_interval} minutes...")
                time.sleep(poll_interval * 60)
                
            except KeyboardInterrupt:
                print("\n[Archiver] Shutting down...")
                break
            except Exception as e:
                print(f"[Archiver] Error in main loop: {e}")
                print(f"[Archiver] Retrying in {poll_interval} minutes...")
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
        print(f"\nProcessed {count} VOD(s)")
    else:
        archiver.run_loop()


if __name__ == "__main__":
    main()


