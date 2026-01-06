# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-06

### Added

- Initial public release
- **Profanity Detection** via Whisper speech recognition
- **Nudity Detection** via NudeNet AI model
- **Sexual Content Detection** for scene-level filtering
- **Violence Detection** with configurable severity levels
- **Severity-Tiered Word Grouping** (Extreme → Moderate → Mild → Skip)
- **Batch Keep/Skip Actions** for efficient review
- **Quick Re-render** with cached detections (skip re-analysis)
- **First-Run Setup Wizard** for easy onboarding
- **Preferences Window** for customization
- **Profile System** for saving filter presets
- **Auto-Sleep** option when queue completes
- **Queue Management** with pause/resume functionality
- **Detection Save/Load** for resumable projects

### Technical

- PySide6 GUI with cinema-themed dark mode
- FFmpeg video processing with hardware acceleration
- VideoToolbox (macOS) and NVENC (NVIDIA) support
- Parallel audio/video analysis pipelines
- Consumer-friendly error handling with logs
- Configuration persistence via YAML

### UI/UX

- Modern dark theme with film reel aesthetics
- Drag-and-drop video import
- Progress indicators with time estimates
- Emoji filter icons with tooltips
- Responsive layout with proper minimum sizes

## [Unreleased]

### Planned

- Windows installer
- Linux AppImage
- Cloud sync for preferences
- Custom wordlist editor in UI
