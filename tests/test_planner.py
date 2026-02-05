"""
Tests for video_censor/editing/planner.py

Tests edit planning, interval merging, audio edit creation,
cut adjustment for timestamps, and the EditPlan dataclass properties.
"""

import pytest

from video_censor.editing.intervals import TimeInterval
from video_censor.editing.planner import (
    AudioEdit,
    EditPlan,
    plan_edits,
    adjust_edits_for_cuts,
)


# ---------------------------------------------------------------------------
# AudioEdit
# ---------------------------------------------------------------------------

class TestAudioEdit:
    def test_duration(self):
        edit = AudioEdit(start=1.0, end=3.5, edit_type="mute")
        assert edit.duration == 2.5

    def test_zero_duration(self):
        edit = AudioEdit(start=5.0, end=5.0, edit_type="beep")
        assert edit.duration == 0.0


# ---------------------------------------------------------------------------
# EditPlan properties
# ---------------------------------------------------------------------------

class TestEditPlanProperties:
    def test_output_duration(self):
        plan = EditPlan(
            original_duration=60.0,
            keep_segments=[
                TimeInterval(0, 10),
                TimeInterval(20, 40),
            ],
        )
        assert plan.output_duration == 30.0

    def test_cut_duration(self):
        plan = EditPlan(
            original_duration=60.0,
            cut_intervals=[
                TimeInterval(10, 20),
                TimeInterval(40, 50),
            ],
        )
        assert plan.cut_duration == 20.0

    def test_counts(self):
        plan = EditPlan(
            original_duration=60.0,
            profanity_intervals=[TimeInterval(1, 2), TimeInterval(5, 6)],
            nudity_intervals=[TimeInterval(10, 15)],
            sexual_content_intervals=[TimeInterval(20, 25), TimeInterval(30, 35)],
            violence_intervals=[],
        )
        assert plan.profanity_count == 2
        assert plan.nudity_count == 1
        assert plan.sexual_content_count == 2
        assert plan.violence_count == 0

    def test_empty_plan(self):
        plan = EditPlan(original_duration=60.0)
        assert plan.output_duration == 0.0
        assert plan.cut_duration == 0.0
        assert plan.profanity_count == 0

    def test_summary_contains_key_info(self):
        plan = EditPlan(
            original_duration=60.0,
            keep_segments=[TimeInterval(0, 50)],
            cut_intervals=[TimeInterval(50, 60)],
            audio_edits=[AudioEdit(1.0, 2.0, "beep")],
            profanity_intervals=[TimeInterval(1, 2)],
            nudity_intervals=[TimeInterval(50, 60)],
        )
        summary = plan.summary()
        assert "60.00" in summary
        assert "50.00" in summary  # output duration
        assert "10.00" in summary  # cut duration
        assert "1" in summary  # profanity count


# ---------------------------------------------------------------------------
# plan_edits
# ---------------------------------------------------------------------------

class TestPlanEdits:
    def test_profanity_only(self):
        """Profanity alone → audio edits, no cuts."""
        profanity = [TimeInterval(5.0, 5.5, reason="damn")]
        plan = plan_edits(
            profanity_intervals=profanity,
            nudity_intervals=[],
            duration=60.0,
        )
        assert len(plan.cut_intervals) == 0
        assert len(plan.audio_edits) == 1
        assert plan.audio_edits[0].edit_type == "beep"  # default
        assert plan.audio_edits[0].start == 5.0

    def test_nudity_only(self):
        """Nudity alone → cuts, no audio edits."""
        nudity = [TimeInterval(10.0, 15.0, reason="nudity")]
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=nudity,
            duration=60.0,
        )
        assert len(plan.cut_intervals) == 1
        assert len(plan.audio_edits) == 0
        assert plan.cut_intervals[0].start == 10.0

    def test_profanity_and_nudity(self):
        """Profanity in kept portion → audio edit. Profanity in cut portion → discarded."""
        profanity = [
            TimeInterval(5.0, 5.5, reason="damn"),    # in kept portion
            TimeInterval(12.0, 12.5, reason="fuck"),   # in cut portion
        ]
        nudity = [TimeInterval(10.0, 15.0, reason="nudity")]
        plan = plan_edits(
            profanity_intervals=profanity,
            nudity_intervals=nudity,
            duration=60.0,
        )
        assert len(plan.cut_intervals) == 1
        # Only the profanity in the kept portion should have an audio edit
        assert len(plan.audio_edits) == 1
        assert plan.audio_edits[0].start == 5.0

    def test_mute_mode(self):
        profanity = [TimeInterval(5.0, 5.5, reason="damn")]
        plan = plan_edits(
            profanity_intervals=profanity,
            nudity_intervals=[],
            duration=60.0,
            censor_mode="mute",
        )
        assert plan.audio_edits[0].edit_type == "mute"

    def test_micro_cuts_filtered(self):
        """Cuts shorter than min_cut_duration should be filtered out."""
        nudity = [TimeInterval(10.0, 10.1, reason="nudity")]  # 0.1s
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=nudity,
            duration=60.0,
            min_cut_duration=0.3,
        )
        assert len(plan.cut_intervals) == 0

    def test_nearby_nudity_intervals_merged(self):
        nudity = [
            TimeInterval(10.0, 12.0),
            TimeInterval(12.3, 14.0),  # gap of 0.3s < default 0.5s merge gap
        ]
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=nudity,
            duration=60.0,
        )
        assert len(plan.cut_intervals) == 1
        assert plan.cut_intervals[0].start == 10.0
        assert plan.cut_intervals[0].end == 14.0

    def test_sexual_content_intervals(self):
        sexual = [TimeInterval(20.0, 25.0, reason="sexual dialog")]
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=[],
            duration=60.0,
            sexual_content_intervals=sexual,
        )
        assert len(plan.cut_intervals) == 1
        assert plan.sexual_content_count == 1

    def test_violence_intervals(self):
        violence = [TimeInterval(30.0, 35.0, reason="violence")]
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=[],
            duration=60.0,
            violence_intervals=violence,
        )
        assert len(plan.cut_intervals) == 1
        assert plan.violence_count == 1

    def test_combined_cuts_merged(self):
        """Nudity + sexual content near each other → merged into single cut."""
        nudity = [TimeInterval(10.0, 15.0)]
        sexual = [TimeInterval(15.3, 20.0)]  # gap 0.3s < merge threshold 0.5s
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=nudity,
            duration=60.0,
            sexual_content_intervals=sexual,
        )
        assert len(plan.cut_intervals) == 1

    def test_keep_segments_are_inverse_of_cuts(self):
        nudity = [TimeInterval(10.0, 20.0)]
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=nudity,
            duration=60.0,
        )
        # Should have 2 keep segments: [0, 10] and [20, 60]
        assert len(plan.keep_segments) == 2
        assert plan.keep_segments[0].start == 0.0
        assert plan.keep_segments[0].end == 10.0
        assert plan.keep_segments[1].start == 20.0
        assert plan.keep_segments[1].end == 60.0

    def test_no_detections_keeps_full_video(self):
        plan = plan_edits(
            profanity_intervals=[],
            nudity_intervals=[],
            duration=60.0,
        )
        assert len(plan.cut_intervals) == 0
        assert len(plan.keep_segments) == 1
        assert plan.keep_segments[0].start == 0.0
        assert plan.keep_segments[0].end == 60.0
        assert plan.output_duration == 60.0

    def test_preserves_raw_detection_lists(self):
        profanity = [TimeInterval(1, 2)]
        nudity = [TimeInterval(10, 15)]
        sexual = [TimeInterval(20, 25)]
        violence = [TimeInterval(30, 35)]
        plan = plan_edits(
            profanity_intervals=profanity,
            nudity_intervals=nudity,
            duration=60.0,
            sexual_content_intervals=sexual,
            violence_intervals=violence,
        )
        assert plan.profanity_intervals is profanity
        assert plan.nudity_intervals is nudity
        assert plan.sexual_content_intervals is sexual
        assert plan.violence_intervals is violence


# ---------------------------------------------------------------------------
# adjust_edits_for_cuts
# ---------------------------------------------------------------------------

class TestAdjustEditsForCuts:
    def test_no_cuts_returns_copy(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[AudioEdit(5.0, 6.0, "beep")],
            cut_intervals=[],
        )
        adjusted = adjust_edits_for_cuts(plan)
        assert len(adjusted) == 1
        assert adjusted[0].start == 5.0

    def test_cut_before_edit_shifts_timestamps(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[AudioEdit(20.0, 21.0, "beep", "damn")],
            cut_intervals=[TimeInterval(5.0, 10.0)],  # 5s cut before
        )
        adjusted = adjust_edits_for_cuts(plan)
        assert len(adjusted) == 1
        assert adjusted[0].start == 15.0  # 20.0 - 5.0
        assert adjusted[0].end == 16.0

    def test_cut_after_edit_no_shift(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[AudioEdit(5.0, 6.0, "beep")],
            cut_intervals=[TimeInterval(20.0, 30.0)],  # cut after
        )
        adjusted = adjust_edits_for_cuts(plan)
        assert adjusted[0].start == 5.0

    def test_multiple_cuts_before_edit(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[AudioEdit(30.0, 31.0, "mute")],
            cut_intervals=[
                TimeInterval(5.0, 10.0),   # 5s
                TimeInterval(15.0, 20.0),  # 5s  → total 10s cut before edit
            ],
        )
        adjusted = adjust_edits_for_cuts(plan)
        assert adjusted[0].start == 20.0  # 30 - 10

    def test_preserves_edit_type_and_reason(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[AudioEdit(20.0, 21.0, "beep", "profanity")],
            cut_intervals=[TimeInterval(5.0, 10.0)],
        )
        adjusted = adjust_edits_for_cuts(plan)
        assert adjusted[0].edit_type == "beep"
        assert adjusted[0].reason == "profanity"

    def test_empty_audio_edits(self):
        plan = EditPlan(
            original_duration=60.0,
            audio_edits=[],
            cut_intervals=[TimeInterval(5.0, 10.0)],
        )
        assert adjust_edits_for_cuts(plan) == []
