"""
Comprehensive tests for enhanced profanity detection.

Tests include:
- Normalization
- Repeated character handling
- Leetspeak conversion
- Fuzzy matching
- Phrase detection
- Edge cases
"""

import pytest
from video_censor.profanity.detector import (
    normalize_word,
    collapse_repeated_chars,
    remove_leetspeak,
    generate_word_variants,
    word_matches_profanity,
    detect_profanity,
    detect_profanity_phrases,
)
from video_censor.profanity.wordlist import DEFAULT_PROFANITY, DEFAULT_PHRASES
from video_censor.audio.transcriber import WordTimestamp


class TestNormalizeWord:
    """Test word normalization."""
    
    def test_lowercase(self):
        assert normalize_word("FUCK") == "fuck"
        assert normalize_word("FuCk") == "fuck"
    
    def test_strip_punctuation(self):
        assert normalize_word("fuck!") == "fuck"
        assert normalize_word("!fuck!") == "fuck"
        assert normalize_word("'fuck'") == "fuck"
        assert normalize_word("fuck,") == "fuck"
        assert normalize_word(".fuck.") == "fuck"
    
    def test_strip_whitespace(self):
        assert normalize_word(" fuck ") == "fuck"
        assert normalize_word("\tfuck\n") == "fuck"
    
    def test_combined(self):
        assert normalize_word("  FUCK!!! ") == "fuck"
        assert normalize_word("'Shit,'") == "shit"


class TestCollapseRepeatedChars:
    """Test repeated character collapsing."""
    
    def test_repeated_letters(self):
        assert collapse_repeated_chars("fuuuck") == "fuck"
        assert collapse_repeated_chars("fuuuuuuuck") == "fuck"
        assert collapse_repeated_chars("shiiiit") == "shit"
        assert collapse_repeated_chars("assss") == "as"  # Aggressive collapse
    
    def test_double_letters(self):
        # Words with intentional double letters get collapsed
        assert collapse_repeated_chars("ass") == "as"
        # "fucking" has no repeated adjacent chars - stays as-is
        assert collapse_repeated_chars("fucking") == "fucking"
    
    def test_no_repeated(self):
        assert collapse_repeated_chars("fuck") == "fuck"
        assert collapse_repeated_chars("shit") == "shit"


class TestRemoveLeetspeak:
    """Test leetspeak conversion."""
    
    def test_number_substitutions(self):
        assert remove_leetspeak("sh1t") == "shit"
        assert remove_leetspeak("a55") == "ass"
        assert remove_leetspeak("fuk3r") == "fuker"
    
    def test_symbol_substitutions(self):
        assert remove_leetspeak("f@ck") == "fack"
        assert remove_leetspeak("a$$") == "ass"
        assert remove_leetspeak("sh!t") == "shit"
    
    def test_asterisk_removal(self):
        assert remove_leetspeak("f*ck") == "fck"
        assert remove_leetspeak("s**t") == "st"


class TestGenerateWordVariants:
    """Test variant generation."""
    
    def test_basic_variants(self):
        variants = generate_word_variants("FUCK!")
        assert "fuck" in variants
    
    def test_repeated_char_variants(self):
        variants = generate_word_variants("fuuuuck")
        assert "fuck" in variants
    
    def test_leetspeak_variants(self):
        variants = generate_word_variants("sh1t")
        assert "shit" in variants


class TestWordMatchesProfanity:
    """Test word matching against profanity list."""
    
    def test_exact_match(self):
        profanity = {"fuck", "shit", "ass"}
        result = word_matches_profanity("fuck", profanity)
        assert result is not None
        assert result[0] == "fuck"
        assert result[1] == "exact"
    
    def test_with_punctuation(self):
        profanity = {"fuck", "shit"}
        result = word_matches_profanity("fuck!", profanity)
        assert result is not None
        assert result[0] == "fuck"
    
    def test_repeated_chars(self):
        profanity = {"fuck", "shit"}
        result = word_matches_profanity("fuuuuck", profanity)
        assert result is not None
        assert result[0] == "fuck"
    
    def test_leetspeak(self):
        profanity = {"shit"}
        result = word_matches_profanity("sh1t", profanity)
        assert result is not None
    
    def test_no_match(self):
        profanity = {"fuck", "shit"}
        result = word_matches_profanity("hello", profanity)
        assert result is None
    
    def test_safe_word_not_matched(self):
        """Words that contain profanity but aren't profane shouldn't match."""
        profanity = {"ass"}
        result = word_matches_profanity("class", profanity)
        # This might match due to 'contains' logic for short words
        # We limit 'contains' to profanity >= 4 chars
        assert result is None
    
    def test_compound_word(self):
        profanity = {"fuck", "asshole"}
        # Test with "bullshit" which contains "shit" - easier to detect
        result = word_matches_profanity("shithead", {"shit"})
        # Contains 'shit' which is >= 4 chars, and word is short enough
        assert result is not None


class TestDetectProfanity:
    """Test profanity detection from word timestamps."""
    
    def test_empty_input(self):
        intervals = detect_profanity([], {"fuck"})
        assert intervals == []
    
    def test_empty_profanity_list(self):
        words = [WordTimestamp("hello", 0.0, 1.0)]
        intervals = detect_profanity(words, set())
        assert intervals == []
    
    def test_single_match(self):
        words = [
            WordTimestamp("hello", 0.0, 1.0),
            WordTimestamp("fuck", 1.0, 1.5),
            WordTimestamp("world", 1.5, 2.5),
        ]
        intervals = detect_profanity(words, {"fuck"})
        assert len(intervals) == 1
        assert "fuck" in intervals[0].reason
    
    def test_multiple_matches(self):
        words = [
            WordTimestamp("what", 0.0, 0.5),
            WordTimestamp("the", 0.5, 0.8),
            WordTimestamp("fuck", 0.8, 1.2),
            WordTimestamp("shit", 1.2, 1.6),
        ]
        intervals = detect_profanity(words, {"fuck", "shit"})
        assert len(intervals) == 2
    
    def test_case_insensitive(self):
        words = [WordTimestamp("FUCK", 0.0, 1.0)]
        intervals = detect_profanity(words, {"fuck"})
        assert len(intervals) == 1
    
    def test_with_punctuation(self):
        words = [WordTimestamp("fuck!", 0.0, 1.0)]
        intervals = detect_profanity(words, {"fuck"})
        assert len(intervals) == 1
    
    def test_buffer_times(self):
        words = [WordTimestamp("fuck", 1.0, 1.5)]
        intervals = detect_profanity(words, {"fuck"}, buffer_before=0.2, buffer_after=0.3)
        assert len(intervals) == 1
        assert intervals[0].start == 0.8  # 1.0 - 0.2
        assert intervals[0].end == 1.8    # 1.5 + 0.3
    
    def test_buffer_clamps_to_zero(self):
        words = [WordTimestamp("fuck", 0.05, 0.5)]
        intervals = detect_profanity(words, {"fuck"}, buffer_before=0.2)
        assert len(intervals) == 1
        assert intervals[0].start == 0.0  # Clamped, not negative
    
    def test_repeated_chars_match(self):
        words = [WordTimestamp("fuuuuck", 0.0, 1.0)]
        intervals = detect_profanity(words, {"fuck"})
        assert len(intervals) == 1


class TestDetectProfanityPhrases:
    """Test multi-word phrase detection."""
    
    def test_two_word_phrase(self):
        words = [
            WordTimestamp("holy", 0.0, 0.5),
            WordTimestamp("shit", 0.5, 1.0),
        ]
        phrases = [["holy", "shit"]]
        intervals = detect_profanity_phrases(words, phrases)
        assert len(intervals) == 1
        assert "holy shit" in intervals[0].reason.lower()
    
    def test_three_word_phrase(self):
        words = [
            WordTimestamp("what", 0.0, 0.3),
            WordTimestamp("the", 0.3, 0.5),
            WordTimestamp("fuck", 0.5, 1.0),
        ]
        phrases = [["what", "the", "fuck"]]
        intervals = detect_profanity_phrases(words, phrases)
        assert len(intervals) == 1
    
    def test_phrase_not_found(self):
        words = [
            WordTimestamp("what", 0.0, 0.5),
            WordTimestamp("is", 0.5, 0.8),
            WordTimestamp("this", 0.8, 1.2),
        ]
        phrases = [["what", "the", "fuck"]]
        intervals = detect_profanity_phrases(words, phrases)
        assert len(intervals) == 0
    
    def test_phrase_with_punctuation(self):
        words = [
            WordTimestamp("'holy", 0.0, 0.5),
            WordTimestamp("shit!'", 0.5, 1.0),
        ]
        phrases = [["holy", "shit"]]
        intervals = detect_profanity_phrases(words, phrases)
        assert len(intervals) == 1


class TestDefaultProfanityList:
    """Test default profanity list coverage."""
    
    def test_common_words_present(self):
        common = ["fuck", "shit", "ass", "bitch", "damn", "hell", "bastard"]
        for word in common:
            assert word in DEFAULT_PROFANITY, f"Missing common word: {word}"
    
    def test_variants_present(self):
        # Check that common variants are included
        assert "fucking" in DEFAULT_PROFANITY
        assert "fucker" in DEFAULT_PROFANITY
        assert "shitty" in DEFAULT_PROFANITY
        assert "asshole" in DEFAULT_PROFANITY
    
    def test_slurs_present(self):
        # Important to catch slurs
        assert "nigger" in DEFAULT_PROFANITY
        assert "faggot" in DEFAULT_PROFANITY
    
    def test_reasonable_size(self):
        # Should have comprehensive coverage
        assert len(DEFAULT_PROFANITY) >= 100


class TestDefaultPhraseList:
    """Test default phrase list coverage."""
    
    def test_common_phrases_present(self):
        common_phrases = [
            ["what", "the", "fuck"],
            ["holy", "shit"],
            ["son", "of", "a", "bitch"],
        ]
        for phrase in common_phrases:
            assert phrase in DEFAULT_PHRASES, f"Missing phrase: {phrase}"
    
    def test_reasonable_size(self):
        assert len(DEFAULT_PHRASES) >= 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
