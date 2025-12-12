"""Profanity detection subpackage."""

from .wordlist import (
    load_profanity_list, 
    load_profanity_phrases, 
    DEFAULT_PROFANITY, 
    DEFAULT_PHRASES,
    PROFANITY_STEMS
)
from .detector import (
    detect_profanity, 
    detect_profanity_phrases,
    analyze_transcript_for_profanity,
    analyze_subtitles_for_profanity,
    normalize_word,
    collapse_repeated_chars,
    remove_leetspeak,
    generate_word_variants,
    word_matches_profanity,
    ProfanityDebugger
)

__all__ = [
    'load_profanity_list', 
    'load_profanity_phrases', 
    'DEFAULT_PROFANITY', 
    'DEFAULT_PHRASES',
    'PROFANITY_STEMS',
    'detect_profanity', 
    'detect_profanity_phrases',
    'analyze_transcript_for_profanity',
    'analyze_subtitles_for_profanity',
    'normalize_word',
    'collapse_repeated_chars',
    'remove_leetspeak',
    'generate_word_variants',
    'word_matches_profanity',
    'ProfanityDebugger'
]
