"""
Unit tests for configuration loading.
"""

import pytest
import tempfile
from pathlib import Path

from video_censor.config import (
    Config,
    ProfanityConfig,
    NudityConfig,
    WhisperConfig,
    OutputConfig,
    LoggingConfig
)


class TestConfigDefaults:
    """Test default configuration values."""
    
    def test_default_profanity_config(self):
        """Test profanity config defaults."""
        config = ProfanityConfig()
        
        assert config.censor_mode == "beep"
        assert config.beep_frequency_hz == 1000
        assert config.beep_volume == 0.5
        assert config.buffer_before == 0.1
        assert config.buffer_after == 0.15
        assert config.merge_gap == 0.3
    
    def test_default_nudity_config(self):
        """Test nudity config defaults."""
        config = NudityConfig()
        
        assert config.threshold == 0.75  # Updated default
        assert config.frame_interval == 0.25
        assert config.min_segment_duration == 0.5
        assert config.buffer_before == 0.25
        assert config.buffer_after == 0.25
        assert config.merge_gap == 0.5
    
    def test_default_whisper_config(self):
        """Test whisper config defaults."""
        config = WhisperConfig()
        
        assert config.model_size == "base"
        assert config.language == "en"
        assert config.compute_type == "int8"
    
    def test_default_output_config(self):
        """Test output config defaults."""
        config = OutputConfig()
        
        assert config.default_pattern == "{input}_censored"
        assert config.video_codec == "libx264"
        assert config.video_crf == 23
        assert config.audio_codec == "aac"
        assert config.audio_bitrate == "192k"
    
    def test_default_logging_config(self):
        """Test logging config defaults."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.log_file == ""
        assert config.show_progress == True


class TestConfigLoad:
    """Test configuration loading from files."""
    
    def test_load_nonexistent_file(self):
        """Test loading from non-existent file returns defaults."""
        config = Config.load(Path("/nonexistent/config.yaml"))
        
        # Should have defaults
        assert config.profanity.censor_mode == "beep"
        assert config.nudity.threshold == 0.75  # Updated default
    
    def test_load_empty_file(self):
        """Test loading from empty file returns defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)
        
        try:
            config = Config.load(temp_path)
            assert config.profanity.censor_mode == "beep"
        finally:
            temp_path.unlink()
    
    def test_load_partial_config(self):
        """Test loading partial config merges with defaults."""
        yaml_content = """
profanity:
  censor_mode: mute
  beep_frequency_hz: 2000

nudity:
  threshold: 0.8
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)
        
        try:
            config = Config.load(temp_path)
            
            # Overridden values
            assert config.profanity.censor_mode == "mute"
            assert config.profanity.beep_frequency_hz == 2000
            assert config.nudity.threshold == 0.8
            
            # Default values preserved
            assert config.profanity.buffer_before == 0.1
            assert config.nudity.frame_interval == 0.25
            assert config.whisper.model_size == "base"
        finally:
            temp_path.unlink()
    
    def test_load_full_config(self):
        """Test loading complete configuration."""
        yaml_content = """
profanity:
  custom_wordlist_path: "/path/to/words.txt"
  censor_mode: mute
  beep_frequency_hz: 800
  beep_volume: 0.3
  buffer_before: 0.2
  buffer_after: 0.25
  merge_gap: 0.5

nudity:
  threshold: 0.7
  frame_interval: 0.5
  min_segment_duration: 1.0
  buffer_before: 0.5
  buffer_after: 0.5
  merge_gap: 1.0

whisper:
  model_size: small
  language: es
  compute_type: float16

output:
  default_pattern: "{input}_clean"
  video_codec: libx265
  video_crf: 20
  audio_codec: mp3
  audio_bitrate: 320k

logging:
  level: DEBUG
  log_file: "/var/log/censor.log"
  show_progress: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)
        
        try:
            config = Config.load(temp_path)
            
            # Profanity
            assert config.profanity.custom_wordlist_path == "/path/to/words.txt"
            assert config.profanity.censor_mode == "mute"
            assert config.profanity.beep_frequency_hz == 800
            
            # Nudity
            assert config.nudity.threshold == 0.7
            assert config.nudity.frame_interval == 0.5
            
            # Whisper
            assert config.whisper.model_size == "small"
            assert config.whisper.language == "es"
            
            # Output
            assert config.output.video_codec == "libx265"
            assert config.output.video_crf == 20
            
            # Logging
            assert config.logging.level == "DEBUG"
            assert config.logging.show_progress == False
        finally:
            temp_path.unlink()
    
    def test_load_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        yaml_content = """
profanity:
  censor_mode: beep
  unknown_key: some_value
  
unknown_section:
  key: value
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)
        
        try:
            config = Config.load(temp_path)
            
            # Known key should be loaded
            assert config.profanity.censor_mode == "beep"
            
            # Unknown key should not cause error and not be present
            assert not hasattr(config.profanity, 'unknown_key')
        finally:
            temp_path.unlink()


class TestConfigNoPath:
    """Test configuration with no path specified."""
    
    def test_load_no_path(self):
        """Test loading with None path returns defaults."""
        config = Config.load(None)
        
        assert config.profanity.censor_mode == "beep"
        assert config.nudity.threshold == 0.75  # Updated default
        assert config.whisper.model_size == "base"
