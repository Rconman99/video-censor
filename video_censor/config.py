"""
Configuration loader for Video Censor Tool.

Loads settings from YAML config file with sensible defaults.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SystemConfig:
    """System-level configuration."""
    performance_mode: str = "low_power"  # high, balanced, low_power



@dataclass
class ProfanityConfig:
    """Configuration for profanity detection."""
    custom_wordlist_path: str = ""
    custom_phrases_path: str = ""  # Path to file with multi-word phrases
    censor_mode: str = "beep"  # "mute" or "beep"
    beep_frequency_hz: int = 1000
    beep_volume: float = 0.5
    buffer_before: float = 0.1
    buffer_after: float = 0.15
    merge_gap: float = 0.3
    # Dynamic buffer: add extra buffer based on word length
    dynamic_buffer: bool = True
    dynamic_buffer_factor: float = 0.02  # Extra seconds per character


@dataclass
class NudityConfig:
    """Configuration for nudity detection."""
    threshold: float = 0.6
    frame_interval: float = 0.25
    min_segment_duration: float = 0.5
    buffer_before: float = 0.25
    buffer_after: float = 0.25
    merge_gap: float = 0.5
    # Body part filtering - list of body parts to detect
    # Available: FEMALE_BREAST_EXPOSED, FEMALE_GENITALIA_EXPOSED,
    #            MALE_GENITALIA_EXPOSED, BUTTOCKS_EXPOSED, ANUS_EXPOSED
    # Leave empty to detect all exposed body parts
    body_parts: list = None  # Will default to all exposed parts
    # Minimum duration for a cut to be applied (prevents micro-cuts)
    min_cut_duration: float = 0.3

    def __post_init__(self):
        if self.body_parts is None:
            self.body_parts = []  # Empty means all


@dataclass
class SexualContentConfig:
    """Configuration for sexual content detection."""
    enabled: bool = True
    threshold: float = 1.0  # Score threshold for flagging
    unsafe_threshold: float = 0.5  # Stricter threshold for minors/unsafe
    custom_terms_path: str = ""  # Path to custom terms file
    custom_phrases_path: str = ""  # Path to custom phrases file
    buffer_before: float = 0.25
    buffer_after: float = 0.25
    merge_gap: float = 0.5
    debug: bool = False  # Enable debug logging
    
    # Phase 1: Context-aware detection
    use_context_modifiers: bool = True  # Suppress/amplify based on surrounding words
    use_safe_context: bool = True  # Reduce scores for medical/educational/news contexts
    use_regex_patterns: bool = True  # Detect leetspeak and evasion patterns
    
    # Phase 2: ML-enhanced detection
    use_hybrid_detection: bool = False  # Use hybrid lexicon + semantic detector
    use_semantic_verification: bool = False  # Verify uncertain detections with ML
    semantic_threshold: float = 0.5  # Minimum semantic similarity to verify
    
    # Phase 2: Multimodal fusion
    use_multimodal_fusion: bool = False  # Combine audio + visual detections
    audio_weight: float = 0.4  # Weight for audio/transcript detections
    visual_weight: float = 0.6  # Weight for visual/nudity detections
    agreement_boost: float = 0.3  # Confidence boost when both modalities agree



@dataclass
class WhisperConfig:
    """Configuration for Whisper speech-to-text."""
    model_size: str = "base"
    language: str = "en"
    compute_type: str = "int8"


@dataclass
class OutputConfig:
    """Configuration for output video."""
    custom_output_dir: str = ""
    default_pattern: str = "{input}_censored"
    video_codec: str = "libx264"
    video_crf: int = 23
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    video_format: str = "mp4"  # output container format (mp4, mkv, avi, mov)
    
    # Quality Preset (simple dropdown selection)
    # Options: original, auto, 1080p_high, 1080p_med, 1080p_10, 1080p_low,
    #          720p_high, 720p_med, 720p_low, 480p, 328p, 240p, 160p
    quality_preset: str = "original"
    
    # Internal usage (for encoding)
    video_crf: int = 23
    hardware_acceleration: str = "auto"


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    log_file: str = ""
    show_progress: bool = True


@dataclass
class NotificationsConfig:
    """Configuration for push notifications."""
    enabled: bool = False
    ntfy_topic: str = ""  # e.g., "videocensor-yourname-12345"
    notify_on_complete: bool = True
    notify_on_error: bool = True
    notify_on_batch_done: bool = True


@dataclass
class ContentLookupConfig:
    """Configuration for external content lookup services."""
    dtdd_api_key: str = ""  # DoesTheDogDie API key from profile
    cache_enabled: bool = True
    cache_ttl_hours: int = 168  # 1 week


@dataclass
class CommunityConfig:
    """Configuration for community timestamp sharing."""
    enabled: bool = True
    auto_lookup: bool = True        # Auto-check cloud on video drop
    auto_upload: bool = False       # Prompt before uploading (safer default)
    min_quality_score: float = 0.5  # Only use timestamps above this score
    device_id: str = ""             # Auto-generated anonymous device ID


@dataclass
class Config:
    """Main configuration container."""
    profanity: ProfanityConfig = field(default_factory=ProfanityConfig)
    nudity: NudityConfig = field(default_factory=NudityConfig)
    sexual_content: SexualContentConfig = field(default_factory=SexualContentConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    content_lookup: ContentLookupConfig = field(default_factory=ContentLookupConfig)
    community: CommunityConfig = field(default_factory=CommunityConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from YAML file.
        
        If no path is provided, uses default values.
        Missing keys in the config file will use defaults.
        """
        config = cls()
        
        if config_path and config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Update profanity config
            if 'profanity' in data:
                for key, value in data['profanity'].items():
                    if hasattr(config.profanity, key):
                        setattr(config.profanity, key, value)
            
            # Update nudity config
            if 'nudity' in data:
                for key, value in data['nudity'].items():
                    if hasattr(config.nudity, key):
                        setattr(config.nudity, key, value)
            
            # Update whisper config
            if 'whisper' in data:
                for key, value in data['whisper'].items():
                    if hasattr(config.whisper, key):
                        setattr(config.whisper, key, value)
            
            # Update output config
            if 'output' in data:
                for key, value in data['output'].items():
                    if hasattr(config.output, key):
                        setattr(config.output, key, value)
            
            # Update logging config
            if 'logging' in data:
                for key, value in data['logging'].items():
                    if hasattr(config.logging, key):
                        setattr(config.logging, key, value)
            
            # Update notifications config
            if 'notifications' in data:
                for key, value in data['notifications'].items():
                    if hasattr(config.notifications, key):
                        setattr(config.notifications, key, value)
            
            # Update sexual_content config
            if 'sexual_content' in data:
                for key, value in data['sexual_content'].items():
                    if hasattr(config.sexual_content, key):
                        setattr(config.sexual_content, key, value)
            
            # Update content_lookup config
            if 'content_lookup' in data:
                for key, value in data['content_lookup'].items():
                        setattr(config.content_lookup, key, value)
            
            # Update system config
            if 'system' in data:
                for key, value in data['system'].items():
                    if hasattr(config.system, key):
                        setattr(config.system, key, value)
            
            # Update community config
            if 'community' in data:
                for key, value in data['community'].items():
                    if hasattr(config.community, key):
                        setattr(config.community, key, value)
        
        return config
    
    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        level = getattr(logging, self.logging.level.upper(), logging.INFO)
        
        handlers = [logging.StreamHandler()]
        if self.logging.log_file:
            handlers.append(logging.FileHandler(self.logging.log_file))
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file."""
        from dataclasses import asdict
        
        data = asdict(self)
        logger.info(f"Saving configuration to {config_path}")
        
        with open(config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
