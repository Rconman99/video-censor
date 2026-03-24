import pytest
from unittest.mock import patch, MagicMock
from video_censor.notifications import (
    send_notification, notify_video_complete, notify_video_failed,
    notify_batch_complete, notify_progress, notify_system,
    notify_processing_complete, notify_render_complete
)


# --- send_notification ---

@patch("video_censor.notifications.requests.post")
def test_send_notification_success(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    result = send_notification("my-topic", "Title", "Body")
    assert result is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://ntfy.sh/my-topic"
    assert kwargs["headers"]["Title"] == "Title"
    assert kwargs["headers"]["Priority"] == "default"
    assert kwargs["data"] == b"Body"
    assert kwargs["timeout"] == 10


@patch("video_censor.notifications.requests.post")
def test_send_notification_failure_non_200(mock_post):
    mock_post.return_value = MagicMock(status_code=500)
    result = send_notification("my-topic", "Title", "Body")
    assert result is False


def test_send_notification_empty_topic():
    result = send_notification("", "Title", "Body")
    assert result is False


@patch("video_censor.notifications.requests.post")
def test_send_notification_with_tags(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    result = send_notification("t", "T", "M", tags=["fire", "star"])
    assert result is True
    headers = mock_post.call_args[1]["headers"]
    assert headers["Tags"] == "fire,star"


@patch("video_censor.notifications.requests.post")
def test_send_notification_without_tags_no_header(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    send_notification("t", "T", "M")
    headers = mock_post.call_args[1]["headers"]
    assert "Tags" not in headers


@patch("video_censor.notifications.requests.post", side_effect=ConnectionError("timeout"))
def test_send_notification_handles_exception(mock_post):
    result = send_notification("t", "T", "M")
    assert result is False


# --- notify_video_complete ---

@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_video_complete_with_duration(mock_send):
    result = notify_video_complete("topic", "movie.mp4", duration="5m 30s")
    assert result is True
    mock_send.assert_called_once()
    assert mock_send.call_args[1]["message"] == "movie.mp4 (5m 30s)"
    assert mock_send.call_args[1]["tags"] == ["white_check_mark", "movie_camera"]


@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_video_complete_without_duration(mock_send):
    notify_video_complete("topic", "movie.mp4")
    assert mock_send.call_args[1]["message"] == "movie.mp4"


# --- notify_video_failed ---

@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_video_failed_with_error(mock_send):
    notify_video_failed("topic", "bad.mp4", error="Codec not found")
    assert mock_send.call_args[1]["message"] == "bad.mp4\nCodec not found"
    assert mock_send.call_args[1]["priority"] == "high"


@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_video_failed_without_error(mock_send):
    notify_video_failed("topic", "bad.mp4")
    assert mock_send.call_args[1]["message"] == "bad.mp4"


@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_video_failed_truncates_long_error(mock_send):
    long_error = "x" * 200
    notify_video_failed("topic", "bad.mp4", error=long_error)
    msg = mock_send.call_args[1]["message"]
    # Error portion should be truncated to 100 chars
    assert msg == f"bad.mp4\n{'x' * 100}"


# --- notify_batch_complete ---

@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_batch_complete_all_successful(mock_send):
    notify_batch_complete("topic", total=5, successful=5, failed=0)
    msg = mock_send.call_args[1]["message"]
    assert "All videos completed" in msg
    assert "5/5 successful" in msg


@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_batch_complete_some_failures(mock_send):
    notify_batch_complete("topic", total=5, successful=3, failed=2)
    msg = mock_send.call_args[1]["message"]
    assert "2 video(s) failed" in msg
    assert "3/5 successful" in msg


# --- notify_progress ---

@patch("video_censor.notifications.send_notification", return_value=True)
def test_notify_progress_formats_correctly(mock_send):
    notify_progress("topic", "clip.mp4", 75, "2m 10s")
    assert mock_send.call_args[1]["title"] == "\u23f3 75% Complete"
    assert mock_send.call_args[1]["message"] == "clip.mp4\nEst. time remaining: 2m 10s"
    assert mock_send.call_args[1]["priority"] == "low"


# --- notify_system ---

@patch("subprocess.run")
@patch("platform.system", return_value="Darwin")
def test_notify_system_darwin(mock_platform, mock_run):
    result = notify_system("Title", "Msg")
    assert result is True
    args = mock_run.call_args[0][0]
    assert args[0] == "osascript"
    assert args[1] == "-e"


@patch("subprocess.run")
@patch("platform.system", return_value="Windows")
def test_notify_system_windows(mock_platform, mock_run):
    result = notify_system("Title", "Msg")
    assert result is True
    args = mock_run.call_args[0][0]
    assert args[0] == "powershell"


@patch("subprocess.run")
@patch("platform.system", return_value="Linux")
def test_notify_system_linux(mock_platform, mock_run):
    result = notify_system("Title", "Msg")
    assert result is True
    mock_run.assert_called_once_with(["notify-send", "Title", "Msg"], check=False)


@patch("subprocess.run", side_effect=FileNotFoundError("not found"))
@patch("platform.system", return_value="Linux")
def test_notify_system_handles_exception(mock_platform, mock_run):
    result = notify_system("Title", "Msg")
    assert result is False


# --- notify_processing_complete ---

@patch("video_censor.notifications.notify_system")
def test_notify_processing_complete_success(mock_sys):
    notify_processing_complete("video.mp4", success=True)
    mock_sys.assert_called_once_with(
        title="\u2705 Processing Complete",
        message="video.mp4 is ready for review"
    )


@patch("video_censor.notifications.notify_system")
def test_notify_processing_complete_failure(mock_sys):
    notify_processing_complete("video.mp4", success=False)
    mock_sys.assert_called_once_with(
        title="\u274c Processing Failed",
        message="video.mp4 encountered an error"
    )


# --- notify_render_complete ---

@patch("video_censor.notifications.notify_system")
def test_notify_render_complete(mock_sys):
    notify_render_complete("video.mp4", "/output/dir/censored_video.mp4")
    mock_sys.assert_called_once_with(
        title="\U0001f3ac Export Complete",
        message="Saved: censored_video.mp4"
    )
