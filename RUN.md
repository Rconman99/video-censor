# Running Video Censor from Source

## Quick Start

```bash
# 1. Activate the virtual environment
source venv/bin/activate

# 2. Launch the app
python main.py
```

## First-Time Setup

If you haven't installed dependencies yet:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Expected UI

When the app launches correctly, you should see:

- **Dark theme** background (#0a0a0f)
- **Title**: "Video Censor" with subtitle
- **Left panel**: Drag-and-drop zone with "Choose File" button
- **Center panel**: Preference Manager with:
  - Profile dropdown
  - Content filter checkboxes
  - Romance/Violence radio groups
  - Custom phrases editor
  - Safe Cover toggle
- **Right panel**: Processing queue

## Troubleshooting

**App doesn't start:**
- Ensure PySide6 is installed: `pip install PySide6`
- Check Python version: requires Python 3.9+

**Still seeing old UI:**
- Make sure you're running `python main.py` (not the old `video_censor_gui.py`)
