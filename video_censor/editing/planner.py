"""
Edit planning for video censoring.

Combines profanity, nudity, sexual content, and violence detections into a cohesive edit plan.
"""

import logging
from dataclasses import dataclass, field
from typing import List

from .intervals import TimeInterval, merge_intervals, compute_keep_segments

logger = logging.getLogger(__name__)


@dataclass
class AudioEdit:
    """An audio edit to apply (mute or beep)."""
    start: float
    end: float
    edit_type: str  # "mute" or "beep"
    reason: str = ""
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class EditPlan:
    """Complete edit plan for a video."""
    # Original video info
    original_duration: float
    
    # Segments to keep (after nudity + sexual content cuts)
    keep_segments: List[TimeInterval] = field(default_factory=list)
    
    # Audio edits to apply (mute/beep for profanity)
    audio_edits: List[AudioEdit] = field(default_factory=list)
    
    # Intervals that were cut (nudity + sexual content combined)
    cut_intervals: List[TimeInterval] = field(default_factory=list)
    
    # Raw detections for reporting
    profanity_intervals: List[TimeInterval] = field(default_factory=list)
    nudity_intervals: List[TimeInterval] = field(default_factory=list)
    sexual_content_intervals: List[TimeInterval] = field(default_factory=list)
    violence_intervals: List[TimeInterval] = field(default_factory=list)
    
    @property
    def output_duration(self) -> float:
        """Calculate expected output duration."""
        return sum(seg.duration for seg in self.keep_segments)
    
    @property
    def cut_duration(self) -> float:
        """Calculate total duration cut."""
        return sum(seg.duration for seg in self.cut_intervals)
    
    @property
    def profanity_count(self) -> int:
        """Number of profanity instances."""
        return len(self.profanity_intervals)
    
    @property
    def nudity_count(self) -> int:
        """Number of nudity segments cut."""
        return len(self.nudity_intervals)
    
    @property
    def sexual_content_count(self) -> int:
        """Number of sexual content segments cut."""
        return len(self.sexual_content_intervals)
    
    @property
    def violence_count(self) -> int:
        """Number of violence segments cut."""
        return len(self.violence_intervals)
    
    def summary(self) -> str:
        """Generate a summary of the edit plan."""
        lines = [
            "Edit Plan Summary",
            "=" * 40,
            f"Original duration: {self.original_duration:.2f}s",
            f"Output duration:   {self.output_duration:.2f}s",
            f"Duration cut:      {self.cut_duration:.2f}s",
            "",
            f"Profanity instances: {self.profanity_count}",
            f"Audio edits:         {len(self.audio_edits)}",
            f"Nudity segments:     {self.nudity_count}",
            f"Sexual content:      {self.sexual_content_count}",
            f"Violence segments:   {self.violence_count}",
            f"Total cuts:          {len(self.cut_intervals)}",
            f"Keep segments:       {len(self.keep_segments)}",
        ]
        return "\n".join(lines)


def plan_edits(
    profanity_intervals: List[TimeInterval],
    nudity_intervals: List[TimeInterval],
    duration: float,
    profanity_merge_gap: float = 0.3,
    nudity_merge_gap: float = 0.5,
    censor_mode: str = "beep",
    min_segment_duration: float = 0.1,
    min_cut_duration: float = 0.3,
    sexual_content_intervals: List[TimeInterval] = None,
    violence_intervals: List[TimeInterval] = None
) -> EditPlan:
    """
    Create an edit plan from detected profanity, nudity, sexual content, and violence.
    
    Args:
        profanity_intervals: Intervals where profanity was detected (beep/mute only)
        nudity_intervals: Intervals where nudity was detected (video cuts)
        duration: Total video duration
        profanity_merge_gap: Gap threshold for merging profanity intervals
        nudity_merge_gap: Gap threshold for merging nudity intervals
        censor_mode: "mute" or "beep" for profanity
        min_segment_duration: Minimum segment duration to keep
        min_cut_duration: Minimum cut duration (prevents micro-cuts)
        sexual_content_intervals: Intervals with sexual dialog (video cuts)
        violence_intervals: Intervals with violence (video cuts)
        
    Returns:
        EditPlan with all edit instructions
    """
    logger.info("Planning edits...")
    
    if sexual_content_intervals is None:
        sexual_content_intervals = []
    if violence_intervals is None:
        violence_intervals = []
    
    # Merge profanity intervals
    merged_profanity = merge_intervals(profanity_intervals, profanity_merge_gap)
    logger.info(f"Merged profanity: {len(profanity_intervals)} -> {len(merged_profanity)} intervals")
    
    # Merge nudity intervals
    merged_nudity = merge_intervals(nudity_intervals, nudity_merge_gap)
    logger.info(f"Merged nudity: {len(nudity_intervals)} -> {len(merged_nudity)} intervals")
    
    # Merge sexual content intervals
    merged_sexual = merge_intervals(sexual_content_intervals, nudity_merge_gap)
    logger.info(f"Merged sexual content: {len(sexual_content_intervals)} -> {len(merged_sexual)} intervals")
    
    # Merge violence intervals
    merged_violence = merge_intervals(violence_intervals, nudity_merge_gap)
    logger.info(f"Merged violence: {len(violence_intervals)} -> {len(merged_violence)} intervals")
    
    # Combine nudity, sexual content, and violence into unified cut list
    all_cut_intervals = merged_nudity + merged_sexual + merged_violence
    all_cuts_merged = merge_intervals(all_cut_intervals, nudity_merge_gap)
    logger.info(f"Combined cuts (nudity + sexual + violence): {len(all_cut_intervals)} -> {len(all_cuts_merged)} intervals")
    
    # Filter out micro-cuts (cuts shorter than min_cut_duration)
    if min_cut_duration > 0:
        original_count = len(all_cuts_merged)
        all_cuts_merged = [
            interval for interval in all_cuts_merged
            if interval.duration >= min_cut_duration
        ]
        if len(all_cuts_merged) < original_count:
            logger.info(f"Filtered micro-cuts: {original_count} -> {len(all_cuts_merged)} (min_duration={min_cut_duration}s)")
    
    # Compute segments to keep (inverse of all cuts)
    keep_segments = compute_keep_segments(
        duration=duration,
        cut_intervals=all_cuts_merged,
        min_segment_duration=min_segment_duration
    )
    logger.info(f"Keep segments: {len(keep_segments)}")
    
    # Create audio edits for profanity
    # Only include profanity that falls within keep segments
    # (profanity in cut sections is already removed)
    audio_edits: List[AudioEdit] = []
    
    for prof_interval in merged_profanity:
        # Check if this profanity falls within a keep segment
        for keep_seg in keep_segments:
            if keep_seg.contains(prof_interval.start) or keep_seg.contains(prof_interval.end):
                # Clip to keep segment bounds
                edit_start = max(prof_interval.start, keep_seg.start)
                edit_end = min(prof_interval.end, keep_seg.end)
                
                if edit_end > edit_start:
                    audio_edits.append(AudioEdit(
                        start=edit_start,
                        end=edit_end,
                        edit_type=censor_mode,
                        reason=prof_interval.reason
                    ))
                break
    
    logger.info(f"Audio edits: {len(audio_edits)}")
    
    # Create the edit plan
    plan = EditPlan(
        original_duration=duration,
        keep_segments=keep_segments,
        audio_edits=audio_edits,
        cut_intervals=all_cuts_merged,
        profanity_intervals=profanity_intervals,
        nudity_intervals=nudity_intervals,
        sexual_content_intervals=sexual_content_intervals,
        violence_intervals=violence_intervals
    )
    
    logger.info(f"Edit plan complete:\n{plan.summary()}")
    
    return plan


def adjust_edits_for_cuts(plan: EditPlan) -> List[AudioEdit]:
    """
    Adjust audio edit timestamps to account for cut segments.
    
    When nudity segments are cut, the timestamps of remaining content
    shift earlier. This function adjusts audio edit times accordingly.
    
    Args:
        plan: The original edit plan
        
    Returns:
        List of AudioEdit with adjusted timestamps
    """
    if not plan.cut_intervals:
        return plan.audio_edits.copy()
    
    adjusted_edits: List[AudioEdit] = []
    
    for edit in plan.audio_edits:
        # Calculate how much time has been cut before this edit
        cut_before = 0.0
        for cut in plan.cut_intervals:
            if cut.end <= edit.start:
                cut_before += cut.duration
        
        # Adjust timestamps
        adjusted_edits.append(AudioEdit(
            start=edit.start - cut_before,
            end=edit.end - cut_before,
            edit_type=edit.edit_type,
            reason=edit.reason
        ))
    
    return adjusted_edits
