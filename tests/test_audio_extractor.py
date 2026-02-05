"""
Tests for video_censor/audio/extractor.py

Tests audio extraction (ffmpeg) and duration queries (ffprobe) with mocked
subprocess calls.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_censor.audio.extractor import extract_audio, get_audio_duration


# ---------------------------------------------------------------------------
# extract_audio
# ---------------------------------------------------------------------------

class TestExtractAudio:
    @patch("video_censor.audio.extractor.subprocess.run")
    def test_default_args_mono_16khz(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        out.write_bytes(b"\x00" * 100)  # fake file
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = extract_audio(Path("video.mp4"), output_path=out)
        cmd = mock_run.call_args[0][0]

        assert result == out
        assert "-ar" in cmd
        assert cmd[cmd.index("-ar") + 1] == "16000"
        assert "-ac" in cmd
        assert cmd[cmd.index("-ac") + 1] == "1"
        assert "-vn" in cmd

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_custom_sample_rate(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        out.write_bytes(b"\x00" * 100)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        extract_audio(Path("v.mp4"), output_path=out, sample_rate=44100)
        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("-ar") + 1] == "44100"

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_stereo_mode(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        out.write_bytes(b"\x00" * 100)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        extract_audio(Path("v.mp4"), output_path=out, mono=False)
        cmd = mock_run.call_args[0][0]
        assert "-ac" not in cmd

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_creates_temp_file_when_no_output(self, mock_run):
        """When output_path is None, a temp directory is used."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        # The function will create a temp path, but the file won't exist after
        # the mocked run, so it will raise RuntimeError about missing file.
        with pytest.raises(RuntimeError, match="not created"):
            extract_audio(Path("v.mp4"))

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_ffmpeg_failure_raises_runtime_error(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="No audio stream"
        )
        with pytest.raises(RuntimeError, match="Failed to extract"):
            extract_audio(Path("v.mp4"), output_path=out)

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_missing_output_file_raises(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        # Don't create the file — simulate ffmpeg running but producing nothing
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        with pytest.raises(RuntimeError, match="not created"):
            extract_audio(Path("v.mp4"), output_path=out)

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_nostdin_flag_present(self, mock_run, tmp_path):
        """Ensure -nostdin is passed to prevent hanging in background."""
        out = tmp_path / "audio.wav"
        out.write_bytes(b"\x00" * 100)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        extract_audio(Path("v.mp4"), output_path=out)
        cmd = mock_run.call_args[0][0]
        assert "-nostdin" in cmd

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_overwrite_flag_present(self, mock_run, tmp_path):
        out = tmp_path / "audio.wav"
        out.write_bytes(b"\x00" * 100)
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        extract_audio(Path("v.mp4"), output_path=out)
        cmd = mock_run.call_args[0][0]
        assert "-y" in cmd

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_creates_parent_directories(self, mock_run, tmp_path):
        out = tmp_path / "sub" / "dir" / "audio.wav"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        # Will fail because file not created, but directories should exist
        with pytest.raises(RuntimeError):
            extract_audio(Path("v.mp4"), output_path=out)

        assert (tmp_path / "sub" / "dir").is_dir()


# ---------------------------------------------------------------------------
# get_audio_duration
# ---------------------------------------------------------------------------

class TestGetAudioDuration:
    @patch("video_censor.audio.extractor.subprocess.run")
    def test_returns_duration(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="125.340000\n"
        )
        assert get_audio_duration(Path("audio.wav")) == pytest.approx(125.34)

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_ffprobe_failure_returns_zero(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")
        assert get_audio_duration(Path("audio.wav")) == 0.0

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_non_numeric_output_returns_zero(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="N/A\n")
        assert get_audio_duration(Path("audio.wav")) == 0.0

    @patch("video_censor.audio.extractor.subprocess.run")
    def test_uses_ffprobe(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="10.0\n")
        get_audio_duration(Path("audio.wav"))
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffprobe"
