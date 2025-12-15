"""
Tests for Phase 2 sexual content detection enhancements.

Tests the hybrid detector and multimodal fusion modules.
Semantic detection tests are skipped if sentence-transformers is not installed.
"""

import pytest
from video_censor.audio.transcriber import WordTimestamp
from video_censor.editing.intervals import TimeInterval
from video_censor.sexual_content import (
    # Phase 2: Hybrid
    HybridSexualContentDetector,
    HybridSegmentScore,
    detect_sexual_content_hybrid,
    # Phase 2: Semantic
    is_semantic_detection_available,
    get_semantic_detector,
    # Phase 2: Multimodal
    MultimodalFusion,
    FusedSegment,
    fuse_multimodal_detections,
    Modality,
)


class TestHybridDetector:
    """Test hybrid lexicon + semantic detection."""
    
    def test_hybrid_without_semantic(self):
        """Test hybrid detector with semantic disabled."""
        words = [
            WordTimestamp("watching", 0.0, 0.4),
            WordTimestamp("porn", 0.4, 0.8),
            WordTimestamp("videos", 0.8, 1.2),
        ]
        
        detector = HybridSexualContentDetector(use_semantic=False)
        result = detector.analyze_segment(words, 0, 3)
        
        assert isinstance(result, HybridSegmentScore)
        assert result.lexicon_score.active_match_count >= 1
        # Without semantic, should be skipped
        assert result.verification_status in ("skipped", "pending")
    
    def test_hybrid_detect_returns_intervals(self):
        """Test that hybrid detect returns TimeInterval list."""
        words = [
            WordTimestamp("explicit", 0.0, 0.4),
            WordTimestamp("pornography", 0.4, 1.0),
        ]
        
        detector = HybridSexualContentDetector(use_semantic=False)
        intervals = detector.detect(words)
        
        assert isinstance(intervals, list)
        assert len(intervals) >= 1
        assert all(isinstance(i, TimeInterval) for i in intervals)
    
    def test_hybrid_convenience_function(self):
        """Test detect_sexual_content_hybrid function."""
        words = [
            WordTimestamp("having", 0.0, 0.3),
            WordTimestamp("sex", 0.3, 0.6),
        ]
        
        intervals = detect_sexual_content_hybrid(
            words, 
            threshold=0.5, 
            use_semantic=False
        )
        
        assert len(intervals) >= 1
        assert intervals[0].metadata.get('verification_status') is not None
    
    def test_hybrid_innocent_content(self):
        """Test that innocent content is not flagged."""
        words = [
            WordTimestamp("the", 0.0, 0.2),
            WordTimestamp("weather", 0.2, 0.5),
            WordTimestamp("is", 0.5, 0.6),
            WordTimestamp("nice", 0.6, 0.9),
        ]
        
        detector = HybridSexualContentDetector(use_semantic=False)
        intervals = detector.detect(words)
        
        assert len(intervals) == 0


class TestMultimodalFusion:
    """Test multimodal audio + visual fusion."""
    
    def test_fusion_audio_only(self):
        """Test fusion with only audio detections."""
        audio_intervals = [
            TimeInterval(start=10.0, end=15.0, reason="sexual content", 
                        metadata={'confidence': 0.7}),
        ]
        visual_intervals = []
        
        fusion = MultimodalFusion()
        fused = fusion.fuse(audio_intervals, visual_intervals)
        
        assert len(fused) == 1
        assert fused[0].has_audio
        assert not fused[0].has_visual
        assert fused[0].agreement_level == "audio_only"
    
    def test_fusion_visual_only(self):
        """Test fusion with only visual detections."""
        audio_intervals = []
        visual_intervals = [
            TimeInterval(start=20.0, end=25.0, reason="nudity",
                        metadata={'confidence': 0.8}),
        ]
        
        fusion = MultimodalFusion()
        fused = fusion.fuse(audio_intervals, visual_intervals)
        
        assert len(fused) == 1
        assert not fused[0].has_audio
        assert fused[0].has_visual
        assert fused[0].agreement_level == "visual_only"
    
    def test_fusion_both_modalities_agree(self):
        """Test fusion when audio and visual overlap and agree."""
        # Overlapping intervals
        audio_intervals = [
            TimeInterval(start=10.0, end=15.0, reason="sexual dialog",
                        metadata={'confidence': 0.6}),
        ]
        visual_intervals = [
            TimeInterval(start=12.0, end=18.0, reason="nudity",
                        metadata={'confidence': 0.8}),
        ]
        
        fusion = MultimodalFusion()
        fused = fusion.fuse(audio_intervals, visual_intervals)
        
        assert len(fused) == 1
        assert fused[0].has_audio
        assert fused[0].has_visual
        assert fused[0].agreement_level == "both"
        # Should be boosted
        assert fused[0].fused_confidence > 0.6
    
    def test_fusion_non_overlapping(self):
        """Test fusion with non-overlapping detections."""
        audio_intervals = [
            TimeInterval(start=10.0, end=15.0, reason="sexual dialog",
                        metadata={'confidence': 0.6}),
        ]
        visual_intervals = [
            TimeInterval(start=50.0, end=55.0, reason="nudity",
                        metadata={'confidence': 0.8}),
        ]
        
        fusion = MultimodalFusion()
        fused = fusion.fuse(audio_intervals, visual_intervals)
        
        # Should have 2 separate segments
        assert len(fused) == 2
        audio_seg = next(s for s in fused if s.agreement_level == "audio_only")
        visual_seg = next(s for s in fused if s.agreement_level == "visual_only")
        assert audio_seg is not None
        assert visual_seg is not None
    
    def test_fusion_to_intervals(self):
        """Test converting fused segments to TimeIntervals."""
        audio_intervals = [
            TimeInterval(start=10.0, end=15.0, reason="sexual content",
                        metadata={'confidence': 0.7}),
        ]
        
        fusion = MultimodalFusion()
        fused = fusion.fuse(audio_intervals, [])
        intervals = fusion.to_intervals(fused, min_confidence=0.2)
        
        assert len(intervals) >= 1
        assert intervals[0].metadata.get('modality') == 'audio'
    
    def test_convenience_function(self):
        """Test fuse_multimodal_detections convenience function."""
        audio_intervals = [
            TimeInterval(start=10.0, end=15.0, reason="sexual",
                        metadata={'confidence': 0.7}),
        ]
        visual_intervals = [
            TimeInterval(start=12.0, end=18.0, reason="nudity",
                        metadata={'confidence': 0.8}),
        ]
        
        result = fuse_multimodal_detections(
            audio_intervals, 
            visual_intervals,
            min_confidence=0.3
        )
        
        assert isinstance(result, list)
        assert len(result) >= 1


class TestFusedSegment:
    """Test FusedSegment properties."""
    
    def test_modality_detection(self):
        """Test that modality is correctly detected."""
        from video_censor.sexual_content.multimodal_fusion import ModalityScore
        
        audio_score = ModalityScore(
            modality=Modality.AUDIO, 
            start=0, end=5, 
            score=0.7
        )
        visual_score = ModalityScore(
            modality=Modality.VISUAL,
            start=0, end=5,
            score=0.8
        )
        
        # Audio only
        seg = FusedSegment(start=0, end=5, audio_score=audio_score)
        assert seg.modality == Modality.AUDIO
        
        # Visual only
        seg = FusedSegment(start=0, end=5, visual_score=visual_score)
        assert seg.modality == Modality.VISUAL
        
        # Both
        seg = FusedSegment(start=0, end=5, audio_score=audio_score, visual_score=visual_score)
        assert seg.modality == Modality.MULTIMODAL


@pytest.mark.skipif(
    not is_semantic_detection_available(),
    reason="sentence-transformers not installed"
)
class TestSemanticDetection:
    """Test semantic detection (only if sentence-transformers is installed)."""
    
    def test_semantic_detector_initialization(self):
        """Test that semantic detector initializes correctly."""
        detector = get_semantic_detector()
        assert detector is not None
    
    def test_analyze_explicit_content(self):
        """Test semantic analysis of explicit content."""
        detector = get_semantic_detector()
        result = detector.analyze("they were watching porn together")
        
        assert result.sexual_score > 0.5
        assert result.is_sexual
    
    def test_analyze_innocent_content(self):
        """Test semantic analysis of innocent content."""
        detector = get_semantic_detector()
        result = detector.analyze("the doctor examined the patient")
        
        # Should have higher safe score
        assert result.safe_score > 0.3


class TestSemanticAvailability:
    """Test semantic detection availability checks."""
    
    def test_availability_check(self):
        """Test that availability check returns boolean."""
        result = is_semantic_detection_available()
        assert isinstance(result, bool)
    
    def test_get_detector_returns_none_when_unavailable(self):
        """Test graceful handling when semantic is unavailable."""
        if is_semantic_detection_available():
            pytest.skip("sentence-transformers is installed")
        
        detector = get_semantic_detector()
        assert detector is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
