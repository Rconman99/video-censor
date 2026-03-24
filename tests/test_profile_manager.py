"""Tests for the ProfileManager class."""

import json
import pytest
from pathlib import Path

from video_censor.profile_manager import ProfileManager
from video_censor.preferences import Profile, ContentFilterSettings, DEFAULT_PROFILES


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """Create a ProfileManager with filesystem redirected to tmp_path."""
    monkeypatch.setattr(ProfileManager, "APP_DIR", tmp_path)
    monkeypatch.setattr(ProfileManager, "PROFILES_FILE", tmp_path / "profiles.json")
    return ProfileManager()


def _make_profile(name: str, **kwargs) -> Profile:
    """Helper to create a Profile with optional setting overrides."""
    settings = ContentFilterSettings(**kwargs)
    return Profile(name=name, settings=settings)


class TestInit:
    """Tests for ProfileManager initialization."""

    def test_init_creates_defaults_when_no_file(self, manager):
        """Init creates default profiles when no profiles file exists."""
        names = manager.list_names()
        assert "Default" in names
        assert len(names) == len(DEFAULT_PROFILES)

    def test_default_profile_always_present(self, manager):
        """The Default profile is always present after init."""
        default = manager.get("Default")
        assert default is not None
        assert default.name == "Default"


class TestGet:
    """Tests for get and get_or_default methods."""

    def test_get_returns_none_for_unknown(self, manager):
        """get() returns None when profile name does not exist."""
        assert manager.get("NonExistent") is None

    def test_get_returns_existing_profile(self, manager):
        """get() returns the profile when it exists."""
        profile = manager.get("Default")
        assert profile is not None
        assert profile.name == "Default"

    def test_get_or_default_falls_back(self, manager):
        """get_or_default() returns Default profile for unknown names."""
        result = manager.get_or_default("DoesNotExist")
        assert result.name == "Default"

    def test_get_or_default_returns_match(self, manager):
        """get_or_default() returns the named profile when it exists."""
        result = manager.get_or_default("Teen")
        assert result.name == "Teen"


class TestListProfiles:
    """Tests for listing profiles."""

    def test_list_profiles_default_first(self, manager):
        """list_profiles() always puts Default first."""
        profiles = manager.list_profiles()
        assert profiles[0].name == "Default"

    def test_list_profiles_alphabetical_after_default(self, manager):
        """Profiles after Default are sorted alphabetically."""
        profiles = manager.list_profiles()
        non_default = [p.name for p in profiles[1:]]
        assert non_default == sorted(non_default)

    def test_list_names_matches_list_profiles(self, manager):
        """list_names() returns names in the same order as list_profiles()."""
        assert manager.list_names() == [p.name for p in manager.list_profiles()]

    def test_list_all_is_alias(self, manager):
        """list_all() returns the same result as list_profiles()."""
        assert [p.name for p in manager.list_all()] == [
            p.name for p in manager.list_profiles()
        ]


class TestAdd:
    """Tests for adding profiles."""

    def test_add_new_profile_persists(self, manager):
        """Adding a new profile persists it to disk."""
        new_profile = _make_profile("Custom", filter_language=False)
        manager.add(new_profile)
        assert manager.get("Custom") is not None

        # Verify it was written to disk by loading a fresh manager
        manager2 = ProfileManager()
        assert manager2.get("Custom") is not None

    def test_add_duplicate_name_raises(self, manager):
        """Adding a profile with an existing name raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            manager.add(_make_profile("Default"))

    def test_add_empty_name_raises(self, manager):
        """Adding a profile with an empty name raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            manager.add(_make_profile(""))

    def test_add_whitespace_name_raises(self, manager):
        """Adding a profile with a whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            manager.add(_make_profile("   "))


class TestUpdate:
    """Tests for updating profiles."""

    def test_update_profile_settings(self, manager):
        """Updating a profile's settings persists correctly."""
        updated = Profile(
            name="Teen",
            description="Updated teen profile",
            settings=ContentFilterSettings(filter_language=False),
        )
        manager.update("Teen", updated)
        result = manager.get("Teen")
        assert result.description == "Updated teen profile"
        assert result.settings.filter_language is False

    def test_update_with_rename(self, manager):
        """Updating a profile with a new name renames it."""
        renamed = Profile(name="Teenager", settings=ContentFilterSettings())
        manager.update("Teen", renamed)
        assert manager.get("Teen") is None
        assert manager.get("Teenager") is not None

    def test_update_cannot_rename_default(self, manager):
        """Renaming the Default profile raises ValueError."""
        renamed = Profile(name="MyDefault", settings=ContentFilterSettings())
        with pytest.raises(ValueError, match="Cannot rename the Default"):
            manager.update("Default", renamed)

    def test_update_nonexistent_raises(self, manager):
        """Updating a profile that does not exist raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.update("Ghost", _make_profile("Ghost"))


class TestDelete:
    """Tests for deleting profiles."""

    def test_delete_profile(self, manager):
        """Deleting a profile removes it."""
        manager.delete("Teen")
        assert manager.get("Teen") is None

    def test_delete_default_raises(self, manager):
        """Deleting the Default profile raises ValueError."""
        with pytest.raises(ValueError, match="Cannot delete the Default"):
            manager.delete("Default")

    def test_delete_unknown_raises(self, manager):
        """Deleting a nonexistent profile raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.delete("NoSuchProfile")


class TestDuplicate:
    """Tests for duplicating profiles."""

    def test_duplicate_profile(self, manager):
        """Duplicating creates a new profile with copied settings."""
        new = manager.duplicate("Default", "My Copy")
        assert new.name == "My Copy"
        assert new.description == "Copy of Default"
        # Settings should match the source
        original = manager.get("Default")
        assert new.settings.filter_language == original.settings.filter_language
        assert new.settings.filter_nudity == original.settings.filter_nudity

    def test_duplicate_existing_name_raises(self, manager):
        """Duplicating to an existing name raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            manager.duplicate("Default", "Teen")

    def test_duplicate_nonexistent_source_raises(self, manager):
        """Duplicating from a nonexistent source raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.duplicate("Ghost", "NewProfile")


class TestResetToDefaults:
    """Tests for resetting to defaults."""

    def test_reset_to_defaults(self, manager):
        """reset_to_defaults() restores factory profiles."""
        manager.add(_make_profile("Custom"))
        manager.delete("Teen")
        manager.reset_to_defaults()

        names = manager.list_names()
        default_names = [p.name for p in DEFAULT_PROFILES]
        assert set(names) == set(default_names)
        assert "Custom" not in names


class TestPersistence:
    """Tests for save/load and filesystem behavior."""

    def test_corrupt_json_handled_gracefully(self, tmp_path, monkeypatch):
        """Loading corrupt JSON falls back to default profiles."""
        monkeypatch.setattr(ProfileManager, "APP_DIR", tmp_path)
        monkeypatch.setattr(ProfileManager, "PROFILES_FILE", tmp_path / "profiles.json")

        (tmp_path / "profiles.json").write_text("{bad json!!", encoding="utf-8")

        mgr = ProfileManager()
        assert mgr.get("Default") is not None
        assert len(mgr.list_profiles()) >= 1

    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        """Profiles survive a save/load cycle."""
        monkeypatch.setattr(ProfileManager, "APP_DIR", tmp_path)
        monkeypatch.setattr(ProfileManager, "PROFILES_FILE", tmp_path / "profiles.json")

        mgr1 = ProfileManager()
        mgr1.add(
            Profile(
                name="Roundtrip",
                description="Test roundtrip",
                settings=ContentFilterSettings(
                    filter_language=False,
                    filter_violence_level=2,
                    custom_block_phrases=["test phrase"],
                ),
            )
        )

        mgr2 = ProfileManager()
        loaded = mgr2.get("Roundtrip")
        assert loaded is not None
        assert loaded.description == "Test roundtrip"
        assert loaded.settings.filter_language is False
        assert loaded.settings.filter_violence_level == 2
        assert loaded.settings.custom_block_phrases == ["test phrase"]
