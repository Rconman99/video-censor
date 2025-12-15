"""
Multimodal fusion for content detection.

Combines audio (transcript analysis) and visual (NudeNet) detection
for more accurate sexual content identification. When both modalities
agree, confidence is boosted.

Key insight: Sexual dialog often accompanies sexual imagery.
- Dialog alone might be innocent (medical, educational, news)
- Visual alone might be ambiguous (art, medical imagery)
- Both together = high confidence
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum, auto

from ..editing.intervals import TimeInterval, merge_intervals

logger = logging.getLogger(__name__)


class Modality(str, Enum):
    """Detection modality source."""
    AUDIO = "audio"
    VISUAL = "visual"
    MULTIMODAL = "multimodal"


@dataclass
class ModalityScore:
    """Score from a single modality."""
    modality: Modality
    start: float
    end: float
    score: float  # 0.0 to 1.0
    confidence: float = 0.0
    categories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedSegment:
    """A segment with fused multimodal scores."""
    start: float
    end: float
    audio_score: Optional[ModalityScore] = None
    visual_score: Optional[ModalityScore] = None
    
    # Fusion results
    fused_confidence: float = 0.0
    agreement_level: str = "none"  # "both", "audio_only", "visual_only", "none"
    
    @property
    def has_audio(self) -> bool:
        return self.audio_score is not None and self.audio_score.score > 0
    
    @property
    def has_visual(self) -> bool:
        return self.visual_score is not None and self.visual_score.score > 0
    
    @property
    def modality(self) -> Modality:
        if self.has_audio and self.has_visual:
            return Modality.MULTIMODAL
        elif self.has_audio:
            return Modality.AUDIO
        elif self.has_visual:
            return Modality.VISUAL
        else:
            return Modality.AUDIO  # Default
    
    @property
    def categories(self) -> List[str]:
        cats = set()
        if self.audio_score:
            cats.update(self.audio_score.categories)
        if self.visual_score:
            cats.update(self.visual_score.categories)
        return list(cats)


class MultimodalFusion:
    """
    Fuses audio and visual detection results for higher accuracy.
    
    Fusion strategies:
    - Late fusion: Combine scores after independent detection
    - Temporal alignment: Match visual detections with nearby audio
    - Agreement boosting: Boost confidence when modalities agree
    """
    
    def __init__(
        self,
        audio_weight: float = 0.4,
        visual_weight: float = 0.6,
        agreement_boost: float = 0.3,
        temporal_tolerance: float = 2.0,
        min_overlap: float = 0.3,
    ):
        """
        Initialize multimodal fusion.
        
        Args:
            audio_weight: Weight for audio/transcript scores
            visual_weight: Weight for visual/nudity scores
            agreement_boost: Extra confidence when modalities agree
            temporal_tolerance: Max gap (seconds) to align detections
            min_overlap: Minimum overlap ratio to consider aligned
        """
        self.audio_weight = audio_weight
        self.visual_weight = visual_weight
        self.agreement_boost = agreement_boost
        self.temporal_tolerance = temporal_tolerance
        self.min_overlap = min_overlap
    
    def _intervals_overlap(
        self, 
        interval1: Tuple[float, float], 
        interval2: Tuple[float, float],
        tolerance: float = 0.0
    ) -> bool:
        """Check if two time intervals overlap (with tolerance)."""
        start1, end1 = interval1
        start2, end2 = interval2
        return start1 <= (end2 + tolerance) and start2 <= (end1 + tolerance)
    
    def _overlap_ratio(
        self,
        interval1: Tuple[float, float],
        interval2: Tuple[float, float]
    ) -> float:
        """Calculate overlap ratio between two intervals."""
        start1, end1 = interval1
        start2, end2 = interval2
        
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start >= overlap_end:
            return 0.0
        
        overlap_duration = overlap_end - overlap_start
        min_duration = min(end1 - start1, end2 - start2)
        
        if min_duration <= 0:
            return 0.0
        
        return overlap_duration / min_duration
    
    def _convert_to_modality_score(
        self,
        interval: TimeInterval,
        modality: Modality
    ) -> ModalityScore:
        """Convert a TimeInterval to ModalityScore."""
        # Extract score from metadata if available
        score = interval.metadata.get('confidence', 0.5)
        confidence = interval.metadata.get('confidence', 0.5)
        categories = interval.metadata.get('categories', [])
        
        # For visual/nudity detections, check for nudity-specific metadata
        if modality == Modality.VISUAL:
            # NudeNet returns detection names as categories
            if 'detections' in interval.metadata:
                categories = [d.get('label', '') for d in interval.metadata['detections']]
            score = max(score, 0.7)  # Visual detections are typically high confidence
        
        return ModalityScore(
            modality=modality,
            start=interval.start,
            end=interval.end,
            score=score,
            confidence=confidence,
            categories=categories,
            metadata=interval.metadata
        )
    
    def fuse(
        self,
        audio_intervals: List[TimeInterval],
        visual_intervals: List[TimeInterval],
    ) -> List[FusedSegment]:
        """
        Fuse audio and visual detection intervals.
        
        Args:
            audio_intervals: Intervals from transcript/audio analysis
            visual_intervals: Intervals from visual/nudity analysis
            
        Returns:
            List of FusedSegment with combined scores
        """
        if not audio_intervals and not visual_intervals:
            return []
        
        # Convert to modality scores
        audio_scores = [
            self._convert_to_modality_score(i, Modality.AUDIO) 
            for i in audio_intervals
        ]
        visual_scores = [
            self._convert_to_modality_score(i, Modality.VISUAL)
            for i in visual_intervals
        ]
        
        # Track which visual intervals have been matched
        visual_matched = [False] * len(visual_scores)
        
        fused_segments: List[FusedSegment] = []
        
        # For each audio interval, look for overlapping visual
        for audio in audio_scores:
            audio_interval = (audio.start, audio.end)
            
            best_visual = None
            best_overlap = 0.0
            best_visual_idx = -1
            
            for idx, visual in enumerate(visual_scores):
                visual_interval = (visual.start, visual.end)
                
                if self._intervals_overlap(audio_interval, visual_interval, self.temporal_tolerance):
                    overlap = self._overlap_ratio(audio_interval, visual_interval)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_visual = visual
                        best_visual_idx = idx
            
            # Create fused segment
            segment = FusedSegment(
                start=audio.start,
                end=audio.end,
                audio_score=audio,
            )
            
            if best_visual and best_overlap >= self.min_overlap:
                segment.visual_score = best_visual
                segment.agreement_level = "both"
                visual_matched[best_visual_idx] = True
                
                # Extend segment to cover both
                segment.start = min(segment.start, best_visual.start)
                segment.end = max(segment.end, best_visual.end)
                
                # Calculate boosted confidence
                segment.fused_confidence = min(1.0,
                    (audio.confidence * self.audio_weight) +
                    (best_visual.confidence * self.visual_weight) +
                    self.agreement_boost
                )
            else:
                segment.agreement_level = "audio_only"
                segment.fused_confidence = audio.confidence * self.audio_weight
            
            fused_segments.append(segment)
        
        # Add unmatched visual intervals
        for idx, visual in enumerate(visual_scores):
            if not visual_matched[idx]:
                segment = FusedSegment(
                    start=visual.start,
                    end=visual.end,
                    visual_score=visual,
                    agreement_level="visual_only",
                    fused_confidence=visual.confidence * self.visual_weight
                )
                fused_segments.append(segment)
        
        # Sort by start time
        fused_segments.sort(key=lambda s: s.start)
        
        logger.info(
            f"Multimodal fusion: {len(audio_intervals)} audio + "
            f"{len(visual_intervals)} visual -> {len(fused_segments)} fused"
        )
        
        return fused_segments
    
    def to_intervals(
        self,
        fused_segments: List[FusedSegment],
        min_confidence: float = 0.3,
    ) -> List[TimeInterval]:
        """
        Convert fused segments back to TimeIntervals.
        
        Args:
            fused_segments: Fused detection segments
            min_confidence: Minimum confidence to include
            
        Returns:
            List of TimeInterval objects
        """
        intervals = []
        
        for segment in fused_segments:
            if segment.fused_confidence < min_confidence:
                continue
            
            # Build reason string
            modality_str = segment.modality.value
            agreement_str = segment.agreement_level
            
            if segment.agreement_level == "both":
                reason = f"multimodal sexual content (audio+visual confirmed)"
            elif segment.agreement_level == "audio_only":
                reason = f"sexual content (audio/transcript)"
            else:
                reason = f"nudity detected (visual)"
            
            intervals.append(TimeInterval(
                start=segment.start,
                end=segment.end,
                reason=reason,
                metadata={
                    'confidence': segment.fused_confidence,
                    'confidence_level': self._confidence_level(segment.fused_confidence),
                    'modality': modality_str,
                    'agreement_level': agreement_str,
                    'categories': segment.categories,
                    'has_audio': segment.has_audio,
                    'has_visual': segment.has_visual,
                }
            ))
        
        return intervals
    
    def _confidence_level(self, confidence: float) -> str:
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"


def fuse_multimodal_detections(
    audio_intervals: List[TimeInterval],
    visual_intervals: List[TimeInterval],
    audio_weight: float = 0.4,
    visual_weight: float = 0.6,
    agreement_boost: float = 0.3,
    min_confidence: float = 0.3,
    merge_gap: float = 0.5,
) -> List[TimeInterval]:
    """
    Convenience function for multimodal fusion.
    
    Args:
        audio_intervals: Intervals from transcript analysis (sexual content)
        visual_intervals: Intervals from visual analysis (nudity)
        audio_weight: Weight for audio detections
        visual_weight: Weight for visual detections
        agreement_boost: Bonus when modalities agree
        min_confidence: Minimum confidence to include
        merge_gap: Gap for merging nearby intervals
        
    Returns:
        List of fused and merged TimeInterval objects
    """
    fusion = MultimodalFusion(
        audio_weight=audio_weight,
        visual_weight=visual_weight,
        agreement_boost=agreement_boost,
    )
    
    fused = fusion.fuse(audio_intervals, visual_intervals)
    intervals = fusion.to_intervals(fused, min_confidence=min_confidence)
    
    # Merge nearby intervals
    merged = merge_intervals(intervals, merge_gap)
    
    logger.info(
        f"Multimodal result: {len(intervals)} fused -> {len(merged)} merged"
    )
    
    return merged
