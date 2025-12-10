"""
Unit tests for profanity detection.
"""

import pytest
from video_censor.audio.transcriber import WordTimestamp
from video_censor.profanity.detector import (
    TimeInterval,
    normalize_word,
    detect_profanity,
    detect_profanity_phrases
)
from video_censor.profanity.wordlist import load_profanity_list, DEFAULT_PROFANITY


class TestNormalizeWord:
    """Tests for word normalization."""
    
    def test_lowercase(self):
        """Test conversion to lowercase."""
        assert normalize_word("HELLO") == "hello"
        assert normalize_word("HeLLo") == "hello"
    
    def test_strip_punctuation(self):
        """Test stripping punctuation."""
        assert normalize_word("hello!") == "hello"
        assert normalize_word("hello?") == "hello"
        assert normalize_word("hello.") == "hello"
        assert normalize_word("hello,") == "hello"
        assert normalize_word("'hello'") == "hello"
        assert normalize_word('"hello"') == "hello"
    
    def test_strip_whitespace(self):
        """Test stripping whitespace."""
        assert normalize_word("  hello  ") == "hello"
        assert normalize_word("\thello\n") == "hello"
    
    def test_combined(self):
        """Test combined normalization."""
        assert normalize_word("  HELLO!  ") == "hello"
        assert normalize_word("'What?'") == "what"


class TestDetectProfanity:
    """Tests for profanity detection."""
    
    def test_empty_input(self):
        """Test with empty word list."""
        result = detect_profanity([], {"bad"})
        assert result == []
    
    def test_empty_profanity_list(self):
        """Test with empty profanity list."""
        words = [WordTimestamp(word="hello", start=0.0, end=0.5)]
        result = detect_profanity(words, set())
        assert result == []
    
    def test_no_matches(self):
        """Test with no profanity matches."""
        words = [
            WordTimestamp(word="hello", start=0.0, end=0.5),
            WordTimestamp(word="world", start=0.5, end=1.0),
        ]
        result = detect_profanity(words, {"bad", "worse"})
        assert result == []
    
    def test_single_match(self):
        """Test single profanity match."""
        words = [
            WordTimestamp(word="hello", start=0.0, end=0.5),
            WordTimestamp(word="damn", start=0.5, end=0.8),
            WordTimestamp(word="world", start=0.8, end=1.2),
        ]
        result = detect_profanity(words, {"damn"}, buffer_before=0.0, buffer_after=0.0)
        
        assert len(result) == 1
        assert result[0].start == 0.5
        assert result[0].end == 0.8
    
    def test_multiple_matches(self):
        """Test multiple profanity matches."""
        words = [
            WordTimestamp(word="damn", start=0.0, end=0.3),
            WordTimestamp(word="this", start=0.3, end=0.5),
            WordTimestamp(word="crap", start=0.5, end=0.8),
        ]
        result = detect_profanity(words, {"damn", "crap"}, buffer_before=0.0, buffer_after=0.0)
        
        assert len(result) == 2
    
    def test_case_insensitive(self):
        """Test case insensitive matching."""
        words = [
            WordTimestamp(word="DAMN", start=0.0, end=0.3),
            WordTimestamp(word="Crap", start=0.3, end=0.6),
        ]
        result = detect_profanity(words, {"damn", "crap"}, buffer_before=0.0, buffer_after=0.0)
        
        assert len(result) == 2
    
    def test_with_punctuation(self):
        """Test matching words with punctuation."""
        words = [
            WordTimestamp(word="damn!", start=0.0, end=0.3),
            WordTimestamp(word="crap,", start=0.3, end=0.6),
        ]
        result = detect_profanity(words, {"damn", "crap"}, buffer_before=0.0, buffer_after=0.0)
        
        assert len(result) == 2
    
    def test_buffer_times(self):
        """Test buffer time addition."""
        words = [
            WordTimestamp(word="damn", start=1.0, end=1.3),
        ]
        result = detect_profanity(words, {"damn"}, buffer_before=0.2, buffer_after=0.3)
        
        assert len(result) == 1
        assert result[0].start == 0.8  # 1.0 - 0.2
        assert result[0].end == 1.6    # 1.3 + 0.3
    
    def test_buffer_clamps_to_zero(self):
        """Test buffer doesn't go below zero."""
        words = [
            WordTimestamp(word="damn", start=0.1, end=0.3),
        ]
        result = detect_profanity(words, {"damn"}, buffer_before=0.5, buffer_after=0.0)
        
        assert result[0].start == 0.0  # Clamped
    
    def test_reason_includes_word(self):
        """Test that reason includes the detected word."""
        words = [
            WordTimestamp(word="damn", start=0.0, end=0.3),
        ]
        result = detect_profanity(words, {"damn"})
        
        assert "damn" in result[0].reason.lower()


class TestDetectProfanityPhrases:
    """Tests for multi-word profanity phrase detection."""
    
    def test_two_word_phrase(self):
        """Test detecting two-word phrase."""
        words = [
            WordTimestamp(word="what", start=0.0, end=0.3),
            WordTimestamp(word="the", start=0.3, end=0.5),
            WordTimestamp(word="hell", start=0.5, end=0.8),
        ]
        phrases = [["the", "hell"]]
        result = detect_profanity_phrases(words, phrases, buffer_before=0.0, buffer_after=0.0)
        
        assert len(result) == 1
        assert result[0].start == 0.3
        assert result[0].end == 0.8
    
    def test_phrase_not_found(self):
        """Test when phrase is not present."""
        words = [
            WordTimestamp(word="hello", start=0.0, end=0.3),
            WordTimestamp(word="world", start=0.3, end=0.6),
        ]
        phrases = [["the", "hell"]]
        result = detect_profanity_phrases(words, phrases)
        
        assert len(result) == 0


class TestLoadProfanityList:
    """Tests for profanity list loading."""
    
    def test_default_list(self):
        """Test loading default list."""
        words = load_profanity_list("")
        
        assert len(words) > 0
        assert "damn" in words
        assert "crap" in words
    
    def test_default_list_copy(self):
        """Test that default list is a copy."""
        words1 = load_profanity_list("")
        words2 = load_profanity_list("")
        
        words1.add("test_word")
        assert "test_word" not in words2
    
    def test_nonexistent_file(self):
        """Test loading from non-existent file returns default."""
        words = load_profanity_list("/nonexistent/path.txt")
        
        assert len(words) > 0  # Should return default
