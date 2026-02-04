"""
Cleanup script to force-delete files in the downloads folder.
Handles locked files by closing handles and retrying.
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def force_delete_file(file_path: Path, max_retries: int = 5):
    """Try to delete a file, even if it's locked."""
    for attempt in range(max_retries):
        try:
            # Try to remove read-only attribute if it exists
            if file_path.exists():
                os.chmod(file_path, 0o777)
            
            file_path.unlink()
            print(f"[OK] Deleted: {file_path.name}")
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                print(f"  File locked, retrying in 1 second... (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)
            else:
                print(f"[FAILED] Could not delete (locked): {file_path.name}")
                print(f"  This file is locked by another process. Try stopping the archiver first.")
                return False
        except Exception as e:
            print(f"[ERROR] Error deleting {file_path.name}: {e}")
            return False
    return False


def cleanup_downloads_folder(downloads_dir: str = "downloads", force: bool = False):
    """Clean up all files in the downloads folder."""
    downloads_path = Path(downloads_dir)
    
    if not downloads_path.exists():
        print(f"Downloads folder does not exist: {downloads_dir}")
        return
    
    print("=" * 60)
    print("  Cleaning Downloads Folder")
    print("=" * 60)
    print(f"Folder: {downloads_path.absolute()}")
    print()
    
    # Get all files
    all_files = list(downloads_path.iterdir())
    
    if not all_files:
        print("Downloads folder is already empty.")
        return
    
    print(f"Found {len(all_files)} file(s) to delete...")
    print()
    
    if not force:
        response = input("Are you sure you want to delete all files? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return
    
    deleted = 0
    failed = 0
    
    for file_path in all_files:
        if file_path.is_file():
            if force_delete_file(file_path):
                deleted += 1
            else:
                failed += 1
    
    print()
    print("=" * 60)
    print(f"Deleted: {deleted} file(s)")
    if failed > 0:
        print(f"Failed: {failed} file(s) (may be locked by another process)")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up downloads folder")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Delete without confirmation"
    )
    parser.add_argument(
        "--dir",
        default="downloads",
        help="Downloads directory (default: downloads)"
    )
    
    args = parser.parse_args()
    cleanup_downloads_folder(args.dir, force=args.force)
