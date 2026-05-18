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
DEFAULT_MODEL = "qwen3-vl:32b"
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Image settings
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_IMAGE_DIMENSION = 2048  # Resize images larger than this
MAX_FILE_SIZE_MB = 10  # Warn if file larger than this

# Prompt files — live alongside this script by default
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT_FILE = SCRIPT_DIR / "prompt.txt"
DEFAULT_SIMPLE_PROMPT_FILE = SCRIPT_DIR / "prompt_simple.txt"


def load_prompt(prompt_path: Path, required: bool = True) -> Optional[str]:
    """
    Load a prompt template from an external file.

    The file should contain a `{title}` placeholder that will be substituted
    at runtime.

    If required=True (default), exits on missing file. If False, returns None.
    """
    if not prompt_path.exists():
        if required:
            print(f"ERROR: Prompt file not found: {prompt_path}")
            print(f"  Create it or specify a path with --prompt")
            sys.exit(1)
        return None

    try:
        text = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        if required:
            print(f"ERROR: Could not read prompt file: {e}")
            sys.exit(1)
        return None

    if "{title}" not in text:
        print(f"WARNING: {prompt_path.name} does not contain a {{title}} placeholder.")
        print(f"  The note title will not be injected into the prompt.")

    return text


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
    prompt_template: Optional[str] = None,
) -> Optional[str]:
    """
    Call Ollama's vision model API with an image and prompt.
    
    Returns the generated text response or None if failed.
    """
    if prompt_template is None:
        prompt_template = load_prompt(DEFAULT_PROMPT_FILE)

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
        prompt = prompt_template.format(title=title)
        
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
    prompt_template: Optional[str] = None,
    fallback_prompt: Optional[str] = None,
) -> bool:
    """
    Process a single image file.
    
    If the primary prompt fails and a fallback_prompt is provided, retries
    with the simpler prompt.
    
    Returns True if successful, False otherwise.
    """
    print(f"\nProcessing: {image_path.name}")
    
    # Derive title if not provided
    if not title:
        title = derive_title_from_filename(image_path.name)
    
    print(f"  Title: {title}")
    
    # Call the vision model
    response = call_ollama_vision(image_path, title, model, prompt_template)
    
    # Retry with fallback prompt if primary failed
    if not response and fallback_prompt:
        print(f"  Retrying with simple prompt...")
        response = call_ollama_vision(image_path, title, model, fallback_prompt)
    
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
    parser.add_argument(
        "--prompt",
        type=Path,
        default=DEFAULT_PROMPT_FILE,
        help=f"Path to prompt template file (default: {DEFAULT_PROMPT_FILE})",
    )
    parser.add_argument(
        "--prompt-simple",
        type=Path,
        default=DEFAULT_SIMPLE_PROMPT_FILE,
        dest="prompt_simple",
        help=f"Path to fallback prompt for retries (default: {DEFAULT_SIMPLE_PROMPT_FILE})",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        dest="no_fallback",
        help="Disable fallback retry with simple prompt",
    )
    
    args = parser.parse_args()
    
    # Load prompt templates once
    prompt_template = load_prompt(args.prompt)
    fallback_prompt = None
    if not args.no_fallback:
        fallback_prompt = load_prompt(args.prompt_simple, required=False)
        if fallback_prompt:
            print(f"Fallback prompt: {args.prompt_simple}")
    
    # Process single image if specified
    if args.image:
        if not args.image.exists():
            print(f"ERROR: Image not found: {args.image}")
            sys.exit(1)
        
        success = process_image(args.image, args.output, args.title, args.model, prompt_template, fallback_prompt)
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
        if process_image(image_path, args.output, args.title, args.model, prompt_template, fallback_prompt):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Complete: {successful} successful, {failed} failed")
    print(f"Output folder: {args.output}")


if __name__ == "__main__":
    main()
