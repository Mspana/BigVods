"""
Standalone script to authenticate with YouTube.
Run this interactively to refresh or set up YouTube credentials.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import
sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube_upload import YouTubeUploader


def main():
    """Authenticate with YouTube interactively."""
    print("=" * 60)
    print("  YouTube Authentication")
    print("=" * 60)
    print()
    print("This will open a browser window for you to sign in.")
    print("After signing in, credentials will be saved for future use.")
    print()
    
    uploader = YouTubeUploader()
    
    print("Starting authentication...")
    if uploader.authenticate():
        print()
        print("=" * 60)
        print("✓ Authentication successful!")
        print("=" * 60)
        print()
        print("Credentials saved. The archiver can now use these credentials.")
        return 0
    else:
        print()
        print("=" * 60)
        print("✗ Authentication failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit(main())
