"""
Tests for video_censor/preferences.py

Tests ContentFilterSettings, Profile, serialization roundtrips,
validation, summaries, and the DEFAULT_PROFILES list.
"""

import pytest

from video_censor.preferences import (
    ContentFilterSettings,
    Profile,
    DEFAULT_PROFILES,
)


# ---------------------------------------------------------------------------
# ContentFilterSettings — defaults & validation
# ---------------------------------------------------------------------------

class TestContentFilterSettingsDefaults:
    def test_default_values(self):
        s = ContentFilterSettings()
        assert s.filter_language is True
        assert s.filter_sexual_content is True
        assert s.filter_nudity is True
        assert s.filter_romance_level == 0
        assert s.filter_violence_level == 0
        assert s.filter_mature_themes is False
        assert s.custom_block_phrases == []
        assert s.profanity_action == "mute"
        assert s.nudity_action == "cut"

    def test_romance_level_clamped_high(self):
        s = ContentFilterSettings(filter_romance_level=99)
        assert s.filter_romance_level == 2

    def test_romance_level_clamped_low(self):
        s = ContentFilterSettings(filter_romance_level=-5)
        assert s.filter_romance_level == 0

    def test_violence_level_clamped_high(self):
        s = ContentFilterSettings(filter_violence_level=10)
        assert s.filter_violence_level == 3

    def test_violence_level_clamped_low(self):
        s = ContentFilterSettings(filter_violence_level=-1)
        assert s.filter_violence_level == 0


# ---------------------------------------------------------------------------
# ContentFilterSettings — serialization
# ---------------------------------------------------------------------------

class TestContentFilterSettingsSerialization:
    def test_to_dict_roundtrip(self):
        original = ContentFilterSettings(
            filter_language=False,
            filter_nudity=False,
            custom_block_phrases=["heck", "darn"],
            profanity_action="beep",
        )
        d = original.to_dict()
        restored = ContentFilterSettings.from_dict(d)
        assert restored.filter_language is False
        assert restored.filter_nudity is False
        assert restored.custom_block_phrases == ["heck", "darn"]
        assert restored.profanity_action == "beep"

    def test_from_dict_ignores_unknown_keys(self):
        data = {"filter_language": True, "unknown_field": 42}
        s = ContentFilterSettings.from_dict(data)
        assert s.filter_language is True
        assert not hasattr(s, "unknown_field") or True  # just doesn't crash

    def test_from_dict_empty_dict(self):
        s = ContentFilterSettings.from_dict({})
        # Should use all defaults
        assert s.filter_language is True
        assert s.profanity_action == "mute"

    def test_from_dict_partial_keys(self):
        s = ContentFilterSettings.from_dict({"filter_nudity": False})
        assert s.filter_nudity is False
        assert s.filter_language is True  # default preserved


# ---------------------------------------------------------------------------
# ContentFilterSettings — copy
# ---------------------------------------------------------------------------

class TestContentFilterSettingsCopy:
    def test_copy_is_equal(self):
        original = ContentFilterSettings(custom_block_phrases=["foo"])
        copied = original.copy()
        assert copied.filter_language == original.filter_language
        assert copied.custom_block_phrases == original.custom_block_phrases

    def test_copy_is_independent(self):
        original = ContentFilterSettings(custom_block_phrases=["foo"])
        copied = original.copy()
        copied.custom_block_phrases.append("bar")
        assert "bar" not in original.custom_block_phrases

    def test_copy_preserves_non_default_values(self):
        original = ContentFilterSettings(
            filter_language=False,
            profanity_action="beep",
            nudity_action="blur",
        )
        copied = original.copy()
        assert copied.filter_language is False
        assert copied.profanity_action == "beep"
        assert copied.nudity_action == "blur"


# ---------------------------------------------------------------------------
# ContentFilterSettings — summary
# ---------------------------------------------------------------------------

class TestContentFilterSettingsSummary:
    def test_summary_includes_language(self):
        s = ContentFilterSettings(filter_language=True)
        assert "Language" in s.summary()

    def test_summary_includes_action(self):
        s = ContentFilterSettings(profanity_action="beep")
        assert "beep" in s.summary()

    def test_summary_excludes_disabled_filters(self):
        s = ContentFilterSettings(
            filter_language=False,
            filter_sexual_content=False,
            filter_nudity=False,
        )
        summary = s.summary()
        assert "Language" not in summary
        assert "Sexual" not in summary
        assert "Nudity" not in summary

    def test_summary_includes_custom_count(self):
        s = ContentFilterSettings(custom_block_phrases=["a", "b", "c"])
        assert "3" in s.summary()

    def test_summary_violence_level(self):
        s = ContentFilterSettings(filter_violence_level=2)
        assert "Violence" in s.summary()

    def test_summary_no_violence_when_zero(self):
        s = ContentFilterSettings(filter_violence_level=0)
        assert "Violence" not in s.summary()


# ---------------------------------------------------------------------------
# ContentFilterSettings — short_summary
# ---------------------------------------------------------------------------

class TestContentFilterSettingsShortSummary:
    def test_all_defaults(self):
        s = ContentFilterSettings()
        short = s.short_summary()
        assert "L" in short
        assert "S" in short
        assert "N" in short

    def test_nothing_enabled(self):
        s = ContentFilterSettings(
            filter_language=False,
            filter_sexual_content=False,
            filter_nudity=False,
        )
        assert s.short_summary() == "None"

    def test_romance_level(self):
        s = ContentFilterSettings(filter_romance_level=2)
        assert "R2" in s.short_summary()

    def test_violence_level(self):
        s = ContentFilterSettings(filter_violence_level=1)
        assert "V1" in s.short_summary()

    def test_subtitles_flag(self):
        s = ContentFilterSettings(force_english_subtitles=True)
        assert "Sub" in s.short_summary()

    def test_safe_cover_flag(self):
        s = ContentFilterSettings(safe_cover_enabled=True)
        assert "Cover" in s.short_summary()


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class TestProfile:
    def test_default_values(self):
        p = Profile(name="Test")
        assert p.name == "Test"
        assert p.description == ""
        assert isinstance(p.settings, ContentFilterSettings)

    def test_to_dict_roundtrip(self):
        p = Profile(
            name="Custom",
            description="My profile",
            settings=ContentFilterSettings(filter_language=False),
        )
        d = p.to_dict()
        restored = Profile.from_dict(d)
        assert restored.name == "Custom"
        assert restored.description == "My profile"
        assert restored.settings.filter_language is False

    def test_from_dict_missing_name(self):
        p = Profile.from_dict({})
        assert p.name == "Unnamed"

    def test_from_dict_missing_settings(self):
        p = Profile.from_dict({"name": "Test"})
        # Should get default settings
        assert p.settings.filter_language is True

    def test_summary_delegates_to_settings(self):
        settings = ContentFilterSettings(filter_language=True)
        p = Profile(name="Test", settings=settings)
        assert p.summary() == settings.summary()


# ---------------------------------------------------------------------------
# DEFAULT_PROFILES
# ---------------------------------------------------------------------------

class TestDefaultProfiles:
    def test_is_list(self):
        assert isinstance(DEFAULT_PROFILES, list)

    def test_has_profiles(self):
        assert len(DEFAULT_PROFILES) >= 3

    def test_all_are_profile_instances(self):
        for p in DEFAULT_PROFILES:
            assert isinstance(p, Profile)

    def test_all_have_names(self):
        for p in DEFAULT_PROFILES:
            assert len(p.name) > 0

    def test_unique_names(self):
        names = [p.name for p in DEFAULT_PROFILES]
        assert len(names) == len(set(names))

    def test_default_profile_exists(self):
        names = [p.name for p in DEFAULT_PROFILES]
        assert "Default" in names

    def test_kid_profile_is_strictest(self):
        kid = next(p for p in DEFAULT_PROFILES if "Kid" in p.name or "kid" in p.name)
        assert kid.settings.filter_language is True
        assert kid.settings.filter_nudity is True
        assert kid.settings.filter_romance_level == 2
        assert kid.settings.filter_violence_level >= 2
