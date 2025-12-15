"""
Hybrid sexual content detector combining lexicon and semantic approaches.

Uses fast lexicon matching as a first pass, then optionally verifies
candidates with semantic similarity for higher accuracy.

This provides the best of both worlds:
- Speed of keyword matching
- Accuracy of ML-based semantic detection
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from ..audio.transcriber import WordTimestamp
from ..editing.intervals import TimeInterval, merge_intervals
from .detector import (
    SexualContentDetector,
    SexualContentMatch,
    SegmentScore,
)
from .semantic_detector import (
    SemanticSexualDetector,
    SemanticAnalysis,
    is_semantic_detection_available,
    get_semantic_detector,
)

logger = logging.getLogger(__name__)


@dataclass
class HybridSegmentScore:
    """Extended segment score with both lexicon and semantic results."""
    
    # From lexicon detector
    lexicon_score: SegmentScore
    
    # From semantic detector (optional)
    semantic_analysis: Optional[SemanticAnalysis] = None
    
    # Combined results
    combined_confidence: float = 0.0
    verification_status: str = "pending"  # "verified", "rejected", "pending", "skipped"
    
    @property
    def start(self) -> float:
        return self.lexicon_score.start
    
    @property
    def end(self) -> float:
        return self.lexicon_score.end
    
    @property
    def text(self) -> str:
        return self.lexicon_score.text
    
    @property
    def is_verified(self) -> bool:
        """Whether semantic detection verified this as sexual content."""
        return self.verification_status == "verified"
    
    @property
    def is_rejected(self) -> bool:
        """Whether semantic detection rejected this as NOT sexual content."""
        return self.verification_status == "rejected"
    
    @property
    def should_flag(self) -> bool:
        """Whether this segment should be flagged based on hybrid analysis."""
        # If semantic verified or skipped (no semantic), use lexicon result
        if self.verification_status in ("verified", "skipped"):
            return True
        # If semantic rejected, don't flag
        if self.verification_status == "rejected":
            return False
        # Pending - use lexicon result as fallback
        return self.lexicon_score.active_match_count > 0


class HybridSexualContentDetector:
    """
    Combines fast lexicon matching with semantic verification.
    
    Strategy:
    1. Run fast lexicon detection on all segments
    2. For flagged segments, optionally verify with semantic detection
    3. Semantic detection can confirm, reject, or be neutral
    
    This reduces false positives while maintaining speed for most content.
    """
    
    def __init__(
        self,
        lexicon_detector: Optional[SexualContentDetector] = None,
        semantic_detector: Optional[SemanticSexualDetector] = None,
        use_semantic: bool = True,
        semantic_threshold: float = 0.5,
        semantic_reject_threshold: float = 0.3,
        semantic_boost: float = 0.3,
        only_verify_uncertain: bool = True,
        uncertain_threshold: float = 1.5,
    ):
        """
        Initialize hybrid detector.
        
        Args:
            lexicon_detector: Pre-configured lexicon detector (uses default if None)
            semantic_detector: Pre-loaded semantic detector (loads on demand if None)
            use_semantic: Whether to use semantic verification
            semantic_threshold: Min semantic score to verify as sexual
            semantic_reject_threshold: Below this, reject as NOT sexual
            semantic_boost: Confidence boost when semantically verified
            only_verify_uncertain: Only run semantic on uncertain detections
            uncertain_threshold: Lexicon score below this is "uncertain"
        """
        self.lexicon = lexicon_detector or SexualContentDetector()
        self.semantic = semantic_detector
        self.use_semantic = use_semantic and is_semantic_detection_available()
        self.semantic_threshold = semantic_threshold
        self.semantic_reject_threshold = semantic_reject_threshold
        self.semantic_boost = semantic_boost
        self.only_verify_uncertain = only_verify_uncertain
        self.uncertain_threshold = uncertain_threshold
        
        self._semantic_loaded = semantic_detector is not None
        
        if self.use_semantic and not self._semantic_loaded:
            logger.info("Semantic detection enabled but detector not loaded yet")
    
    def _ensure_semantic_loaded(self) -> bool:
        """Lazy-load semantic detector if needed."""
        if self._semantic_loaded:
            return self.semantic is not None
        
        if not self.use_semantic:
            return False
        
        logger.info("Loading semantic detector (first use)...")
        self.semantic = get_semantic_detector()
        self._semantic_loaded = True
        
        if self.semantic is None:
            logger.warning("Failed to load semantic detector, falling back to lexicon-only")
            self.use_semantic = False
            return False
        
        return True
    
    def _should_verify_semantically(self, segment: SegmentScore) -> bool:
        """Determine if a segment should be semantically verified."""
        if not self.use_semantic:
            return False
        
        # No matches = no need to verify
        if segment.active_match_count == 0:
            return False
        
        # If only verifying uncertain, check threshold
        if self.only_verify_uncertain:
            return segment.total_score < self.uncertain_threshold
        
        return True
    
    def analyze_segment(
        self,
        words: List[WordTimestamp],
        start_idx: int,
        end_idx: int
    ) -> HybridSegmentScore:
        """
        Analyze a segment with hybrid detection.
        
        Args:
            words: All transcript words
            start_idx: Start index in words list
            end_idx: End index in words list
            
        Returns:
            HybridSegmentScore with combined analysis
        """
        # Step 1: Lexicon analysis
        lexicon_score = self.lexicon.analyze_segment(words, start_idx, end_idx)
        
        result = HybridSegmentScore(
            lexicon_score=lexicon_score,
            combined_confidence=lexicon_score.confidence
        )
        
        # Step 2: Semantic verification if warranted
        if self._should_verify_semantically(lexicon_score):
            if not self._ensure_semantic_loaded():
                result.verification_status = "skipped"
                return result
            
            # Run semantic analysis
            semantic = self.semantic.analyze(lexicon_score.text)
            result.semantic_analysis = semantic
            
            if semantic.is_sexual and semantic.confidence >= self.semantic_threshold:
                # Semantically verified as sexual
                result.verification_status = "verified"
                result.combined_confidence = min(1.0, 
                    lexicon_score.confidence + (semantic.confidence * self.semantic_boost)
                )
            elif semantic.sexual_score < self.semantic_reject_threshold:
                # Semantically rejected as NOT sexual
                result.verification_status = "rejected"
                result.combined_confidence = max(0.0, 
                    lexicon_score.confidence * 0.3  # Heavily reduce confidence
                )
            else:
                # Semantic is neutral, use lexicon result
                result.verification_status = "pending"
                result.combined_confidence = lexicon_score.confidence
        else:
            if lexicon_score.active_match_count > 0:
                result.verification_status = "skipped"  # High confidence, skipped semantic
            else:
                result.verification_status = "pending"  # No lexicon matches
        
        return result
    
    def detect(
        self,
        words: List[WordTimestamp],
        segment_gap: float = 1.0
    ) -> List[TimeInterval]:
        """
        Detect sexual content using hybrid approach.
        
        Args:
            words: List of transcribed words with timestamps
            segment_gap: Gap between words to start new segment
            
        Returns:
            List of TimeInterval objects to cut
        """
        if not words:
            return []
        
        intervals: List[TimeInterval] = []
        
        # Build segments based on gaps in speech
        segments: List[Tuple[int, int]] = []
        segment_start = 0
        
        for i in range(1, len(words)):
            gap = words[i].start - words[i-1].end
            if gap > segment_gap:
                segments.append((segment_start, i))
                segment_start = i
        
        segments.append((segment_start, len(words)))
        
        # Analyze each segment with hybrid detection
        for start_idx, end_idx in segments:
            result = self.analyze_segment(words, start_idx, end_idx)
            
            if result.should_flag:
                # Include hybrid-specific metadata
                metadata = {
                    'confidence': result.combined_confidence,
                    'confidence_level': self._confidence_level(result.combined_confidence),
                    'lexicon_score': result.lexicon_score.total_score,
                    'verification_status': result.verification_status,
                    'categories': list(result.lexicon_score.categories),
                    'match_count': result.lexicon_score.active_match_count,
                }
                
                if result.semantic_analysis:
                    metadata['semantic_score'] = result.semantic_analysis.sexual_score
                    metadata['semantic_safe_score'] = result.semantic_analysis.safe_score
                
                active_matches = [
                    m for m in result.lexicon_score.matches if not m.suppressed
                ]
                match_summary = ', '.join(m.text for m in active_matches[:3])
                
                interval = TimeInterval(
                    start=result.start,
                    end=result.end,
                    reason=f"sexual content ({result.verification_status}): {match_summary}",
                    metadata=metadata
                )
                intervals.append(interval)
                
                logger.debug(
                    f"Flagged at {result.start:.2f}s "
                    f"(hybrid={result.combined_confidence:.2f}, "
                    f"status={result.verification_status})"
                )
        
        logger.info(f"Hybrid detection found {len(intervals)} sexual content segments")
        return intervals
    
    def _confidence_level(self, confidence: float) -> str:
        """Get human-readable confidence level."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"


def detect_sexual_content_hybrid(
    words: List[WordTimestamp],
    threshold: float = 1.0,
    use_semantic: bool = True,
    merge_gap: float = 0.5,
    buffer_before: float = 0.25,
    buffer_after: float = 0.25,
) -> List[TimeInterval]:
    """
    Convenience function for hybrid sexual content detection.
    
    Args:
        words: Transcribed words with timestamps
        threshold: Lexicon score threshold for flagging
        use_semantic: Whether to use semantic verification
        merge_gap: Gap for merging nearby intervals
        buffer_before: Buffer time before each interval
        buffer_after: Buffer time after each interval
        
    Returns:
        List of merged TimeInterval objects to cut
    """
    lexicon = SexualContentDetector(threshold=threshold)
    detector = HybridSexualContentDetector(
        lexicon_detector=lexicon,
        use_semantic=use_semantic
    )
    
    raw_intervals = detector.detect(words)
    
    # Add buffers
    buffered = []
    for interval in raw_intervals:
        buffered.append(TimeInterval(
            start=max(0, interval.start - buffer_before),
            end=interval.end + buffer_after,
            reason=interval.reason,
            metadata=interval.metadata
        ))
    
    # Merge nearby intervals  
    merged = merge_intervals(buffered, merge_gap)
    
    if len(merged) < len(raw_intervals):
        logger.info(f"Merged hybrid results: {len(raw_intervals)} -> {len(merged)} intervals")
    
    return merged
