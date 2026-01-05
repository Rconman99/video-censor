"""
Smart frame sampling with scene change detection.

Optimizes frame extraction by:
- Sampling more frequently during scene changes
- Sampling less frequently during static scenes
- Always sampling first frame of new scene

Uses frame differencing to detect scene changes.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SceneChange:
    """A detected scene change."""
    timestamp: float
    confidence: float = 1.0


@dataclass 
class SamplingPlan:
    """Plan for frame sampling."""
    timestamps: List[float]
    scene_changes: List[SceneChange]
    strategy: str = "adaptive"


def detect_scene_changes(
    video_path: Path,
    threshold: float = 0.3,
    min_scene_length: float = 1.0
) -> List[SceneChange]:
    """
    Detect scene changes in a video using FFmpeg's scene filter.
    
    Args:
        video_path: Path to video file
        threshold: Scene change detection threshold (0-1, lower = more sensitive)
        min_scene_length: Minimum time between scene changes
        
    Returns:
        List of SceneChange objects with timestamps
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_frames',
        '-select_streams', 'v:0',
        '-of', 'csv=p=0',
        '-f', 'lavfi',
        f"movie='{str(video_path)}',select='gt(scene\\,{threshold})'",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        scene_changes = []
        last_time = -min_scene_length
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split(',')
            if len(parts) >= 5:
                try:
                    pts_time = float(parts[4])
                    if pts_time - last_time >= min_scene_length:
                        scene_changes.append(SceneChange(
                            timestamp=pts_time,
                            confidence=threshold
                        ))
                        last_time = pts_time
                except (ValueError, IndexError):
                    continue
        
        logger.info(f"Detected {len(scene_changes)} scene changes")
        return scene_changes
        
    except subprocess.TimeoutExpired:
        logger.warning("Scene detection timed out, using fallback")
        return []
    except Exception as e:
        logger.warning(f"Scene detection failed: {e}")
        return []


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 0.0


def create_adaptive_sampling_plan(
    video_path: Path,
    base_interval: float = 0.5,
    scene_interval: float = 0.1,
    scene_duration: float = 2.0,
    scene_threshold: float = 0.3
) -> SamplingPlan:
    """
    Create an adaptive frame sampling plan.
    
    Samples more densely around scene changes, less during static content.
    
    Args:
        video_path: Path to video file
        base_interval: Interval for static scenes (seconds)
        scene_interval: Interval around scene changes (seconds)
        scene_duration: Duration to use dense sampling after scene change
        scene_threshold: Threshold for scene change detection
        
    Returns:
        SamplingPlan with optimized timestamps
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        logger.warning("Could not determine video duration")
        return SamplingPlan(timestamps=[], scene_changes=[], strategy="failed")
    
    # Detect scene changes
    scene_changes = detect_scene_changes(video_path, scene_threshold)
    
    # Build timeline of "dense" regions (around scene changes)
    dense_regions: List[Tuple[float, float]] = []
    for sc in scene_changes:
        start = max(0, sc.timestamp - scene_duration / 2)
        end = min(duration, sc.timestamp + scene_duration / 2)
        dense_regions.append((start, end))
    
    # Merge overlapping regions
    dense_regions = _merge_regions(dense_regions)
    
    # Generate timestamps
    timestamps = []
    t = 0.0
    
    while t < duration:
        timestamps.append(t)
        
        # Check if in dense region
        in_dense = any(start <= t <= end for start, end in dense_regions)
        
        if in_dense:
            t += scene_interval
        else:
            t += base_interval
    
    # Ensure we sample first and last frames
    if timestamps and timestamps[-1] < duration - 0.5:
        timestamps.append(duration - 0.1)
    
    # Add first frame of each scene
    for sc in scene_changes:
        if sc.timestamp not in timestamps:
            timestamps.append(sc.timestamp)
    
    timestamps = sorted(set(timestamps))
    
    logger.info(f"Adaptive sampling: {len(timestamps)} frames "
                f"(vs {int(duration / base_interval)} at fixed interval)")
    
    return SamplingPlan(
        timestamps=timestamps,
        scene_changes=scene_changes,
        strategy="adaptive"
    )


def create_fixed_sampling_plan(
    video_path: Path,
    interval: float = 0.15
) -> SamplingPlan:
    """
    Create a fixed-interval sampling plan (fallback/simple mode).
    
    Args:
        video_path: Path to video file
        interval: Fixed interval between frames
        
    Returns:
        SamplingPlan with evenly-spaced timestamps
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return SamplingPlan(timestamps=[], scene_changes=[], strategy="fixed")
    
    timestamps = []
    t = 0.0
    while t < duration:
        timestamps.append(t)
        t += interval
    
    return SamplingPlan(
        timestamps=timestamps,
        scene_changes=[],
        strategy="fixed"
    )


def get_sample_timestamps(
    video_path: Path,
    adaptive: bool = True,
    base_interval: float = 0.5,
    scene_interval: float = 0.1,
    fixed_interval: float = 0.15
) -> List[float]:
    """
    Get frame timestamps for sampling.
    
    Args:
        video_path: Path to video file
        adaptive: Use adaptive sampling (True) or fixed interval (False)
        base_interval: Interval for adaptive static scenes
        scene_interval: Interval for adaptive scene regions
        fixed_interval: Interval for fixed sampling
        
    Returns:
        List of timestamps to sample
    """
    if adaptive:
        plan = create_adaptive_sampling_plan(
            video_path,
            base_interval=base_interval,
            scene_interval=scene_interval
        )
        if plan.strategy == "failed":
            # Fallback to fixed
            plan = create_fixed_sampling_plan(video_path, fixed_interval)
    else:
        plan = create_fixed_sampling_plan(video_path, fixed_interval)
    
    return plan.timestamps


def _merge_regions(regions: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Merge overlapping time regions."""
    if not regions:
        return []
    
    sorted_regions = sorted(regions, key=lambda r: r[0])
    merged = [sorted_regions[0]]
    
    for start, end in sorted_regions[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    
    return merged
