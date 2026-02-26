# 🎬 Video Censor

**Automatically detect and censor profanity, nudity, and sexual content in videos.**

Fully local, offline video censoring powered by AI. No cloud services, no uploads—your videos stay private.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![Build and Release](https://github.com/Rconman99/video-censor/actions/workflows/release.yml/badge.svg)](https://github.com/Rconman99/video-censor/actions/workflows/release.yml)
[![Tests](https://github.com/Rconman99/video-censor/actions/workflows/test.yml/badge.svg)](https://github.com/Rconman99/video-censor/actions/workflows/test.yml)

---

## 📸 Screenshots

<p align="center">
  <img src="docs/screenshots/main-window.png" width="700" alt="Main Window">
  <br><em>Main window with video queue and processing options</em>
</p>

<p align="center">
  <img src="docs/screenshots/detection-review.png" width="700" alt="Detection Review">
  <br><em>Severity-tiered detection review with batch actions</em>
</p>

<p align="center">
  <img src="docs/screenshots/preferences.png" width="500" alt="Preferences">
  <br><em>Customizable filter settings and preferences</em>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤬 **Profanity Detection** | Whisper-powered speech-to-text with customizable word lists |
| 👁 **Nudity Detection** | NudeNet AI model for visual content detection |
| 🔞 **Sexual Content Filter** | Audio + visual analysis for intimate scenes |
| ⚡ **Hardware Acceleration** | VideoToolbox (macOS) for 3-5x faster exports |
| 🎯 **Smart Rendering** | Stream-copy unedited segments for lightning-fast output |
| 📝 **Subtitle Support** | Import SRT files for enhanced profanity detection |

---

## 🚀 Quick Start

### Option 1: Download Pre-built App (macOS)

1. Go to [Releases](https://github.com/Rconman99/video-censor/releases)
2. Download `VideoCensor-x.x.x.dmg`
3. Drag to Applications and launch

### Option 2: Download Pre-built App (Windows)

1. Go to [Releases](https://github.com/Rconman99/video-censor/releases)
2. Download `VideoCensor-x.x.x-windows.zip`
3. Extract and run `VideoCensor.exe`

> **Note:** Windows may show a SmartScreen warning since the app isn't signed. Click "More info" → "Run anyway".

### Option 3: Run from Source

```bash
# Clone the repo
git clone https://github.com/Rconman99/video-censor.git
cd video-censor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (required)
brew install ffmpeg

# Run the app
python main.py
```

---

## 📋 Requirements

- **Python**: 3.10 or higher
- **FFmpeg**: Required for video processing
- **RAM**: 4GB minimum (8GB+ recommended)
- **OS**: macOS (Apple Silicon recommended) or Windows

---

## 🎯 Usage

1. **Launch the app** (`python main.py` or open VideoCensor.app)
2. **Drag & drop** a video file onto the main window
3. **Configure filters** in the Preferences panel:
   - Toggle profanity/nudity/sexual content detection
   - Set custom blocked phrases
   - Choose output quality
4. **Click "Start Processing"** and wait for analysis
5. **Review edits** (optional) in the timeline editor
6. **Export** your censored video

---

## ⚙️ Configuration

Settings are stored in `config.yaml`:

```yaml
whisper:
  model_size: "large-v3"  # Options: tiny, base, small, medium, large-v3

nudity:
  min_confidence: 0.6
  frame_interval: 0.15

output:
  video_codec: "h265"     # h264 or h265
  quality_preset: "1080p_high"
```

---

## 🔔 Push Notifications

Get notified when processing completes:

1. Download the [ntfy app](https://ntfy.sh) on your phone
2. Subscribe to a unique topic (e.g., `videocensor-yourname-12345`)
3. Enter the same topic in app Settings → Notifications

---

## 🛠 Development

```bash
# Run tests
python -m pytest tests/

# Build macOS app
pyinstaller --windowed --name "VideoCensor" main.py

# Create DMG installer
brew install create-dmg
create-dmg --volname "Video Censor" dist/VideoCensor-1.0.dmg dist/VideoCensor.app
```

---

## 📄 License

MIT License - Use freely for personal or commercial projects.

---

## 🤝 Contributing

Pull requests welcome! Please open an issue first to discuss major changes.

---

**Made with ❤️ for families who want cleaner entertainment.**
