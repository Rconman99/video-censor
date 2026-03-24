"""Tests for scene_detector and extractor modules."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from video_censor.nudity.scene_detector import (
    SceneChange, SamplingPlan, detect_scene_changes, get_video_duration,
    create_adaptive_sampling_plan, create_fixed_sampling_plan,
    get_sample_timestamps, _merge_regions
)
from video_censor.nudity.extractor import FrameInfo, extract_frames, cleanup_frames, get_frame_at_time


# ── Dataclass tests ──────────────────────────────────────────────────────────


class TestSceneChangeDataclass:
    def test_fields_and_defaults(self):
        sc = SceneChange(timestamp=1.5)
        assert sc.timestamp == 1.5
        assert sc.confidence == 1.0

    def test_explicit_confidence(self):
        sc = SceneChange(timestamp=2.0, confidence=0.8)
        assert sc.confidence == 0.8


class TestSamplingPlanDataclass:
    def test_fields_and_defaults(self):
        plan = SamplingPlan(timestamps=[0.0, 0.5], scene_changes=[])
        assert plan.timestamps == [0.0, 0.5]
        assert plan.scene_changes == []
        assert plan.strategy == "adaptive"

    def test_explicit_strategy(self):
        plan = SamplingPlan(timestamps=[], scene_changes=[], strategy="fixed")
        assert plan.strategy == "fixed"


class TestFrameInfoDataclass:
    def test_fields(self):
        p = Path("/tmp/frame.jpg")
        fi = FrameInfo(path=p, timestamp=1.25, frame_number=5)
        assert fi.path == p
        assert fi.timestamp == 1.25
        assert fi.frame_number == 5

    def test_repr_format(self):
        fi = FrameInfo(path=Path("/tmp/f.jpg"), timestamp=3.5, frame_number=14)
        assert repr(fi) == "FrameInfo(frame=14, t=3.50s)"


# ── detect_scene_changes tests ──────────────────────────────────────────────


class TestDetectSceneChanges:
    @patch("subprocess.run")
    def test_parses_csv_output(self, mock_run):
        csv_lines = (
            "video,0,key_frame,1,1.000000,1234\n"
            "video,0,key_frame,1,3.500000,5678\n"
        )
        mock_run.return_value = MagicMock(stdout=csv_lines)

        with patch.object(Path, "exists", return_value=True):
            results = detect_scene_changes(Path("/fake/video.mp4"), threshold=0.3)

        assert len(results) == 2
        assert results[0].timestamp == 1.0
        assert results[1].timestamp == 3.5
        assert results[0].confidence == 0.3

    def test_raises_file_not_found(self):
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Video not found"):
                detect_scene_changes(Path("/nonexistent/video.mp4"))

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=300))
    def test_returns_empty_on_timeout(self, mock_run):
        with patch.object(Path, "exists", return_value=True):
            result = detect_scene_changes(Path("/fake/video.mp4"))
        assert result == []

    @patch("subprocess.run")
    def test_respects_min_scene_length(self, mock_run):
        # Two scene changes only 0.5s apart, min_scene_length=1.0 should drop the second
        csv_lines = (
            "video,0,key_frame,1,2.000000,100\n"
            "video,0,key_frame,1,2.400000,200\n"
            "video,0,key_frame,1,5.000000,300\n"
        )
        mock_run.return_value = MagicMock(stdout=csv_lines)

        with patch.object(Path, "exists", return_value=True):
            results = detect_scene_changes(Path("/fake/video.mp4"), min_scene_length=1.0)

        assert len(results) == 2
        assert results[0].timestamp == 2.0
        assert results[1].timestamp == 5.0

    @patch("subprocess.run", side_effect=OSError("ffprobe not found"))
    def test_returns_empty_on_generic_error(self, mock_run):
        with patch.object(Path, "exists", return_value=True):
            result = detect_scene_changes(Path("/fake/video.mp4"))
        assert result == []


# ── get_video_duration tests ─────────────────────────────────────────────────


class TestGetVideoDuration:
    @patch("subprocess.run")
    def test_returns_float(self, mock_run):
        mock_run.return_value = MagicMock(stdout="  120.500\n")
        assert get_video_duration(Path("/fake/video.mp4")) == 120.5

    @patch("subprocess.run", side_effect=Exception("fail"))
    def test_returns_zero_on_error(self, mock_run):
        assert get_video_duration(Path("/fake/video.mp4")) == 0.0


# ── _merge_regions tests ─────────────────────────────────────────────────────


class TestMergeRegions:
    def test_empty_input(self):
        assert _merge_regions([]) == []

    def test_non_overlapping(self):
        regions = [(0.0, 1.0), (2.0, 3.0), (5.0, 6.0)]
        assert _merge_regions(regions) == [(0.0, 1.0), (2.0, 3.0), (5.0, 6.0)]

    def test_overlapping(self):
        regions = [(0.0, 2.0), (1.5, 3.0), (5.0, 7.0), (6.0, 8.0)]
        merged = _merge_regions(regions)
        assert merged == [(0.0, 3.0), (5.0, 8.0)]

    def test_adjacent_regions(self):
        # start == last_end should merge
        regions = [(0.0, 1.0), (1.0, 2.0)]
        assert _merge_regions(regions) == [(0.0, 2.0)]


# ── create_adaptive_sampling_plan tests ──────────────────────────────────────


class TestCreateAdaptiveSamplingPlan:
    @patch("video_censor.nudity.scene_detector.detect_scene_changes", return_value=[])
    @patch("video_censor.nudity.scene_detector.get_video_duration", return_value=0.0)
    def test_failed_strategy_when_duration_zero(self, mock_dur, mock_sc):
        plan = create_adaptive_sampling_plan(Path("/fake/video.mp4"))
        assert plan.strategy == "failed"
        assert plan.timestamps == []


# ── create_fixed_sampling_plan tests ─────────────────────────────────────────


class TestCreateFixedSamplingPlan:
    @patch("video_censor.nudity.scene_detector.get_video_duration", return_value=1.0)
    def test_generates_correct_timestamps(self, mock_dur):
        plan = create_fixed_sampling_plan(Path("/fake/video.mp4"), interval=0.25)
        assert plan.strategy == "fixed"
        assert plan.scene_changes == []
        expected = [0.0, 0.25, 0.5, 0.75]
        assert len(plan.timestamps) == len(expected)
        for a, b in zip(plan.timestamps, expected):
            assert abs(a - b) < 1e-9

    @patch("video_censor.nudity.scene_detector.get_video_duration", return_value=0.0)
    def test_empty_when_duration_zero(self, mock_dur):
        plan = create_fixed_sampling_plan(Path("/fake/video.mp4"))
        assert plan.timestamps == []


# ── get_sample_timestamps tests ──────────────────────────────────────────────


class TestGetSampleTimestamps:
    @patch("video_censor.nudity.scene_detector.create_fixed_sampling_plan")
    @patch("video_censor.nudity.scene_detector.create_adaptive_sampling_plan")
    def test_adaptive_falls_back_to_fixed(self, mock_adaptive, mock_fixed):
        mock_adaptive.return_value = SamplingPlan(timestamps=[], scene_changes=[], strategy="failed")
        mock_fixed.return_value = SamplingPlan(timestamps=[0.0, 0.15], scene_changes=[], strategy="fixed")

        result = get_sample_timestamps(Path("/fake/video.mp4"), adaptive=True)
        assert result == [0.0, 0.15]
        mock_adaptive.assert_called_once()
        mock_fixed.assert_called_once()

    @patch("video_censor.nudity.scene_detector.create_fixed_sampling_plan")
    def test_non_adaptive_uses_fixed(self, mock_fixed):
        mock_fixed.return_value = SamplingPlan(timestamps=[0.0, 0.5], scene_changes=[], strategy="fixed")
        result = get_sample_timestamps(Path("/fake/video.mp4"), adaptive=False, fixed_interval=0.5)
        assert result == [0.0, 0.5]


# ── extract_frames tests ────────────────────────────────────────────────────


class TestExtractFrames:
    @patch("subprocess.run")
    def test_builds_correct_ffmpeg_command(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        # Create a fake frame file so the glob picks it up
        (tmp_path / "frame_000001.jpg").touch()

        frames = extract_frames(Path("/fake/video.mp4"), interval=0.25, output_dir=tmp_path)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert str(Path("/fake/video.mp4")) in cmd
        assert "-vf" in cmd
        assert "fps=4.0" in cmd
        assert len(frames) == 1

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="error"))
    def test_raises_runtime_error_on_failure(self, mock_run, tmp_path):
        with pytest.raises(RuntimeError, match="Failed to extract frames"):
            extract_frames(Path("/fake/video.mp4"), output_dir=tmp_path)

    @patch("subprocess.run")
    def test_with_start_and_end_time(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        (tmp_path / "frame_000001.jpg").touch()

        extract_frames(
            Path("/fake/video.mp4"),
            interval=0.5,
            output_dir=tmp_path,
            start_time=5.0,
            end_time=10.0,
        )

        cmd = mock_run.call_args[0][0]
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "5.0"
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "5.0"  # duration = end - start

    @patch("subprocess.run")
    def test_no_ss_when_start_is_zero(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        extract_frames(Path("/fake/video.mp4"), output_dir=tmp_path, start_time=0.0)
        cmd = mock_run.call_args[0][0]
        assert "-ss" not in cmd


# ── cleanup_frames tests ────────────────────────────────────────────────────


class TestCleanupFrames:
    def test_deletes_files(self, tmp_path):
        paths = []
        for i in range(3):
            p = tmp_path / f"frame_{i}.jpg"
            p.touch()
            paths.append(p)

        frames = [FrameInfo(path=p, timestamp=i * 0.25, frame_number=i) for i, p in enumerate(paths)]
        cleanup_frames(frames)

        for p in paths:
            assert not p.exists()

    def test_handles_already_deleted(self, tmp_path):
        p = tmp_path / "gone.jpg"  # does not exist
        frames = [FrameInfo(path=p, timestamp=0.0, frame_number=0)]
        # Should not raise
        cleanup_frames(frames)


# ── get_frame_at_time tests ─────────────────────────────────────────────────


class TestGetFrameAtTime:
    @patch("subprocess.run")
    def test_builds_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        out = Path("/tmp/out.jpg")
        result = get_frame_at_time(Path("/fake/video.mp4"), timestamp=2.5, output_path=out)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        ss_idx = cmd.index("-ss")
        assert cmd[ss_idx + 1] == "2.5"
        assert "-frames:v" in cmd
        assert str(out) in cmd
        assert result == out

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="err"))
    def test_raises_runtime_error_on_failure(self, mock_run):
        with pytest.raises(RuntimeError, match="Failed to extract frame"):
            get_frame_at_time(Path("/fake/video.mp4"), timestamp=1.0, output_path=Path("/tmp/f.jpg"))
