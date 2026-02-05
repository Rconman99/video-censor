"""
Tests for video_censor/profanity/whitelist.py

Tests the DEFAULT_WHITELIST and ALWAYS_FLAG sets for correctness,
completeness, and mutual exclusivity.
"""

from video_censor.profanity.whitelist import DEFAULT_WHITELIST, ALWAYS_FLAG


# ---------------------------------------------------------------------------
# DEFAULT_WHITELIST basics
# ---------------------------------------------------------------------------

class TestDefaultWhitelist:
    def test_is_a_set(self):
        assert isinstance(DEFAULT_WHITELIST, set)

    def test_is_non_empty(self):
        assert len(DEFAULT_WHITELIST) > 0

    def test_all_lowercase(self):
        for word in DEFAULT_WHITELIST:
            assert word == word.lower(), f"Whitelist entry '{word}' is not lowercase"

    def test_known_safe_words_present(self):
        """Key safe words that contain profanity substrings."""
        expected = [
            "class", "pass", "hello", "shell", "cocktail",
            "title", "analyze", "christmas", "passport", "massachusetts",
        ]
        for word in expected:
            assert word in DEFAULT_WHITELIST, f"'{word}' missing from whitelist"

    def test_shiitake_present(self):
        """Classic false positive for 'shit'."""
        assert "shiitake" in DEFAULT_WHITELIST

    def test_mississippi_present(self):
        """Classic false positive for 'piss'."""
        assert "mississippi" in DEFAULT_WHITELIST

    def test_no_duplicates(self):
        """Sets don't have duplicates by definition, but verify length."""
        as_list = list(DEFAULT_WHITELIST)
        assert len(as_list) == len(set(as_list))


# ---------------------------------------------------------------------------
# ALWAYS_FLAG basics
# ---------------------------------------------------------------------------

class TestAlwaysFlag:
    def test_is_a_set(self):
        assert isinstance(ALWAYS_FLAG, set)

    def test_is_non_empty(self):
        assert len(ALWAYS_FLAG) > 0

    def test_all_lowercase(self):
        for word in ALWAYS_FLAG:
            assert word == word.lower(), f"ALWAYS_FLAG entry '{word}' is not lowercase"

    def test_core_profanity_present(self):
        core = ["fuck", "shit", "ass", "bitch", "damn", "cunt"]
        for word in core:
            assert word in ALWAYS_FLAG, f"'{word}' missing from ALWAYS_FLAG"

    def test_slurs_present(self):
        slurs = ["nigger", "nigga", "fag", "faggot", "retard"]
        for word in slurs:
            assert word in ALWAYS_FLAG, f"'{word}' missing from ALWAYS_FLAG"


# ---------------------------------------------------------------------------
# Relationship between the two sets
# ---------------------------------------------------------------------------

class TestWhitelistAlwaysFlagRelationship:
    def test_no_overlap(self):
        """ALWAYS_FLAG and DEFAULT_WHITELIST must be mutually exclusive."""
        overlap = DEFAULT_WHITELIST & ALWAYS_FLAG
        assert overlap == set(), f"Overlap found: {overlap}"

    def test_whitelist_words_contain_profanity_substrings(self):
        """Verify whitelist words actually contain substrings of flagged words."""
        profanity_substrings = {"ass", "hell", "damn", "shit", "cock", "dick",
                                "piss", "crap", "tit", "cum", "anal", "sex",
                                "god", "christ"}
        found_any = False
        for word in DEFAULT_WHITELIST:
            for sub in profanity_substrings:
                if sub in word:
                    found_any = True
                    break
        assert found_any, "Whitelist should contain words with profanity substrings"

    def test_whitelist_does_not_contain_standalone_profanity(self):
        """No exact profanity match should appear in the whitelist."""
        standalone = {"fuck", "shit", "ass", "hell", "damn", "bitch", "cunt",
                      "cock", "dick", "piss", "crap"}
        for word in standalone:
            assert word not in DEFAULT_WHITELIST, f"Profanity '{word}' in whitelist"
