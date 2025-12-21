"""
YouTube Video Uploader using YouTube Data API v3.
Handles OAuth authentication and video uploads.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# OAuth scopes needed for uploading videos
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def format_size(bytes_val: float) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"


class ProgressBar:
    """Simple ASCII progress bar for uploads."""
    
    def __init__(self, width: int = 40):
        self.width = width
        self.last_line_len = 0
        self.start_time = None
        self.last_update_time = 0
        self.update_interval = 0.5  # Only update every 0.5 seconds
        self.is_tty = sys.stdout.isatty()
    
    def start(self):
        """Start timing the upload."""
        self.start_time = time.time()
        self.last_update_time = 0
    
    def update(self, percent: float, uploaded_bytes: int = 0, total_bytes: int = 0, force: bool = False):
        """Update the progress bar display."""
        current_time = time.time()
        
        # Throttle updates to reduce output spam (unless forced or at 100%)
        if not force and percent < 100 and (current_time - self.last_update_time) < self.update_interval:
            return
        
        self.last_update_time = current_time
        
        filled = int(self.width * percent / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        
        # Calculate speed if we have timing info
        extra = ""
        if self.start_time and uploaded_bytes > 0:
            elapsed = current_time - self.start_time
            if elapsed > 0:
                speed = uploaded_bytes / elapsed
                extra = f"| {format_size(uploaded_bytes)}/{format_size(total_bytes)} | {format_size(speed)}/s"
                
                # ETA
                if percent > 0 and percent < 100:
                    remaining_bytes = total_bytes - uploaded_bytes
                    eta_seconds = remaining_bytes / speed if speed > 0 else 0
                    if eta_seconds < 60:
                        extra += f" | ETA: {int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        extra += f" | ETA: {int(eta_seconds // 60)}m"
                    else:
                        extra += f" | ETA: {int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
        
        line = f"[Upload]   [{bar}] {percent:5.1f}% {extra}"
        
        if self.is_tty:
            # Interactive terminal: use carriage return to overwrite
            output = f"\r{line}"
            padding = max(0, self.last_line_len - len(line))
            sys.stdout.write(output + " " * padding)
            sys.stdout.flush()
        else:
            # Non-TTY (piped/redirected): print new lines but throttled
            print(line)
        
        self.last_line_len = len(line)
    
    def finish(self):
        """Finish the progress bar with a newline."""
        print()


class YouTubeUploader:
    """Handles YouTube video uploads with OAuth authentication."""
    
    def __init__(
        self,
        client_secrets_file: str = "client_secrets.json",
        credentials_file: str = "youtube_credentials.json"
    ):
        self.client_secrets_file = client_secrets_file
        self.credentials_file = credentials_file
        self.youtube = None
    
    def authenticate(self) -> bool:
        """
        Authenticate with YouTube API.
        Will open browser for OAuth consent on first run.
        Stores credentials for future use.
        
        Returns True if successful, False otherwise.
        """
        credentials = None
        
        # Load existing credentials if available
        if os.path.exists(self.credentials_file):
            try:
                credentials = Credentials.from_authorized_user_file(
                    self.credentials_file, SCOPES
                )
            except Exception as e:
                print(f"[YouTube] Failed to load credentials: {e}")
        
        # Refresh or get new credentials
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                print("[YouTube] Refreshing expired credentials...")
                try:
                    credentials.refresh(Request())
                except Exception as e:
                    print(f"[YouTube] Failed to refresh: {e}")
                    credentials = None
            
            if not credentials:
                if not os.path.exists(self.client_secrets_file):
                    print(f"[YouTube] Error: {self.client_secrets_file} not found")
                    print("[YouTube] Download from Google Cloud Console")
                    return False
                
                print("[YouTube] Opening browser for authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, SCOPES
                )
                credentials = flow.run_local_server(port=0)
            
            # Save credentials for next time
            with open(self.credentials_file, "w") as f:
                f.write(credentials.to_json())
            print(f"[YouTube] Credentials saved to {self.credentials_file}")
        
        # Build the YouTube API client
        try:
            self.youtube = build("youtube", "v3", credentials=credentials)
            print("[YouTube] Authenticated successfully")
            return True
        except Exception as e:
            print(f"[YouTube] Failed to build API client: {e}")
            return False
    
    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        privacy_status: str = "unlisted",
        tags: Optional[list[str]] = None
    ) -> Optional[str]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to the video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            privacy_status: "public", "private", or "unlisted"
            tags: Optional list of tags
        
        Returns:
            YouTube video ID if successful, None otherwise
        """
        if not self.youtube:
            if not self.authenticate():
                return None
        
        # Validate file exists
        if not os.path.exists(video_path):
            print(f"[YouTube] Error: Video file not found: {video_path}")
            return None
        
        # Get file size for progress tracking
        file_size = os.path.getsize(video_path)
        
        # Truncate title/description to YouTube limits
        title = title[:100]
        description = description[:5000]
        
        print(f"[YouTube] Uploading: {title}")
        print(f"[YouTube] File: {video_path} ({format_size(file_size)})")
        print(f"[YouTube] Privacy: {privacy_status}")
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "20"  # Gaming category
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        # Create the media upload object with resumable upload
        # Using smaller chunks for more frequent progress updates
        chunk_size = 1024 * 1024 * 5  # 5MB chunks for more granular progress
        media = MediaFileUpload(
            video_path,
            mimetype="video/*",
            resumable=True,
            chunksize=chunk_size
        )
        
        progress_bar = ProgressBar()
        progress_bar.start()
        
        try:
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    percent = status.progress() * 100
                    uploaded = int(status.resumable_progress)
                    progress_bar.update(percent, uploaded, file_size)
            
            progress_bar.update(100, file_size, file_size, force=True)
            progress_bar.finish()
            
            video_id = response["id"]
            print(f"[YouTube] Upload complete! Video ID: {video_id}")
            print(f"[YouTube] URL: https://www.youtube.com/watch?v={video_id}")
            return video_id
            
        except HttpError as e:
            progress_bar.finish()
            error_content = json.loads(e.content.decode())
            error_reason = error_content.get("error", {}).get("errors", [{}])[0].get("reason", "unknown")
            
            if error_reason == "quotaExceeded":
                print("[YouTube] Error: Daily quota exceeded. Try again tomorrow.")
            elif error_reason == "uploadLimitExceeded":
                print("[YouTube] Error: Upload limit exceeded.")
            else:
                print(f"[YouTube] API Error: {e}")
            return None
            
        except Exception as e:
            progress_bar.finish()
            print(f"[YouTube] Upload failed: {e}")
            return None


if __name__ == "__main__":
    # Test authentication (won't upload anything)
    uploader = YouTubeUploader()
    
    if uploader.authenticate():
        print("Authentication successful!")
        print("To test upload, provide a video file path.")
    else:
        print("Authentication failed!")
