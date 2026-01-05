"""
Audio extraction from video files.

Uses ffmpeg to extract audio track in a format suitable for transcription.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_audio(
    video_path: Path,
    output_path: Optional[Path] = None,
    sample_rate: int = 16000,
    mono: bool = True
) -> Path:
    """
    Extract audio from a video file.
    
    Extracts audio to WAV format at 16kHz mono, which is optimal
    for Whisper transcription.
    
    Args:
        video_path: Path to the input video file
        output_path: Path for output audio file (optional, creates temp file if not provided)
        sample_rate: Audio sample rate in Hz (default 16000 for Whisper)
        mono: Convert to mono audio (default True for Whisper)
        
    Returns:
        Path to the extracted audio file
        
    Raises:
        RuntimeError: If audio extraction fails
    """
    # Create output path if not provided
    if output_path is None:
        temp_dir = tempfile.mkdtemp(prefix="video_censor_")
        output_path = Path(temp_dir) / "audio.wav"
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Extracting audio from {video_path.name}")
    
    # Build ffmpeg command
    cmd = [
        'ffmpeg',
        '-nostdin', # Prevent reading from stdin (crucial for background processes)
        '-y',  # Overwrite output
        '-i', str(video_path),
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
        '-ar', str(sample_rate),  # Sample rate
    ]
    
    if mono:
        cmd.extend(['-ac', '1'])  # Mono
    
    cmd.append(str(output_path))
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.debug(f"ffmpeg output: {result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Audio extraction failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract audio: {e.stderr}")
    
    if not output_path.exists():
        raise RuntimeError("Audio file was not created")
    
    file_size = output_path.stat().st_size
    logger.info(f"Extracted audio: {output_path.name} ({file_size / 1024 / 1024:.2f} MB)")
    
    return output_path


def get_audio_duration(audio_path: Path) -> float:
    """
    Get the duration of an audio file in seconds.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Duration in seconds
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(audio_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.warning(f"Could not get audio duration: {e}")
        return 0.0
