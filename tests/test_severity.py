"""
Tests for video_censor/profanity/severity.py

Tests severity tier classification, partial matching, overrides,
custom tiers, and tier word retrieval.
"""

import pytest

from video_censor.profanity.severity import (
    SEVERITY_TIERS,
    get_severity,
    get_tier_words,
)


class TestSeverityTierStructure:
    def test_has_four_default_tiers(self):
        assert len(SEVERITY_TIERS) == 4

    def test_tier_names(self):
        assert set(SEVERITY_TIERS.keys()) == {"severe", "moderate", "mild", "religious"}

    def test_tier_order(self):
        assert SEVERITY_TIERS["severe"]["order"] == 1
        assert SEVERITY_TIERS["moderate"]["order"] == 2
        assert SEVERITY_TIERS["mild"]["order"] == 3
        assert SEVERITY_TIERS["religious"]["order"] == 4

    def test_each_tier_has_color(self):
        for tier in SEVERITY_TIERS.values():
            assert tier["color"].startswith("#")

    def test_each_tier_has_words(self):
        for tier in SEVERITY_TIERS.values():
            assert len(tier["words"]) > 0


class TestGetSeverityExactMatch:
    def test_severe_word(self):
        tier, order, color = get_severity("fuck")
        assert tier == "severe"
        assert order == 1
        assert color == "#FF0000"

    def test_moderate_word(self):
        tier, order, color = get_severity("crap")
        assert tier == "moderate"
        assert order == 2

    def test_mild_word(self):
        tier, order, color = get_severity("damn")
        assert tier == "mild"
        assert order == 3

    def test_religious_word(self):
        tier, order, color = get_severity("jesus")
        assert tier == "religious"
        assert order == 4

    def test_case_insensitive(self):
        tier, _, _ = get_severity("FUCK")
        assert tier == "severe"

    def test_unknown_word(self):
        tier, order, color = get_severity("banana")
        assert tier == "unknown"
        assert order == 99
        assert color == "#808080"


class TestGetSeverityPartialMatch:
    def test_compound_word_matches_severe(self):
        """Words containing a tier word should match via partial matching."""
        tier, order, _ = get_severity("motherfucking")
        # "fuck" is in "motherfucking" → severe
        assert tier == "severe"

    def test_higher_severity_matched_first(self):
        """If multiple tiers match, the higher severity (lower order) wins."""
        # "ass" is in mild, "asshole" is in severe
        tier, _, _ = get_severity("asshole")
        assert tier == "severe"


class TestGetSeverityOverrides:
    def test_override_moves_word_to_different_tier(self):
        overrides = {"heck": "severe"}
        tier, order, color = get_severity("heck", overrides=overrides)
        assert tier == "severe"
        assert order == 1

    def test_override_unknown_word(self):
        overrides = {"fiddlesticks": "moderate"}
        tier, _, _ = get_severity("fiddlesticks", overrides=overrides)
        assert tier == "moderate"

    def test_override_invalid_tier_name(self):
        """Override pointing to nonexistent tier should fall through."""
        overrides = {"damn": "nonexistent_tier"}
        tier, _, _ = get_severity("damn", overrides=overrides)
        # Falls through override, matches exact in "mild"
        assert tier == "mild"


class TestGetSeverityCustomTiers:
    def test_custom_tier_added(self):
        custom = [{"name": "slang", "order": 5, "color": "#00FF00", "words": ["yikes", "sheesh"]}]
        tier, order, color = get_severity("yikes", custom_tiers=custom)
        assert tier == "slang"
        assert order == 5
        assert color == "#00FF00"

    def test_custom_tier_does_not_break_defaults(self):
        custom = [{"name": "slang", "order": 5, "color": "#00FF00", "words": ["yikes"]}]
        tier, _, _ = get_severity("fuck", custom_tiers=custom)
        assert tier == "severe"

    def test_custom_tier_without_name_ignored(self):
        custom = [{"order": 5, "color": "#00FF00", "words": ["test"]}]
        # Should not crash
        tier, _, _ = get_severity("test", custom_tiers=custom)
        # Won't match because name is None
        assert tier == "unknown"


class TestGetTierWords:
    def test_get_severe_words(self):
        words = get_tier_words("severe")
        assert "fuck" in words
        assert "shit" in words

    def test_get_mild_words(self):
        words = get_tier_words("mild")
        assert "damn" in words

    def test_nonexistent_tier_returns_empty(self):
        assert get_tier_words("nonexistent") == []
