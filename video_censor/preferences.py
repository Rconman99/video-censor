"""
Content filter preferences and profile models.

Provides dataclasses for storing filter settings and named profiles
for the Video Censor parental control system.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional

# Import Action from intervals (circular import avoidance might be needed, 
# but preferences usually is independent. If intervals is low level, we might drag in 
# dependencies. Let's define the strings here or use strings directly to avoid coupling.)
# For preferences, strings are safer for JSON serialization.



@dataclass
class ContentFilterSettings:
    """
    Content filter settings for video censoring.
    
    Attributes:
        filter_language: Mute or beep strong profanity and slurs in dialogue
        filter_sexual_content: Cut sexual content segments from dialogue/narration
        filter_nudity: Cut visual nudity detected by the nudity model
        filter_romance_level: Control romance filtering intensity
            0 = Keep all romance
            1 = Remove only explicit/heavy romance
            2 = Remove kissing and strong romantic implication as well
        filter_violence_level: Control violence filtering intensity
            0 = Keep all violence
            1 = Remove graphic violence (blood, gore, weapon injuries)
            2 = Remove all fighting and physical combat
        filter_mature_themes: Future: filter drugs, self-harm, etc.
        custom_block_phrases: User-defined words/sentences to mute or cut
        safe_cover_enabled: Generate a kid-friendly cover image for media players
        force_english_subtitles: Extract and burn English subtitles into video

        censor_subtitle_profanity: Replace profanity in subtitles with [...]
        
        # Actions (cut, mute, beep, blur, none)
        profanity_action: Action to take for profanity (default: mute)
        nudity_action: Action to take for nudity (default: cut)
        sexual_content_action: Action to take for sexual content (default: cut)
        violence_action: Action to take for violence (default: cut)
    """
    filter_language: bool = True
    filter_sexual_content: bool = True
    filter_nudity: bool = True
    filter_romance_level: int = 0
    filter_violence_level: int = 0
    filter_mature_themes: bool = False
    custom_block_phrases: List[str] = field(default_factory=list)
    safe_cover_enabled: bool = False
    force_english_subtitles: bool = False

    censor_subtitle_profanity: bool = True
    
    # Default Actions
    profanity_action: str = "mute"
    nudity_action: str = "cut"
    sexual_content_action: str = "cut"
    violence_action: str = "cut"
    
    def __post_init__(self):
        """Validate romance and violence levels are in valid range."""
        if self.filter_romance_level not in (0, 1, 2):
            self.filter_romance_level = max(0, min(2, self.filter_romance_level))
        if self.filter_violence_level not in (0, 1, 2, 3):
            self.filter_violence_level = max(0, min(3, self.filter_violence_level))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContentFilterSettings":
        """Create from dictionary (e.g., loaded from JSON)."""
        # Handle missing or extra keys gracefully
        valid_fields = {
            'filter_language',
            'filter_sexual_content', 
            'filter_nudity',
            'filter_romance_level',
            'filter_violence_level',
            'filter_mature_themes',
            'custom_block_phrases',
            'safe_cover_enabled',
            'force_english_subtitles',


            'censor_subtitle_profanity',
            'profanity_action',
            'nudity_action',
            'sexual_content_action',
            'violence_action'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def copy(self) -> "ContentFilterSettings":
        """Create a deep copy of settings."""
        return ContentFilterSettings(
            filter_language=self.filter_language,
            filter_sexual_content=self.filter_sexual_content,
            filter_nudity=self.filter_nudity,
            filter_romance_level=self.filter_romance_level,
            filter_violence_level=self.filter_violence_level,
            filter_mature_themes=self.filter_mature_themes,
            custom_block_phrases=list(self.custom_block_phrases),
            safe_cover_enabled=self.safe_cover_enabled,
            force_english_subtitles=self.force_english_subtitles,

            censor_subtitle_profanity=self.censor_subtitle_profanity,
            profanity_action=self.profanity_action,
            nudity_action=self.nudity_action,
            sexual_content_action=self.sexual_content_action,
            violence_action=self.violence_action
        )
    
    def summary(self) -> str:
        """Generate a human-readable summary of active filters."""
        parts = []
        if self.filter_language:
            parts.append(f"Language ({self.profanity_action})")
        if self.filter_sexual_content:
            parts.append(f"Sexual ({self.sexual_content_action})")
        if self.filter_nudity:
            parts.append(f"Nudity ({self.nudity_action})")
        parts.append(f"Romance: {self.filter_romance_level}")
        if self.filter_violence_level > 0:
            parts.append(f"Violence: {self.filter_violence_level} ({self.violence_action})")
        if self.filter_mature_themes:
            parts.append("Mature ✓")
        if self.custom_block_phrases:
            parts.append(f"Custom: {len(self.custom_block_phrases)}")
        if self.safe_cover_enabled:
            parts.append("SafeCover ✓")
        if self.force_english_subtitles:
            parts.append("Subtitles ✓")
        return " | ".join(parts)
    
    def short_summary(self) -> str:
        """Generate a compact summary for queue display."""
        flags = []
        if self.filter_language:
            flags.append("L")
        if self.filter_sexual_content:
            flags.append("S")
        if self.filter_nudity:
            flags.append("N")
        if self.filter_romance_level > 0:
            flags.append(f"R{self.filter_romance_level}")
        if self.filter_violence_level > 0:
            flags.append(f"V{self.filter_violence_level}")
        if self.filter_mature_themes:
            flags.append("M")
        if self.custom_block_phrases:
            flags.append("Custom")
        if self.safe_cover_enabled:
            flags.append("Cover")
        if self.force_english_subtitles:
            flags.append("Sub")
        return " ".join(flags) if flags else "None"


@dataclass
class Profile:
    """
    A named filter profile for reusable content settings.
    
    Attributes:
        name: Display name for the profile (e.g., "Kid under 10")
        settings: The ContentFilterSettings for this profile
        description: Optional description of the profile's purpose
    """
    name: str
    settings: ContentFilterSettings = field(default_factory=ContentFilterSettings)
    description: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "settings": self.settings.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        """Create from dictionary (e.g., loaded from JSON)."""
        settings_data = data.get("settings", {})
        return cls(
            name=data.get("name", "Unnamed"),
            description=data.get("description", ""),
            settings=ContentFilterSettings.from_dict(settings_data)
        )
    
    def summary(self) -> str:
        """Generate a human-readable summary of this profile's filters."""
        return self.settings.summary()


# Default profiles that ship with the app
DEFAULT_PROFILES = [
    Profile(
        name="Default",
        description="Standard family-safe filtering",
        settings=ContentFilterSettings(
            filter_language=True,
            filter_sexual_content=True,
            filter_nudity=True,
            filter_romance_level=1,
            filter_violence_level=1,  # Graphic only
            filter_mature_themes=False
        )
    ),
    Profile(
        name="Kid under 10",
        description="Maximum filtering for young children",
        settings=ContentFilterSettings(
            filter_language=True,
            filter_sexual_content=True,
            filter_nudity=True,
            filter_romance_level=2,
            filter_violence_level=2,  # All fighting
            filter_mature_themes=True
        )
    ),
    Profile(
        name="Teen",
        description="Moderate filtering for teenagers",
        settings=ContentFilterSettings(
            filter_language=True,
            filter_sexual_content=True,
            filter_nudity=True,
            filter_romance_level=0,
            filter_violence_level=1,  # Graphic only
            filter_mature_themes=False
        )
    ),
    Profile(
        name="Adults (language only)",
        description="Only mute strong language, allow other content",
        settings=ContentFilterSettings(
            filter_language=True,
            filter_sexual_content=False,
            filter_nudity=False,
            filter_romance_level=0,
            filter_violence_level=0,  # Keep all
            filter_mature_themes=False
        )
    )
]
