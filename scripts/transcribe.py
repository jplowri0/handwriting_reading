#!/usr/bin/env python3
"""
Handwriting Transcription Script

Processes handwritten note images from ~/Desktop/inbox using Qwen 2.5-VL via Ollama
and outputs structured Markdown transcriptions.

Usage:
    python transcribe.py                           # Process all images in inbox
    python transcribe.py --image note.png          # Process single image
    python transcribe.py --title "20260301_Journal" # Specify title
"""

import argparse
import base64
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

# Default paths
DEFAULT_INBOX = Path.home() / "Desktop" / "inbox"
DEFAULT_OUTPUT = Path.home() / "Desktop" / "outbox"
DEFAULT_MODEL = "qwen3.5:27b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Image settings
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_IMAGE_DIMENSION = 2048  # Resize images larger than this
MAX_FILE_SIZE_MB = 10  # Warn if file larger than this

# The transcription prompt template
TRANSCRIPTION_PROMPT = """You are a handwriting transcription assistant. Your task is to transcribe handwritten notes from images and output structured Markdown.

## Output Format

Always output in this exact structure:

```markdown
# {title}

## Transcription

{{Verbatim transcription of the handwriting. Use ~~strikethrough~~ for crossed-out words. Use **bold** for underlined text. Preserve line breaks where meaningful.}}

---

## Summary

{{2-5 bullet points or short paragraphs contextualising what the note is about. Add interpretation where helpful.}}

---

## Highlights

| Colour | Category | Theme | Text |
|--------|----------|-------|------|
{{Extract highlighted text from the image and categorise as follows:}}
```

## Highlight Categories

Identify highlighted/marked text by colour and assign categories:

| Highlight Colour | Category | Theme Column |
|------------------|----------|--------------|
| PINK (Negative) | My Error | Assign a theme from the theme list |
| YELLOW (Positive) | What I can do to do better | Assign a theme from the theme list |
| ORANGE | Generic Keywords | Leave blank |
| GREEN | People | Leave blank |

## Theme List (for PINK/Negative and YELLOW/Positive only)

Choose the most appropriate theme:

- `[[anticipate-needs]]` — Predicting what others will need
- `[[empathy-check]]` — Checking in on others' emotional state
- `[[energy-management]]` — Managing energy levels, avoiding burnout
- `[[proactive-action]]` — Doing things before being asked
- `[[parenting-patience]]` — Staying calm with kids
- `[[self-care]]` — Taking breaks, looking after yourself
- `[[presence-with-kids]]` — Quality time and connection with children
- `[[humility-and-repair]]` — Admitting mistakes, apologising
- `[[pause-before-reacting]]` — Not reacting impulsively
- `[[communication-tone]]` — Being mindful of tone
- `[[time-management]]` — Keeping track of time and commitments
- `[[apology-calibration]]` — Knowing when to apologise and when to stop
- `[[emotional-regulation]]` — Managing own emotions, maintaining composure
- `[[follow-through]]` — Completing what you said you'd do
- `[[boundary-setting]]` — Setting limits with others

If none fit, create a new theme in the same `[[kebab-case]]` format.

## Rules

1. Transcribe exactly what is written — do not correct spelling or grammar
2. If text is crossed out, wrap it in ~~strikethrough~~
3. If you cannot read a word, use [illegible]
4. For journal entries, note the mood score if present (e.g., "= +2", "= -1", "= 0")
5. If multiple entries exist on one page, separate them with **Entry 1**, **Entry 2**, etc.
6. Only include highlights that are visibly marked/highlighted in the image
7. For ORANGE highlights, leave the Theme column empty
8. For GREEN highlights (People), format names as wikilinks: [[Name]]
9. For PINK and YELLOW highlights, always assign a theme

## Example Output

```markdown
# 20260218_Journal

## Transcription

= +1 Went to gym this morning felt good. This is going to be something that must be done so I dont rot away.

---

## Summary

- Gym session in the morning, felt positive
- Recognising exercise as essential for wellbeing

---

## Highlights

| Colour | Category | Theme | Text |
|--------|----------|-------|------|
| PINK | My Error | [[time-management]] | "I did lose track of time" |
| YELLOW | What I can do to do better | [[proactive-action]] | "I knew I had to do it straight away" |
| ORANGE | Generic Keywords | | "Manjaro" |
| GREEN | People | | [[Dr Sata]] |
```

---

Now transcribe the image I provide. The title for this note is: {title}

IMPORTANT: Output ONLY the Markdown content. Do not include any preamble, explanation, or commentary before or after the Markdown.
"""


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Get image dimensions using sips (macOS) or file command."""
    try:
        # Try sips first (macOS)
        result = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(image_path)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            width = height = 0
            for line in lines:
                if "pixelWidth" in line:
                    width = int(line.split(":")[-1].strip())
                elif "pixelHeight" in line:
                    height = int(line.split(":")[-1].strip())
            return width, height
    except:
        pass
    return 0, 0


def resize_image_if_needed(image_path: Path, max_dimension: int = MAX_IMAGE_DIMENSION) -> Path:
    """
    Resize image if it exceeds max_dimension. Returns path to resized image.
    Uses sips on macOS for fast resizing.
    """
    width, height = get_image_dimensions(image_path)
    
    if width == 0 or height == 0:
        print(f"  Warning: Could not get image dimensions, using original")
        return image_path
    
    if width <= max_dimension and height <= max_dimension:
        return image_path
    
    print(f"  Resizing image from {width}x{height} to max {max_dimension}px...")
    
    # Create temp resized file
    resized_path = image_path.parent / f".resized_{image_path.name}"
    
    try:
        # Copy original first
        subprocess.run(["cp", str(image_path), str(resized_path)], check=True)
        
        # Resize using sips (macOS)
        subprocess.run(
            ["sips", "-Z", str(max_dimension), str(resized_path)],
            capture_output=True,
            check=True
        )
        
        return resized_path
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not resize image: {e}")
        if resized_path.exists():
            resized_path.unlink()
        return image_path


def encode_image_to_base64(image_path: Path) -> str:
    """Read an image file and return its base64 encoding."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: Path) -> str:
    """Get the MIME type for an image based on its extension."""
    ext = image_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    return mime_types.get(ext, "image/png")


def call_ollama_vision(
    image_path: Path,
    title: str,
    model: str = DEFAULT_MODEL,
) -> Optional[str]:
    """
    Call Ollama's vision model API with an image and prompt.
    
    Returns the generated text response or None if failed.
    """
    # Resize image if needed
    processed_path = resize_image_if_needed(image_path)
    resized = processed_path != image_path
    
    try:
        # Check file size
        file_size_mb = processed_path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            print(f"  Warning: Image is {file_size_mb:.1f}MB, may be slow...")
        
        # Encode image
        image_base64 = encode_image_to_base64(processed_path)
        
        # Build the prompt
        prompt = TRANSCRIPTION_PROMPT.format(title=title)
        
        # Prepare the API request
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for accurate transcription
                "num_predict": 4096,  # Allow long responses
            }
        }
        
        print(f"  Calling Ollama API with model '{model}'...")
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=900,  # 15 minute timeout for large images
        )
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("response", "")
        
        if not response_text or response_text.strip() == "":
            print("ERROR: Model returned empty response")
            return None
            
        return response_text
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to Ollama. Is it running?")
        print("  Start Ollama with: ollama serve")
        return None
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out. The image may be too large.")
        print("  Try resizing manually: sips -Z 1024 <image>")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP error from Ollama: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return None
    finally:
        # Clean up resized temp file
        if resized and processed_path.exists():
            processed_path.unlink()


def derive_title_from_filename(filename: str) -> str:
    """
    Derive a reasonable title from a filename.
    
    Examples:
        Screenshot_2026-02-21_at_14_34_13.png -> 20260221_Note
        note_journal.png -> note_journal
        IMG_1234.jpg -> IMG_1234
    """
    stem = Path(filename).stem
    
    # Try to extract date from common screenshot formats
    import re
    
    # Pattern: Screenshot_YYYY-MM-DD or similar
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', stem)
    if date_match:
        year, month, day = date_match.groups()
        return f"{year}{month}{day}_Note"
    
    # Pattern: YYYYMMDD
    date_match = re.search(r'(\d{8})', stem)
    if date_match:
        return f"{date_match.group(1)}_Note"
    
    # Default: use the stem, cleaned up
    return stem.replace(" ", "_")


def clean_markdown_output(text: str) -> str:
    """
    Clean up the model output to ensure it's valid Markdown.
    
    Removes any preamble or postamble that isn't part of the Markdown.
    """
    lines = text.strip().split("\n")
    
    # Find where the Markdown content starts (first # heading)
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            start_idx = i
            break
    
    # Find where it ends (look for closing ``` if present, or take all)
    cleaned_lines = lines[start_idx:]
    
    # Remove any trailing ``` if the model wrapped output in code blocks
    result = "\n".join(cleaned_lines)
    
    # If wrapped in ```markdown ... ```, extract the content
    if result.startswith("```markdown"):
        result = result[len("```markdown"):].strip()
    if result.startswith("```"):
        result = result[3:].strip()
    if result.endswith("```"):
        result = result[:-3].strip()
    
    return result


def process_image(
    image_path: Path,
    output_dir: Path,
    title: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> bool:
    """
    Process a single image file.
    
    Returns True if successful, False otherwise.
    """
    print(f"\nProcessing: {image_path.name}")
    
    # Derive title if not provided
    if not title:
        title = derive_title_from_filename(image_path.name)
    
    print(f"  Title: {title}")
    
    # Call the vision model
    response = call_ollama_vision(image_path, title, model)
    
    if not response:
        print(f"  FAILED: No response from model")
        return False
    
    # Clean up the output
    markdown_content = clean_markdown_output(response)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write the output file
    output_filename = f"{title}.md"
    output_path = output_dir / output_filename
    
    # Handle duplicate filenames
    counter = 1
    while output_path.exists():
        output_filename = f"{title}_{counter}.md"
        output_path = output_dir / output_filename
        counter += 1
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    print(f"  Output: {output_path}")
    return True


def find_images_in_inbox(inbox_dir: Path) -> list[Path]:
    """Find all image files in the inbox directory."""
    if not inbox_dir.exists():
        return []
    
    images = []
    for item in inbox_dir.iterdir():
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(item)
    
    return sorted(images)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe handwritten notes using Qwen 2.5-VL via Ollama"
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
        "--image",
        type=Path,
        help="Process a single specific image",
    )
    parser.add_argument(
        "--title",
        type=str,
        help="Custom title for the note (default: derived from filename)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL})",
    )
    
    args = parser.parse_args()
    
    # Process single image if specified
    if args.image:
        if not args.image.exists():
            print(f"ERROR: Image not found: {args.image}")
            sys.exit(1)
        
        success = process_image(args.image, args.output, args.title, args.model)
        sys.exit(0 if success else 1)
    
    # Process all images in inbox
    print(f"Scanning inbox: {args.inbox}")
    images = find_images_in_inbox(args.inbox)
    
    if not images:
        print("No images found in inbox.")
        print(f"  Place image files in: {args.inbox}")
        sys.exit(0)
    
    print(f"Found {len(images)} image(s) to process")
    
    successful = 0
    failed = 0
    
    for image_path in images:
        if process_image(image_path, args.output, args.title, args.model):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Complete: {successful} successful, {failed} failed")
    print(f"Output folder: {args.output}")


if __name__ == "__main__":
    main()
