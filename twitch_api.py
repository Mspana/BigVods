"""
Twitch API client for fetching VODs from a channel.
Uses the Twitch Helix API with client credentials flow.
"""

import requests
from typing import Optional


class TwitchAPI:
    """Client for interacting with the Twitch Helix API."""
    
    AUTH_URL = "https://id.twitch.tv/oauth2/token"
    API_BASE = "https://api.twitch.tv/helix"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
    
    def authenticate(self) -> bool:
        """
        Get an app access token using client credentials flow.
        Returns True if successful, False otherwise.
        """
        try:
            response = requests.post(self.AUTH_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            })
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            print(f"[Twitch] Authenticated successfully")
            return True
        except requests.RequestException as e:
            print(f"[Twitch] Authentication failed: {e}")
            return False
    
    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
    
    def get_user_id(self, username: str) -> Optional[str]:
        """Get the user ID for a given username."""
        if not self.access_token:
            if not self.authenticate():
                return None
        
        try:
            response = requests.get(
                f"{self.API_BASE}/users",
                headers=self._get_headers(),
                params={"login": username}
            )
            response.raise_for_status()
            data = response.json()
            
            if data["data"]:
                return data["data"][0]["id"]
            else:
                print(f"[Twitch] User '{username}' not found")
                return None
        except requests.RequestException as e:
            print(f"[Twitch] Failed to get user ID: {e}")
            return None
    
    def get_vods(self, user_id: str, limit: int = 20) -> list[dict]:
        """
        Get VODs (past broadcasts) for a user.
        
        Returns a list of VOD objects with keys:
        - id: VOD ID
        - title: Stream title
        - created_at: When the stream started
        - duration: Length of the VOD
        - url: URL to the VOD
        - thumbnail_url: Thumbnail URL template
        """
        if not self.access_token:
            if not self.authenticate():
                return []
        
        try:
            response = requests.get(
                f"{self.API_BASE}/videos",
                headers=self._get_headers(),
                params={
                    "user_id": user_id,
                    "type": "archive",  # Only past broadcasts, not highlights/uploads
                    "first": limit
                }
            )
            response.raise_for_status()
            data = response.json()
            
            vods = []
            for video in data["data"]:
                vods.append({
                    "id": video["id"],
                    "title": video["title"],
                    "created_at": video["created_at"],
                    "duration": video["duration"],
                    "url": video["url"],
                    "thumbnail_url": video["thumbnail_url"],
                    "description": video.get("description", "")
                })
            
            print(f"[Twitch] Found {len(vods)} VODs")
            return vods
            
        except requests.RequestException as e:
            print(f"[Twitch] Failed to get VODs: {e}")
            return []
    
    def get_channel_vods(self, channel_name: str, limit: int = 20) -> list[dict]:
        """
        Convenience method to get VODs by channel name.
        Combines get_user_id and get_vods.
        """
        user_id = self.get_user_id(channel_name)
        if not user_id:
            return []
        return self.get_vods(user_id, limit)


if __name__ == "__main__":
    # Test the API
    import json
    
    with open("config.json") as f:
        config = json.load(f)
    
    twitch = TwitchAPI(
        config["twitch"]["client_id"],
        config["twitch"]["client_secret"]
    )
    
    vods = twitch.get_channel_vods(config["twitch"]["channel_name"])
    for vod in vods[:5]:
        print(f"  - {vod['title']} ({vod['duration']}) - {vod['url']}")


