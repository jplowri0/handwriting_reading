#!/bin/bash
#
# transcribe.sh - Quick transcription of handwritten notes
#
# Usage:
#   ./transcribe.sh                           # Process all images in inbox
#   ./transcribe.sh image.png                 # Process single image
#   ./transcribe.sh image.png "My Title"      # Process with custom title
#   ./transcribe.sh --watch                   # Watch inbox for new images
#
# Setup:
#   1. Ensure Ollama is running: ollama serve
#   2. Pull the model: ollama pull qwen2.5vl:32b
#   3. Place images in ~/Desktop/inbox/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INBOX="${HOME}/Desktop/inbox"
OUTPUT="${HOME}/Desktop/outbox"
MODEL="qwen3.5:27b"
PYTHON="${SCRIPT_DIR}/venv/bin/python3"

# Fall back to system python if venv doesn't exist
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

# Check if Ollama is running
check_ollama() {
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "ERROR: Ollama is not running."
        echo "Start it with: ollama serve"
        exit 1
    fi
}

# Show help
show_help() {
    echo "Handwriting Transcription Tool"
    echo ""
    echo "Usage:"
    echo "  $0                           Process all images in inbox"
    echo "  $0 <image>                   Process single image"
    echo "  $0 <image> <title>           Process with custom title"
    echo "  $0 --watch                   Watch inbox for new images"
    echo "  $0 --batch <title> <images>  Combine multiple images into one note"
    echo "  $0 --help                    Show this help"
    echo ""
    echo "Paths:"
    echo "  Inbox:  $INBOX"
    echo "  Output: $OUTPUT"
    echo "  Model:  $MODEL"
}

# Main logic
case "$1" in
    --help|-h)
        show_help
        ;;
    --watch|-w)
        check_ollama
        "$PYTHON" "${SCRIPT_DIR}/scripts/watch_inbox.py" --archive
        ;;
    --batch|-b)
        check_ollama
        shift
        TITLE="$1"
        shift
        if [ -z "$TITLE" ]; then
            echo "ERROR: --batch requires a title"
            echo "Usage: $0 --batch <title> <image1> <image2> ..."
            exit 1
        fi
        "$PYTHON" "${SCRIPT_DIR}/scripts/batch_transcribe.py" --title "$TITLE" "$@"
        ;;
    "")
        # No arguments - process all inbox images
        check_ollama
        "$PYTHON" "${SCRIPT_DIR}/scripts/transcribe.py"
        ;;
    *)
        # Single image provided
        check_ollama
        IMAGE="$1"
        TITLE="$2"
        
        if [ ! -f "$IMAGE" ]; then
            # Maybe it's in the inbox?
            if [ -f "${INBOX}/${IMAGE}" ]; then
                IMAGE="${INBOX}/${IMAGE}"
            else
                echo "ERROR: Image not found: $IMAGE"
                exit 1
            fi
        fi
        
        if [ -n "$TITLE" ]; then
            "$PYTHON" "${SCRIPT_DIR}/scripts/transcribe.py" --image "$IMAGE" --title "$TITLE"
        else
            "$PYTHON" "${SCRIPT_DIR}/scripts/transcribe.py" --image "$IMAGE"
        fi
        ;;
esac
