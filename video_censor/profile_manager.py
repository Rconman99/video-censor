"""
Profile manager for persistent profile storage.

Handles loading, saving, and CRUD operations for user-defined
content filter profiles stored in ~/.video_censor/profiles.json.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .preferences import Profile, ContentFilterSettings, DEFAULT_PROFILES

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Manages profile storage and retrieval.
    
    Profiles are stored in a JSON file in the user's home directory.
    A "Default" profile always exists and cannot be deleted.
    """
    
    APP_DIR = Path.home() / ".video_censor"
    PROFILES_FILE = APP_DIR / "profiles.json"
    CURRENT_VERSION = 1
    
    def __init__(self):
        """Initialize the profile manager and load profiles from disk."""
        self._profiles: Dict[str, Profile] = {}
        self._ensure_app_dir()
        self.load()
    
    def _ensure_app_dir(self) -> None:
        """Ensure the app directory exists."""
        try:
            self.APP_DIR.mkdir(parents=True, exist_ok=True)
            logger.debug(f"App directory ensured: {self.APP_DIR}")
        except OSError as e:
            logger.error(f"Failed to create app directory: {e}")
    
    def _ensure_default_profile(self) -> None:
        """Ensure at least a Default profile exists."""
        if "Default" not in self._profiles:
            default = next(
                (p for p in DEFAULT_PROFILES if p.name == "Default"),
                Profile(name="Default", settings=ContentFilterSettings())
            )
            self._profiles["Default"] = Profile(
                name=default.name,
                description=default.description,
                settings=default.settings.copy()
            )
            logger.info("Created default profile")
    
    def load(self) -> None:
        """Load profiles from disk. Creates defaults if file doesn't exist."""
        if not self.PROFILES_FILE.exists():
            logger.info("No profiles file found, creating defaults")
            self._initialize_defaults()
            self.save()
            return
        
        try:
            with open(self.PROFILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle version migrations if needed
            version = data.get("version", 1)
            if version > self.CURRENT_VERSION:
                logger.warning(f"Profiles file version {version} is newer than supported {self.CURRENT_VERSION}")
            
            # Load profiles
            profiles_data = data.get("profiles", [])
            self._profiles = {}
            for profile_data in profiles_data:
                try:
                    profile = Profile.from_dict(profile_data)
                    self._profiles[profile.name] = profile
                except Exception as e:
                    logger.warning(f"Failed to load profile: {e}")
            
            logger.info(f"Loaded {len(self._profiles)} profiles from disk")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in profiles file: {e}")
            self._initialize_defaults()
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            self._initialize_defaults()
        
        # Always ensure default exists
        self._ensure_default_profile()
    
    def _initialize_defaults(self) -> None:
        """Initialize with default profiles."""
        self._profiles = {}
        for default_profile in DEFAULT_PROFILES:
            self._profiles[default_profile.name] = Profile(
                name=default_profile.name,
                description=default_profile.description,
                settings=default_profile.settings.copy()
            )
        logger.info(f"Initialized {len(self._profiles)} default profiles")
    
    def save(self) -> None:
        """Write all profiles to disk."""
        try:
            data = {
                "version": self.CURRENT_VERSION,
                "profiles": [p.to_dict() for p in self._profiles.values()]
            }
            
            with open(self.PROFILES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved {len(self._profiles)} profiles to disk")
            
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
            raise
    
    def get(self, name: str) -> Optional[Profile]:
        """Get a profile by name. Returns None if not found."""
        return self._profiles.get(name)
    
    def get_or_default(self, name: str) -> Profile:
        """Get a profile by name, or return Default if not found."""
        return self._profiles.get(name, self._profiles["Default"])
    
    def list_profiles(self) -> List[Profile]:
        """Get all profiles as a list, with Default first."""
        profiles = list(self._profiles.values())
        # Sort with Default first, then alphabetically
        profiles.sort(key=lambda p: (0 if p.name == "Default" else 1, p.name))
        return profiles
    
    def list_names(self) -> List[str]:
        """Get all profile names, with Default first."""
        return [p.name for p in self.list_profiles()]
    
    def add(self, profile: Profile) -> None:
        """Add a new profile. Raises ValueError if name already exists."""
        if profile.name in self._profiles:
            raise ValueError(f"Profile '{profile.name}' already exists")
        if not profile.name.strip():
            raise ValueError("Profile name cannot be empty")
        
        self._profiles[profile.name] = profile
        self.save()
        logger.info(f"Added profile: {profile.name}")
    
    def update(self, name: str, profile: Profile) -> None:
        """
        Update an existing profile.
        
        If the name changes, the old profile is removed and a new one is added.
        """
        if name not in self._profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        # Handle rename
        if name != profile.name:
            if profile.name in self._profiles:
                raise ValueError(f"Profile '{profile.name}' already exists")
            if name == "Default":
                raise ValueError("Cannot rename the Default profile")
            del self._profiles[name]
        
        self._profiles[profile.name] = profile
        self.save()
        logger.info(f"Updated profile: {name} -> {profile.name}")
    
    def delete(self, name: str) -> None:
        """Delete a profile. Cannot delete the Default profile."""
        if name == "Default":
            raise ValueError("Cannot delete the Default profile")
        if name not in self._profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        del self._profiles[name]
        self.save()
        logger.info(f"Deleted profile: {name}")
    
    def duplicate(self, source_name: str, new_name: str) -> Profile:
        """
        Create a copy of an existing profile with a new name.
        
        Returns the new profile.
        """
        source = self.get(source_name)
        if source is None:
            raise ValueError(f"Source profile '{source_name}' not found")
        if new_name in self._profiles:
            raise ValueError(f"Profile '{new_name}' already exists")
        if not new_name.strip():
            raise ValueError("New profile name cannot be empty")
        
        new_profile = Profile(
            name=new_name,
            description=f"Copy of {source_name}",
            settings=source.settings.copy()
        )
        self._profiles[new_name] = new_profile
        self.save()
        logger.info(f"Duplicated profile: {source_name} -> {new_name}")
        return new_profile
    
    def reset_to_defaults(self) -> None:
        """Reset all profiles to factory defaults."""
        self._initialize_defaults()
        self.save()
        logger.info("Reset profiles to defaults")
