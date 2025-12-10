"""
Input validation for Video Censor Tool.

Validates video files before processing.
"""

import logging
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Supported video formats (by extension)
SUPPORTED_FORMATS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpeg', '.mpg', '.3gp', '.ts', '.mts'
}


@dataclass
class VideoInfo:
    """Information about a video file."""
    path: Path
    duration: float  # seconds
    width: int
    height: int
    fps: float
    has_audio: bool
    video_codec: str
    audio_codec: Optional[str]
    
    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


class ValidationError(Exception):
    """Raised when video validation fails."""
    pass


def get_video_info(video_path: Path) -> VideoInfo:
    """
    Get detailed information about a video file using ffprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        VideoInfo object with video details
        
    Raises:
        ValidationError: If the file cannot be probed
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise ValidationError(f"Failed to probe video: {e.stderr}")
    except json.JSONDecodeError as e:
        raise ValidationError(f"Failed to parse ffprobe output: {e}")
    
    # Extract format info
    format_info = data.get('format', {})
    duration = float(format_info.get('duration', 0))
    
    # Find video and audio streams
    video_stream = None
    audio_stream = None
    
    for stream in data.get('streams', []):
        codec_type = stream.get('codec_type')
        if codec_type == 'video' and video_stream is None:
            video_stream = stream
        elif codec_type == 'audio' and audio_stream is None:
            audio_stream = stream
    
    if video_stream is None:
        raise ValidationError("No video stream found in file")
    
    # Extract video properties
    width = int(video_stream.get('width', 0))
    height = int(video_stream.get('height', 0))
    video_codec = video_stream.get('codec_name', 'unknown')
    
    # Parse frame rate (can be "30/1" or "29.97" format)
    fps_str = video_stream.get('r_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)
    
    # Audio info
    has_audio = audio_stream is not None
    audio_codec = audio_stream.get('codec_name') if audio_stream else None
    
    return VideoInfo(
        path=video_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
        video_codec=video_codec,
        audio_codec=audio_codec
    )


def validate_input(video_path: Path) -> Tuple[bool, Optional[str], Optional[VideoInfo]]:
    """
    Validate that the input file exists and is a supported video format.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Tuple of (is_valid, error_message, video_info)
    """
    # Check file exists
    if not video_path.exists():
        return False, f"File not found: {video_path}", None
    
    # Check it's a file, not a directory
    if not video_path.is_file():
        return False, f"Not a file: {video_path}", None
    
    # Check extension is supported
    suffix = video_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return False, f"Unsupported format '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}", None
    
    # Check ffprobe is available
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, "ffprobe not found. Please install ffmpeg: brew install ffmpeg", None
    
    # Get video info
    try:
        info = get_video_info(video_path)
    except ValidationError as e:
        return False, str(e), None
    
    # Validate video has content
    if info.duration <= 0:
        return False, "Video has no duration", None
    
    if info.width <= 0 or info.height <= 0:
        return False, "Video has invalid dimensions", None
    
    logger.info(f"Validated video: {info.resolution} @ {info.fps:.2f}fps, {info.duration:.2f}s")
    
    return True, None, info


def validate_output_path(output_path: Path, overwrite: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate that the output path is writable.
    
    Args:
        output_path: Path for the output file
        overwrite: Whether to allow overwriting existing files
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check parent directory exists
    parent = output_path.parent
    if not parent.exists():
        return False, f"Output directory does not exist: {parent}"
    
    # Check parent is writable
    if not parent.is_dir():
        return False, f"Output parent is not a directory: {parent}"
    
    # Check if file already exists
    if output_path.exists() and not overwrite:
        return False, f"Output file already exists: {output_path}. Use --overwrite to replace."
    
    return True, None
