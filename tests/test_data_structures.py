
import unittest
import json
from video_censor.editing.intervals import TimeInterval, Action, MatchSource
from video_censor.preferences import ContentFilterSettings, Profile

class TestDataStructures(unittest.TestCase):
    
    def test_time_interval_defaults(self):
        """Test TimeInterval default values."""
        interval = TimeInterval(start=1.0, end=2.0)
        self.assertEqual(interval.action, Action.CUT)
        self.assertEqual(interval.source, MatchSource.UNKNOWN)
        self.assertEqual(interval.metadata, {})
        
    def test_content_filter_settings_defaults(self):
        """Test ContentFilterSettings new fields defaults."""
        settings = ContentFilterSettings()
        self.assertEqual(settings.profanity_action, "mute")
        self.assertEqual(settings.nudity_action, "cut")
        self.assertEqual(settings.sexual_content_action, "cut")
        self.assertEqual(settings.violence_action, "cut")
        
    def test_settings_serialization(self):
        """Test JSON serialization of settings."""
        settings = ContentFilterSettings(
            profanity_action="beep",
            nudity_action="blur"
        )
        data = settings.to_dict()
        self.assertEqual(data["profanity_action"], "beep")
        self.assertEqual(data["nudity_action"], "blur")
        
        # Test deserialization
        new_settings = ContentFilterSettings.from_dict(data)
        self.assertEqual(new_settings.profanity_action, "beep")
        self.assertEqual(new_settings.nudity_action, "blur")
        
    def test_backward_compatibility(self):
        """Test loading old profile data (missing new fields)."""
        old_data = {
            "filter_language": True,
            "filter_sexual_content": False
        }
        settings = ContentFilterSettings.from_dict(old_data)
        # Should populate defaults
        self.assertEqual(settings.profanity_action, "mute")
        self.assertEqual(settings.nudity_action, "cut")
        
    def test_profile_copy(self):
        """Test deep copy of settings."""
        settings = ContentFilterSettings(profanity_action="beep")
        copy = settings.copy()
        self.assertEqual(copy.profanity_action, "beep")
        
        # Modify copy, original should be unchanged
        copy.profanity_action = "mute"
        self.assertEqual(settings.profanity_action, "beep")
        self.assertEqual(copy.profanity_action, "mute")

if __name__ == "__main__":
    unittest.main()
