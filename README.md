# Video Censor Tool

A fully local, offline video editing tool that automatically detects and censors profanity and nudity from video files on macOS.

## Features

- **100% Offline**: All processing happens locally on your Mac—no cloud APIs, no data leaves your device
- **Profanity Detection**: Uses faster-whisper for speech-to-text, then censors swear words with mute or beep
- **Nudity Detection**: Uses NudeNet to analyze video frames and cut explicit content
- **Configurable**: Customize word lists, detection thresholds, and output settings
- **Detailed Reports**: Get summaries of what was censored and when

## Quick Install

```bash
# Install ffmpeg first (required)
brew install ffmpeg

# Install Video Censor from GitHub
pip install git+https://github.com/Rconman99/video-censor.git

# Launch the app
video-censor
```

## Requirements

- macOS (tested on Sonoma/Ventura)
- Python 3.10 or 3.11
- ffmpeg (installed via Homebrew)
- ~2-4GB disk space for models

## Installation

### 1. Install Homebrew packages

```bash
# Install ffmpeg
brew install ffmpeg
```

### 2. Set up Python environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. First run (downloads models)

The first run will automatically download required models:
- Whisper model (~150MB for 'base')
- NudeNet model (~10MB)

## Usage

### Basic Usage

```bash
# Censor a video (profanity + nudity)
python censor_video.py input.mp4 output.mp4

# Censor only profanity (skip nudity detection)
python censor_video.py --no-nudity input.mp4 output_audio_only.mp4

# Censor only nudity (skip profanity detection)
python censor_video.py --no-profanity input.mp4 output_video_only.mp4
```

### With Custom Config

```bash
python censor_video.py --config my_config.yaml input.mp4 output.mp4
```

### Options

| Option | Description |
|--------|-------------|
| `--config`, `-c` | Path to YAML configuration file |
| `--overwrite`, `-y` | Overwrite output file if exists |
| `--no-profanity` | Skip profanity detection |
| `--no-nudity` | Skip nudity detection |
| `--verbose`, `-v` | Enable verbose logging |
| `--quiet`, `-q` | Suppress progress output |
| `--save-summary` | Save JSON summary to file |
| `--save-timeline` | Save detailed edit timeline to file |
| `--threshold` | Override nudity detection threshold (0.0-1.0) |
| `--model` | Override Whisper model (tiny/base/small/medium/large-v3) |
| `--censor-mode` | Override profanity censor mode (mute/beep) |
| `--frame-interval` | Override frame sampling interval (seconds) |

### Example Output

```
==================================================
VIDEO CENSOR - PROCESSING COMPLETE
==================================================

Input:  movie.mp4
Output: movie_censored.mp4

--------------------------------------------------
DURATION
--------------------------------------------------
  Original:  01:32:45.000
  Final:     01:31:22.500
  Removed:   01:22.500 (1.5%)

--------------------------------------------------
PROFANITY CENSORING
--------------------------------------------------
  Instances detected: 47
  Audio edits made:   32

--------------------------------------------------
NUDITY REMOVAL
--------------------------------------------------
  Segments cut:     3
  Duration removed: 01:22.500

==================================================
```

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
profanity:
  # How to handle profanity: "mute" or "beep"
  censor_mode: "beep"
  
  # Beep tone settings
  beep_frequency_hz: 1000
  beep_volume: 0.5
  
  # Buffer time around words (seconds)
  buffer_before: 0.1
  buffer_after: 0.15

nudity:
  # Detection threshold (0.0-1.0, higher = stricter)
  threshold: 0.6
  
  # Frame sampling interval (seconds)
  frame_interval: 0.25

whisper:
  # Model size: tiny, base, small, medium, large-v3
  model_size: "base"
```

### Custom Profanity List

Create a text file with one word per line:

```txt
# my_words.txt
word1
word2
phrase with spaces
```

Then reference it in config:

```yaml
profanity:
  custom_wordlist_path: "/path/to/my_words.txt"
```

## How It Works

### Pipeline Overview

```
Input Video
    │
    ├─── Audio Track ─── Whisper STT ─── Profanity Detection ─── Audio Edits
    │
    └─── Video Frames ─── NudeNet ─── Nudity Detection ─── Video Cuts
    
                              │
                              ▼
                        Edit Planning
                              │
                              ▼
                    ffmpeg Rendering
                              │
                              ▼
                      Censored Video
```

### Processing Steps

1. **Extract Audio**: Pull audio track from video (16kHz WAV)
2. **Transcribe**: Run faster-whisper with word-level timestamps
3. **Detect Profanity**: Match words against profanity list
4. **Extract Frames**: Sample frames at configured interval
5. **Detect Nudity**: Run NudeNet on each frame
6. **Plan Edits**: Merge intervals, calculate keep segments
7. **Render**: Use ffmpeg to apply audio edits and video cuts
8. **Report**: Generate summary of changes

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_intervals.py -v
```

## Performance Notes

- **Whisper Model Size**: Larger models are more accurate but slower
  - `tiny`: ~10x real-time on M1
  - `base`: ~5x real-time on M1
  - `small`: ~2x real-time on M1
  - `medium`/`large`: Slower, may need GPU

- **Frame Sampling**: Default 0.25s (4 fps) balances accuracy vs speed
  - Faster: 0.5s (2 fps) - may miss brief nudity
  - More accurate: 0.1s (10 fps) - much slower

- **Video Length**: Expect ~2-5x real-time processing for typical videos

## Troubleshooting

### "ffmpeg not found"

```bash
brew install ffmpeg
```

### "faster-whisper not working"

Ensure you have the right Python version:
```bash
python3 --version  # Should be 3.10 or 3.11
```

### Out of memory

Try a smaller Whisper model:
```yaml
whisper:
  model_size: "tiny"
```

Or increase frame interval:
```yaml
nudity:
  frame_interval: 0.5
```

## Privacy & Safety

- **No Cloud Calls**: All processing is local
- **No Data Upload**: Videos never leave your device
- **Open Source Models**: Uses publicly available ML models
- **Temp Files**: Cleaned up after processing

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Speech-to-text
- [NudeNet](https://github.com/notAI-tech/NudeNet) - Nudity detection
- [ffmpeg](https://ffmpeg.org/) - Video processing
