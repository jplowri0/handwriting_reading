# Handwriting Transcription Skill

Transcribe handwritten notes from images using a local Qwen 3-VL model via Ollama. Outputs structured Markdown with automatic keyword tagging.

## Features

- **Verbatim transcription** of handwritten text
- **Automatic keyword tagging** from a known keyword list
- **Suggested keywords** for themes not in the known list
- **Batch processing** for multi-page notes
- **Inbox watcher** for automatic processing
- **Fully local** — no cloud APIs required

## Quick Start

### 1. Install Prerequisites

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.ai

# Pull the vision model
ollama pull qwen3-vl:32b

# Start Ollama server (if not already running)
ollama serve
```

### 2. Setup the Skill

```bash
# Clone/copy the skill folder to your preferred location
cp -r handwriting-transcription-skill ~/tools/

# Make the shell script executable
chmod +x ~/tools/handwriting-transcription-skill/transcribe.sh

# Optional: Add to PATH
echo 'export PATH="$HOME/tools/handwriting-transcription-skill:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 3. Create Inbox Folder

```bash
mkdir -p ~/Desktop/inbox
mkdir -p ~/Desktop/outbox
```

### 4. Transcribe!

```bash
# Place images in ~/Desktop/inbox, then:
./transcribe.sh

# Or process a specific image:
./transcribe.sh ~/Desktop/inbox/note.png "20260301_Journal"
```

## Usage

### Process All Images in Inbox

```bash
./transcribe.sh
# or
python scripts/transcribe.py
```

### Process Single Image

```bash
./transcribe.sh image.png
./transcribe.sh image.png "Custom Title"

# or
python scripts/transcribe.py --image image.png --title "Custom Title"
```

### Batch Process (Multi-Page Notes)

```bash
./transcribe.sh --batch "20260301_Journal" page1.png page2.png page3.png

# or
python scripts/batch_transcribe.py --title "20260301_Journal" page1.png page2.png
```

### Watch Inbox for New Images

```bash
./transcribe.sh --watch

# or
python scripts/watch_inbox.py --archive
```

This monitors `~/Desktop/inbox` and automatically transcribes new images, moving processed ones to an archive folder.

## Output Format

Each transcription produces a Markdown file like this:

```markdown
# 20260301_Journal

## Transcription

= +1 Had a great morning with the kids...

Talked to [[Dr Sata]] about the project.

---

## Summary

- Positive morning routine with family
- Gym session completed
- Work meeting went well

---

## Keywords

- [[self-care]]
- [[presence-with-kids]]
- [[energy-management]]

---

## Suggested Keywords

- [[physical-fitness]] — Committing to regular exercise as a health priority
```

## Known Keywords

The model assigns relevant keywords from this list:

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

When the note covers a theme not in this list, the model suggests new keywords in `[[kebab-case]]` format with a short description.

## Configuration

Edit the defaults in `scripts/transcribe.py`:

```python
DEFAULT_INBOX = Path.home() / "Desktop" / "inbox"
DEFAULT_OUTPUT = Path.home() / "Desktop" / "outbox"
DEFAULT_MODEL = "qwen3-vl:32b"
```

Or use command-line arguments:

```bash
python scripts/transcribe.py \
    --inbox ~/Documents/notes/inbox \
    --output ~/Documents/notes/outbox \
    --model qwen3-vl:72b
```

## Troubleshooting

### Ollama not responding

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Model not found

```bash
# List available models
ollama list

# Pull the model
ollama pull qwen3-vl:32b
```

### Poor transcription quality

- Ensure images are well-lit with good contrast
- Crop to just the handwritten content
- Resize very large images (>4000px) down
- Try a larger model variant if available

### Slow processing

- The 32B model requires significant RAM/VRAM
- Consider using a smaller model variant
- Ensure you have sufficient system resources

## Integration with Obsidian

The output Markdown files are designed to work with Obsidian and Zettelkasten workflows:

1. Set `--output` to your Obsidian vault folder
2. Keywords like `[[time-management]]` become wikilinks
3. People names are formatted as `[[Name]]` wikilinks
4. Create MOC (Map of Content) notes for keywords
5. Use Dataview to query keywords across notes

Example Dataview query for self-care entries:

```dataview
LIST
FROM "journal"
WHERE contains(file.content, "[[self-care]]")
```

## Files

```
handwriting-transcription-skill/
├── SKILL.md              # Skill metadata and documentation
├── README.md             # This file
├── transcribe.sh         # Shell wrapper for easy CLI usage
├── prompt.txt            # Standalone prompt for direct Ollama use
└── scripts/
    ├── transcribe.py     # Main transcription script
    ├── batch_transcribe.py # Multi-image batch processing
    └── watch_inbox.py    # Inbox watcher daemon
```

## License

MIT
