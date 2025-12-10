"""
Sexual content detector for transcript analysis.

Detects sexually explicit dialog/narration and generates cut intervals.
Uses scoring thresholds to determine when content should be cut entirely.

Features:
- Single word and phrase detection
- Category-based scoring
- Configurable thresholds
- Debug logging
- Integration with edit pipeline
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional

from ..audio.transcriber import WordTimestamp
from ..editing.intervals import TimeInterval, merge_intervals
from ..profanity.detector import normalize_word, generate_word_variants
from .lexicon import (
    DEFAULT_SEXUAL_TERMS,
    DEFAULT_SEXUAL_PHRASES,
    CATEGORY_WEIGHTS,
    CATEGORY_MINORS_UNSAFE,
    get_category_weight,
)

logger = logging.getLogger(__name__)


# Debug configuration
DEBUG_SEXUAL_CONTENT = os.environ.get('DEBUG_SEXUAL_CONTENT', '').lower() in ('1', 'true', 'yes')
DEBUG_LOG_PATH = Path("sexual_content_debug.log")


@dataclass
class SexualContentMatch:
    """A matched sexual content term or phrase."""
    text: str
    category: str
    match_type: str  # "word" or "phrase"
    start: float
    end: float
    weight: float = 1.0
    
    @property
    def score(self) -> float:
        """Calculate score for this match."""
        return self.weight


@dataclass
class SegmentScore:
    """Score for a transcript segment."""
    start: float
    end: float
    text: str
    matches: List[SexualContentMatch] = field(default_factory=list)
    
    @property
    def total_score(self) -> float:
        """Calculate total score from all matches."""
        return sum(m.score for m in self.matches)
    
    @property
    def has_unsafe_content(self) -> bool:
        """Check if segment has minors/unsafe content."""
        return any(m.category == CATEGORY_MINORS_UNSAFE for m in self.matches)
    
    @property
    def categories(self) -> Set[str]:
        """Get all matched categories."""
        return {m.category for m in self.matches}


class SexualContentDebugger:
    """Debug logger for sexual content detection."""
    
    def __init__(self, enabled: bool = False, output_path: Optional[Path] = None):
        self.enabled = enabled
        self.output_path = output_path or DEBUG_LOG_PATH
        self.flagged_segments: List[SegmentScore] = []
        self.all_segments: List[SegmentScore] = []
        self.matched_terms: Dict[str, int] = {}
        self.total_cut_duration: float = 0.0
        
        if self.enabled:
            with open(self.output_path, 'w') as f:
                f.write(f"=== Sexual Content Detection Debug Log ===\n")
                f.write(f"Started: {datetime.now().isoformat()}\n\n")
    
    def log_segment(self, segment: SegmentScore, flagged: bool, threshold: float):
        """Log a processed segment."""
        if not self.enabled:
            return
        
        self.all_segments.append(segment)
        if flagged:
            self.flagged_segments.append(segment)
            self.total_cut_duration += segment.end - segment.start
        
        # Track matched terms
        for match in segment.matches:
            key = f"{match.text}|{match.category}"
            self.matched_terms[key] = self.matched_terms.get(key, 0) + 1
        
        with open(self.output_path, 'a') as f:
            status = "🔴 FLAGGED FOR CUT" if flagged else "✓ OK"
            f.write(f"\n--- Segment: {segment.start:.2f}s - {segment.end:.2f}s ---\n")
            f.write(f"Status: {status}\n")
            f.write(f"Text: {segment.text}\n")
            f.write(f"Score: {segment.total_score:.2f} (threshold: {threshold})\n")
            
            if segment.matches:
                f.write(f"Matches:\n")
                for match in segment.matches:
                    f.write(f"  - '{match.text}' [{match.category}] ({match.match_type}) "
                           f"score={match.score:.2f}\n")
            else:
                f.write("Matches: none\n")
    
    def write_summary(self):
        """Write summary at end of processing."""
        if not self.enabled:
            return
        
        with open(self.output_path, 'a') as f:
            f.write(f"\n\n{'='*50}\n")
            f.write(f"=== SEXUAL CONTENT DETECTION SUMMARY ===\n")
            f.write(f"{'='*50}\n\n")
            
            f.write(f"Total segments analyzed: {len(self.all_segments)}\n")
            f.write(f"Segments flagged for cut: {len(self.flagged_segments)}\n")
            f.write(f"Total duration removed: {self.total_cut_duration:.2f}s\n\n")
            
            f.write("TERMS THAT TRIGGERED CUTS:\n")
            for term, count in sorted(self.matched_terms.items(), key=lambda x: -x[1]):
                text, category = term.split('|')
                f.write(f"  - {text} [{category}]: {count}x\n")
            
            f.write(f"\nLog completed: {datetime.now().isoformat()}\n")
        
        logger.info(f"Sexual content debug log written to: {self.output_path}")


class SexualContentDetector:
    """
    Detects sexual content in transcript and generates cut intervals.
    """
    
    def __init__(
        self,
        terms: Optional[Dict[str, str]] = None,
        phrases: Optional[List[Tuple[List[str], str]]] = None,
        threshold: float = 1.0,
        unsafe_threshold: float = 0.5,
        context_window: int = 0,
        debug: bool = False
    ):
        """
        Initialize detector.
        
        Args:
            terms: Dict mapping terms to categories
            phrases: List of (phrase_words, category) tuples
            threshold: Score threshold for flagging (default 1.0)
            unsafe_threshold: Threshold for minors/unsafe content (default 0.5 = more aggressive)
            context_window: Number of adjacent segments to consider (0 = none)
            debug: Enable debug logging
        """
        self.terms = terms if terms is not None else DEFAULT_SEXUAL_TERMS.copy()
        self.phrases = phrases if phrases is not None else list(DEFAULT_SEXUAL_PHRASES)
        self.threshold = threshold
        self.unsafe_threshold = unsafe_threshold
        self.context_window = context_window
        self.debug = debug or DEBUG_SEXUAL_CONTENT
        self.debugger = SexualContentDebugger(enabled=self.debug)
        
        # Normalize terms for matching
        self.normalized_terms = {
            k.lower(): (v, get_category_weight(v))
            for k, v in self.terms.items()
        }
        
        # Normalize phrases
        self.normalized_phrases = [
            ([w.lower() for w in phrase], cat, get_category_weight(cat))
            for phrase, cat in self.phrases
        ]
    
    def _match_word(self, word: str) -> Optional[Tuple[str, str, float]]:
        """
        Check if a word matches any sexual term.
        
        Returns: (matched_term, category, weight) or None
        """
        variants = generate_word_variants(word)
        
        for variant in variants:
            if variant in self.normalized_terms:
                category, weight = self.normalized_terms[variant]
                return (variant, category, weight)
        
        return None
    
    def _match_phrases(
        self, 
        words: List[WordTimestamp],
        start_idx: int,
        end_idx: int
    ) -> List[SexualContentMatch]:
        """
        Find phrase matches in a segment.
        
        Args:
            words: All transcript words
            start_idx: Start index for this segment
            end_idx: End index for this segment
            
        Returns:
            List of phrase matches
        """
        matches = []
        segment_words = words[start_idx:end_idx]
        
        if not segment_words:
            return matches
        
        # Normalize segment words
        normalized = [normalize_word(w.word) for w in segment_words]
        
        for phrase, category, weight in self.normalized_phrases:
            phrase_len = len(phrase)
            
            for i in range(len(normalized) - phrase_len + 1):
                if normalized[i:i + phrase_len] == phrase:
                    phrase_text = ' '.join(w.word for w in segment_words[i:i + phrase_len])
                    matches.append(SexualContentMatch(
                        text=phrase_text,
                        category=category,
                        match_type="phrase",
                        start=segment_words[i].start,
                        end=segment_words[i + phrase_len - 1].end,
                        weight=weight * 1.2  # Phrases get bonus weight
                    ))
        
        return matches
    
    def analyze_segment(
        self,
        words: List[WordTimestamp],
        start_idx: int,
        end_idx: int
    ) -> SegmentScore:
        """
        Analyze a transcript segment for sexual content.
        
        Args:
            words: All transcript words
            start_idx: Start index in words list
            end_idx: End index in words list
            
        Returns:
            SegmentScore with all matches and total score
        """
        segment_words = words[start_idx:end_idx]
        
        if not segment_words:
            return SegmentScore(start=0, end=0, text="")
        
        segment_start = segment_words[0].start
        segment_end = segment_words[-1].end
        segment_text = ' '.join(w.word for w in segment_words)
        
        matches: List[SexualContentMatch] = []
        
        # Find single word matches
        for i, word_ts in enumerate(segment_words):
            match_result = self._match_word(word_ts.word)
            if match_result:
                term, category, weight = match_result
                matches.append(SexualContentMatch(
                    text=word_ts.word,
                    category=category,
                    match_type="word",
                    start=word_ts.start,
                    end=word_ts.end,
                    weight=weight
                ))
        
        # Find phrase matches
        phrase_matches = self._match_phrases(words, start_idx, end_idx)
        matches.extend(phrase_matches)
        
        return SegmentScore(
            start=segment_start,
            end=segment_end,
            text=segment_text,
            matches=matches
        )
    
    def should_flag_segment(self, segment: SegmentScore) -> bool:
        """
        Determine if a segment should be flagged for cutting.
        
        Args:
            segment: The analyzed segment
            
        Returns:
            True if segment should be cut
        """
        if not segment.matches:
            return False
        
        # Always flag unsafe content with lower threshold
        if segment.has_unsafe_content:
            return segment.total_score >= self.unsafe_threshold
        
        # Use normal threshold for other content
        return segment.total_score >= self.threshold
    
    def detect(
        self,
        words: List[WordTimestamp],
        segment_gap: float = 1.0
    ) -> List[TimeInterval]:
        """
        Detect sexual content and generate cut intervals.
        
        Segments are determined by gaps in speech (>segment_gap seconds).
        
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
        
        # Add final segment
        segments.append((segment_start, len(words)))
        
        # Analyze each segment
        for start_idx, end_idx in segments:
            segment_score = self.analyze_segment(words, start_idx, end_idx)
            flagged = self.should_flag_segment(segment_score)
            
            # Log to debugger
            threshold = self.unsafe_threshold if segment_score.has_unsafe_content else self.threshold
            self.debugger.log_segment(segment_score, flagged, threshold)
            
            if flagged:
                # Create cut interval for entire segment
                interval = TimeInterval(
                    start=segment_score.start,
                    end=segment_score.end,
                    reason=f"sexual content: {', '.join(m.text for m in segment_score.matches[:3])}"
                )
                intervals.append(interval)
                
                logger.debug(f"Flagged sexual content at {segment_score.start:.2f}s: "
                           f"{segment_score.text[:50]}...")
        
        # Write debug summary
        self.debugger.write_summary()
        
        logger.info(f"Detected {len(intervals)} sexual content segments")
        
        return intervals


def detect_sexual_content(
    words: List[WordTimestamp],
    terms: Optional[Dict[str, str]] = None,
    phrases: Optional[List[Tuple[List[str], str]]] = None,
    threshold: float = 1.0,
    unsafe_threshold: float = 0.5,
    merge_gap: float = 0.5,
    buffer_before: float = 0.25,
    buffer_after: float = 0.25,
    debug: bool = False
) -> List[TimeInterval]:
    """
    Convenience function to detect sexual content.
    
    Args:
        words: Transcribed words with timestamps
        terms: Optional custom terms dict
        phrases: Optional custom phrases list
        threshold: Score threshold for flagging
        unsafe_threshold: Threshold for minors/unsafe content
        merge_gap: Gap for merging nearby intervals
        buffer_before: Buffer time before each interval
        buffer_after: Buffer time after each interval
        debug: Enable debug logging
        
    Returns:
        List of merged TimeInterval objects to cut
    """
    detector = SexualContentDetector(
        terms=terms,
        phrases=phrases,
        threshold=threshold,
        unsafe_threshold=unsafe_threshold,
        debug=debug
    )
    
    raw_intervals = detector.detect(words)
    
    # Add buffers
    buffered = []
    for interval in raw_intervals:
        buffered.append(TimeInterval(
            start=max(0, interval.start - buffer_before),
            end=interval.end + buffer_after,
            reason=interval.reason
        ))
    
    # Merge nearby intervals
    merged = merge_intervals(buffered, merge_gap)
    
    if len(merged) < len(raw_intervals):
        logger.info(f"Merged sexual content: {len(raw_intervals)} -> {len(merged)} intervals")
    
    return merged
