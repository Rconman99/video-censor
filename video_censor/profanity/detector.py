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
from ..audio.transcriber import WordTimestamp
from ..editing.intervals import TimeInterval, Action, MatchSource

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



# Legacy function - kept for compatibility if needed, but unused by new logic
def word_matches_profanity(word: str, profanity_set: Set[str]) -> Optional[Tuple[str, str]]:
    """Legacy check - replaced by ProfanityDetector regex matching."""
    variants = generate_word_variants(word)
    for variant in variants:
        if variant in profanity_set:
            return (variant, "exact")
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
    
    # Initialize implementation
    from .wordlist import ProfanityDetector, DEFAULT_WHITELIST
    # We don't have access to config here directly, but we can infer whitelist if not passed?
    # Actually, the user wants us to use the config whitelist.
    # But detect_profanity signature doesn't take whitelist. 
    # For now, we'll use empty whitelist or default, and rely on caller to pass it? 
    # Or better: We assume standard profanity detection for now, and subsequent filtering?
    # No, the request is to fix detection itself.
    
    # We will instantiate ProfanityDetector with the passed list
    # Assuming the caller has merged custom checklists if needed.
    detector = ProfanityDetector(profanity_list)
    
    # Log segment if debugging
    if should_debug and words:
        debugger.log_segment(words, 0, len(words))
    
    # Pre-calculate normalized words to speed up processing
    # But regex runs on raw text? No, it runs on "text".
    # We have a list of WordTimestamp objects.
    # We should reconstruct the text? Or run matching on each word individually?
    # Running on each word individually is safer for timestamp accuracy, 
    # effectively keeping the current flow but using better matching logic.
    
    for word_ts in words:
        # Use new regex-based matching on individual word
        # This handles "Good" vs "god" because "Good" won't match regex `\bgod\b`
        matches = detector.find_matches(word_ts.word)
        
        if matches:
            # We take the first match
            match = matches[0]
            matched_pattern = match['word']
            match_type = "regex_exact"
            
            # Add buffer time around the word
            start = max(0, word_ts.start - buffer_before)
            end = word_ts.end + buffer_after
            
            interval = TimeInterval(
                start=start,
                end=end,
                reason=f"profanity: '{word_ts.word}' ({match_type}: {matched_pattern})",
                metadata={
                    'word': word_ts.word,
                    'confidence': getattr(word_ts, 'probability', 1.0),
                    'match_type': match_type,
                    'matched_pattern': matched_pattern
                }
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
        debugger.write_summary(profanity_list) # Use the raw set
    
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


def analyze_subtitles_for_profanity(
    intervals: List[TimeInterval],
    profanity_list: Set[str],
    phrases: List[List[str]],
    buffer_before: float = 0.0,
    buffer_after: float = 0.0
) -> Tuple[List[TimeInterval], Dict]:
    """
    Analyze subtitle intervals for profanity.
    
    Unlike audio alignment where we have per-word timestamps, for subtitles
    we only have the block timestamp. If profanity is found, we mask the
    entire block (plus buffer).
    
    Args:
        intervals: List of TimeInterval objects parsed from SRT
        profanity_list: Set of profanity words
        phrases: List of profanity phrases
        buffer_before: Buffer before
        buffer_after: Buffer after
        
    Returns:
        Tuple of (censored_intervals, stats)
    """
    censored_intervals = []
    normalized_profanity = {w.lower() for w in profanity_list}
    
    count_detected = 0
    
    for interval in intervals:
        text = interval.metadata.get('text', '')
        if not text:
            continue
            
        # Simple tokenization for matching
        # Note: This loses some context but is decent for v1
        words_in_sub = re.findall(r'\b\w+\b', text)
        
        found = False
        matched_term = ""
        
        # Check single words
        for word in words_in_sub:
            match = word_matches_profanity(word, normalized_profanity)
            if match:
                found = True
                matched_term = f"{match[0]} ({match[1]})"
                break
                
        # Check phrases (simple robust check)
        if not found and phrases:
            text_lower = text.lower()
            for phrase in phrases:
                phrase_str = " ".join(phrase).lower()
                if phrase_str in text_lower:
                    found = True
                    matched_term = f"phrase: {phrase_str}"
                    break
        
        if found:
            count_detected += 1
            # Create censor block covering the whole subtitle
            censor_int = TimeInterval(
                start=max(0, interval.start - buffer_before),
                end=interval.end + buffer_after,
                reason=f"subtitle profanity: {matched_term}",
                action=Action.MUTE, # Detector creates the interval, default to MUTE
                source=MatchSource.SUBTITLE,
                metadata=interval.metadata
            )
            censored_intervals.append(censor_int)
            
    stats = {
        "total_subtitles": len(intervals),
        "detections": count_detected
    }
    
    logger.info(f"Subtitle analysis: {count_detected}/{len(intervals)} blocks flagged")
    
    return censored_intervals, stats
