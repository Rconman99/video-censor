"""
Keyframe extraction and snapping utilities.

Provides functions to extract keyframe timestamps from video files
and snap cut points to keyframes for faster (stream copy) rendering.

Inspired by LosslessCut's smart cutting approach.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Literal

logger = logging.getLogger(__name__)


def get_keyframes(video_path: Path, timeout: int = 60) -> List[float]:
    """
    Extract keyframe timestamps from a video file using ffprobe.
    
    Args:
        video_path: Path to video file
        timeout: Maximum time to wait for ffprobe (seconds)
        
    Returns:
        Sorted list of keyframe timestamps in seconds
    """
    logger.info(f"Extracting keyframes from: {video_path.name}")
    
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',  # First video stream
        '-show_packets',
        '-show_entries', 'packet=pts_time,flags',
        '-of', 'json',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.warning(f"ffprobe failed: {result.stderr}")
            return []
        
        data = json.loads(result.stdout)
        packets = data.get('packets', [])
        
        keyframes = []
        for packet in packets:
            flags = packet.get('flags', '')
            pts_time = packet.get('pts_time')
            
            # Keyframes have 'K' flag
            if 'K' in flags and pts_time:
                try:
                    keyframes.append(float(pts_time))
                except (ValueError, TypeError):
                    continue
        
        keyframes = sorted(set(keyframes))  # Remove duplicates, sort
        logger.info(f"Found {len(keyframes)} keyframes in {video_path.name}")
        
        return keyframes
        
    except subprocess.TimeoutExpired:
        logger.error(f"Keyframe extraction timed out after {timeout}s")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe output: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to extract keyframes: {e}")
        return []


SnapMode = Literal['nearest', 'before', 'after']


def snap_to_keyframe(
    time: float,
    keyframes: List[float],
    mode: SnapMode = 'nearest',
    tolerance: float = 0.5
) -> Optional[float]:
    """
    Snap a cut point to the nearest keyframe.
    
    Args:
        time: Target cut time in seconds
        keyframes: List of keyframe timestamps
        mode: Snap behavior
            - 'nearest': Closest keyframe (best for user edits)
            - 'before': Keyframe at or before time (safe for start cuts)
            - 'after': Keyframe at or after time (safe for end cuts)
        tolerance: Max distance to snap (seconds). If no keyframe within
                   tolerance, returns None.
    
    Returns:
        Snapped keyframe time, or None if no keyframe within tolerance
    """
    if not keyframes:
        return None
    
    if mode == 'nearest':
        closest = min(keyframes, key=lambda kf: abs(kf - time))
        if abs(closest - time) <= tolerance:
            return closest
        return None
    
    elif mode == 'before':
        # Find keyframes at or before time
        candidates = [kf for kf in keyframes if kf <= time + 0.001]
        if not candidates:
            return None
        closest = max(candidates)  # Latest keyframe before time
        if abs(closest - time) <= tolerance:
            return closest
        return None
    
    elif mode == 'after':
        # Find keyframes at or after time
        candidates = [kf for kf in keyframes if kf >= time - 0.001]
        if not candidates:
            return None
        closest = min(candidates)  # Earliest keyframe after time
        if abs(closest - time) <= tolerance:
            return closest
        return None
    
    return None


def is_on_keyframe(time: float, keyframes: List[float], epsilon: float = 0.001) -> bool:
    """
    Check if a time is exactly on a keyframe.
    
    Args:
        time: Time to check
        keyframes: List of keyframe timestamps
        epsilon: Tolerance for floating point comparison
        
    Returns:
        True if time is on a keyframe
    """
    if not keyframes:
        return False
    return any(abs(kf - time) < epsilon for kf in keyframes)


def find_keyframe_interval(
    start: float,
    end: float,
    keyframes: List[float]
) -> tuple[Optional[float], Optional[float]]:
    """
    Find the largest keyframe-aligned interval within [start, end].
    
    This is useful for maximizing stream-copy portion of a cut.
    
    Args:
        start: Interval start time
        end: Interval end time
        keyframes: List of keyframe timestamps
        
    Returns:
        Tuple of (adjusted_start, adjusted_end) or (None, None) if no keyframes in range
    """
    # Find keyframes within the interval
    interval_keyframes = [kf for kf in keyframes if start <= kf <= end]
    
    if not interval_keyframes:
        return (None, None)
    
    # First keyframe at or after start
    adjusted_start = min(interval_keyframes)
    
    # Last keyframe at or before end (but after start)
    candidates = [kf for kf in keyframes if adjusted_start < kf <= end]
    if candidates:
        adjusted_end = max(candidates)
    else:
        adjusted_end = adjusted_start
    
    return (adjusted_start, adjusted_end)


def get_keyframe_density(keyframes: List[float], duration: float) -> float:
    """
    Calculate average keyframes per second.
    
    Args:
        keyframes: List of keyframe timestamps
        duration: Video duration in seconds
        
    Returns:
        Keyframes per second (typically 0.5-2 for most videos)
    """
    if duration <= 0:
        return 0.0
    return len(keyframes) / duration
