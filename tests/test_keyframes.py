"""
Tests for video_censor/editing/keyframes.py

Tests keyframe extraction (mocked ffprobe), snap-to-keyframe logic,
keyframe interval finding, and density calculation.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_censor.editing.keyframes import (
    get_keyframes,
    snap_to_keyframe,
    is_on_keyframe,
    find_keyframe_interval,
    get_keyframe_density,
)


# ---------------------------------------------------------------------------
# get_keyframes
# ---------------------------------------------------------------------------

def _ffprobe_packets(*timestamps):
    """Build a fake ffprobe JSON response with keyframe packets."""
    packets = []
    for ts in timestamps:
        packets.append({"pts_time": str(ts), "flags": "K_"})
    return json.dumps({"packets": packets})


class TestGetKeyframes:
    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_extracts_keyframe_timestamps(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_ffprobe_packets(0.0, 2.0, 4.0, 6.0),
        )
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == [0.0, 2.0, 4.0, 6.0]

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_deduplicates_and_sorts(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_ffprobe_packets(4.0, 2.0, 2.0, 0.0),
        )
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == [0.0, 2.0, 4.0]

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_skips_non_keyframe_packets(self, mock_run):
        data = {
            "packets": [
                {"pts_time": "0.0", "flags": "K_"},
                {"pts_time": "1.0", "flags": "__"},  # not a keyframe
                {"pts_time": "2.0", "flags": "K_"},
            ]
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(data))
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == [0.0, 2.0]

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_skips_invalid_pts_time(self, mock_run):
        data = {
            "packets": [
                {"pts_time": "0.0", "flags": "K_"},
                {"pts_time": "not_a_number", "flags": "K_"},
                {"flags": "K_"},  # missing pts_time
            ]
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(data))
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == [0.0]

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_ffprobe_failure_returns_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == []

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_timeout_returns_empty(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 60)
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == []

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_malformed_json_returns_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json{")
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == []

    @patch("video_censor.editing.keyframes.subprocess.run")
    def test_empty_packets_returns_empty(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps({"packets": []})
        )
        kfs = get_keyframes(Path("video.mp4"))
        assert kfs == []


# ---------------------------------------------------------------------------
# snap_to_keyframe
# ---------------------------------------------------------------------------

KEYFRAMES = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]


class TestSnapToKeyframe:
    def test_nearest_exact_match(self):
        assert snap_to_keyframe(4.0, KEYFRAMES, mode="nearest") == 4.0

    def test_nearest_within_tolerance(self):
        assert snap_to_keyframe(4.3, KEYFRAMES, mode="nearest", tolerance=0.5) == 4.0

    def test_nearest_outside_tolerance_returns_none(self):
        assert snap_to_keyframe(5.0, KEYFRAMES, mode="nearest", tolerance=0.3) is None

    def test_before_mode(self):
        result = snap_to_keyframe(5.0, KEYFRAMES, mode="before", tolerance=2.0)
        assert result == 4.0

    def test_before_mode_exact(self):
        assert snap_to_keyframe(4.0, KEYFRAMES, mode="before") == 4.0

    def test_before_no_candidate_returns_none(self):
        # All keyframes are after -1.0, and with small tolerance, nothing matches
        assert snap_to_keyframe(-1.0, KEYFRAMES, mode="before", tolerance=0.5) is None

    def test_after_mode(self):
        result = snap_to_keyframe(3.0, KEYFRAMES, mode="after", tolerance=2.0)
        assert result == 4.0

    def test_after_mode_exact(self):
        assert snap_to_keyframe(6.0, KEYFRAMES, mode="after") == 6.0

    def test_after_no_candidate_returns_none(self):
        assert snap_to_keyframe(11.0, KEYFRAMES, mode="after", tolerance=0.5) is None

    def test_empty_keyframes_returns_none(self):
        assert snap_to_keyframe(5.0, [], mode="nearest") is None

    def test_single_keyframe_nearest(self):
        assert snap_to_keyframe(0.1, [0.0], mode="nearest", tolerance=0.5) == 0.0


# ---------------------------------------------------------------------------
# is_on_keyframe
# ---------------------------------------------------------------------------

class TestIsOnKeyframe:
    def test_exact_match(self):
        assert is_on_keyframe(4.0, KEYFRAMES) is True

    def test_within_epsilon(self):
        assert is_on_keyframe(4.0005, KEYFRAMES, epsilon=0.001) is True

    def test_outside_epsilon(self):
        assert is_on_keyframe(4.01, KEYFRAMES, epsilon=0.001) is False

    def test_empty_keyframes(self):
        assert is_on_keyframe(0.0, []) is False


# ---------------------------------------------------------------------------
# find_keyframe_interval
# ---------------------------------------------------------------------------

class TestFindKeyframeInterval:
    def test_finds_interval(self):
        start, end = find_keyframe_interval(1.0, 7.0, KEYFRAMES)
        assert start == 2.0
        assert end == 6.0

    def test_no_keyframes_in_range(self):
        start, end = find_keyframe_interval(0.5, 1.5, KEYFRAMES)
        assert start is None
        assert end is None

    def test_single_keyframe_in_range(self):
        start, end = find_keyframe_interval(3.5, 4.5, KEYFRAMES)
        assert start == 4.0
        assert end == 4.0

    def test_boundary_inclusive(self):
        start, end = find_keyframe_interval(2.0, 4.0, KEYFRAMES)
        assert start == 2.0
        assert end == 4.0

    def test_empty_keyframes(self):
        start, end = find_keyframe_interval(0.0, 10.0, [])
        assert start is None
        assert end is None


# ---------------------------------------------------------------------------
# get_keyframe_density
# ---------------------------------------------------------------------------

class TestGetKeyframeDensity:
    def test_normal_density(self):
        density = get_keyframe_density(KEYFRAMES, 10.0)
        assert density == 0.6  # 6 keyframes / 10 seconds

    def test_zero_duration(self):
        assert get_keyframe_density(KEYFRAMES, 0.0) == 0.0

    def test_negative_duration(self):
        assert get_keyframe_density(KEYFRAMES, -5.0) == 0.0

    def test_empty_keyframes(self):
        assert get_keyframe_density([], 10.0) == 0.0
