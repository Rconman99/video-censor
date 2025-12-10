"""
Enhanced profanity detection in transcribed text.

Features:
- Fuzzy matching for repeated characters (fuuuuck -> fuck)
- Handles punctuation attached to words (fuck! -> fuck)
- Substring matching for obfuscated words
- Multi-word phrase detection with sliding window
- Debug logging for troubleshooting missed words
"""

import logging
import re
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple

from ..audio.transcriber import WordTimestamp
from ..editing.intervals import TimeInterval

logger = logging.getLogger(__name__)


# Debug configuration
DEBUG_PROFANITY = os.environ.get('DEBUG_PROFANITY', '').lower() in ('1', 'true', 'yes')
DEBUG_LOG_PATH = Path("profanity_debug.log")


@dataclass
class DetectionResult:
    """Result of profanity detection with debug info."""
    word: str
    normalized: str
    matched_pattern: str
    match_type: str  # "exact", "fuzzy", "contains", "pattern"
    start: float
    end: float


class ProfanityDebugger:
    """Debug logger for profanity detection."""
    
    def __init__(self, enabled: bool = False, output_path: Optional[Path] = None):
        self.enabled = enabled
        self.output_path = output_path or DEBUG_LOG_PATH
        self.detections: List[DetectionResult] = []
        self.missed_words: List[Tuple[str, str, float, float]] = []  # (original, normalized, start, end)
        self.matched_patterns: Set[str] = set()
        self.segments_processed: int = 0
        self.total_words: int = 0
        
        if self.enabled:
            # Clear previous log
            with open(self.output_path, 'w') as f:
                f.write(f"=== Profanity Detection Debug Log ===\n")
                f.write(f"Started: {datetime.now().isoformat()}\n\n")
    
    def log_segment(self, words: List[WordTimestamp], start_idx: int, end_idx: int):
        """Log a transcript segment."""
        if not self.enabled:
            return
        
        self.segments_processed += 1
        segment_words = words[start_idx:end_idx]
        
        if not segment_words:
            return
            
        start_time = segment_words[0].start
        end_time = segment_words[-1].end
        text = ' '.join(w.word for w in segment_words)
        
        with open(self.output_path, 'a') as f:
            f.write(f"\n--- Segment {self.segments_processed} ---\n")
            f.write(f"Time: {start_time:.2f}s - {end_time:.2f}s\n")
            f.write(f"Text: {text}\n")
            f.write(f"Tokens: {[w.word for w in segment_words]}\n")
    
    def log_detection(self, result: DetectionResult):
        """Log a detected profanity."""
        if not self.enabled:
            return
        
        self.detections.append(result)
        self.matched_patterns.add(result.matched_pattern)
        
        with open(self.output_path, 'a') as f:
            f.write(f"  ✓ DETECTED: '{result.word}' -> '{result.normalized}' "
                   f"matched '{result.matched_pattern}' ({result.match_type}) "
                   f"at {result.start:.2f}s\n")
    
    def log_no_match(self, word: str, normalized: str, start: float, end: float):
        """Log a word that didn't match."""
        if not self.enabled:
            return
        
        self.missed_words.append((word, normalized, start, end))
        self.total_words += 1
    
    def write_summary(self, profanity_list: Set[str]):
        """Write summary at end of processing."""
        if not self.enabled:
            return
        
        with open(self.output_path, 'a') as f:
            f.write(f"\n\n{'='*50}\n")
            f.write(f"=== DETECTION SUMMARY ===\n")
            f.write(f"{'='*50}\n\n")
            
            f.write(f"Segments processed: {self.segments_processed}\n")
            f.write(f"Total words analyzed: {self.total_words + len(self.detections)}\n")
            f.write(f"Profanity detected: {len(self.detections)}\n")
            f.write(f"Unique patterns matched: {len(self.matched_patterns)}\n\n")
            
            # Detected terms
            f.write("DETECTED TERMS:\n")
            for detection in sorted(set(d.matched_pattern for d in self.detections)):
                count = sum(1 for d in self.detections if d.matched_pattern == detection)
                f.write(f"  - {detection}: {count}x\n")
            
            # Unmatched profanity list terms
            unmatched = profanity_list - self.matched_patterns
            f.write(f"\nPROFANITY LIST TERMS NOT FOUND ({len(unmatched)}):\n")
            for term in sorted(list(unmatched)[:50]):  # Show first 50
                f.write(f"  - {term}\n")
            if len(unmatched) > 50:
                f.write(f"  ... and {len(unmatched) - 50} more\n")
            
            f.write(f"\nLog completed: {datetime.now().isoformat()}\n")
        
        logger.info(f"Profanity debug log written to: {self.output_path}")


def normalize_word(word: str) -> str:
    """
    Normalize a word for matching.
    
    - Converts to lowercase
    - Removes leading/trailing punctuation
    - Strips whitespace
    """
    # Remove leading/trailing punctuation and whitespace
    word = re.sub(r'^[\s\W]+|[\s\W]+$', '', word)
    return word.lower()


def collapse_repeated_chars(word: str) -> str:
    """
    Collapse repeated characters to handle elongated words.
    
    Examples:
        fuuuuck -> fuck
        shiiiit -> shit
        assssss -> ass
    """
    # Collapse 3+ repeated chars to 1 (aggressive)
    collapsed = re.sub(r'(.)\1{2,}', r'\1', word)
    
    # Also try collapsing 2+ to handle "fuuck" -> "fuck"
    if collapsed == word:
        collapsed = re.sub(r'(.)\1+', r'\1', word)
    
    return collapsed


def remove_leetspeak(word: str) -> str:
    """
    Convert common leetspeak substitutions.
    
    Examples:
        sh1t -> shit
        a$$ -> ass
        f@ck -> fack (close enough to match patterns)
    """
    replacements = {
        '0': 'o',
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '7': 't',
        '8': 'b',
        '@': 'a',
        '$': 's',
        '!': 'i',
        '*': '',  # Remove asterisks
        '#': '',  # Remove hash
    }
    
    result = word
    for leet, normal in replacements.items():
        result = result.replace(leet, normal)
    
    return result


def generate_word_variants(word: str) -> List[str]:
    """
    Generate multiple normalized variants of a word for matching.
    
    Returns list of variants to try matching against profanity list.
    """
    variants = set()
    
    # Original normalized
    normalized = normalize_word(word)
    variants.add(normalized)
    
    # Collapsed repeated chars
    collapsed = collapse_repeated_chars(normalized)
    variants.add(collapsed)
    
    # Leetspeak converted
    deleet = remove_leetspeak(normalized)
    variants.add(deleet)
    
    # Both collapsed and deleet
    both = collapse_repeated_chars(deleet)
    variants.add(both)
    
    # Remove all non-alpha characters
    alpha_only = re.sub(r'[^a-z]', '', normalized)
    variants.add(alpha_only)
    
    return [v for v in variants if v]


def word_matches_profanity(word: str, profanity_set: Set[str]) -> Optional[Tuple[str, str]]:
    """
    Check if a word matches any profanity.
    
    Args:
        word: The word to check
        profanity_set: Set of profanity words
        
    Returns:
        Tuple of (matched_pattern, match_type) or None
    """
    variants = generate_word_variants(word)
    
    for variant in variants:
        if not variant:
            continue
            
        # Exact match
        if variant in profanity_set:
            return (variant, "exact")
        
        # Check if any profanity is contained in the variant (for compound words)
        # But only for longer profanity words to avoid false positives
        for profanity in profanity_set:
            if len(profanity) >= 4 and profanity in variant and len(variant) <= len(profanity) * 3:
                return (profanity, "contains")
    
    return None


def detect_profanity(
    words: List[WordTimestamp],
    profanity_list: Set[str],
    buffer_before: float = 0.1,
    buffer_after: float = 0.15,
    debug: bool = False
) -> List[TimeInterval]:
    """
    Detect profanity in transcribed words with enhanced matching.
    
    Features:
    - Fuzzy matching for repeated characters
    - Handles leetspeak and obfuscation
    - Word boundary aware
    - Debug logging option
    
    Args:
        words: List of transcribed words with timestamps
        profanity_list: Set of profanity words to match
        buffer_before: Seconds to add before each detection
        buffer_after: Seconds to add after each detection
        debug: Enable debug logging
        
    Returns:
        List of TimeInterval objects where profanity was detected
    """
    intervals: List[TimeInterval] = []
    
    # Initialize debugger
    should_debug = debug or DEBUG_PROFANITY
    debugger = ProfanityDebugger(enabled=should_debug)
    
    # Normalize profanity list
    normalized_profanity = {w.lower() for w in profanity_list}
    
    # Log segment if debugging
    if should_debug and words:
        debugger.log_segment(words, 0, len(words))
    
    for word_ts in words:
        match_result = word_matches_profanity(word_ts.word, normalized_profanity)
        
        if match_result:
            matched_pattern, match_type = match_result
            
            # Add buffer time around the word
            start = max(0, word_ts.start - buffer_before)
            end = word_ts.end + buffer_after
            
            interval = TimeInterval(
                start=start,
                end=end,
                reason=f"profanity: '{word_ts.word}' ({match_type}: {matched_pattern})"
            )
            intervals.append(interval)
            
            logger.debug(f"Detected profanity: '{word_ts.word}' -> '{matched_pattern}' ({match_type}) at {word_ts.start:.2f}s")
            
            if should_debug:
                debugger.log_detection(DetectionResult(
                    word=word_ts.word,
                    normalized=normalize_word(word_ts.word),
                    matched_pattern=matched_pattern,
                    match_type=match_type,
                    start=start,
                    end=end
                ))
        else:
            if should_debug:
                debugger.log_no_match(
                    word_ts.word, 
                    normalize_word(word_ts.word),
                    word_ts.start,
                    word_ts.end
                )
    
    # Write debug summary
    if should_debug:
        debugger.write_summary(normalized_profanity)
    
    logger.info(f"Detected {len(intervals)} profanity instances")
    
    return intervals


def detect_profanity_phrases(
    words: List[WordTimestamp],
    phrases: List[List[str]],
    buffer_before: float = 0.1,
    buffer_after: float = 0.15
) -> List[TimeInterval]:
    """
    Detect multi-word profanity phrases using sliding window.
    
    Args:
        words: List of transcribed words with timestamps
        phrases: List of phrases (each phrase is a list of words)
        buffer_before: Seconds to add before each detection
        buffer_after: Seconds to add after each detection
        
    Returns:
        List of TimeInterval objects where phrases were detected
    """
    intervals: List[TimeInterval] = []
    
    if not words or not phrases:
        return intervals
    
    # Normalize phrases
    normalized_phrases = [
        [w.lower() for w in phrase] 
        for phrase in phrases
    ]
    
    # Create list of normalized transcribed words for efficient matching
    normalized_words = [normalize_word(w.word) for w in words]
    
    for phrase in normalized_phrases:
        phrase_len = len(phrase)
        
        # Sliding window over transcript
        for i in range(len(words) - phrase_len + 1):
            # Check if words match the phrase
            match = True
            for j, phrase_word in enumerate(phrase):
                # Use fuzzy matching for each word in phrase
                variants = generate_word_variants(words[i + j].word)
                if phrase_word not in variants:
                    match = False
                    break
            
            if match:
                start = max(0, words[i].start - buffer_before)
                end = words[i + phrase_len - 1].end + buffer_after
                
                phrase_text = ' '.join(w.word for w in words[i:i + phrase_len])
                interval = TimeInterval(
                    start=start,
                    end=end,
                    reason=f"profanity phrase: '{phrase_text}'"
                )
                intervals.append(interval)
                
                logger.debug(f"Detected phrase: '{phrase_text}' at {start:.2f}s")
    
    return intervals


def analyze_transcript_for_profanity(
    words: List[WordTimestamp],
    profanity_list: Set[str],
    phrases: List[List[str]],
    buffer_before: float = 0.1,
    buffer_after: float = 0.15,
    debug: bool = False
) -> Tuple[List[TimeInterval], Dict]:
    """
    Complete profanity analysis with both single words and phrases.
    
    Args:
        words: List of transcribed words with timestamps
        profanity_list: Set of profanity words
        phrases: List of profanity phrases
        buffer_before: Buffer before detections
        buffer_after: Buffer after detections
        debug: Enable debug logging
        
    Returns:
        Tuple of (intervals, stats_dict)
    """
    # Detect single words
    word_intervals = detect_profanity(
        words, profanity_list, buffer_before, buffer_after, debug
    )
    
    # Detect phrases
    phrase_intervals = detect_profanity_phrases(
        words, phrases, buffer_before, buffer_after
    )
    
    # Combine
    all_intervals = word_intervals + phrase_intervals
    
    stats = {
        "total_words": len(words),
        "word_detections": len(word_intervals),
        "phrase_detections": len(phrase_intervals),
        "total_detections": len(all_intervals),
        "profanity_list_size": len(profanity_list),
        "phrase_list_size": len(phrases),
    }
    
    logger.info(f"Profanity analysis complete: {stats['word_detections']} words + "
               f"{stats['phrase_detections']} phrases = {stats['total_detections']} total")
    
    return all_intervals, stats
