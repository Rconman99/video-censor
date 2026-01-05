"""
Built-in filter presets for common use cases.

Provides one-click configuration for different content filtering needs:
- Family Friendly: Maximum filtering for family viewing
- YouTube Safe: Suitable for YouTube monetization
- Broadcast: Meets broadcast TV standards
- Minimal: Light filtering, only severe content
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class FilterPreset:
    """A named configuration preset."""
    name: str
    description: str
    icon: str
    settings: Dict[str, Any] = field(default_factory=dict)


# Built-in presets
PRESETS: Dict[str, FilterPreset] = {
    "family_friendly": FilterPreset(
        name="Family Friendly",
        description="Maximum protection for family movie night",
        icon="👨‍👩‍👧‍👦",
        settings={
            "profanity": {
                "enabled": True,
                "context_aware": True,
                "censor_mode": "beep",
            },
            "nudity": {
                "threshold": 0.6,  # More sensitive
                "frame_interval": 0.1,  # Dense sampling
            },
            "sexual_content": {
                "enabled": True,
                "threshold": 0.8,
            },
        }
    ),
    
    "youtube_safe": FilterPreset(
        name="YouTube Safe",
        description="Suitable for YouTube monetization",
        icon="📺",
        settings={
            "profanity": {
                "enabled": True,
                "context_aware": True,
                "censor_mode": "beep",
            },
            "nudity": {
                "threshold": 0.75,
            },
            "sexual_content": {
                "enabled": True,
                "threshold": 1.0,
            },
        }
    ),
    
    "broadcast": FilterPreset(
        name="Broadcast TV",
        description="Meets broadcast standards",
        icon="📡",
        settings={
            "profanity": {
                "enabled": True,
                "context_aware": True,
                "censor_mode": "mute",  # Mute instead of beep
            },
            "nudity": {
                "threshold": 0.5,  # Very sensitive
            },
            "sexual_content": {
                "enabled": True,
                "threshold": 0.5,
            },
        }
    ),
    
    "minimal": FilterPreset(
        name="Minimal",
        description="Only censor severe content",
        icon="🔇",
        settings={
            "profanity": {
                "enabled": True,
                "context_aware": False,  # Fast, less checking
                "censor_mode": "beep",
            },
            "nudity": {
                "threshold": 0.9,  # Very high bar
            },
            "sexual_content": {
                "enabled": False,
            },
        }
    ),
    
    "default": FilterPreset(
        name="Default",
        description="Balanced filtering",
        icon="⚖️",
        settings={
            "profanity": {
                "enabled": True,
                "censor_mode": "beep",
            },
            "nudity": {
                "threshold": 0.75,
            },
            "sexual_content": {
                "enabled": True,
                "threshold": 1.0,
            },
        }
    ),
}


def get_preset(name: str) -> Optional[FilterPreset]:
    """Get a preset by name."""
    return PRESETS.get(name.lower().replace(" ", "_"))


def list_presets() -> list[FilterPreset]:
    """List all available presets."""
    return list(PRESETS.values())


def apply_preset(config, preset_name: str) -> None:
    """
    Apply a preset's settings to a Config object.
    
    Args:
        config: Main Config object to modify
        preset_name: Name of preset to apply
    """
    preset = get_preset(preset_name)
    if not preset:
        return
    
    settings = preset.settings
    
    # Apply profanity settings
    if 'profanity' in settings:
        for key, value in settings['profanity'].items():
            if hasattr(config.profanity, key):
                setattr(config.profanity, key, value)
    
    # Apply nudity settings
    if 'nudity' in settings:
        for key, value in settings['nudity'].items():
            if hasattr(config.nudity, key):
                setattr(config.nudity, key, value)
    
    # Apply sexual_content settings
    if 'sexual_content' in settings:
        for key, value in settings['sexual_content'].items():
            if hasattr(config.sexual_content, key):
                setattr(config.sexual_content, key, value)


def get_preset_summary(preset_name: str) -> str:
    """Get a human-readable summary of preset settings."""
    preset = get_preset(preset_name)
    if not preset:
        return "Unknown preset"
    
    parts = [f"{preset.icon} {preset.name}: {preset.description}"]
    settings = preset.settings
    
    if 'profanity' in settings:
        mode = settings['profanity'].get('censor_mode', 'beep')
        parts.append(f"  Audio: {mode}")
    
    if 'nudity' in settings:
        threshold = settings['nudity'].get('threshold', 0.75)
        sensitivity = "high" if threshold < 0.7 else "medium" if threshold < 0.85 else "low"
        parts.append(f"  Visual: {sensitivity} sensitivity")
    
    return "\n".join(parts)
