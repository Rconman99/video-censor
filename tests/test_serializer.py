"""
Tests for Detection Serializer.
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path

from video_censor.editing.intervals import TimeInterval, Action, MatchSource
from video_censor.detection.serializer import (
    DetectionSerializer, 
    serialize_interval, deserialize_interval, save_detections, load_detections
)

class TestSerializer(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_interval_roundtrip(self):
        """Test serialize -> deserialize roundtrip for single interval."""
        original = TimeInterval(
            start=10.5,
            end=15.2,
            reason="bad word",
            action=Action.MUTE,
            source=MatchSource.AUDIO,
            metadata={'confidence': 0.95, 'word': 'test'}
        )
        
        serialized = DetectionSerializer.serialize_interval(original)
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized['start'], 10.5)
        self.assertEqual(serialized['action'], "mute")
        
        restored = DetectionSerializer.deserialize_interval(serialized)
        self.assertEqual(restored.start, original.start)
        self.assertEqual(restored.end, original.end)
        self.assertEqual(restored.reason, original.reason)
        self.assertEqual(restored.action, original.action)
        self.assertEqual(restored.source, original.source)
        self.assertEqual(restored.metadata, original.metadata)
        
    def test_save_load_class(self):
        """Test new class-based save and load with metadata."""
        video_path = self.temp_path / "video.mp4"
        video_path.touch()
        # Write some data to simulate hash
        with open(video_path, 'wb') as f:
            f.write(b"data" * 1000)
            
        intervals = [
            TimeInterval(start=1.0, end=2.0, reason="1"),
            TimeInterval(start=3.0, end=4.0, reason="2")
        ]
        
        # Test Save
        output_path = DetectionSerializer.save(video_path, intervals)
        self.assertTrue(Path(output_path).exists())
        
        # Verify file content
        with open(output_path, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['version'], "1.0")
            self.assertEqual(data['detection_count'], 2)
            self.assertIn('video_hash', data)
            
        # Test Load
        loaded_intervals, metadata = DetectionSerializer.load(output_path, video_path)
        self.assertEqual(len(loaded_intervals), 2)
        self.assertEqual(metadata['version'], "1.0")
        self.assertEqual(metadata['detection_count'], 2)
        
    def test_legacy_aliases(self):
        """Test backward compatibility aliases."""
        path = self.temp_path / "detections_legacy.json"
        intervals = [TimeInterval(start=1.0, end=2.0)]
        
        # Alias save
        save_detections(path, intervals)
        self.assertTrue(path.exists())
        
        # Alias load
        loaded = load_detections(path)
        self.assertIsInstance(loaded, list)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].start, 1.0)
        
    def test_video_hash_mismatch(self):
        """Test loading with mismatched video."""
        video_path_1 = self.temp_path / "v1.mp4"
        video_path_1.write_bytes(b"video1")
        
        video_path_2 = self.temp_path / "v2.mp4"
        video_path_2.write_bytes(b"video2")
        
        intervals = [TimeInterval(start=0, end=1)]
        output_path = DetectionSerializer.save(video_path_1, intervals)
        
        # Load with different video - should log warning but succeed
        loaded, meta = DetectionSerializer.load(output_path, video_path_2)
        self.assertEqual(len(loaded), 1)

if __name__ == '__main__':
    unittest.main()
