"""
Interval merging utilities.

Provides functions to merge overlapping or nearby time intervals.
This is critical to prevent stuttering playback from many small edits.
"""

import logging
from dataclasses import dataclass
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class Action(str, Enum):
    """Action to take for a censored segment."""
    CUT = "cut"
    MUTE = "mute"
    BEEP = "beep"
    BLUR = "blur"
    NONE = "none"


class MatchSource(str, Enum):
    """Source of the detection."""
    AUDIO = "audio"      # From Whisper transcript
    VISUAL = "visual"    # From Nudity/Violence detector
    SUBTITLE = "subtitle" # From subtitle file
    MANUAL = "manual"    # User manually added
    UNKNOWN = "unknown"



@dataclass
class TimeInterval:
    """A time interval in the video."""
    start: float  # seconds
    end: float    # seconds
    reason: str = ""  # Why this interval was marked
    action: Action = Action.CUT  # Default action
    source: MatchSource = MatchSource.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    def __repr__(self) -> str:
        return f"TimeInterval({self.start:.2f}-{self.end:.2f}s, {self.action.value}, {self.reason})"
    
    def __lt__(self, other: "TimeInterval") -> bool:
        return self.start < other.start
    
    def overlaps(self, other: "TimeInterval", gap: float = 0.0) -> bool:
        """
        Check if this interval overlaps with another, considering a gap tolerance.
        
        Args:
            other: Another TimeInterval
            gap: Maximum gap between intervals to still consider them overlapping
            
        Returns:
            True if intervals overlap or are within gap distance
        """
        return self.start <= (other.end + gap) and other.start <= (self.end + gap)
    
    def merge(self, other: "TimeInterval") -> "TimeInterval":
        """Merge this interval with another, combining reasons."""
        reasons = []
        if self.reason:
            reasons.append(self.reason)
        if other.reason and other.reason not in reasons:
            reasons.append(other.reason)
            
        # Determine merged action - CUT overrides MUTE/BEEP
        merged_action = self.action
        if Action.CUT in (self.action, other.action):
            merged_action = Action.CUT
            
        return TimeInterval(
            start=min(self.start, other.start),
            end=max(self.end, other.end),
            reason="; ".join(reasons) if reasons else "",
            action=merged_action,
            source=self.source # Keep primary source of left interval
        )
    
    def contains(self, time: float) -> bool:
        """Check if a time point falls within this interval."""
        return self.start <= time <= self.end


def merge_intervals(
    intervals: List[TimeInterval],
    gap: float = 0.0
) -> List[TimeInterval]:
    """
    Merge overlapping or nearby intervals.
    
    This is an important step to prevent stuttering edits when
    multiple detections occur close together.
    
    Args:
        intervals: List of TimeInterval objects
        gap: Maximum gap (seconds) between intervals to merge them
        
    Returns:
        List of merged TimeInterval objects, sorted by start time
    """
    if not intervals:
        return []
    
    # Sort by start time
    sorted_intervals = sorted(intervals)
    
    merged: List[TimeInterval] = [sorted_intervals[0]]
    
    for current in sorted_intervals[1:]:
        last = merged[-1]
        
        if last.overlaps(current, gap):
            # Merge with the last interval
            merged[-1] = last.merge(current)
        else:
            # No overlap, add as new interval
            merged.append(current)
    
    original_count = len(intervals)
    merged_count = len(merged)
    
    if merged_count < original_count:
        logger.info(f"Merged {original_count} intervals into {merged_count}")
    
    return merged


def subtract_intervals(
    base: List[TimeInterval],
    subtract: List[TimeInterval]
) -> List[TimeInterval]:
    """
    Subtract one set of intervals from another.
    
    Returns the parts of base intervals that don't overlap with subtract intervals.
    
    Args:
        base: Base intervals to subtract from
        subtract: Intervals to remove
        
    Returns:
        Remaining intervals after subtraction
    """
    if not base:
        return []
    if not subtract:
        return base.copy()
    
    result: List[TimeInterval] = []
    
    for interval in base:
        remaining = [interval]
        
        for sub in subtract:
            new_remaining = []
            
            for rem in remaining:
                if not rem.overlaps(sub):
                    # No overlap, keep as is
                    new_remaining.append(rem)
                else:
                    # Has overlap, may split into parts
                    if rem.start < sub.start:
                        # Part before subtraction
                        new_remaining.append(TimeInterval(
                            start=rem.start,
                            end=min(rem.end, sub.start),
                            reason=rem.reason
                        ))
                    if rem.end > sub.end:
                        # Part after subtraction
                        new_remaining.append(TimeInterval(
                            start=max(rem.start, sub.end),
                            end=rem.end,
                            reason=rem.reason
                        ))
            
            remaining = new_remaining
        
        result.extend(remaining)
    
    return result


def compute_keep_segments(
    duration: float,
    cut_intervals: List[TimeInterval],
    min_segment_duration: float = 0.1
) -> List[TimeInterval]:
    """
    Compute the segments to keep (inverse of cut intervals).
    
    Args:
        duration: Total video duration in seconds
        cut_intervals: Intervals to cut from the video
        min_segment_duration: Minimum segment duration to keep
        
    Returns:
        List of intervals to keep
    """
    if not cut_intervals:
        return [TimeInterval(start=0, end=duration, reason="full video")]
    
    # Merge and sort cut intervals
    merged_cuts = merge_intervals(cut_intervals)
    
    keep_segments: List[TimeInterval] = []
    current_time = 0.0
    
    for cut in merged_cuts:
        if cut.start > current_time:
            # There's a segment to keep before this cut
            segment = TimeInterval(
                start=current_time,
                end=cut.start,
                reason="keep"
            )
            if segment.duration >= min_segment_duration:
                keep_segments.append(segment)
        
        current_time = cut.end
    
    # Handle end of video
    if current_time < duration:
        segment = TimeInterval(
            start=current_time,
            end=duration,
            reason="keep"
        )
        if segment.duration >= min_segment_duration:
            keep_segments.append(segment)
    
    return keep_segments


def add_buffer_to_intervals(
    intervals: List[TimeInterval],
    buffer_before: float,
    buffer_after: float,
    max_duration: Optional[float] = None
) -> List[TimeInterval]:
    """
    Add buffer time before and after each interval.
    
    Args:
        intervals: List of intervals
        buffer_before: Seconds to add before each interval
        buffer_after: Seconds to add after each interval
        max_duration: Maximum allowed end time (clips to video duration)
        
    Returns:
        List of buffered intervals
    """
    buffered = []
    
    for interval in intervals:
        start = max(0, interval.start - buffer_before)
        end = interval.end + buffer_after
        
        if max_duration is not None:
            end = min(end, max_duration)
        
        buffered.append(TimeInterval(
            start=start,
            end=end,
            reason=interval.reason
        ))
    
    return buffered
