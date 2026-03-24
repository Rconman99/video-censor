"""Tests for waveform generation and subtitle extraction modules."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from video_censor.audio.waveform import (
    generate_waveform_png,
    generate_waveform_for_segment,
    get_audio_peaks,
)
from video_censor.subtitles.extractor import (
    SubtitleTrack,
    detect_subtitle_tracks,
    find_best_english_track,
    extract_english_subtitles,
    has_english_subtitles,
)


# ---------------------------------------------------------------------------
# Waveform: generate_waveform_png
# ---------------------------------------------------------------------------


class TestGenerateWaveformPng:
    """Tests for generate_waveform_png."""

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        """1. Success case: output file exists with size > 0."""
        out = tmp_path / "wave.png"
        out.write_bytes(b"\x89PNG fake data")

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = generate_waveform_png(Path("/fake/video.mp4"), output_path=out)
        assert result == out
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd[0]

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_failure_nonzero_returncode(self, mock_run, tmp_path):
        """2. Failure when ffmpeg returns non-zero exit code."""
        out = tmp_path / "wave.png"
        mock_run.return_value = MagicMock(returncode=1, stderr="error msg")

        result = generate_waveform_png(Path("/fake/video.mp4"), output_path=out)
        assert result is None

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_timeout_returns_none(self, mock_run):
        """3. TimeoutExpired returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60)

        result = generate_waveform_png(Path("/fake/video.mp4"))
        assert result is None

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_transparent_vs_nontransparent_filter(self, mock_run, tmp_path):
        """4. Transparent background uses different filter than opaque."""
        out = tmp_path / "wave.png"
        out.write_bytes(b"\x89PNG")

        mock_run.return_value = MagicMock(returncode=0)

        # Transparent (default)
        generate_waveform_png(Path("/f.mp4"), output_path=out, background="transparent")
        cmd_transparent = mock_run.call_args[0][0]
        filter_arg_t = [a for a in cmd_transparent if "showwavespic" in a][0]
        assert "split_channels" not in filter_arg_t

        # Non-transparent
        out.write_bytes(b"\x89PNG")
        generate_waveform_png(Path("/f.mp4"), output_path=out, background="black")
        cmd_opaque = mock_run.call_args[0][0]
        filter_arg_o = [a for a in cmd_opaque if "showwavespic" in a][0]
        assert "split_channels=0" in filter_arg_o

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_empty_output_file_returns_none(self, mock_run, tmp_path):
        """Output file exists but is empty -> None."""
        out = tmp_path / "wave.png"
        out.write_bytes(b"")  # empty

        mock_run.return_value = MagicMock(returncode=0)

        result = generate_waveform_png(Path("/fake/video.mp4"), output_path=out)
        assert result is None


# ---------------------------------------------------------------------------
# Waveform: generate_waveform_for_segment
# ---------------------------------------------------------------------------


class TestGenerateWaveformForSegment:
    """Tests for generate_waveform_for_segment."""

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        """5. Segment waveform success: file is created."""
        out = tmp_path / "seg.png"
        out.write_bytes(b"\x89PNG seg")

        mock_run.return_value = MagicMock(returncode=0)

        result = generate_waveform_for_segment(
            Path("/fake/video.mp4"), start=10.0, end=15.0, output_path=out
        )
        assert result == out
        cmd = mock_run.call_args[0][0]
        assert "-ss" in cmd
        assert "-t" in cmd

    def test_duration_lte_zero_returns_none(self):
        """6. Duration <= 0 returns None without calling ffmpeg."""
        result = generate_waveform_for_segment(
            Path("/fake/video.mp4"), start=10.0, end=10.0
        )
        assert result is None

        result2 = generate_waveform_for_segment(
            Path("/fake/video.mp4"), start=15.0, end=10.0
        )
        assert result2 is None


# ---------------------------------------------------------------------------
# Waveform: get_audio_peaks
# ---------------------------------------------------------------------------


class TestGetAudioPeaks:
    """Tests for get_audio_peaks."""

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_parses_db_values(self, mock_run):
        """7. Parses dB values and converts to linear scale."""
        # -20 dB -> 10^(-20/20) = 10^(-1) = 0.1
        # -6 dB -> 10^(-6/20) ≈ 0.501
        mock_run.return_value = MagicMock(
            returncode=0, stdout="-20.0\n-6.0\n0.0\n"
        )

        peaks = get_audio_peaks(Path("/fake/video.mp4"))
        assert len(peaks) == 3
        assert abs(peaks[0] - 0.1) < 0.001
        assert abs(peaks[1] - 10 ** (-6 / 20)) < 0.001
        assert peaks[2] == 1.0  # 0 dB -> 1.0, capped at 1.0

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_returns_empty_on_error(self, mock_run):
        """8. Returns [] when ffprobe fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        assert get_audio_peaks(Path("/fake/video.mp4")) == []

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_clips_to_num_samples(self, mock_run):
        """9. Output is clipped to num_samples."""
        lines = "\n".join(["-10.0"] * 100)
        mock_run.return_value = MagicMock(returncode=0, stdout=lines)

        peaks = get_audio_peaks(Path("/fake/video.mp4"), num_samples=5)
        assert len(peaks) == 5

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_very_low_db_becomes_zero(self, mock_run):
        """Values below -60 dB map to 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="-80.0\n-61.0\n")

        peaks = get_audio_peaks(Path("/fake/video.mp4"))
        assert peaks == [0, 0]

    @patch("video_censor.audio.waveform.subprocess.run")
    def test_exception_returns_empty(self, mock_run):
        """General exception returns []."""
        mock_run.side_effect = Exception("boom")
        assert get_audio_peaks(Path("/fake/video.mp4")) == []


# ---------------------------------------------------------------------------
# SubtitleTrack dataclass
# ---------------------------------------------------------------------------


class TestSubtitleTrack:
    """Tests for SubtitleTrack properties."""

    def test_is_text_based_for_various_codecs(self):
        """10. is_text_based returns True for text codecs, False for bitmap."""
        text_codecs = ["subrip", "ass", "ssa", "mov_text", "webvtt", "srt", "text"]
        bitmap_codecs = ["hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle"]

        for codec in text_codecs:
            track = SubtitleTrack(0, codec, "eng", None, False, False)
            assert track.is_text_based is True, f"{codec} should be text-based"

        for codec in bitmap_codecs:
            track = SubtitleTrack(0, codec, "eng", None, False, False)
            assert track.is_text_based is False, f"{codec} should NOT be text-based"

    def test_is_english_for_various_languages(self):
        """11. is_english for eng, en, english, spa, None."""
        for lang in ("eng", "en", "english", "ENG", "En"):
            track = SubtitleTrack(0, "subrip", lang, None, False, False)
            assert track.is_english is True, f"{lang} should be English"

        for lang in ("spa", "fre", "jpn"):
            track = SubtitleTrack(0, "subrip", lang, None, False, False)
            assert track.is_english is False, f"{lang} should not be English"

        track_none = SubtitleTrack(0, "subrip", None, None, False, False)
        assert track_none.is_english is False


# ---------------------------------------------------------------------------
# detect_subtitle_tracks
# ---------------------------------------------------------------------------


class TestDetectSubtitleTracks:
    """Tests for detect_subtitle_tracks."""

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_parses_ffprobe_json(self, mock_run):
        """12. Parses ffprobe JSON output into SubtitleTrack objects."""
        ffprobe_data = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "subrip",
                    "tags": {"language": "eng", "title": "English"},
                    "disposition": {"forced": 0, "default": 1},
                },
                {
                    "index": 3,
                    "codec_name": "ass",
                    "tags": {"language": "spa"},
                    "disposition": {"forced": 0, "default": 0},
                },
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_data)
        )

        tracks = detect_subtitle_tracks(Path("/fake/video.mkv"))
        assert len(tracks) == 2
        assert tracks[0].index == 2
        assert tracks[0].codec == "subrip"
        assert tracks[0].language == "eng"
        assert tracks[0].title == "English"
        assert tracks[0].default is True
        assert tracks[0].forced is False
        assert tracks[1].language == "spa"

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_returns_empty_on_error(self, mock_run):
        """13. Returns [] when ffprobe raises CalledProcessError."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe", stderr="err")

        assert detect_subtitle_tracks(Path("/fake/video.mkv")) == []

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_returns_empty_on_bad_json(self, mock_run):
        """Returns [] on invalid JSON output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")

        assert detect_subtitle_tracks(Path("/fake/video.mkv")) == []


# ---------------------------------------------------------------------------
# find_best_english_track
# ---------------------------------------------------------------------------


class TestFindBestEnglishTrack:
    """Tests for find_best_english_track."""

    def test_priority_forced_over_default_over_text_over_bitmap(self):
        """14. Forced+text > default+text > text > bitmap."""
        forced_text = SubtitleTrack(1, "subrip", "eng", None, forced=True, default=False)
        default_text = SubtitleTrack(2, "subrip", "eng", None, forced=False, default=True)
        plain_text = SubtitleTrack(3, "ass", "eng", None, forced=False, default=False)
        bitmap = SubtitleTrack(4, "hdmv_pgs_subtitle", "eng", None, forced=False, default=False)

        # All present: forced wins
        assert find_best_english_track([bitmap, plain_text, default_text, forced_text]) == forced_text

        # Without forced: default wins
        assert find_best_english_track([bitmap, plain_text, default_text]) == default_text

        # Without forced or default: plain text wins
        assert find_best_english_track([bitmap, plain_text]) == plain_text

        # Only bitmap: still returned as fallback
        assert find_best_english_track([bitmap]) == bitmap

    def test_no_english_returns_none(self):
        """15. Returns None when no English track exists."""
        spa = SubtitleTrack(0, "subrip", "spa", None, False, False)
        fre = SubtitleTrack(1, "subrip", "fre", None, False, False)

        assert find_best_english_track([spa, fre]) is None
        assert find_best_english_track([]) is None


# ---------------------------------------------------------------------------
# extract_english_subtitles
# ---------------------------------------------------------------------------


class TestExtractEnglishSubtitles:
    """Tests for extract_english_subtitles."""

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        """16. Successful extraction returns output path."""
        ffprobe_data = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "subrip",
                    "tags": {"language": "eng"},
                    "disposition": {"forced": 0, "default": 1},
                }
            ]
        }
        # First call: ffprobe (detect_subtitle_tracks with check=True)
        # Second call: ffmpeg (extract with check=True)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(ffprobe_data)),
            MagicMock(returncode=0),
        ]

        out = tmp_path / "subs.srt"
        result = extract_english_subtitles(Path("/fake/video.mkv"), out)
        assert result == out
        assert mock_run.call_count == 2

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_no_tracks_returns_none(self, mock_run):
        """17. Returns None if no subtitle tracks found."""
        ffprobe_data = {"streams": []}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_data)
        )

        result = extract_english_subtitles(
            Path("/fake/video.mkv"), Path("/tmp/subs.srt")
        )
        assert result is None

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_bitmap_track_returns_none(self, mock_run):
        """18. Returns None for bitmap-only English track."""
        ffprobe_data = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "hdmv_pgs_subtitle",
                    "tags": {"language": "eng"},
                    "disposition": {"forced": 0, "default": 1},
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_data)
        )

        result = extract_english_subtitles(
            Path("/fake/video.mkv"), Path("/tmp/subs.srt")
        )
        assert result is None

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_specified_track_not_found_returns_none(self, mock_run):
        """Returns None when specified track_index doesn't match any track."""
        ffprobe_data = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "subrip",
                    "tags": {"language": "eng"},
                    "disposition": {"forced": 0, "default": 0},
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_data)
        )

        result = extract_english_subtitles(
            Path("/fake/video.mkv"), Path("/tmp/subs.srt"), track_index=99
        )
        assert result is None


# ---------------------------------------------------------------------------
# has_english_subtitles
# ---------------------------------------------------------------------------


class TestHasEnglishSubtitles:
    """Tests for has_english_subtitles."""

    @patch("video_censor.subtitles.extractor.subprocess.run")
    def test_delegates_correctly(self, mock_run):
        """19. Returns True when English track exists, False otherwise."""
        # Has English
        ffprobe_eng = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "subrip",
                    "tags": {"language": "eng"},
                    "disposition": {"forced": 0, "default": 0},
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_eng)
        )
        assert has_english_subtitles(Path("/fake/video.mkv")) is True

        # No English
        ffprobe_spa = {
            "streams": [
                {
                    "index": 2,
                    "codec_name": "subrip",
                    "tags": {"language": "spa"},
                    "disposition": {"forced": 0, "default": 0},
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_spa)
        )
        assert has_english_subtitles(Path("/fake/video.mkv")) is False

        # No tracks at all
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe", stderr="err")
        assert has_english_subtitles(Path("/fake/video.mkv")) is False
