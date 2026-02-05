"""
Tests for video_censor/validator.py

Tests format validation, ffprobe integration (mocked), and output path checks.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_censor.validator import (
    SUPPORTED_FORMATS,
    VideoInfo,
    ValidationError,
    get_video_info,
    validate_input,
    validate_output_path,
)


# ---------------------------------------------------------------------------
# SUPPORTED_FORMATS
# ---------------------------------------------------------------------------

class TestSupportedFormats:
    def test_common_formats_included(self):
        for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            assert ext in SUPPORTED_FORMATS

    def test_image_formats_excluded(self):
        for ext in (".jpg", ".png", ".gif", ".bmp"):
            assert ext not in SUPPORTED_FORMATS


# ---------------------------------------------------------------------------
# VideoInfo
# ---------------------------------------------------------------------------

class TestVideoInfo:
    def test_resolution_property(self):
        info = VideoInfo(
            path=Path("test.mp4"),
            duration=120.0,
            width=1920,
            height=1080,
            fps=24.0,
            has_audio=True,
            video_codec="h264",
            audio_codec="aac",
        )
        assert info.resolution == "1920x1080"


# ---------------------------------------------------------------------------
# get_video_info
# ---------------------------------------------------------------------------

SAMPLE_FFPROBE_OUTPUT = {
    "format": {"duration": "120.5"},
    "streams": [
        {
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "codec_name": "h264",
            "r_frame_rate": "24000/1001",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
        },
    ],
}


class TestGetVideoInfo:
    @patch("video_censor.validator.subprocess.run")
    def test_parses_ffprobe_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_FFPROBE_OUTPUT),
        )
        info = get_video_info(Path("test.mp4"))
        assert info.duration == 120.5
        assert info.width == 1920
        assert info.height == 1080
        assert info.video_codec == "h264"
        assert info.audio_codec == "aac"
        assert info.has_audio is True
        assert abs(info.fps - 23.976) < 0.01

    @patch("video_censor.validator.subprocess.run")
    def test_fractional_fps(self, mock_run):
        data = {
            "format": {"duration": "60"},
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "codec_name": "h264", "r_frame_rate": "30/1"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        info = get_video_info(Path("test.mp4"))
        assert info.fps == 30.0

    @patch("video_censor.validator.subprocess.run")
    def test_no_audio_stream(self, mock_run):
        data = {
            "format": {"duration": "60"},
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "codec_name": "h264", "r_frame_rate": "25/1"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        info = get_video_info(Path("test.mp4"))
        assert info.has_audio is False
        assert info.audio_codec is None

    @patch("video_censor.validator.subprocess.run")
    def test_no_video_stream_raises(self, mock_run):
        data = {
            "format": {"duration": "60"},
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        with pytest.raises(ValidationError, match="No video stream"):
            get_video_info(Path("test.mp4"))

    @patch("video_censor.validator.subprocess.run")
    def test_ffprobe_failure_raises(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffprobe", stderr="error"
        )
        with pytest.raises(ValidationError, match="Failed to probe"):
            get_video_info(Path("test.mp4"))

    @patch("video_censor.validator.subprocess.run")
    def test_malformed_json_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json{")
        with pytest.raises(ValidationError, match="Failed to parse"):
            get_video_info(Path("test.mp4"))

    @patch("video_censor.validator.subprocess.run")
    def test_zero_denominator_fps_defaults_to_30(self, mock_run):
        data = {
            "format": {"duration": "60"},
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "codec_name": "h264", "r_frame_rate": "0/0"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        info = get_video_info(Path("test.mp4"))
        assert info.fps == 30.0

    @patch("video_censor.validator.subprocess.run")
    def test_missing_duration_defaults_to_zero(self, mock_run):
        data = {
            "format": {},
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "codec_name": "h264", "r_frame_rate": "30/1"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(data)
        )
        info = get_video_info(Path("test.mp4"))
        assert info.duration == 0.0


# ---------------------------------------------------------------------------
# validate_input
# ---------------------------------------------------------------------------

class TestValidateInput:
    def test_nonexistent_file(self):
        valid, err, info = validate_input(Path("/nonexistent/video.mp4"))
        assert valid is False
        assert "not found" in err.lower() or "File not found" in err

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            valid, err, info = validate_input(Path(td))
            assert valid is False
            assert "Not a file" in err

    def test_unsupported_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            valid, err, info = validate_input(Path(f.name))
            assert valid is False
            assert "Unsupported format" in err

    @patch("video_censor.validator.get_video_info")
    @patch("video_censor.validator.subprocess.run")
    def test_valid_video(self, mock_run, mock_info):
        mock_run.return_value = MagicMock(returncode=0)
        mock_info.return_value = VideoInfo(
            path=Path("test.mp4"), duration=60.0,
            width=1920, height=1080, fps=24.0,
            has_audio=True, video_codec="h264", audio_codec="aac"
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            valid, err, info = validate_input(Path(f.name))
            assert valid is True
            assert err is None
            assert info.duration == 60.0

    @patch("video_censor.validator.get_video_info")
    @patch("video_censor.validator.subprocess.run")
    def test_zero_duration_rejected(self, mock_run, mock_info):
        mock_run.return_value = MagicMock(returncode=0)
        mock_info.return_value = VideoInfo(
            path=Path("test.mp4"), duration=0.0,
            width=1920, height=1080, fps=24.0,
            has_audio=True, video_codec="h264", audio_codec="aac"
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            valid, err, info = validate_input(Path(f.name))
            assert valid is False
            assert "no duration" in err.lower()

    @patch("video_censor.validator.get_video_info")
    @patch("video_censor.validator.subprocess.run")
    def test_zero_dimensions_rejected(self, mock_run, mock_info):
        mock_run.return_value = MagicMock(returncode=0)
        mock_info.return_value = VideoInfo(
            path=Path("test.mp4"), duration=60.0,
            width=0, height=0, fps=24.0,
            has_audio=True, video_codec="h264", audio_codec="aac"
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            valid, err, info = validate_input(Path(f.name))
            assert valid is False
            assert "invalid dimensions" in err.lower()

    @patch("video_censor.validator.subprocess.run")
    def test_ffprobe_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            valid, err, info = validate_input(Path(f.name))
            assert valid is False
            assert "ffprobe" in err.lower()


# ---------------------------------------------------------------------------
# validate_output_path
# ---------------------------------------------------------------------------

class TestValidateOutputPath:
    def test_valid_output_path(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "output.mp4"
            valid, err = validate_output_path(out)
            assert valid is True

    def test_nonexistent_parent_rejected(self):
        valid, err = validate_output_path(Path("/nonexistent/dir/out.mp4"))
        assert valid is False
        assert "does not exist" in err

    def test_existing_file_without_overwrite_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = Path(f.name)
        try:
            valid, err = validate_output_path(path, overwrite=False)
            assert valid is False
            assert "already exists" in err
        finally:
            path.unlink(missing_ok=True)

    def test_existing_file_with_overwrite_accepted(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = Path(f.name)
        try:
            valid, err = validate_output_path(path, overwrite=True)
            assert valid is True
        finally:
            path.unlink(missing_ok=True)
