"""Tests for video_censor.detection.confidence_merger module."""

import pytest
from dataclasses import dataclass
from typing import Optional

from video_censor.detection.confidence_merger import (
    DetectionSignal,
    MergedDetection,
    ConfidenceConfig,
    ConfidenceMerger,
    create_merger_from_config,
)


# ---------------------------------------------------------------------------
# 1. Default ConfidenceConfig values
# ---------------------------------------------------------------------------

class TestConfidenceConfig:
    def test_default_values(self):
        cfg = ConfidenceConfig()
        assert cfg.profanity_weight == 0.4
        assert cfg.nudity_weight == 0.4
        assert cfg.sexual_content_weight == 0.3
        assert cfg.llm_context_weight == 0.2
        assert cfg.single_signal_threshold == 0.9
        assert cfg.multi_signal_threshold == 0.6
        assert cfg.agreement_boost == 0.3
        assert cfg.require_multi_signal is False


# ---------------------------------------------------------------------------
# 2-7. should_censor tests
# ---------------------------------------------------------------------------

class TestShouldCensor:
    def setup_method(self):
        self.merger = ConfidenceMerger()

    # 2. No signals -> no censor
    def test_no_signals(self):
        censor, score, reason = self.merger.should_censor({})
        assert censor is False
        assert score == 0.0

    # 3. Single profanity signal below threshold (0.4*1.0 = 0.4 < 0.9)
    def test_single_profanity_below_threshold(self):
        signals = {"profanity_detected": True, "profanity_confidence": 1.0}
        censor, score, reason = self.merger.should_censor(signals)
        assert censor is False
        assert score == pytest.approx(0.4)

    # 4. High profanity alone still doesn't reach 0.9
    def test_high_profanity_alone_below_single_threshold(self):
        """Even with max profanity confidence, 0.4*1.0=0.4 < 0.9."""
        signals = {"profanity_detected": True, "profanity_confidence": 1.0}
        censor, score, _ = self.merger.should_censor(signals)
        assert censor is False
        assert score < 0.9

    # 5. Two signals with agreement boost crosses multi threshold
    def test_two_signals_agreement_boost(self):
        """profanity(0.4*1.0) + nudity(0.4*0.8) + boost(0.3) = 1.02 >= 0.6."""
        signals = {
            "profanity_detected": True,
            "profanity_confidence": 1.0,
            "nudity_score": 0.8,
        }
        censor, score, reason = self.merger.should_censor(signals)
        expected = 0.4 * 1.0 + 0.4 * 0.8 + 0.3  # 1.02
        assert score == pytest.approx(expected)
        assert censor is True
        assert "multi_signal_boost" in reason

    # 6. Nudity score <= 0.5 is ignored
    def test_nudity_at_threshold_ignored(self):
        signals = {"nudity_score": 0.5}
        censor, score, _ = self.merger.should_censor(signals)
        assert score == 0.0
        assert censor is False

    def test_nudity_just_above_threshold(self):
        signals = {"nudity_score": 0.51}
        censor, score, _ = self.merger.should_censor(signals)
        assert score == pytest.approx(0.4 * 0.51)
        assert censor is False  # still below 0.9 single threshold

    # 7. require_multi_signal mode rejects single signals
    def test_require_multi_signal_rejects_single(self):
        cfg = ConfidenceConfig(require_multi_signal=True)
        merger = ConfidenceMerger(cfg)
        signals = {"profanity_detected": True, "profanity_confidence": 1.0}
        censor, score, reason = merger.should_censor(signals)
        assert censor is False
        assert "Multi-signal required" in reason

    def test_require_multi_signal_allows_two_signals(self):
        cfg = ConfidenceConfig(require_multi_signal=True)
        merger = ConfidenceMerger(cfg)
        signals = {
            "profanity_detected": True,
            "profanity_confidence": 1.0,
            "nudity_score": 0.8,
        }
        censor, score, _ = merger.should_censor(signals)
        assert censor is True

    def test_sexual_content_detected_adds_score(self):
        signals = {"sexual_content_detected": True, "sexual_content_confidence": 0.9}
        censor, score, reason = self.merger.should_censor(signals)
        assert score == pytest.approx(0.3 * 0.9)
        assert "sexual" in reason

    def test_explicit_dialog_adds_score(self):
        signals = {"explicit_dialog": True}
        censor, score, _ = self.merger.should_censor(signals)
        # Default confidence when not provided is 0.8
        assert score == pytest.approx(0.3 * 0.8)

    def test_llm_context_confirmed_adds_weight(self):
        signals = {"context_confirmed": True}
        censor, score, reason = self.merger.should_censor(signals)
        assert score == pytest.approx(0.2)
        assert "context_confirmed" in reason

    def test_profanity_default_confidence(self):
        """When profanity_confidence not provided, defaults to 1.0."""
        signals = {"profanity_detected": True}
        _, score, _ = self.merger.should_censor(signals)
        assert score == pytest.approx(0.4 * 1.0)

    def test_all_signals_combined(self):
        signals = {
            "profanity_detected": True,
            "profanity_confidence": 0.9,
            "nudity_score": 0.7,
            "sexual_content_detected": True,
            "sexual_content_confidence": 0.8,
            "context_confirmed": True,
        }
        censor, score, reason = self.merger.should_censor(signals)
        # profanity: 0.4*0.9 + nudity: 0.4*0.7 + sexual: 0.3*0.8 + llm: 0.2 + boost: 0.3
        # 3 signal types active (profanity, nudity, sexual)
        expected = 0.4 * 0.9 + 0.4 * 0.7 + 0.3 * 0.8 + 0.2 + 0.3
        assert score == pytest.approx(expected)
        assert censor is True


# ---------------------------------------------------------------------------
# 8-11. merge_overlapping tests
# ---------------------------------------------------------------------------

class TestMergeOverlapping:
    def setup_method(self):
        self.merger = ConfidenceMerger()

    # 8. Empty list
    def test_empty_list(self):
        result = self.merger.merge_overlapping([])
        assert result == []

    # 9. Overlapping signals grouped together
    def test_overlapping_signals_grouped(self):
        signals = [
            DetectionSignal("profanity", 1.0, 2.0, confidence=1.0),
            DetectionSignal("nudity", 1.5, 3.0, confidence=0.8),
        ]
        result = self.merger.merge_overlapping(signals)
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 3.0
        assert len(result[0].signals) == 2

    # 10. Respects time_tolerance
    def test_time_tolerance_groups_gap(self):
        """Signals with a gap <= time_tolerance should be grouped."""
        signals = [
            DetectionSignal("profanity", 1.0, 2.0, confidence=1.0),
            DetectionSignal("nudity", 2.4, 3.0, confidence=0.8),
        ]
        # Gap of 0.4 <= default tolerance 0.5
        result = self.merger.merge_overlapping(signals, time_tolerance=0.5)
        assert len(result) == 1

    def test_time_tolerance_separates_large_gap(self):
        """Signals with a gap > time_tolerance should be separate."""
        signals = [
            DetectionSignal("profanity", 1.0, 2.0, confidence=1.0),
            DetectionSignal("nudity", 3.0, 4.0, confidence=0.8),
        ]
        # Gap of 1.0 > default tolerance 0.5
        result = self.merger.merge_overlapping(signals, time_tolerance=0.5)
        assert len(result) == 2

    # 11. Non-overlapping produce separate groups
    def test_non_overlapping_separate_groups(self):
        signals = [
            DetectionSignal("profanity", 1.0, 2.0, confidence=1.0),
            DetectionSignal("profanity", 5.0, 6.0, confidence=0.9),
            DetectionSignal("profanity", 10.0, 11.0, confidence=0.8),
        ]
        result = self.merger.merge_overlapping(signals)
        assert len(result) == 3
        assert result[0].start == 1.0
        assert result[1].start == 5.0
        assert result[2].start == 10.0

    def test_unsorted_signals_sorted_before_merge(self):
        signals = [
            DetectionSignal("profanity", 5.0, 6.0, confidence=1.0),
            DetectionSignal("nudity", 1.0, 2.0, confidence=0.8),
        ]
        result = self.merger.merge_overlapping(signals)
        assert len(result) == 2
        assert result[0].start == 1.0
        assert result[1].start == 5.0


# ---------------------------------------------------------------------------
# 12. _finalize_group maps detector types correctly
# ---------------------------------------------------------------------------

class TestFinalizeGroup:
    def test_maps_detector_types(self):
        merger = ConfidenceMerger()
        group = [
            DetectionSignal("profanity", 1.0, 2.0, confidence=0.95),
            DetectionSignal("nudity", 1.2, 2.5, confidence=0.8),
            DetectionSignal("sexual_content", 1.0, 2.0, confidence=0.7),
            DetectionSignal("llm_context", 1.0, 2.0, confidence=0.9),
        ]
        result = merger._finalize_group(group)
        assert result.start == 1.0
        assert result.end == 2.5
        assert result.should_censor is True
        assert len(result.signals) == 4
        assert result.confidence <= 1.0

    def test_finalize_empty_group_raises(self):
        merger = ConfidenceMerger()
        with pytest.raises(ValueError, match="Cannot finalize empty group"):
            merger._finalize_group([])

    def test_llm_context_low_confidence_not_confirmed(self):
        """llm_context with confidence <= 0.5 should not set context_confirmed."""
        merger = ConfidenceMerger()
        group = [
            DetectionSignal("llm_context", 1.0, 2.0, confidence=0.3),
        ]
        result = merger._finalize_group(group)
        # context_confirmed should be False, so no llm score added
        assert result.total_score == 0.0


# ---------------------------------------------------------------------------
# 13-14. create_merger_from_config
# ---------------------------------------------------------------------------

class TestCreateMergerFromConfig:
    # 13. With sexual_content config
    def test_with_sexual_content_config(self):
        @dataclass
        class SexualContentConfig:
            visual_weight: float = 0.7
            audio_weight: float = 0.5
            agreement_boost: float = 0.4
            use_multimodal_fusion: bool = True

        @dataclass
        class MockConfig:
            sexual_content: SexualContentConfig = None

            def __post_init__(self):
                self.sexual_content = SexualContentConfig()

        config = MockConfig()
        merger = create_merger_from_config(config)
        assert merger.config.nudity_weight == 0.7
        assert merger.config.profanity_weight == 0.5
        assert merger.config.agreement_boost == 0.4
        assert merger.config.require_multi_signal is True

    # 14. Without sexual_content config
    def test_without_sexual_content_config(self):
        @dataclass
        class MockConfig:
            pass

        config = MockConfig()
        merger = create_merger_from_config(config)
        # Should use defaults
        assert merger.config.profanity_weight == 0.4
        assert merger.config.nudity_weight == 0.4
        assert merger.config.agreement_boost == 0.3
        assert merger.config.require_multi_signal is False
