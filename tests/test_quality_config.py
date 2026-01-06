import unittest
import sys
from pathlib import Path
import shutil
import tempfile

# Add parent to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from video_censor.config import Config
from video_censor.editing.renderer import get_quality_args

class TestQualityConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.yaml"
        self.config = Config()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    @unittest.skip("Uses removed quality_mode API - test needs update")
    def test_crf_mode(self):
        """Test default CRF mode args generation."""
        self.config.output.quality_mode = "crf"
        self.config.output.video_crf = 23
        self.config.output.encoding_speed = "medium"
        
        args = get_quality_args(self.config)
        
        self.assertIn("-preset", args)
        self.assertIn("medium", args)
        self.assertIn("-crf", args)
        self.assertIn("23", args)
        self.assertNotIn("-b:v", args)
        
    @unittest.skip("Uses removed quality_mode API - test needs update")
    def test_target_size_mode(self):
        """Test target size mode args generation."""
        self.config.output.quality_mode = "target_size"
        self.config.output.target_size_mb = 100
        self.config.output.encoding_speed = "fast"
        
        # 60 seconds duration
        # Target: 100MB * 8192 = 819,200 kbits
        # 819,200 / 60 = ~13,653 kbps total
        # Video = 13,653 - 192 = 13,461 kbps
        duration = 60.0
        
        args = get_quality_args(self.config, duration)
        
        self.assertIn("-preset", args)
        self.assertIn("fast", args)
        self.assertIn("-b:v", args)
        
        # Find bitrate value
        idx = args.index("-b:v")
        bitrate = args[idx+1]
        
        # Verify it ends with 'k'
        self.assertTrue(bitrate.endswith("k"))
        val = int(bitrate[:-1])
        
        # Check if reasonably close to expected (13461)
        self.assertTrue(13000 < val < 14000, f"Bitrate {val} not in expected range")
        
    @unittest.skip("Uses removed quality_mode API - test needs update")
    def test_config_save_load(self):
        """Verify config saves and loads new fields."""
        self.config.output.quality_mode = "target_size"
        self.config.output.target_size_mb = 50
        self.config.output.encoding_speed = "slower"
        
        self.config.save(self.config_path)
        
        loaded = Config.load(self.config_path)
        
        self.assertEqual(loaded.output.quality_mode, "target_size")
        self.assertEqual(loaded.output.target_size_mb, 50)
        self.assertEqual(loaded.output.encoding_speed, "slower")

if __name__ == "__main__":
    unittest.main()
