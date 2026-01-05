# Video Censor App — CLAUDE.md

> Project context for AI-assisted development with Antigravity, Claude Code, or any AI agent.

---

## Mission

Desktop app that automatically detects and censors profanity (audio) and nudity (visual) in video files. Local-first, privacy-preserving, no cloud AI required.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **GUI** | PySide6 (Qt6) |
| **Audio AI** | faster-whisper (local Whisper) |
| **Visual AI** | NudeNet (local NSFW detection) |
| **Video Processing** | FFmpeg |
| **Config** | PyYAML |
| **Database** | Supabase (cloud, optional) |
| **Testing** | pytest |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (PySide6)                       │
│   MainWindow │ DetectionBrowser │ Timeline │ Player         │
├─────────────────────────────────────────────────────────────┤
│                    Detection Layer                           │
│   Transcriber (whisper) │ NudityDetector │ ExplicitDetector │
├─────────────────────────────────────────────────────────────┤
│                    Editing Layer                             │
│   Renderer (FFmpeg) │ Keyframes │ Project Save/Load         │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure                            │
│   Config │ Queue │ Supabase (optional)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
video_censor/
├── main.py                    # GUI entry point
├── censor_video.py            # CLI entry point
├── config.yaml.example        # Config template
├── ui/                        # PySide6 GUI components
│   ├── main_window.py
│   ├── detection_browser.py   # Review detected segments
│   ├── timeline.py            # Video timeline widget
│   └── player.py              # Video player
├── video_censor/              # Core package
│   ├── audio/
│   │   ├── transcriber.py     # faster-whisper STT
│   │   └── waveform.py        # Audio visualization
│   ├── nudity/
│   │   └── detector.py        # NudeNet frame analysis
│   ├── profanity/
│   │   └── wordlist.py        # Blocked words/phrases
│   ├── sexual_content/
│   │   └── detector.py        # Explicit dialog detection
│   ├── editing/
│   │   ├── renderer.py        # FFmpeg rendering
│   │   ├── keyframes.py       # Keyframe snapping
│   │   └── project.py         # Project save/load
│   ├── config.py              # Configuration dataclasses
│   └── queue.py               # Processing queue
└── tests/                     # pytest tests
```

---

## Key Files & Responsibilities

| File | Purpose | When to Modify |
|------|---------|----------------|
| `video_censor/audio/transcriber.py` | Whisper transcription with word timestamps | Changing STT behavior, model settings |
| `video_censor/nudity/detector.py` | NudeNet frame analysis | Detection thresholds, frame sampling |
| `video_censor/profanity/wordlist.py` | Blocked words list | Adding/removing censored terms |
| `video_censor/editing/renderer.py` | FFmpeg video processing | Output format, quality, effects |
| `ui/main_window.py` | Main GUI orchestration | UI flow, menu items, window behavior |
| `ui/detection_browser.py` | Review/edit detections | Detection review UX |
| `ui/timeline.py` | Video timeline widget | Playback, scrubbing, markers |
| `config.yaml.example` | Default configuration | New settings, model options |

---

## Configuration

```yaml
# Key config options (from config.yaml.example)
whisper:
  model_size: large-v3      # tiny, base, small, medium, large-v3
  compute_type: int8        # float16, int8 (for speed)

nudity:
  threshold: 0.75           # Detection confidence (0-1)
  frame_interval: 0.15      # Seconds between frame checks

output:
  hardware_acceleration: auto  # auto, none, nvenc, videotoolbox
  quality_preset: 1080p_high
```

---

## Entry Points

| Command | What It Does |
|---------|--------------|
| `python main.py` | Launch GUI |
| `python -m video_censor` | CLI mode |
| `python censor_video.py <path>` | Direct file processing |

---

## Detection Pipeline

```
Video File
    │
    ├─► Audio Track ─► faster-whisper ─► Word Timestamps
    │                                          │
    │                                          ▼
    │                              Profanity Wordlist Match
    │                                          │
    │                                          ▼
    │                              Audio Censor Regions
    │
    ├─► Video Frames ─► NudeNet ─► Frame Scores
    │                                    │
    │                                    ▼
    │                         Threshold Filter
    │                                    │
    │                                    ▼
    │                         Visual Blur Regions
    │
    └─► Both ─► Merge Regions ─► FFmpeg Render ─► Output
```

---

## Common Agent Tasks

### Task: Add a New Profanity Word/Phrase
1. Open `video_censor/profanity/wordlist.py`
2. Add to appropriate list (single words vs phrases)
3. Consider case sensitivity and variations
4. Test with audio containing the word

### Task: Adjust Nudity Detection Sensitivity
1. Modify `config.yaml` → `nudity.threshold`
2. Lower = more detections (more false positives)
3. Higher = fewer detections (may miss content)
4. Test with edge cases

### Task: Add New Censor Effect (Blur Style, Bleep Sound)
1. `video_censor/editing/renderer.py` for video effects
2. FFmpeg filter chain modifications
3. Test render pipeline

### Task: Improve Detection Accuracy
1. For audio: Consider language-specific Whisper models
2. For visual: Adjust `frame_interval` for more samples
3. For explicit dialog: Enhance pattern matching in `sexual_content/detector.py`

### Task: Add Export Format
1. `video_censor/editing/renderer.py`
2. FFmpeg output arguments
3. Add to quality presets in config

---

## AI/ML Models Reference

| Model | Library | Location | Purpose |
|-------|---------|----------|---------|
| Whisper large-v3 | faster-whisper | Auto-downloaded | Speech-to-text |
| NudeNet | nudenet | Auto-downloaded | NSFW frame detection |

### Model Performance Notes
- **Whisper**: `int8` compute type is fastest on CPU, `float16` on GPU
- **NudeNet**: Frame interval of 0.15s balances speed vs accuracy
- Both models run locally—no API calls, no cloud dependency

---

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_transcriber.py

# Run with coverage
pytest --cov=video_censor tests/
```

---

## Potential Enhancements (Resource Index Mapping)

| Enhancement | Relevant Pattern | Why |
|-------------|------------------|-----|
| Smarter context-aware censoring | LLM integration | Detect sarcasm, quotes, context where profanity is acceptable |
| User preference memory | Zep Memory pattern | Remember user's custom word lists, thresholds per project |
| Batch processing queue | Queue patterns | Process multiple videos with progress tracking |
| Cloud sync for settings | Supabase (already integrated) | Share wordlists, presets across devices |

---

## Code Conventions

- **Naming**: snake_case for files/functions, PascalCase for classes
- **Type hints**: Use throughout (Python 3.10+ syntax)
- **Config**: All tunables go in config.yaml, not hardcoded
- **GUI**: Keep UI logic in `ui/`, business logic in `video_censor/`
- **Tests**: Mirror structure in `tests/` folder

---

## Quick Reference

```
DETECTION MODELS
  Audio:  faster-whisper (large-v3, int8)
  Visual: NudeNet (threshold 0.75)

CONFIG LOCATION
  config.yaml (copy from config.yaml.example)

KEY TUNING PARAMS
  whisper.model_size    → accuracy vs speed
  nudity.threshold      → sensitivity (0.75 default)
  nudity.frame_interval → sample rate (0.15s default)

ENTRY POINTS
  GUI: python main.py
  CLI: python -m video_censor
```

---

*Last updated: January 2026*
