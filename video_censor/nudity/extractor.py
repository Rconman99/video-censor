"""
Frame extraction from video files.

Uses ffmpeg to extract frames at configurable intervals for nudity detection.
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """Information about an extracted frame."""
    path: Path
    timestamp: float  # seconds
    frame_number: int
    
    def __repr__(self) -> str:
        return f"FrameInfo(frame={self.frame_number}, t={self.timestamp:.2f}s)"


def extract_frames(
    video_path: Path,
    interval: float = 0.25,
    output_dir: Optional[Path] = None,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    max_frames: Optional[int] = None
) -> List[FrameInfo]:
    """
    Extract frames from a video at specified intervals.
    
    Args:
        video_path: Path to the input video file
        interval: Time between frames in seconds (default 0.25 = 4 fps)
        output_dir: Directory for output frames (creates temp dir if not provided)
        start_time: Start extracting from this time (seconds)
        end_time: Stop extracting at this time (seconds, None = end of video)
        max_frames: Maximum number of frames to extract (None = no limit)
        
    Returns:
        List of FrameInfo objects for extracted frames
        
    Raises:
        RuntimeError: If frame extraction fails
    """
    # Create output directory
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="video_censor_frames_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Extracting frames from {video_path.name} (interval={interval}s)")
    
    # Calculate fps from interval
    fps = 1.0 / interval
    
    # Build ffmpeg command
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output
        '-i', str(video_path),
    ]
    
    # Add time bounds
    if start_time > 0:
        cmd.extend(['-ss', str(start_time)])
    
    if end_time is not None:
        duration = end_time - start_time
        cmd.extend(['-t', str(duration)])
    
    # Output settings
    cmd.extend([
        '-vf', f'fps={fps}',  # Frame rate filter
        '-frame_pts', '1',    # Use presentation timestamp in filename
        str(output_dir / 'frame_%06d.jpg')
    ])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.debug(f"ffmpeg output: {result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Frame extraction failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract frames: {e.stderr}")
    
    # Collect extracted frames
    frames: List[FrameInfo] = []
    frame_files = sorted(output_dir.glob('frame_*.jpg'))
    
    for i, frame_path in enumerate(frame_files):
        if max_frames is not None and i >= max_frames:
            break
            
        timestamp = start_time + (i * interval)
        frames.append(FrameInfo(
            path=frame_path,
            timestamp=timestamp,
            frame_number=i
        ))
    
    logger.info(f"Extracted {len(frames)} frames to {output_dir}")
    
    return frames


def cleanup_frames(frames: List[FrameInfo]) -> None:
    """
    Delete extracted frame files.
    
    Args:
        frames: List of FrameInfo objects to clean up
    """
    for frame in frames:
        try:
            if frame.path.exists():
                frame.path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete frame {frame.path}: {e}")


def get_frame_at_time(
    video_path: Path,
    timestamp: float,
    output_path: Optional[Path] = None
) -> Path:
    """
    Extract a single frame at a specific timestamp.
    
    Args:
        video_path: Path to the video file
        timestamp: Time in seconds
        output_path: Path for output image (creates temp file if not provided)
        
    Returns:
        Path to the extracted frame image
    """
    if output_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="video_censor_"))
        output_path = temp_dir / f"frame_{timestamp:.3f}.jpg"
    
    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(timestamp),
        '-i', str(video_path),
        '-frames:v', '1',
        '-q:v', '2',  # High quality
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract frame at {timestamp}s: {e.stderr}")
    
    return output_path
