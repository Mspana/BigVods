"""
VOD Downloader using yt-dlp.
Handles downloading Twitch VODs to local storage.
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional

import yt_dlp


def format_size(bytes_val: float) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"


def format_speed(bytes_per_sec: float) -> str:
    """Format download speed."""
    return f"{format_size(bytes_per_sec)}/s"


def format_time(seconds: float) -> str:
    """Format seconds to human readable time."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


class ProgressBar:
    """Simple ASCII progress bar."""
    
    def __init__(self, width: int = 40):
        self.width = width
        self.last_line_len = 0
    
    def update(self, percent: float, extra_info: str = ""):
        """Update the progress bar display."""
        filled = int(self.width * percent / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        line = f"\r[Download] [{bar}] {percent:5.1f}% {extra_info}"
        
        # Clear any leftover characters from previous line
        padding = max(0, self.last_line_len - len(line))
        sys.stdout.write(line + " " * padding)
        sys.stdout.flush()
        self.last_line_len = len(line)
    
    def finish(self):
        """Finish the progress bar with a newline."""
        print()


class VODDownloader:
    """Downloads Twitch VODs using yt-dlp."""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.progress_bar = ProgressBar()
        self.downloaded_file = None
    
    def sanitize_filename(self, title: str) -> str:
        """Remove invalid characters from filename."""
        # Remove characters that are invalid in Windows filenames
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace multiple spaces with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        # Trim to reasonable length
        return sanitized[:200].strip()
    
    def _find_existing_file(self, vod_id: str) -> Optional[str]:
        """Check if a file for this VOD already exists."""
        try:
            for file in self.download_dir.iterdir():
                if file.name.startswith(f"{vod_id}_") and file.is_file():
                    # Verify it's a video file and has non-zero size
                    if file.suffix.lower() in ['.mp4', '.mkv', '.webm', '.ts', '.flv'] and file.stat().st_size > 0:
                        return str(file)
        except Exception:
            pass
        return None
    
    def _progress_hook(self, d: dict):
        """Hook called by yt-dlp with download progress."""
        if d['status'] == 'downloading':
            # Get progress info
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0
            
            if total > 0:
                percent = (downloaded / total) * 100
                extra = f"| {format_size(downloaded)}/{format_size(total)} | {format_speed(speed)} | ETA: {format_time(eta)}"
                self.progress_bar.update(percent, extra)
            else:
                # No total known, show downloaded amount
                extra = f"| {format_size(downloaded)} | {format_speed(speed)}"
                self.progress_bar.update(0, extra)
                
        elif d['status'] == 'finished':
            self.progress_bar.update(100, "| Download complete, processing...")
            self.progress_bar.finish()
            self.downloaded_file = d.get('filename')
    
    def download(self, vod_url: str, vod_id: str, title: str) -> Optional[str]:
        """
        Download a Twitch VOD.
        
        Args:
            vod_url: URL to the Twitch VOD
            vod_id: Unique VOD ID (for filename)
            title: VOD title (for filename)
        
        Returns:
            Path to downloaded file, or None if failed
        """
        safe_title = self.sanitize_filename(title)
        output_template = str(self.download_dir / f"{vod_id}_{safe_title}.%(ext)s")
        
        # Check if file already exists (resume support)
        existing_file = self._find_existing_file(vod_id)
        if existing_file:
            print(f"[Downloader] Found existing file, skipping download: {existing_file}")
            return existing_file
        
        print(f"[Downloader] Downloading: {title}")
        print(f"[Downloader] URL: {vod_url}")
        
        self.downloaded_file = None
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self._progress_hook],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([vod_url])
            
            # Find the downloaded file
            if self.downloaded_file and os.path.exists(self.downloaded_file):
                print(f"[Downloader] Saved to: {self.downloaded_file}")
                return self.downloaded_file
            
            # Fallback: search for the file
            for file in self.download_dir.iterdir():
                if file.name.startswith(f"{vod_id}_"):
                    print(f"[Downloader] Saved to: {file}")
                    return str(file)
            
            print("[Downloader] Download completed but file not found")
            return None
            
        except Exception as e:
            self.progress_bar.finish()
            print(f"[Downloader] Error: {e}")
            return None
    
    def delete(self, file_path: str) -> bool:
        """Delete a downloaded file."""
        try:
            os.remove(file_path)
            print(f"[Downloader] Deleted: {file_path}")
            return True
        except Exception as e:
            print(f"[Downloader] Failed to delete {file_path}: {e}")
            return False


if __name__ == "__main__":
    # Test download with a sample VOD
    downloader = VODDownloader()
    
    # Test with a short clip or VOD
    test_url = "https://www.twitch.tv/videos/2334649588"  # Replace with actual VOD
    result = downloader.download(test_url, "test123", "Test VOD Download")
    
    if result:
        print(f"Success! File at: {result}")
        # Optionally delete after test
        # downloader.delete(result)
    else:
        print("Download failed")
