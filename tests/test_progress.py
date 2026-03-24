"""
Tests for the progress tracking modules:
  - video_censor.progress.stages
  - video_censor.progress.time_estimator
  - video_censor.progress.reporter
"""

import pytest
from unittest.mock import patch, MagicMock

from video_censor.progress.stages import ProcessingStage, StageInfo, STAGE_INFO, get_stage_label, get_overall_progress
from video_censor.progress.time_estimator import TimeEstimator
from video_censor.progress.reporter import ProgressReporter


# ── ProcessingStage enum ─────────────────────────────────────────────────────

class TestProcessingStage:
    def test_all_enum_values_exist(self):
        expected = [
            "INITIALIZING", "EXTRACTING_AUDIO", "ANALYZING_AUDIO",
            "ANALYZING_VIDEO", "MERGING_DETECTIONS", "REVIEWING",
            "RENDERING", "FINALIZING", "COMPLETE", "ERROR",
        ]
        actual = [s.name for s in ProcessingStage]
        assert actual == expected

    def test_enum_string_values(self):
        assert ProcessingStage.INITIALIZING.value == "initializing"
        assert ProcessingStage.COMPLETE.value == "complete"
        assert ProcessingStage.ERROR.value == "error"


# ── STAGE_INFO ────────────────────────────────────────────────────────────────

class TestStageInfo:
    def test_all_stages_have_info(self):
        for stage in ProcessingStage:
            assert stage in STAGE_INFO, f"Missing STAGE_INFO entry for {stage}"

    def test_weights_sum_close_to_one(self):
        total = sum(info.weight for info in STAGE_INFO.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_reviewing_has_zero_weight(self):
        assert STAGE_INFO[ProcessingStage.REVIEWING].weight == 0

    def test_stage_info_is_dataclass(self):
        info = STAGE_INFO[ProcessingStage.INITIALIZING]
        assert isinstance(info, StageInfo)
        assert isinstance(info.label, str)
        assert isinstance(info.icon, str)
        assert isinstance(info.weight, float)


# ── get_stage_label ───────────────────────────────────────────────────────────

class TestGetStageLabel:
    def test_label_without_detail(self):
        result = get_stage_label(ProcessingStage.INITIALIZING)
        info = STAGE_INFO[ProcessingStage.INITIALIZING]
        assert result == f"{info.icon} {info.label}"

    def test_label_with_detail(self):
        result = get_stage_label(ProcessingStage.ANALYZING_AUDIO, detail="50%")
        info = STAGE_INFO[ProcessingStage.ANALYZING_AUDIO]
        assert result == f"{info.icon} {info.label} (50%)"

    def test_label_detail_none_is_same_as_no_detail(self):
        assert get_stage_label(ProcessingStage.COMPLETE, detail=None) == get_stage_label(ProcessingStage.COMPLETE)


# ── get_overall_progress ─────────────────────────────────────────────────────

class TestGetOverallProgress:
    def test_initializing_at_zero(self):
        assert get_overall_progress(ProcessingStage.INITIALIZING, 0) == 0.0

    def test_complete_is_100(self):
        result = get_overall_progress(ProcessingStage.COMPLETE, 100)
        assert result == 100.0

    def test_mid_stage_calculation(self):
        # At ANALYZING_AUDIO, 50% done
        # prior stages: INITIALIZING(0.02) + EXTRACTING_AUDIO(0.05) = 0.07
        # current: 0.35 * 0.5 = 0.175
        # total: 0.245 * 100 = 24.5
        result = get_overall_progress(ProcessingStage.ANALYZING_AUDIO, 50)
        assert result == pytest.approx(24.5, abs=0.1)

    def test_stage_fully_complete_equals_next_stage_start(self):
        # Completing EXTRACTING_AUDIO at 100% should equal starting ANALYZING_AUDIO at 0%
        end_of_extract = get_overall_progress(ProcessingStage.EXTRACTING_AUDIO, 100)
        start_of_analyze = get_overall_progress(ProcessingStage.ANALYZING_AUDIO, 0)
        assert end_of_extract == pytest.approx(start_of_analyze, abs=0.01)

    def test_reviewing_not_in_stages_order(self):
        # REVIEWING is not in stages_order, so the loop never breaks on it
        # and sums all weights, resulting in 100 (capped).
        result = get_overall_progress(ProcessingStage.REVIEWING, 50)
        assert result == 100.0

    def test_progress_never_exceeds_100(self):
        result = get_overall_progress(ProcessingStage.COMPLETE, 200)
        assert result <= 100.0


# ── TimeEstimator.format_time ─────────────────────────────────────────────────

class TestFormatTime:
    def test_none_returns_calculating(self):
        assert TimeEstimator.format_time(None) == "Calculating..."

    def test_negative_returns_calculating(self):
        assert TimeEstimator.format_time(-5) == "Calculating..."

    def test_seconds_range(self):
        assert TimeEstimator.format_time(45) == "~45s remaining"

    def test_zero_seconds(self):
        assert TimeEstimator.format_time(0) == "~0s remaining"

    def test_minutes_range(self):
        assert TimeEstimator.format_time(120) == "~2m remaining"

    def test_hours_range(self):
        assert TimeEstimator.format_time(3661) == "~1h 1m remaining"

    def test_exact_hour(self):
        assert TimeEstimator.format_time(3600) == "~1h 0m remaining"


# ── TimeEstimator core ────────────────────────────────────────────────────────

class TestTimeEstimator:
    @patch("video_censor.progress.time_estimator.time.time")
    def test_needs_three_samples(self, mock_time):
        est = TimeEstimator()
        mock_time.return_value = 0.0
        est.start()

        # Sample 1
        mock_time.return_value = 1.0
        assert est.update(10) is None

        # Sample 2
        mock_time.return_value = 2.0
        assert est.update(20) is None

        # Sample 3 — now should return an estimate
        mock_time.return_value = 3.0
        result = est.update(30)
        assert result is not None
        assert isinstance(result, int)

    @patch("video_censor.progress.time_estimator.time.time")
    def test_returns_none_if_progress_not_increasing(self, mock_time):
        est = TimeEstimator()
        mock_time.return_value = 0.0
        est.start()

        mock_time.return_value = 1.0
        est.update(10)

        # Same progress
        mock_time.return_value = 2.0
        assert est.update(10) is None

        # Lower progress
        mock_time.return_value = 3.0
        assert est.update(5) is None

    @patch("video_censor.progress.time_estimator.time.time")
    def test_get_elapsed(self, mock_time):
        est = TimeEstimator()
        assert est.get_elapsed() == 0  # not started

        mock_time.return_value = 100.0
        est.start()

        mock_time.return_value = 110.0
        assert est.get_elapsed() == 10

    @patch("video_censor.progress.time_estimator.time.time")
    def test_estimate_is_reasonable(self, mock_time):
        est = TimeEstimator()
        mock_time.return_value = 0.0
        est.start()

        # Constant rate: 10 progress per second
        for i in range(1, 6):
            mock_time.return_value = float(i)
            result = est.update(i * 10)

        # At progress=50, rate=10/s, remaining=50 -> 5 seconds
        assert result == 5


# ── ProgressReporter ──────────────────────────────────────────────────────────

class TestProgressReporter:
    def test_callback_invoked_on_start(self):
        reporter = ProgressReporter()
        cb = MagicMock()
        reporter.add_callback(cb)

        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()

        assert cb.called
        args = cb.call_args[0]
        assert len(args) == 3  # overall_percent, stage_label, time_str

    def test_remove_callback(self):
        reporter = ProgressReporter()
        cb = MagicMock()
        reporter.add_callback(cb)
        reporter.remove_callback(cb)

        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()

        assert not cb.called

    def test_set_stage_transitions(self):
        reporter = ProgressReporter()
        cb = MagicMock()
        reporter.add_callback(cb)

        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()
            reporter.set_stage(ProcessingStage.ANALYZING_AUDIO, "model loaded")

        assert reporter.stage == ProcessingStage.ANALYZING_AUDIO
        assert reporter.stage_progress == 0
        assert reporter.detail == "model loaded"

    def test_update_clamps_progress(self):
        reporter = ProgressReporter()
        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()
            reporter.update(150)
        assert reporter.stage_progress == 100

        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.update(-10)
        assert reporter.stage_progress == 0

    def test_increment(self):
        reporter = ProgressReporter()
        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()
            reporter.update(10)
            reporter.increment(5)
        assert reporter.stage_progress == 15

    def test_complete_sets_stage_and_progress(self):
        reporter = ProgressReporter()
        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()
            reporter.complete()

        assert reporter.stage == ProcessingStage.COMPLETE
        assert reporter.stage_progress == 100

    def test_error_sets_stage_and_detail(self):
        reporter = ProgressReporter()
        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()
            reporter.error("something broke")

        assert reporter.stage == ProcessingStage.ERROR
        assert reporter.detail == "something broke"

    def test_get_current_state_returns_tuple(self):
        reporter = ProgressReporter()
        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            reporter.start()

        state = reporter.get_current_state()
        assert isinstance(state, tuple)
        assert len(state) == 3
        overall, label, time_str = state
        assert isinstance(overall, float)
        assert isinstance(label, str)
        assert isinstance(time_str, str)

    def test_callback_exception_does_not_propagate(self):
        reporter = ProgressReporter()

        def bad_callback(overall, label, time_str):
            raise RuntimeError("boom")

        reporter.add_callback(bad_callback)

        with patch("video_censor.progress.time_estimator.time.time", return_value=0.0):
            # Should not raise
            reporter.start()
            reporter.update(50)
            reporter.complete()
