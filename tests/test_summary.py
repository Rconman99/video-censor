"""Tests for video_censor.reporting.summary module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from video_censor.reporting.summary import (
    format_duration,
    generate_summary,
    print_summary,
    save_summary_json,
    save_edit_timeline,
)
from video_censor.editing.planner import EditPlan, AudioEdit
from video_censor.editing.intervals import TimeInterval, MatchSource, Action


# ---------------------------------------------------------------------------
# Helpers to build EditPlan objects
# ---------------------------------------------------------------------------

def _empty_plan(duration: float = 120.0) -> EditPlan:
    """An edit plan with no detections."""
    return EditPlan(
        original_duration=duration,
        keep_segments=[TimeInterval(start=0, end=duration, reason="full video")],
    )


def _profanity_plan() -> EditPlan:
    """Plan with two profanity detections and corresponding audio edits."""
    prof1 = TimeInterval(start=10.0, end=10.5, reason="word1", action=Action.BEEP, source=MatchSource.AUDIO)
    prof2 = TimeInterval(start=30.0, end=30.8, reason="word2", action=Action.BEEP, source=MatchSource.AUDIO)
    edit1 = AudioEdit(start=10.0, end=10.5, edit_type="beep", reason="word1")
    edit2 = AudioEdit(start=30.0, end=30.8, edit_type="beep", reason="word2")
    return EditPlan(
        original_duration=60.0,
        keep_segments=[TimeInterval(start=0, end=60.0, reason="full video")],
        audio_edits=[edit1, edit2],
        profanity_intervals=[prof1, prof2],
    )


def _nudity_plan() -> EditPlan:
    """Plan with one nudity cut."""
    nud = TimeInterval(start=20.0, end=25.0, reason="nudity", action=Action.CUT, source=MatchSource.VISUAL)
    return EditPlan(
        original_duration=60.0,
        keep_segments=[
            TimeInterval(start=0, end=20.0, reason="keep"),
            TimeInterval(start=25.0, end=60.0, reason="keep"),
        ],
        cut_intervals=[nud],
        nudity_intervals=[nud],
    )


def _combined_plan() -> EditPlan:
    """Plan with both profanity and nudity."""
    prof = TimeInterval(start=5.0, end=5.5, reason="word1", action=Action.BEEP, source=MatchSource.AUDIO)
    nud = TimeInterval(start=40.0, end=45.0, reason="nudity", action=Action.CUT, source=MatchSource.VISUAL)
    edit = AudioEdit(start=5.0, end=5.5, edit_type="mute", reason="word1")
    return EditPlan(
        original_duration=90.0,
        keep_segments=[
            TimeInterval(start=0, end=40.0, reason="keep"),
            TimeInterval(start=45.0, end=90.0, reason="keep"),
        ],
        audio_edits=[edit],
        cut_intervals=[nud],
        profanity_intervals=[prof],
        nudity_intervals=[nud],
    )


# ===========================================================================
# format_duration tests
# ===========================================================================

class TestFormatDuration:
    def test_zero(self):
        assert format_duration(0) == "00:00.000"

    def test_seconds_only(self):
        result = format_duration(5.123)
        assert result == "00:05.123"

    def test_fractional_rounding(self):
        # 1.9999 should display as ~2.000
        result = format_duration(2.0)
        assert result == "00:02.000"

    def test_minutes_and_seconds(self):
        result = format_duration(125.456)
        assert result == "02:05.456"

    def test_hours_minutes_seconds(self):
        result = format_duration(3661.5)
        assert result == "01:01:01.500"

    def test_large_value(self):
        result = format_duration(36000.0)  # 10 hours
        assert result == "10:00:00.000"

    def test_sub_second(self):
        result = format_duration(0.75)
        assert result == "00:00.750"


# ===========================================================================
# generate_summary tests
# ===========================================================================

class TestGenerateSummary:
    def test_empty_plan(self):
        plan = _empty_plan(120.0)
        summary = generate_summary(plan, Path("/in/video.mp4"), Path("/out/video.mp4"), 10.0)

        assert summary["input"]["path"] == "/in/video.mp4"
        assert summary["output"]["path"] == "/out/video.mp4"
        assert summary["input"]["duration"] == 120.0
        assert summary["profanity"]["detected_count"] == 0
        assert summary["nudity"]["segments_cut"] == 0
        assert summary["processing"]["time_seconds"] == 10.0
        assert summary["summary"]["percent_removed"] == 0

    def test_profanity_plan(self):
        plan = _profanity_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))

        assert summary["profanity"]["detected_count"] == 2
        assert summary["profanity"]["audio_edits_count"] == 2
        assert len(summary["profanity"]["intervals"]) == 2
        assert summary["profanity"]["intervals"][0]["reason"] == "word1"

    def test_nudity_plan(self):
        plan = _nudity_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))

        assert summary["nudity"]["segments_cut"] == 1
        assert summary["nudity"]["duration_removed"] == 5.0
        assert len(summary["nudity"]["intervals"]) == 1
        assert summary["nudity"]["intervals"][0]["start"] == 20.0
        assert summary["nudity"]["intervals"][0]["end"] == 25.0

    def test_combined_plan(self):
        plan = _combined_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"), 30.0)

        assert summary["profanity"]["detected_count"] == 1
        assert summary["nudity"]["segments_cut"] == 1
        assert summary["summary"]["total_profanity_instances"] == 1
        assert summary["summary"]["total_nudity_segments"] == 1
        assert summary["summary"]["duration_removed"] == 5.0

    def test_percent_removed(self):
        plan = _nudity_plan()  # 5s cut from 60s
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))

        expected_pct = 5.0 / 60.0 * 100
        assert abs(summary["summary"]["percent_removed"] - expected_pct) < 0.01

    def test_zero_duration_no_division_error(self):
        plan = EditPlan(original_duration=0.0)
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))
        assert summary["summary"]["percent_removed"] == 0

    def test_timestamp_present(self):
        plan = _empty_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))
        assert "timestamp" in summary
        # Should be a valid ISO-format string
        assert "T" in summary["timestamp"]


# ===========================================================================
# print_summary tests
# ===========================================================================

class TestPrintSummary:
    def test_empty_plan_no_crash(self, capsys):
        plan = _empty_plan()
        print_summary(plan, Path("/in/video.mp4"), Path("/out/video.mp4"))
        captured = capsys.readouterr()
        assert "VIDEO CENSOR" in captured.out
        assert "video.mp4" in captured.out

    def test_profanity_plan_output(self, capsys):
        plan = _profanity_plan()
        print_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"), 5.0)
        captured = capsys.readouterr()
        assert "Instances detected: 2" in captured.out
        assert "Audio edits made:   2" in captured.out
        assert "beep" in captured.out.lower()

    def test_nudity_plan_output(self, capsys):
        plan = _nudity_plan()
        print_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))
        captured = capsys.readouterr()
        assert "Segments cut:     1" in captured.out

    def test_combined_plan_output(self, capsys):
        plan = _combined_plan()
        print_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"), 15.0)
        captured = capsys.readouterr()
        assert "Processing time:" in captured.out

    def test_no_processing_time_hides_section(self, capsys):
        plan = _empty_plan()
        print_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"), 0.0)
        captured = capsys.readouterr()
        assert "Processing time:" not in captured.out


# ===========================================================================
# save_summary_json tests
# ===========================================================================

class TestSaveSummaryJson:
    def test_writes_valid_json(self, tmp_path):
        plan = _profanity_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"), 5.0)
        json_path = tmp_path / "summary.json"

        save_summary_json(summary, json_path)

        loaded = json.loads(json_path.read_text())
        assert loaded["profanity"]["detected_count"] == 2
        assert loaded["input"]["path"] == "/in/v.mp4"

    def test_file_is_readable_json(self, tmp_path):
        plan = _empty_plan()
        summary = generate_summary(plan, Path("/in/v.mp4"), Path("/out/v.mp4"))
        json_path = tmp_path / "empty.json"

        save_summary_json(summary, json_path)

        with open(json_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "summary" in data


# ===========================================================================
# save_edit_timeline tests
# ===========================================================================

class TestSaveEditTimeline:
    def test_empty_plan(self, tmp_path):
        plan = _empty_plan()
        timeline_path = tmp_path / "timeline.txt"
        save_edit_timeline(plan, timeline_path)

        content = timeline_path.read_text()
        assert "VIDEO CENSOR - EDIT TIMELINE" in content
        assert "PROFANITY DETECTIONS" in content
        assert "AUDIO EDITS" in content
        assert "NUDITY CUTS" in content
        assert "KEEP SEGMENTS" in content

    def test_profanity_entries(self, tmp_path):
        plan = _profanity_plan()
        timeline_path = tmp_path / "timeline.txt"
        save_edit_timeline(plan, timeline_path)

        content = timeline_path.read_text()
        # Two profanity detections listed
        assert "word1" in content
        assert "word2" in content
        # Two audio edits listed with type
        assert "[beep]" in content

    def test_nudity_entries(self, tmp_path):
        plan = _nudity_plan()
        timeline_path = tmp_path / "timeline.txt"
        save_edit_timeline(plan, timeline_path)

        content = timeline_path.read_text()
        assert "NUDITY CUTS" in content
        # Duration line
        assert "Duration: 5.000s" in content

    def test_keep_segments_listed(self, tmp_path):
        plan = _nudity_plan()
        timeline_path = tmp_path / "timeline.txt"
        save_edit_timeline(plan, timeline_path)

        content = timeline_path.read_text()
        # Two keep segments for nudity plan
        lines = [l for l in content.splitlines() if "Duration:" in l]
        # 1 nudity cut duration + 2 keep segment durations = 3 Duration lines
        assert len(lines) == 3

    def test_generated_timestamp_present(self, tmp_path):
        plan = _empty_plan()
        timeline_path = tmp_path / "timeline.txt"
        save_edit_timeline(plan, timeline_path)

        content = timeline_path.read_text()
        assert "Generated:" in content
