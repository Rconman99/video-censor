"""
Tests for sexual content detection.
"""

import pytest
from video_censor.sexual_content.lexicon import (
    DEFAULT_SEXUAL_TERMS,
    DEFAULT_SEXUAL_PHRASES,
    CATEGORY_PORNOGRAPHY,
    CATEGORY_SEXUAL_ACTS,
    CATEGORY_MINORS_UNSAFE,
    load_sexual_terms,
    load_sexual_phrases,
)
from video_censor.sexual_content.detector import (
    SexualContentDetector,
    detect_sexual_content,
    SexualContentMatch,
    SegmentScore,
)
from video_censor.audio.transcriber import WordTimestamp


class TestLexicon:
    """Test sexual content lexicon."""
    
    def test_porn_terms_present(self):
        assert "porn" in DEFAULT_SEXUAL_TERMS
        assert "pornography" in DEFAULT_SEXUAL_TERMS
        assert "nsfw" in DEFAULT_SEXUAL_TERMS
    
    def test_sexual_acts_present(self):
        assert "sex" in DEFAULT_SEXUAL_TERMS
        assert "masturbate" in DEFAULT_SEXUAL_TERMS
        assert "blowjob" in DEFAULT_SEXUAL_TERMS
    
    def test_minors_unsafe_present(self):
        assert "pedophile" in DEFAULT_SEXUAL_TERMS
        assert "molest" in DEFAULT_SEXUAL_TERMS
    
    def test_categories_assigned(self):
        assert DEFAULT_SEXUAL_TERMS["porn"] == CATEGORY_PORNOGRAPHY
        assert DEFAULT_SEXUAL_TERMS["sex"] == CATEGORY_SEXUAL_ACTS
        assert DEFAULT_SEXUAL_TERMS["pedophile"] == CATEGORY_MINORS_UNSAFE
    
    def test_phrases_present(self):
        phrase_texts = [' '.join(p[0]) for p in DEFAULT_SEXUAL_PHRASES]
        assert "watching porn" in phrase_texts
        assert "having sex" in phrase_texts
    
    def test_load_default_terms(self):
        terms = load_sexual_terms()
        assert len(terms) > 100
    
    def test_load_default_phrases(self):
        phrases = load_sexual_phrases()
        assert len(phrases) > 50


class TestSegmentScore:
    """Test segment scoring."""
    
    def test_empty_segment(self):
        segment = SegmentScore(start=0, end=1, text="hello world")
        assert segment.total_score == 0
        assert not segment.has_unsafe_content
    
    def test_single_match(self):
        match = SexualContentMatch(
            text="porn",
            category=CATEGORY_PORNOGRAPHY,
            match_type="word",
            start=0.0,
            end=0.5,
            weight=1.0
        )
        segment = SegmentScore(
            start=0, end=1, text="watching porn",
            matches=[match]
        )
        assert segment.total_score == 1.0
        assert not segment.has_unsafe_content
    
    def test_unsafe_content_flag(self):
        match = SexualContentMatch(
            text="molest",
            category=CATEGORY_MINORS_UNSAFE,
            match_type="word",
            start=0.0,
            end=0.5,
            weight=2.0
        )
        segment = SegmentScore(
            start=0, end=1, text="molest",
            matches=[match]
        )
        assert segment.has_unsafe_content


class TestSexualContentDetector:
    """Test sexual content detector."""
    
    def test_empty_input(self):
        detector = SexualContentDetector()
        intervals = detector.detect([])
        assert intervals == []
    
    def test_no_sexual_content(self):
        words = [
            WordTimestamp("hello", 0.0, 0.5),
            WordTimestamp("world", 0.5, 1.0),
        ]
        detector = SexualContentDetector()
        intervals = detector.detect(words)
        assert len(intervals) == 0
    
    def test_single_word_match(self):
        words = [
            WordTimestamp("watching", 0.0, 0.5),
            WordTimestamp("porn", 0.5, 1.0),
        ]
        detector = SexualContentDetector(threshold=0.5)
        intervals = detector.detect(words)
        assert len(intervals) == 1
        assert "porn" in intervals[0].reason
    
    def test_phrase_match(self):
        words = [
            WordTimestamp("they", 0.0, 0.3),
            WordTimestamp("were", 0.3, 0.5),
            WordTimestamp("having", 0.5, 0.8),
            WordTimestamp("sex", 0.8, 1.2),
        ]
        detector = SexualContentDetector(threshold=0.5)
        intervals = detector.detect(words)
        assert len(intervals) == 1
    
    def test_unsafe_content_low_threshold(self):
        words = [
            WordTimestamp("he", 0.0, 0.3),
            WordTimestamp("molested", 0.3, 0.8),
            WordTimestamp("someone", 0.8, 1.2),
        ]
        # Even with high threshold, unsafe content should trigger
        detector = SexualContentDetector(threshold=5.0, unsafe_threshold=0.5)
        
        # Check the segment analysis
        segment = detector.analyze_segment(words, 0, len(words))
        assert segment.has_unsafe_content or len(segment.matches) > 0
    
    def test_multiple_matches_combine_score(self):
        words = [
            WordTimestamp("porn", 0.0, 0.4),
            WordTimestamp("and", 0.4, 0.6),
            WordTimestamp("sex", 0.6, 1.0),
        ]
        detector = SexualContentDetector(threshold=1.5)
        
        segment = detector.analyze_segment(words, 0, len(words))
        # Two words matched, score should be > 1
        assert segment.total_score >= 1.5


class TestDetectSexualContent:
    """Test the convenience detection function."""
    
    def test_basic_detection(self):
        words = [
            WordTimestamp("he", 0.0, 0.2),
            WordTimestamp("was", 0.2, 0.4),
            WordTimestamp("watching", 0.4, 0.8),
            WordTimestamp("porn", 0.8, 1.2),
            WordTimestamp("on", 1.2, 1.4),
            WordTimestamp("his", 1.4, 1.6),
            WordTimestamp("laptop", 1.6, 2.0),
        ]
        
        intervals = detect_sexual_content(
            words,
            threshold=0.5,
            debug=False
        )
        
        assert len(intervals) >= 1
    
    def test_safe_content_not_flagged(self):
        words = [
            WordTimestamp("the", 0.0, 0.2),
            WordTimestamp("weather", 0.2, 0.5),
            WordTimestamp("is", 0.5, 0.7),
            WordTimestamp("nice", 0.7, 1.0),
            WordTimestamp("today", 1.0, 1.4),
        ]
        
        intervals = detect_sexual_content(
            words,
            threshold=0.5,
            debug=False
        )
        
        assert len(intervals) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_case_insensitive(self):
        words = [
            WordTimestamp("PORN", 0.0, 0.5),
        ]
        # Disable regex patterns to test pure lexicon matching
        detector = SexualContentDetector(threshold=0.5, use_regex_patterns=False)
        segment = detector.analyze_segment(words, 0, 1)
        assert len(segment.matches) == 1
    
    def test_with_punctuation(self):
        words = [
            WordTimestamp("porn,", 0.0, 0.5),
        ]
        # Disable regex patterns to test pure lexicon matching
        detector = SexualContentDetector(threshold=0.5, use_regex_patterns=False)
        segment = detector.analyze_segment(words, 0, 1)
        assert len(segment.matches) == 1
    
    def test_misspelled_pron(self):
        words = [
            WordTimestamp("pron", 0.0, 0.5),
        ]
        detector = SexualContentDetector(threshold=0.5)
        segment = detector.analyze_segment(words, 0, 1)
        # "pron" is in lexicon
        assert len(segment.matches) >= 1


class TestContextModifiers:
    """Test context-aware suppression and amplification."""
    
    def test_suck_suppressed_in_innocent_context(self):
        """'suck' should be suppressed when used in 'this sucks' context."""
        words = [
            WordTimestamp("this", 0.0, 0.3),
            WordTimestamp("movie", 0.3, 0.6),
            WordTimestamp("sucks", 0.6, 1.0),
        ]
        detector = SexualContentDetector(threshold=0.5, use_context_modifiers=True)
        segment = detector.analyze_segment(words, 0, 3)
        
        # Should have a match but it should be suppressed
        suck_matches = [m for m in segment.matches if "suck" in m.text.lower()]
        assert all(m.suppressed for m in suck_matches)
        assert segment.active_match_count == 0
    
    def test_escort_suppressed_in_police_context(self):
        """'escort' should be suppressed when used with 'police'."""
        words = [
            WordTimestamp("police", 0.0, 0.4),
            WordTimestamp("escort", 0.4, 0.8),
            WordTimestamp("arrived", 0.8, 1.2),
        ]
        detector = SexualContentDetector(threshold=0.5, use_context_modifiers=True)
        segment = detector.analyze_segment(words, 0, 3)
        
        escort_matches = [m for m in segment.matches if "escort" in m.text.lower()]
        assert all(m.suppressed for m in escort_matches)
    
    def test_suck_amplified_in_explicit_context(self):
        """'suck' should be amplified when used with explicit terms."""
        words = [
            WordTimestamp("suck", 0.0, 0.3),
            WordTimestamp("my", 0.3, 0.5),
            WordTimestamp("dick", 0.5, 0.9),
        ]
        detector = SexualContentDetector(threshold=0.5, use_context_modifiers=True)
        segment = detector.analyze_segment(words, 0, 3)
        
        suck_matches = [m for m in segment.matches if m.text.lower() == "suck"]
        assert len(suck_matches) >= 1
        assert suck_matches[0].context_modifier == 1.5  # Amplified
        assert not suck_matches[0].suppressed


class TestSafeContextPatterns:
    """Test safe context detection for medical/educational/news content."""
    
    def test_medical_context_reduces_score(self):
        """Medical context words should reduce the score."""
        words = [
            WordTimestamp("doctor", 0.0, 0.3),
            WordTimestamp("examined", 0.3, 0.6),
            WordTimestamp("breasts", 0.6, 1.0),
            WordTimestamp("patient", 1.0, 1.3),
        ]
        detector = SexualContentDetector(threshold=0.5, use_safe_context=True)
        segment = detector.analyze_segment(words, 0, 4)
        
        # Safe context should reduce the modifier
        assert segment.safe_context_modifier < 1.0
        # Total score should be reduced
        assert segment.total_score < segment.raw_score
    
    def test_news_context_reduces_score(self):
        """News/reporting context should reduce the score."""
        words = [
            WordTimestamp("police", 0.0, 0.3),
            WordTimestamp("arrested", 0.3, 0.6),
            WordTimestamp("sex", 0.6, 0.9),
            WordTimestamp("offender", 0.9, 1.2),
        ]
        detector = SexualContentDetector(threshold=0.5, use_safe_context=True)
        segment = detector.analyze_segment(words, 0, 4)
        
        # Safe context should reduce the modifier
        assert segment.safe_context_modifier < 1.0


class TestRegexPatterns:
    """Test regex pattern matching for evasion detection."""
    
    def test_leetspeak_porn_detected(self):
        """Leetspeak 'p0rn' should be detected."""
        words = [
            WordTimestamp("watching", 0.0, 0.5),
            WordTimestamp("p0rn", 0.5, 1.0),
        ]
        detector = SexualContentDetector(threshold=0.5, use_regex_patterns=True)
        segment = detector.analyze_segment(words, 0, 2)
        
        # Should have regex matches
        regex_matches = [m for m in segment.matches if m.match_type == "regex"]
        assert len(regex_matches) >= 1
    
    def test_spaced_out_evasion_detected(self):
        """Spaced out 's e x' should be detected."""
        words = [
            WordTimestamp("having", 0.0, 0.4),
            WordTimestamp("s", 0.4, 0.5),
            WordTimestamp("e", 0.5, 0.6),  
            WordTimestamp("x", 0.6, 0.7),
        ]
        detector = SexualContentDetector(threshold=0.5, use_regex_patterns=True)
        segment = detector.analyze_segment(words, 0, 4)
        
        # The segment text is "having s e x" which should match spaced pattern
        regex_matches = [m for m in segment.matches if m.match_type == "regex"]
        assert len(regex_matches) >= 1


class TestConfidenceScoring:
    """Test confidence score calculation."""
    
    def test_confidence_high_for_multiple_matches(self):
        """Multiple matches should result in high confidence."""
        words = [
            WordTimestamp("porn", 0.0, 0.4),
            WordTimestamp("and", 0.4, 0.6),
            WordTimestamp("sex", 0.6, 1.0),
        ]
        detector = SexualContentDetector(threshold=0.5, use_regex_patterns=False)
        segment = detector.analyze_segment(words, 0, 3)
        
        # Multiple matches = higher confidence
        assert segment.confidence > 0.5
        assert segment.confidence_level in ("medium", "high")
    
    def test_confidence_zero_when_suppressed(self):
        """Suppressed matches should result in zero confidence."""
        words = [
            WordTimestamp("this", 0.0, 0.3),
            WordTimestamp("game", 0.3, 0.6),
            WordTimestamp("sucks", 0.6, 1.0),
        ]
        detector = SexualContentDetector(threshold=0.5, use_context_modifiers=True)
        segment = detector.analyze_segment(words, 0, 3)
        
        # "sucks" suppressed in innocent context
        assert segment.confidence == 0.0
        assert segment.confidence_level == "low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

