"""
Sync YouTube playlist video IDs with processed VODs.
Fetches all videos from a playlist and matches them to Twitch VOD IDs.
"""

import json
import re
from youtube_upload import YouTubeUploader
from twitch_api import TwitchAPI


def extract_vod_id_from_text(text: str) -> list[str]:
    """Extract potential Twitch VOD IDs from text (title/description)."""
    if not text:
        return []
    
    # Look for patterns like "2649202680" (10-digit numbers that could be VOD IDs)
    # Twitch VOD IDs are typically 10 digits
    matches = re.findall(r'\b(\d{10})\b', text)
    return matches


def get_playlist_videos(uploader: YouTubeUploader, playlist_id: str) -> list[dict]:
    """Fetch all videos from a YouTube playlist."""
    if not uploader.youtube:
        if not uploader.authenticate():
            return []
    
    videos = []
    next_page_token = None
    
    try:
        while True:
            request = uploader.youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                
                video_id = content_details.get("videoId")
                if not video_id:
                    continue
                
                videos.append({
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "position": snippet.get("position", 0),
                    "video_details": None  # Will fetch separately if needed
                })
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        
        print(f"Found {len(videos)} videos in playlist")
        return videos
    
    except Exception as e:
        print(f"Error fetching playlist: {e}")
        return []


def match_videos_to_vods(playlist_videos: list[dict], processed_vods: dict) -> dict:
    """Match YouTube videos to Twitch VOD IDs."""
    matches = {}
    unmatched_videos = []
    
    for video in playlist_videos:
        video_id = video["video_id"]
        title = video["title"]
        description = video["description"]
        
        # Try to find VOD ID in title or description
        potential_ids = extract_vod_id_from_text(title + " " + description)
        
        matched = False
        for vod_id in potential_ids:
            if vod_id in processed_vods:
                matches[vod_id] = {
                    "youtube_id": video_id,
                    "title": title,
                    "published_at": video.get("published_at", ""),
                    "matched_by": "vod_id_in_text"
                }
                matched = True
                print(f"✓ Matched: VOD {vod_id} -> YouTube {video_id} ({title[:50]}...)")
                break
        
        if not matched:
            unmatched_videos.append(video)
    
    if unmatched_videos:
        print(f"\n⚠ {len(unmatched_videos)} videos couldn't be automatically matched")
        print("These might need manual matching:")
        for video in unmatched_videos[:10]:  # Show first 10
            print(f"  - {video['video_id']}: {video['title'][:60]}")
    
    return matches


def update_processed_vods(processed_file: str, matches: dict):
    """Update processed_vods.json with YouTube video IDs."""
    try:
        with open(processed_file, 'r') as f:
            processed_vods = json.load(f)
        
        # Handle old format
        if isinstance(processed_vods, list):
            processed_vods = {vod_id: {"twitch_id": vod_id} for vod_id in processed_vods}
        
        updated_count = 0
        for vod_id, match_data in matches.items():
            if vod_id in processed_vods:
                # Update existing entry
                processed_vods[vod_id]["youtube_id"] = match_data["youtube_id"]
                if not processed_vods[vod_id].get("title"):
                    processed_vods[vod_id]["title"] = match_data["title"]
                # Use published_at from YouTube as uploaded_at if not already set
                if match_data.get("published_at") and not processed_vods[vod_id].get("uploaded_at"):
                    processed_vods[vod_id]["uploaded_at"] = match_data["published_at"]
                # Add stream_date if available
                if match_data.get("stream_date"):
                    processed_vods[vod_id]["stream_date"] = match_data["stream_date"]
                updated_count += 1
            else:
                # Add new entry
                processed_vods[vod_id] = {
                    "twitch_id": vod_id,
                    "youtube_id": match_data["youtube_id"],
                    "title": match_data["title"],
                    "uploaded_at": match_data.get("published_at"),
                    "stream_date": match_data.get("stream_date")
                }
        
        with open(processed_file, 'w') as f:
            json.dump(processed_vods, f, indent=2)
        
        print(f"\n✓ Updated {updated_count} VOD entries with YouTube links")
        return True
    
    except Exception as e:
        print(f"Error updating processed_vods.json: {e}")
        return False


def fetch_stream_dates(twitch: TwitchAPI, vod_ids: list[str], channel_name: str) -> dict:
    """Fetch stream dates from Twitch API for given VOD IDs."""
    print(f"\nFetching stream dates from Twitch for {len(vod_ids)} VODs...")
    stream_dates = {}
    
    # Get all VODs from the channel
    all_vods = twitch.get_channel_vods(channel_name, limit=100)
    
    # Create a lookup by VOD ID
    for vod in all_vods:
        if vod["id"] in vod_ids:
            stream_dates[vod["id"]] = vod["created_at"]
    
    print(f"Found stream dates for {len(stream_dates)} VODs")
    return stream_dates


def main():
    """Main function."""
    import json as json_module
    
    playlist_id = "PLEvRxdycLtQprdGYeZecpKjlR1WOAQDrf"
    processed_file = "processed_vods.json"
    
    print("=" * 60)
    print("  YouTube Playlist Link Sync")
    print("=" * 60)
    print()
    
    # Load config for Twitch API
    try:
        with open("config.json", 'r') as f:
            config = json_module.load(f)
        channel_name = config["twitch"]["channel_name"]
    except:
        print("Warning: Could not load config.json, stream dates won't be fetched")
        channel_name = None
    
    # Load processed VODs
    try:
        with open(processed_file, 'r') as f:
            data = json_module.load(f)
            if isinstance(data, list):
                processed_vods = {vod_id: {"twitch_id": vod_id} for vod_id in data}
            else:
                processed_vods = data
        print(f"Loaded {len(processed_vods)} processed VODs")
    except FileNotFoundError:
        print(f"Error: {processed_file} not found")
        return
    except json.JSONDecodeError as e:
        print(f"Error reading {processed_file}: {e}")
        return
    
    # Authenticate and fetch playlist
    uploader = YouTubeUploader()
    print(f"\nFetching videos from playlist: {playlist_id}")
    playlist_videos = get_playlist_videos(uploader, playlist_id)
    
    if not playlist_videos:
        print("No videos found in playlist")
        return
    
    # Match videos to VODs
    print(f"\nMatching videos to VOD IDs...")
    matches = match_videos_to_vods(playlist_videos, processed_vods)
    
    if not matches:
        print("\n⚠ No matches found. Make sure VOD IDs appear in video titles/descriptions.")
        return
    
    # Fetch stream dates from Twitch for matched VODs
    stream_dates = {}
    if channel_name:
        try:
            twitch = TwitchAPI(
                config["twitch"]["client_id"],
                config["twitch"]["client_secret"]
            )
            matched_vod_ids = list(matches.keys())
            stream_dates = fetch_stream_dates(twitch, matched_vod_ids, channel_name)
        except Exception as e:
            print(f"Warning: Could not fetch stream dates: {e}")
    
    # Add stream dates to matches
    for vod_id in matches:
        if vod_id in stream_dates:
            matches[vod_id]["stream_date"] = stream_dates[vod_id]
    
    # Update processed_vods.json
    print(f"\nUpdating {processed_file}...")
    update_processed_vods(processed_file, matches)
    
    print("\n" + "=" * 60)
    print("Sync complete! Refresh the dashboard to see the links.")
    print("=" * 60)


if __name__ == "__main__":
    main()
