#!/usr/bin/env python3
"""
Inbox Watcher Script

Monitors ~/Desktop/inbox for new images and automatically transcribes them.
Runs as a background process.

Usage:
    python watch_inbox.py                    # Start watching
    python watch_inbox.py --interval 30      # Check every 30 seconds
    python watch_inbox.py --archive          # Move processed images to archive folder
"""

import argparse
import time
import sys
from pathlib import Path
from datetime import datetime

from transcribe import (
    DEFAULT_INBOX,
    DEFAULT_OUTPUT,
    DEFAULT_MODEL,
    IMAGE_EXTENSIONS,
    process_image,
)


def get_processed_log_path(inbox_dir: Path) -> Path:
    """Get the path to the processed files log."""
    return inbox_dir / ".processed_images.txt"


def load_processed_images(inbox_dir: Path) -> set:
    """Load the set of already-processed image filenames."""
    log_path = get_processed_log_path(inbox_dir)
    if not log_path.exists():
        return set()
    
    with open(log_path, "r") as f:
        return set(line.strip() for line in f if line.strip())


def mark_image_processed(inbox_dir: Path, filename: str):
    """Add an image to the processed log."""
    log_path = get_processed_log_path(inbox_dir)
    with open(log_path, "a") as f:
        f.write(f"{filename}\n")


def find_new_images(inbox_dir: Path, processed: set) -> list[Path]:
    """Find images that haven't been processed yet."""
    new_images = []
    
    if not inbox_dir.exists():
        return new_images
    
    for item in inbox_dir.iterdir():
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            if item.name not in processed:
                new_images.append(item)
    
    return sorted(new_images)


def archive_image(image_path: Path, archive_dir: Path):
    """Move a processed image to the archive folder."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Add timestamp to avoid collisions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{timestamp}_{image_path.name}"
    archive_path = archive_dir / archive_name
    
    image_path.rename(archive_path)
    print(f"  Archived: {archive_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Watch inbox for new images and transcribe them"
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=DEFAULT_INBOX,
        help=f"Path to inbox folder (default: {DEFAULT_INBOX})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output folder for Markdown files (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Seconds between inbox checks (default: 10)",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Move processed images to archive folder",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Archive folder (default: inbox/archived)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process once and exit (don't watch continuously)",
    )
    
    args = parser.parse_args()
    
    # Set default archive directory
    if args.archive and not args.archive_dir:
        args.archive_dir = args.inbox / "archived"
    
    # Ensure inbox exists
    args.inbox.mkdir(parents=True, exist_ok=True)
    
    print(f"Handwriting Transcription Watcher")
    print(f"{'='*50}")
    print(f"Inbox:    {args.inbox}")
    print(f"Output:   {args.output}")
    print(f"Model:    {args.model}")
    print(f"Interval: {args.interval}s")
    if args.archive:
        print(f"Archive:  {args.archive_dir}")
    print(f"{'='*50}")
    
    if not args.once:
        print(f"\nWatching for new images... (Ctrl+C to stop)\n")
    
    try:
        while True:
            # Load processed images
            processed = load_processed_images(args.inbox)
            
            # Find new images
            new_images = find_new_images(args.inbox, processed)
            
            if new_images:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(new_images)} new image(s)")
                
                for image_path in new_images:
                    success = process_image(
                        image_path,
                        args.output,
                        title=None,  # Auto-derive from filename
                        model=args.model,
                    )
                    
                    if success:
                        mark_image_processed(args.inbox, image_path.name)
                        
                        if args.archive:
                            archive_image(image_path, args.archive_dir)
            
            if args.once:
                if not new_images:
                    print("No new images to process.")
                break
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\nStopped watching.")
        sys.exit(0)


if __name__ == "__main__":
    main()
