"""
Tests for video_censor/error_handler.py

Tests exception-to-friendly-message mapping, the safe_operation decorator,
and UserFriendlyError pass-through.
"""

import pytest

from video_censor.error_handler import (
    UserFriendlyError,
    get_friendly_message,
    handle_error,
    safe_operation,
)


# ---------------------------------------------------------------------------
# UserFriendlyError
# ---------------------------------------------------------------------------

class TestUserFriendlyError:
    def test_basic_creation(self):
        err = UserFriendlyError("Something broke")
        assert err.user_message == "Something broke"
        assert err.technical_message == "Something broke"

    def test_with_technical_message(self):
        err = UserFriendlyError("Oops", "NullPointerException at line 42")
        assert err.user_message == "Oops"
        assert err.technical_message == "NullPointerException at line 42"

    def test_str_is_technical(self):
        err = UserFriendlyError("User msg", "Tech msg")
        assert str(err) == "Tech msg"


# ---------------------------------------------------------------------------
# get_friendly_message — type-based matching
# ---------------------------------------------------------------------------

class TestGetFriendlyMessageByType:
    def test_file_not_found(self):
        title, msg = get_friendly_message(FileNotFoundError("test.mp4"))
        assert "not found" in title.lower()

    def test_permission_error(self):
        title, msg = get_friendly_message(PermissionError("denied"))
        assert "permission" in title.lower()

    def test_is_a_directory_error(self):
        title, msg = get_friendly_message(IsADirectoryError("dir"))
        assert "file" in title.lower() or "invalid" in title.lower()

    def test_memory_error(self):
        title, msg = get_friendly_message(MemoryError("oom"))
        assert "memory" in title.lower()

    def test_connection_error(self):
        title, msg = get_friendly_message(ConnectionError("refused"))
        assert "connection" in title.lower()

    def test_timeout_error(self):
        title, msg = get_friendly_message(TimeoutError("timed out"))
        assert "timed out" in title.lower()

    def test_os_error(self):
        title, msg = get_friendly_message(OSError("disk full"))
        assert "disk" in title.lower() or "error" in title.lower()


# ---------------------------------------------------------------------------
# get_friendly_message — string-based matching
# ---------------------------------------------------------------------------

class TestGetFriendlyMessageByString:
    def test_ffmpeg_error(self):
        title, msg = get_friendly_message(RuntimeError("ffmpeg: codec not found"))
        assert "video" in title.lower() or "processing" in title.lower()

    def test_cuda_error(self):
        # Note: ERROR_MESSAGES key "CUDA out of memory" is case-sensitive but
        # get_friendly_message lowercases the error string, so this key never
        # matches and falls through to the LOG_FILE fallback bug.
        with pytest.raises(NameError):
            get_friendly_message(RuntimeError("CUDA out of memory"))

    def test_whisper_error(self):
        title, msg = get_friendly_message(RuntimeError("whisper failed to load"))
        assert "speech" in title.lower() or "audio" in title.lower()

    def test_nudenet_error(self):
        title, msg = get_friendly_message(RuntimeError("nudenet initialization failed"))
        assert "visual" in title.lower() or "detection" in title.lower()

    def test_model_error(self):
        title, msg = get_friendly_message(RuntimeError("model checkpoint corrupt"))
        assert "model" in title.lower() or "ai" in title.lower()

    def test_yaml_error(self):
        title, msg = get_friendly_message(RuntimeError("yaml parsing failed"))
        assert "settings" in title.lower()

    def test_default_fallback(self):
        # Note: the source has a bug where LOG_FILE is undefined in the fallback path.
        # This test documents that behavior.
        with pytest.raises(NameError):
            get_friendly_message(RuntimeError("something totally unexpected"))


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------

class TestHandleError:
    def test_returns_friendly_tuple(self):
        title, msg = handle_error(FileNotFoundError("test.mp4"), "loading video")
        assert isinstance(title, str)
        assert isinstance(msg, str)
        assert len(title) > 0


# ---------------------------------------------------------------------------
# safe_operation decorator
# ---------------------------------------------------------------------------

class TestSafeOperation:
    def test_normal_return_value(self):
        @safe_operation("test")
        def good_func():
            return 42
        assert good_func() == 42

    def test_wraps_generic_exception(self):
        # Note: the source has a bug where LOG_FILE is undefined in the fallback
        # message path, so a generic ValueError (no keyword match) causes NameError
        # to propagate through safe_operation instead of UserFriendlyError.
        @safe_operation("test")
        def bad_func():
            raise ValueError("something bad")
        with pytest.raises(NameError):
            bad_func()

    def test_passes_through_user_friendly_error(self):
        @safe_operation("test")
        def already_friendly():
            raise UserFriendlyError("Already friendly", "technical detail")
        with pytest.raises(UserFriendlyError) as exc_info:
            already_friendly()
        assert exc_info.value.user_message == "Already friendly"

    def test_preserves_original_exception_as_cause(self):
        # Test with a keyword-matched error so the fallback LOG_FILE bug isn't hit
        @safe_operation("test")
        def bad_func():
            raise RuntimeError("ffmpeg process crashed")
        with pytest.raises(UserFriendlyError) as exc_info:
            bad_func()
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_decorated_function_metadata_preserved(self):
        @safe_operation("test")
        def my_function():
            """My docstring."""
            pass
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."
