"""
Tests for video_censor/editing/renderer.py

Tests quality preset mapping, audio filter construction, segment extraction
command generation, and error handling — all via mocked subprocess calls.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from video_censor.config import Config, OutputConfig
from video_censor.editing.planner import AudioEdit, EditPlan
from video_censor.editing.intervals import TimeInterval
from video_censor.editing.renderer import (
    get_quality_args,
    generate_beep_tone,
    build_audio_filter,
    extract_segment,
    concat_segments,
    render_audio_only,
    render_censored_video,
    _get_hardware_encoder_args,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(preset="original", crf=23, hw="off"):
    """Return a Config with common overrides."""
    cfg = Config.default()
    cfg.output.quality_preset = preset
    cfg.output.video_crf = crf
    cfg.output.hardware_acceleration = hw
    return cfg


# ---------------------------------------------------------------------------
# get_quality_args
# ---------------------------------------------------------------------------

class TestGetQualityArgs:
    def test_original_preset_returns_crf(self):
        args = get_quality_args(_config("original"))
        assert "-crf" in args
        assert "-vf" not in args

    def test_auto_preset_returns_crf(self):
        args = get_quality_args(_config("auto"))
        assert "-crf" in args

    def test_1080p_high_has_scale_and_bitrate(self):
        args = get_quality_args(_config("1080p_high"))
        assert "-vf" in args
        vf_idx = args.index("-vf")
        assert "1080" in args[vf_idx + 1]
        assert "-b:v" in args
        bv_idx = args.index("-b:v")
        assert args[bv_idx + 1] == "20000k"

    def test_480p_preset(self):
        args = get_quality_args(_config("480p"))
        vf_idx = args.index("-vf")
        assert "480" in args[vf_idx + 1]

    def test_unknown_preset_falls_back_to_original(self):
        args = get_quality_args(_config("nonexistent_preset"))
        assert "-crf" in args
        assert "-vf" not in args

    def test_4k_high_bitrate(self):
        args = get_quality_args(_config("4k_high"))
        bv_idx = args.index("-b:v")
        assert args[bv_idx + 1] == "40000k"

    def test_160p_low_bitrate(self):
        args = get_quality_args(_config("160p"))
        bv_idx = args.index("-b:v")
        assert args[bv_idx + 1] == "200k"

    def test_maxrate_and_bufsize_present(self):
        args = get_quality_args(_config("720p_med"))
        assert "-maxrate" in args
        assert "-bufsize" in args


# ---------------------------------------------------------------------------
# build_audio_filter
# ---------------------------------------------------------------------------

class TestBuildAudioFilter:
    def test_empty_edits_returns_anull(self):
        assert build_audio_filter([]) == "anull"

    def test_single_mute(self):
        edits = [AudioEdit(start=1.0, end=2.0, edit_type="mute")]
        result = build_audio_filter(edits)
        assert "volume=enable=" in result
        assert "1.000" in result
        assert "2.000" in result
        assert "volume=0" in result

    def test_single_beep_also_mutes(self):
        edits = [AudioEdit(start=3.0, end=4.5, edit_type="beep")]
        result = build_audio_filter(edits)
        assert "volume=0" in result

    def test_multiple_edits_joined_by_comma(self):
        edits = [
            AudioEdit(start=1.0, end=2.0, edit_type="mute"),
            AudioEdit(start=5.0, end=6.0, edit_type="beep"),
        ]
        result = build_audio_filter(edits)
        assert result.count("volume=enable=") == 2
        assert "," in result


# ---------------------------------------------------------------------------
# generate_beep_tone
# ---------------------------------------------------------------------------

class TestGenerateBeepTone:
    @patch("video_censor.editing.renderer.subprocess.run")
    def test_generates_beep_file(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "beep.wav"
            result = generate_beep_tone(1.0, output_path=out)
            assert result == out
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "ffmpeg" in cmd[0]
            assert "sine=frequency=1000:duration=1.0" in " ".join(cmd)

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_custom_frequency_and_volume(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "beep.wav"
            generate_beep_tone(2.5, frequency=440, volume=0.8, output_path=out)
            cmd = " ".join(mock_run.call_args[0][0])
            assert "frequency=440" in cmd
            assert "volume=0.8" in cmd

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_ffmpeg_failure_raises(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"error")
        with tempfile.TemporaryDirectory() as td:
            with pytest.raises(RuntimeError, match="Failed to generate beep"):
                generate_beep_tone(1.0, output_path=Path(td) / "beep.wav")

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_temp_file_created_when_no_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = generate_beep_tone(1.0)
        assert result.name == "beep.wav"
        assert "video_censor_" in str(result.parent)


# ---------------------------------------------------------------------------
# _get_hardware_encoder_args
# ---------------------------------------------------------------------------

class TestHardwareEncoderArgs:
    def test_off_returns_none(self):
        cfg = _config(hw="off")
        assert _get_hardware_encoder_args(cfg) is None

    @patch("video_censor.editing.renderer.sys")
    def test_auto_on_non_darwin_returns_none(self, mock_sys):
        mock_sys.platform = "linux"
        cfg = _config(hw="auto")
        assert _get_hardware_encoder_args(cfg) is None

    @patch("video_censor.editing.renderer.sys")
    def test_auto_on_darwin_returns_hevc(self, mock_sys):
        mock_sys.platform = "darwin"
        cfg = _config(hw="auto")
        result = _get_hardware_encoder_args(cfg, prefer_hevc=True)
        assert result is not None
        assert "hevc_videotoolbox" in result

    @patch("video_censor.editing.renderer.sys")
    def test_auto_on_darwin_h264(self, mock_sys):
        mock_sys.platform = "darwin"
        cfg = _config(hw="auto")
        result = _get_hardware_encoder_args(cfg, prefer_hevc=False)
        assert result is not None
        assert "h264_videotoolbox" in result


# ---------------------------------------------------------------------------
# extract_segment
# ---------------------------------------------------------------------------

class TestExtractSegment:
    @patch("video_censor.editing.renderer.subprocess.run")
    def test_stream_copy_when_force_copy_no_edits(self, mock_run):
        """force_copy + no audio edits → pure stream copy."""
        mock_run.return_value = MagicMock(returncode=0)
        cfg = _config("original")
        extract_segment(
            Path("in.mp4"), Path("out.mp4"),
            start=10.0, end=20.0,
            audio_edits=[], config=cfg,
            force_copy=True
        )
        cmd = mock_run.call_args[0][0]
        assert "-c" in cmd
        copy_idx = cmd.index("-c")
        assert cmd[copy_idx + 1] == "copy"

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_original_preset_reencodes_with_crf(self, mock_run):
        """Original preset returns quality args (crf), so video is re-encoded."""
        mock_run.return_value = MagicMock(returncode=0)
        cfg = _config("original")
        edits = [AudioEdit(start=0.5, end=1.5, edit_type="mute")]
        extract_segment(
            Path("in.mp4"), Path("out.mp4"),
            start=10.0, end=20.0,
            audio_edits=edits, config=cfg
        )
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "-af" in cmd
        # Original preset provides quality args, so it goes to re-encode path
        assert "libx264" in cmd_str or "hevc_videotoolbox" in cmd_str

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_full_reencode_with_quality_preset(self, mock_run):
        """Quality preset → full re-encode."""
        mock_run.return_value = MagicMock(returncode=0)
        cfg = _config("720p_med")
        extract_segment(
            Path("in.mp4"), Path("out.mp4"),
            start=0.0, end=5.0,
            audio_edits=[], config=cfg
        )
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "libx264" in cmd_str or "hevc_videotoolbox" in cmd_str

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_force_copy_ignores_quality(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        cfg = _config("1080p_high")
        extract_segment(
            Path("in.mp4"), Path("out.mp4"),
            start=0.0, end=5.0,
            audio_edits=[], config=cfg,
            force_copy=True
        )
        cmd = mock_run.call_args[0][0]
        assert "-c" in cmd
        c_idx = cmd.index("-c")
        assert cmd[c_idx + 1] == "copy"

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_ffmpeg_failure_raises_runtime_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="codec error"
        )
        with pytest.raises(RuntimeError, match="Failed to extract segment"):
            extract_segment(
                Path("in.mp4"), Path("out.mp4"),
                start=0.0, end=5.0,
                audio_edits=[], config=_config()
            )


# ---------------------------------------------------------------------------
# concat_segments
# ---------------------------------------------------------------------------

class TestConcatSegments:
    @patch("video_censor.editing.renderer.subprocess.run")
    def test_creates_concat_list_and_runs_ffmpeg(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            segs = [td / "seg1.mp4", td / "seg2.mp4"]
            concat_segments(segs, td / "out.mp4", td)

            # Verify concat list file was written
            list_file = td / "concat_list.txt"
            assert list_file.exists()
            content = list_file.read_text()
            assert "seg1.mp4" in content
            assert "seg2.mp4" in content

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_concat_ffmpeg_failure_raises(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="concat fail"
        )
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with pytest.raises(RuntimeError, match="Failed to concatenate"):
                concat_segments([td / "a.mp4"], td / "out.mp4", td)

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_path_with_single_quote_escaped(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            seg = td / "it's a test.mp4"
            concat_segments([seg], td / "out.mp4", td)
            content = (td / "concat_list.txt").read_text()
            assert "'\\''" in content  # escaped single quote


# ---------------------------------------------------------------------------
# render_censored_video — integration-level tests with mocks
# ---------------------------------------------------------------------------

class TestRenderCensoredVideo:
    @patch("video_censor.editing.renderer.subprocess.run")
    def test_no_edits_copies_file(self, mock_run):
        """No cuts and no audio edits → copy file."""
        plan = EditPlan(
            original_duration=60.0,
            keep_segments=[],
            audio_edits=[],
            cut_intervals=[],
        )
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            inp = td / "input.mp4"
            inp.write_bytes(b"fake video data")
            out = td / "output.mp4"

            render_censored_video(inp, out, plan, _config())
            # shutil.copy should have been called — output should exist
            assert out.exists()
            assert out.read_bytes() == b"fake video data"

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_audio_only_edits(self, mock_run):
        """Audio edits but no cuts → render_audio_only path."""
        mock_run.return_value = MagicMock(returncode=0)
        plan = EditPlan(
            original_duration=60.0,
            keep_segments=[TimeInterval(0, 60)],
            audio_edits=[AudioEdit(start=5.0, end=6.0, edit_type="mute")],
            cut_intervals=[],
        )
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            inp = td / "input.mp4"
            inp.write_bytes(b"fake")
            out = td / "output.mp4"
            out.write_bytes(b"rendered")  # simulate ffmpeg writing output

            render_censored_video(inp, out, plan, _config())
            # subprocess.run should have been called (for ffmpeg)
            assert mock_run.called

    @patch("video_censor.editing.renderer.subprocess.run")
    def test_output_directory_created(self, mock_run):
        """Output dir is created if it doesn't exist."""
        mock_run.return_value = MagicMock(returncode=0)
        plan = EditPlan(original_duration=10.0)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            inp = td / "input.mp4"
            inp.write_bytes(b"fake")
            out = td / "subdir" / "output.mp4"

            render_censored_video(inp, out, plan, _config())
            assert out.parent.exists()
