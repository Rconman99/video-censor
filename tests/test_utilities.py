import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from video_censor.first_run import FirstRunManager
from video_censor.video_info import get_video_info, VideoInfo, _format_duration, _format_size
import video_censor.recent_files as recent_files_mod
from video_censor.recent_files import get_recent_files, add_recent_file, clear_recent_files
from video_censor.file_utils import open_folder, reveal_in_finder, get_output_folder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def first_run_dir(tmp_path, monkeypatch):
    """Redirect FirstRunManager paths to tmp_path for isolation."""
    config_dir = tmp_path / ".videocensor"
    state_file = config_dir / "app_state.json"
    monkeypatch.setattr(FirstRunManager, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(FirstRunManager, "STATE_FILE", state_file)
    return config_dir, state_file


@pytest.fixture
def recent_dir(tmp_path, monkeypatch):
    """Redirect recent_files module paths to tmp_path for isolation."""
    config_dir = tmp_path / ".videocensor"
    recent_file = config_dir / "recent_files.json"
    monkeypatch.setattr(recent_files_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(recent_files_mod, "RECENT_FILE", recent_file)
    return config_dir, recent_file


# ---------------------------------------------------------------------------
# FirstRunManager tests
# ---------------------------------------------------------------------------

class TestFirstRunManager:
    def test_is_first_run_no_file(self, first_run_dir):
        """First run when state file does not exist."""
        assert FirstRunManager.is_first_run() is True

    def test_is_first_run_empty_file(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text("")
        assert FirstRunManager.is_first_run() is True

    def test_is_first_run_corrupted_file(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text("not valid json {{{")
        assert FirstRunManager.is_first_run() is True

    def test_is_first_run_setup_incomplete(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"setup_complete": False}))
        assert FirstRunManager.is_first_run() is True

    def test_is_first_run_setup_complete(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"setup_complete": True}))
        assert FirstRunManager.is_first_run() is False

    def test_mark_setup_complete(self, first_run_dir):
        config_dir, state_file = first_run_dir
        FirstRunManager.mark_setup_complete()
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["setup_complete"] is True
        assert data["setup_version"] == "1.0"

    def test_mark_setup_complete_preserves_existing(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"custom_key": "value"}))
        FirstRunManager.mark_setup_complete()
        data = json.loads(state_file.read_text())
        assert data["setup_complete"] is True
        assert data["custom_key"] == "value"

    def test_reset_first_run(self, first_run_dir):
        FirstRunManager.mark_setup_complete()
        assert FirstRunManager.is_first_run() is False
        FirstRunManager.reset_first_run()
        assert FirstRunManager.is_first_run() is True

    def test_reset_first_run_corrupted_deletes_file(self, first_run_dir):
        config_dir, state_file = first_run_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text("corrupted data!!!")
        FirstRunManager.reset_first_run()
        assert not state_file.exists()


# ---------------------------------------------------------------------------
# video_info tests
# ---------------------------------------------------------------------------

def _make_ffprobe_output(
    duration="120.5",
    size="50000000",
    width=1920,
    height=1080,
    codec="h264",
    fps="24000/1001",
    audio_codec="aac",
    include_video=True,
    include_audio=True,
):
    """Build a fake ffprobe JSON output."""
    streams = []
    if include_video:
        streams.append({
            "codec_type": "video",
            "codec_name": codec,
            "width": width,
            "height": height,
            "r_frame_rate": fps,
        })
    if include_audio:
        streams.append({
            "codec_type": "audio",
            "codec_name": audio_codec,
        })
    return json.dumps({
        "streams": streams,
        "format": {"duration": duration, "size": size},
    })


class TestFormatDuration:
    def test_short_duration(self):
        assert _format_duration(65) == "1:05"

    def test_zero(self):
        assert _format_duration(0) == "0:00"

    def test_hours(self):
        assert _format_duration(3661) == "1:01:01"

    def test_minutes_only(self):
        assert _format_duration(600) == "10:00"


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500.0 B"

    def test_megabytes(self):
        result = _format_size(5 * 1024 * 1024)
        assert result == "5.0 MB"

    def test_gigabytes(self):
        result = _format_size(2 * 1024 ** 3)
        assert result == "2.0 GB"


class TestGetVideoInfo:
    @patch("video_censor.video_info.subprocess.run")
    def test_basic_video(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=_make_ffprobe_output(),
            returncode=0,
        )
        info = get_video_info("/fake/video.mp4")
        assert info is not None
        assert isinstance(info, VideoInfo)
        assert info.width == 1920
        assert info.height == 1080
        assert info.has_audio is True
        assert info.audio_codec == "aac"
        assert info.duration == 120.5
        assert info.fps == pytest.approx(23.98, abs=0.01)

    @patch("video_censor.video_info.subprocess.run")
    def test_no_video_stream_returns_none(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=_make_ffprobe_output(include_video=False),
            returncode=0,
        )
        assert get_video_info("/fake/audio_only.mp3") is None

    @patch("video_censor.video_info.subprocess.run")
    def test_no_audio_stream(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=_make_ffprobe_output(include_audio=False),
            returncode=0,
        )
        info = get_video_info("/fake/silent.mp4")
        assert info is not None
        assert info.has_audio is False
        assert info.audio_codec is None

    @patch("video_censor.video_info.subprocess.run")
    def test_ffprobe_error_returns_none(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ffprobe not found")
        assert get_video_info("/fake/video.mp4") is None

    @patch("video_censor.video_info.subprocess.run")
    def test_integer_fps(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=_make_ffprobe_output(fps="30"),
            returncode=0,
        )
        info = get_video_info("/fake/video.mp4")
        assert info.fps == 30.0


# ---------------------------------------------------------------------------
# recent_files tests
# ---------------------------------------------------------------------------

class TestRecentFiles:
    def test_get_recent_files_empty(self, recent_dir):
        assert get_recent_files() == []

    def test_add_and_get(self, recent_dir, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        add_recent_file(str(video))
        result = get_recent_files()
        assert len(result) == 1
        assert result[0]["name"] == "video.mp4"

    def test_add_with_custom_name(self, recent_dir, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        add_recent_file(str(video), name="My Movie")
        result = get_recent_files()
        assert result[0]["name"] == "My Movie"

    def test_deduplication(self, recent_dir, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        add_recent_file(str(video))
        add_recent_file(str(video))
        result = get_recent_files()
        assert len(result) == 1

    def test_max_limit(self, recent_dir, tmp_path):
        for i in range(15):
            f = tmp_path / f"video_{i}.mp4"
            f.touch()
            add_recent_file(str(f))
        result = get_recent_files()
        assert len(result) == 10

    def test_filters_nonexistent(self, recent_dir, tmp_path):
        """Files that no longer exist are excluded from results."""
        config_dir, recent_file = recent_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        existing = tmp_path / "exists.mp4"
        existing.touch()
        data = [
            {"path": str(existing), "name": "exists.mp4", "opened_at": "2026-01-01"},
            {"path": "/gone/deleted.mp4", "name": "deleted.mp4", "opened_at": "2026-01-01"},
        ]
        recent_file.write_text(json.dumps(data))
        result = get_recent_files()
        assert len(result) == 1
        assert result[0]["name"] == "exists.mp4"

    def test_clear_recent_files(self, recent_dir, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        add_recent_file(str(video))
        clear_recent_files()
        assert get_recent_files() == []

    def test_clear_no_file(self, recent_dir):
        """Clearing when no file exists should not raise."""
        clear_recent_files()


# ---------------------------------------------------------------------------
# file_utils tests
# ---------------------------------------------------------------------------

class TestOpenFolder:
    @patch("video_censor.file_utils.platform.system", return_value="Darwin")
    @patch("video_censor.file_utils.subprocess.run")
    def test_open_folder_macos(self, mock_run, _mock_sys, tmp_path):
        folder = tmp_path / "output"
        folder.mkdir()
        open_folder(folder)
        mock_run.assert_called_once_with(["open", str(folder)])

    @patch("video_censor.file_utils.platform.system", return_value="Linux")
    @patch("video_censor.file_utils.subprocess.run")
    def test_open_folder_linux(self, mock_run, _mock_sys, tmp_path):
        folder = tmp_path / "output"
        folder.mkdir()
        open_folder(folder)
        mock_run.assert_called_once_with(["xdg-open", str(folder)])

    @patch("video_censor.file_utils.platform.system", return_value="Windows")
    @patch("video_censor.file_utils.subprocess.run")
    def test_open_folder_windows(self, mock_run, _mock_sys, tmp_path):
        folder = tmp_path / "output"
        folder.mkdir()
        open_folder(folder)
        mock_run.assert_called_once_with(["explorer", str(folder)])

    @patch("video_censor.file_utils.platform.system", return_value="Linux")
    @patch("video_censor.file_utils.subprocess.run")
    def test_open_folder_nonexistent_falls_back_to_home(self, mock_run, _mock_sys):
        open_folder("/nonexistent/path")
        called_path = mock_run.call_args[0][0][1]
        assert called_path == str(Path.home())


class TestRevealInFinder:
    @patch("video_censor.file_utils.platform.system", return_value="Darwin")
    @patch("video_censor.file_utils.subprocess.run")
    def test_reveal_macos(self, mock_run, _mock_sys, tmp_path):
        f = tmp_path / "video.mp4"
        f.touch()
        reveal_in_finder(f)
        mock_run.assert_called_once_with(["open", "-R", str(f)])

    @patch("video_censor.file_utils.platform.system", return_value="Windows")
    @patch("video_censor.file_utils.subprocess.run")
    def test_reveal_windows(self, mock_run, _mock_sys, tmp_path):
        f = tmp_path / "video.mp4"
        f.touch()
        reveal_in_finder(f)
        mock_run.assert_called_once_with(["explorer", "/select,", str(f)])


class TestGetOutputFolder:
    def test_returns_movies_if_exists(self, monkeypatch, tmp_path):
        movies = tmp_path / "Movies"
        movies.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        assert get_output_folder() == movies

    def test_returns_videos_if_no_movies(self, monkeypatch, tmp_path):
        videos = tmp_path / "Videos"
        videos.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        assert get_output_folder() == videos

    def test_returns_desktop_if_no_videos(self, monkeypatch, tmp_path):
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        assert get_output_folder() == desktop

    def test_returns_home_as_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        assert get_output_folder() == tmp_path
