"""
Video metadata extraction using ffprobe.
"""

import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class VideoInfo:
    """Video file metadata."""
    path: str
    filename: str
    duration: float  # seconds
    duration_str: str  # "1:23:45"
    width: int
    height: int
    resolution_str: str  # "1920x1080"
    file_size: int  # bytes
    file_size_str: str  # "2.3 GB"
    codec: str
    fps: float
    has_audio: bool
    audio_codec: Optional[str]


def get_video_info(path: str) -> Optional[VideoInfo]:
    """Get video metadata using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        # Get video stream
        video_stream = next(
            (s for s in data.get("streams", []) if s["codec_type"] == "video"),
            None
        )
        
        # Get audio stream
        audio_stream = next(
            (s for s in data.get("streams", []) if s["codec_type"] == "audio"),
            None
        )
        
        format_info = data.get("format", {})
        
        if not video_stream:
            return None
        
        duration = float(format_info.get("duration", 0))
        file_size = int(format_info.get("size", 0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        # Parse FPS (could be "24000/1001" or "24")
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) > 0 else 0
        else:
            fps = float(fps_str)
        
        return VideoInfo(
            path=str(path),
            filename=Path(path).name,
            duration=duration,
            duration_str=_format_duration(duration),
            width=width,
            height=height,
            resolution_str=f"{width}×{height}",
            file_size=file_size,
            file_size_str=_format_size(file_size),
            codec=video_stream.get("codec_name", "unknown"),
            fps=round(fps, 2),
            has_audio=audio_stream is not None,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None
        )
    except Exception as e:
        logger.warning(f"Error getting video info: {e}")
        return None


def _format_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def _format_size(bytes_size: int) -> str:
    """Format bytes as human readable size."""
    size = float(bytes_size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
