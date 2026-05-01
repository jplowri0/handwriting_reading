---
name: handwriting-transcription
description: Transcribe handwritten notes from images using a local Qwen 2.5-VL model via Ollama. Use this skill when the user wants to process handwritten journal entries, notes, or any handwriting stored in ~/Desktop/inbox. Triggers on phrases like "transcribe my notes", "process inbox", "transcribe handwriting", "journal transcription", or when images need OCR with structured Markdown output including highlights categorisation.
---

# Handwriting Transcription Skill

This skill processes handwritten note images from `~/Desktop/inbox` using a local Qwen 2.5-VL (26B) model running via Ollama, and outputs structured Markdown transcriptions.

## Prerequisites

- **Ollama** installed and running locally
- **Qwen 2.5-VL model** pulled: `ollama pull qwen2.5vl:32b` (or your specific variant)
- **Python 3.8+** with `requests` and `base64` modules (standard library)
- Images placed in `~/Desktop/inbox/`

## Usage

### Process all images in inbox:

```bash
python scripts/transcribe.py
```

### Process a specific image with a custom title:

```bash
python scripts/transcribe.py --image ~/Desktop/inbox/note.png --title "20260301_Journal"
```

### Options:

- `--inbox` — Path to inbox folder (default: `~/Desktop/inbox`)
- `--output` — Output folder for Markdown files (default: `~/Desktop/outbox`)
- `--image` — Process a single specific image
- `--title` — Custom title for the note (default: derived from filename)
- `--model` — Ollama model name (default: `qwen2.5vl:32b`)

## Output Format

Each transcription produces a Markdown file with:

1. **Transcription** — Verbatim text from handwriting
2. **Summary** — Contextual bullet points
3. **Highlights** — Table categorising marked/highlighted text:
   - **PINK/Negative** → "My Error" + Theme tag
   - **YELLOW/Positive** → "What I can do to do better" + Theme tag
   - **ORANGE** → "Generic Keywords"
   - **GREEN** → "People"

## Highlight Themes

For PINK and YELLOW highlights, the model assigns themes like:
- `[[time-management]]`, `[[emotional-regulation]]`, `[[parenting-patience]]`
- `[[proactive-action]]`, `[[self-care]]`, `[[communication-tone]]`
- And more (see full list in prompt)

## Workflow

1. Place scanned/photographed handwritten notes in `~/Desktop/inbox/`
2. Run `python scripts/transcribe.py`
3. Find structured Markdown output in `~/Desktop/outbox/`
4. Move processed images to archive or delete them

## Troubleshooting

- **Ollama not responding**: Ensure Ollama is running (`ollama serve`)
- **Model not found**: Pull the model first (`ollama pull qwen2.5vl:32b`)
- **Poor transcription**: Ensure images are well-lit, high contrast, and not too large (resize if needed)
