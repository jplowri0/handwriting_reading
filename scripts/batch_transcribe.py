#!/usr/bin/env python3
"""
Batch Transcription Script

Process multiple images as parts of the same note (e.g., multi-page journal entry).
Combines all transcriptions into a single Markdown file.

Usage:
    python batch_transcribe.py --title "20260301_Journal" image1.png image2.png image3.png
    python batch_transcribe.py --inbox ~/Desktop/inbox --title "20260301_Journal"
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Import from the main transcribe module
from transcribe import (
    DEFAULT_INBOX,
    DEFAULT_OUTPUT,
    DEFAULT_MODEL,
    IMAGE_EXTENSIONS,
    call_ollama_vision,
    clean_markdown_output,
    find_images_in_inbox,
)


def combine_transcriptions(transcriptions: List[str], title: str) -> str:
    """
    Combine multiple transcriptions into a single Markdown document.
    
    Merges the Transcription sections and combines Highlights tables.
    """
    all_transcriptions = []
    all_summaries = []
    all_highlights = []
    
    for i, text in enumerate(transcriptions, 1):
        lines = text.strip().split("\n")
        
        current_section = None
        transcription_lines = []
        summary_lines = []
        highlight_lines = []
        in_table = False
        table_header_seen = False
        
        for line in lines:
            # Detect section headers
            if line.strip() == "## Transcription":
                current_section = "transcription"
                continue
            elif line.strip() == "## Summary":
                current_section = "summary"
                continue
            elif line.strip() == "## Highlights":
                current_section = "highlights"
                continue
            elif line.startswith("# "):
                # Skip the title line
                continue
            elif line.strip() == "---":
                continue
            
            # Collect content
            if current_section == "transcription":
                transcription_lines.append(line)
            elif current_section == "summary":
                summary_lines.append(line)
            elif current_section == "highlights":
                # Skip table header rows after the first transcription
                if line.startswith("|") and "Colour" in line:
                    if not table_header_seen:
                        table_header_seen = True
                        highlight_lines.append(line)
                    continue
                elif line.startswith("|") and "---" in line:
                    if len(highlight_lines) == 1:  # Only add separator once
                        highlight_lines.append(line)
                    continue
                elif line.startswith("|"):
                    highlight_lines.append(line)
        
        # Add page marker if multiple pages
        if len(transcriptions) > 1:
            all_transcriptions.append(f"**Page {i}**\n")
        all_transcriptions.extend(transcription_lines)
        all_transcriptions.append("")
        
        all_summaries.extend(summary_lines)
        all_highlights.extend(highlight_lines)
    
    # Build combined document
    output = [f"# {title}", "", "## Transcription", ""]
    output.extend(all_transcriptions)
    output.extend(["---", "", "## Summary", ""])
    output.extend(all_summaries)
    output.extend(["---", "", "## Highlights", ""])
    
    # Ensure we have table headers
    if all_highlights:
        # Check if headers exist
        has_header = any("Colour" in line for line in all_highlights)
        if not has_header:
            output.append("| Colour | Category | Theme | Text |")
            output.append("|--------|----------|-------|------|")
        output.extend(all_highlights)
    else:
        output.append("*No highlighted text in this note.*")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Batch transcribe multiple images into a single note"
    )
    parser.add_argument(
        "images",
        type=Path,
        nargs="*",
        help="Image files to process (in order)",
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        help="Process all images in inbox folder instead of specifying files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output folder for Markdown files (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--title",
        type=str,
        required=True,
        help="Title for the combined note (required)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL})",
    )
    
    args = parser.parse_args()
    
    # Determine which images to process
    if args.inbox:
        images = find_images_in_inbox(args.inbox)
        if not images:
            print(f"No images found in: {args.inbox}")
            sys.exit(1)
    elif args.images:
        images = args.images
        # Validate all images exist
        for img in images:
            if not img.exists():
                print(f"ERROR: Image not found: {img}")
                sys.exit(1)
    else:
        print("ERROR: Specify images or use --inbox")
        parser.print_help()
        sys.exit(1)
    
    print(f"Processing {len(images)} image(s) for: {args.title}")
    
    # Process each image
    transcriptions = []
    for i, image_path in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}] Processing: {image_path.name}")
        
        response = call_ollama_vision(image_path, args.title, args.model)
        
        if response:
            cleaned = clean_markdown_output(response)
            transcriptions.append(cleaned)
            print(f"  ✓ Success")
        else:
            print(f"  ✗ Failed")
    
    if not transcriptions:
        print("\nERROR: No successful transcriptions")
        sys.exit(1)
    
    # Combine transcriptions
    print(f"\nCombining {len(transcriptions)} transcription(s)...")
    combined = combine_transcriptions(transcriptions, args.title)
    
    # Write output
    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / f"{args.title}.md"
    
    # Handle duplicates
    counter = 1
    while output_path.exists():
        output_path = args.output / f"{args.title}_{counter}.md"
        counter += 1
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined)
    
    print(f"\n{'='*50}")
    print(f"Output: {output_path}")
    print(f"Processed: {len(transcriptions)}/{len(images)} images")


if __name__ == "__main__":
    main()
