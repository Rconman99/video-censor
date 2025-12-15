
import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QFrame

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.main_window import MainWindow, PreferencePanel
from ui.review_panel import ReviewPanel

class TestFullIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create app instance if not exists
        cls.app = QApplication.instance() or QApplication(sys.argv)
        
    def setUp(self):
        self.window = MainWindow()
        
    def test_preference_panel_structure(self):
        """Verify PreferencePanel has all new components."""
        panel = self.window.preference_panel
        self.assertIsInstance(panel, PreferencePanel)
        
        # Check for new widgets
        self.assertTrue(hasattr(panel, 'whisper_combo'), "Missing Whisper Combo")
        self.assertTrue(hasattr(panel, 'performance_combo'), "Missing Performance Combo")
        self.assertTrue(hasattr(panel, 'cb_notify_enabled'), "Missing Notification Checkbox")
        self.assertTrue(hasattr(panel, 'phrases_edit'), "Missing Phrases Editor")
        self.assertTrue(hasattr(panel, 'romance_slider'), "Missing Romance Slider")
        self.assertTrue(hasattr(panel, 'violence_slider'), "Missing Violence Slider")
        
        # Check if they are actually QWidgets not just None
        self.assertIsNotNone(panel.whisper_combo)
        self.assertIsNotNone(panel.performance_combo)

    def test_main_window_layout(self):
        """Verify main window has correct tabs and panels."""
        # Process Tab
        self.assertIsNotNone(self.window.drop_zone)
        self.assertIsNotNone(self.window.queue_panel)
        
        # Review Panel check
        self.assertTrue(hasattr(self.window, 'review_panel'))
        self.assertIsInstance(self.window.review_panel, ReviewPanel)
        
        # Search Tab check
        # Assuming search tab is added
        tabs = self.window.findChild(QFrame, "search_tab") # Or check via index if stored
        # Accessing private attribute for tab widget if needed, 
        # but let's just check if 'search_tab' module is imported and used in __init__
        self.assertTrue(hasattr(self.window, 'search_tab'))

    def test_no_legacy_artifacts(self):
        """Ensure no legacy attributes are lingering."""
        # e.g. 'root' was often used in Tkinter
        self.assertFalse(hasattr(self.window, 'root'), "Found legacy 'root' attribute")
        self.assertFalse(hasattr(self.window, 'frame'), "Found generic 'frame' attribute from legacy code")

    def test_start_button_logic(self):
        """Verify 'Start Filtering' button enables when video is set."""
        panel = self.window.preference_panel
        # Initially disabled
        self.assertFalse(panel.start_btn.isEnabled(), "Start button should be disabled initially")
        
        # Set video
        panel.set_video("/tmp/test_video.mp4")
        
        # Should be enabled
        self.assertTrue(panel.start_btn.isEnabled(), "Start button should be enabled after setting video")
        self.assertIn("test_video.mp4", panel.start_btn.text())
        
        # Check instance
        self.assertEqual(panel.current_video_path, "/tmp/test_video.mp4")

if __name__ == '__main__':
    unittest.main()
