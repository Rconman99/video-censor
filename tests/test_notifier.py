import pytest
from unittest.mock import patch, MagicMock
from video_censor.notifier import Notifier, get_notifier, _notifier
import video_censor.notifier as notifier_mod


@pytest.fixture(autouse=True)
def reset_global():
    notifier_mod._notifier = None
    yield
    notifier_mod._notifier = None


def _make_config(enabled=True, ntfy_topic=""):
    config = MagicMock()
    config.notifications.enabled = enabled
    config.notifications.ntfy_topic = ntfy_topic
    return config


class TestSend:
    def test_disabled_does_nothing(self):
        config = _make_config(enabled=False)
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification") as mac, \
             patch.object(n, "_send_ntfy_notification") as ntfy:
            n.send("Title", "msg")
            mac.assert_not_called()
            ntfy.assert_not_called()

    def test_enabled_calls_macos(self):
        config = _make_config(enabled=True)
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification") as mac, \
             patch.object(n, "_send_ntfy_notification") as ntfy:
            n.send("Title", "msg")
            mac.assert_called_once_with("Title", "msg")
            ntfy.assert_not_called()

    def test_with_ntfy_topic_sends_ntfy(self):
        config = _make_config(enabled=True, ntfy_topic="my_topic")
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification"), \
             patch.object(n, "_send_ntfy_notification") as ntfy:
            n.send("Title", "msg", priority="high")
            ntfy.assert_called_once_with("Title", "msg", "high")

    def test_without_ntfy_topic_skips_ntfy(self):
        config = _make_config(enabled=True, ntfy_topic="")
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification"), \
             patch.object(n, "_send_ntfy_notification") as ntfy:
            n.send("Title", "msg")
            ntfy.assert_not_called()

    def test_macos_exception_handled_gracefully(self):
        config = _make_config(enabled=True)
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification", side_effect=OSError("fail")):
            # Should not raise
            n.send("Title", "msg")

    def test_ntfy_exception_handled_gracefully(self):
        config = _make_config(enabled=True, ntfy_topic="topic")
        n = Notifier(config)
        with patch.object(n, "_send_macos_notification"), \
             patch.object(n, "_send_ntfy_notification", side_effect=Exception("fail")):
            # Should not raise
            n.send("Title", "msg")


class TestSendMacOS:
    @patch("video_censor.notifier.subprocess.run")
    def test_calls_osascript(self, mock_run):
        config = _make_config()
        n = Notifier(config)
        n._send_macos_notification("My Title", "My message")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert args[1] == "-e"
        assert "My Title" in args[2]
        assert "My message" in args[2]


class TestSendNtfy:
    @patch("video_censor.notifier.requests.post")
    def test_posts_to_correct_url_with_headers(self, mock_post):
        config = _make_config(ntfy_topic="test_topic")
        n = Notifier(config)
        n._send_ntfy_notification("Title", "body", "default")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["headers"]["Title"] == "Title"
        assert call_kwargs[1]["headers"]["Tags"] == "movie_camera"
        assert "Priority" not in call_kwargs[1]["headers"]
        assert "https://ntfy.sh/test_topic" in (call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", ""))

    @patch("video_censor.notifier.requests.post")
    def test_high_priority_when_priority_high(self, mock_post):
        config = _make_config(ntfy_topic="t")
        n = Notifier(config)
        n._send_ntfy_notification("Title", "body", "high")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Priority"] == "high"
        assert headers["Tags"] == "warning"

    @patch("video_censor.notifier.requests.post")
    def test_high_priority_when_error_in_title(self, mock_post):
        config = _make_config(ntfy_topic="t")
        n = Notifier(config)
        n._send_ntfy_notification("Error occurred", "body", "default")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Priority"] == "high"
        assert headers["Tags"] == "warning"


class TestGetNotifier:
    def test_creates_singleton(self):
        config = _make_config()
        result = get_notifier(config)
        assert isinstance(result, Notifier)
        assert notifier_mod._notifier is result

    def test_reuses_existing_instance(self):
        config = _make_config()
        first = get_notifier(config)
        second = get_notifier()
        assert first is second

    @patch("video_censor.notifier.Config.load")
    def test_loads_config_when_none(self, mock_load):
        mock_load.return_value = _make_config()
        result = get_notifier(None)
        mock_load.assert_called_once()
        assert isinstance(result, Notifier)
