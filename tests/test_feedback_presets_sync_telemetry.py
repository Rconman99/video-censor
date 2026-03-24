"""
Tests for feedback_processor, presets, sync, and telemetry modules.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from video_censor.feedback_processor import FeedbackItem, FeedbackProcessor, get_feedback_processor
from video_censor.presets import FilterPreset, PRESETS, get_preset, list_presets, apply_preset, get_preset_summary
from video_censor.sync import SyncResult, SyncManager
from video_censor.telemetry import SessionInfo, TelemetryClient, get_telemetry, track_error, APP_VERSION


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global singletons between tests to avoid cross-test pollution."""
    import video_censor.feedback_processor as fp
    import video_censor.telemetry as tm
    fp._processor = None
    tm._telemetry = None
    yield


# ---------------------------------------------------------------------------
# Presets Tests (10)
# ---------------------------------------------------------------------------

class TestPresets:
    def test_presets_has_five_entries(self):
        assert len(PRESETS) == 5

    def test_get_preset_by_name(self):
        preset = get_preset("family_friendly")
        assert preset is not None
        assert preset.name == "Family Friendly"

    def test_get_preset_with_spaces(self):
        preset = get_preset("Family Friendly")
        assert preset is not None
        assert preset.name == "Family Friendly"

    def test_get_preset_unknown_returns_none(self):
        assert get_preset("nonexistent_preset") is None

    def test_list_presets_returns_all(self):
        presets = list_presets()
        assert len(presets) == 5
        assert all(isinstance(p, FilterPreset) for p in presets)

    def test_apply_preset_modifies_config(self):
        """apply_preset should set attributes on config sub-objects."""
        config = MagicMock()
        config.profanity = MagicMock()
        config.nudity = MagicMock()
        config.sexual_content = MagicMock()

        # Ensure hasattr returns True for relevant keys
        config.profanity.enabled = None
        config.profanity.censor_mode = None
        config.profanity.context_aware = None
        config.nudity.threshold = None
        config.nudity.frame_interval = None
        config.sexual_content.enabled = None
        config.sexual_content.threshold = None

        apply_preset(config, "family_friendly")

        assert config.profanity.censor_mode == "beep"
        assert config.nudity.threshold == 0.6
        assert config.sexual_content.enabled is True

    def test_apply_preset_unknown_does_nothing(self):
        config = MagicMock()
        # Should not raise
        apply_preset(config, "totally_unknown")
        # Config should not have been touched via setattr for profanity/nudity/sexual_content
        config.profanity.assert_not_called()

    def test_get_preset_summary_returns_formatted_string(self):
        summary = get_preset_summary("family_friendly")
        assert "Family Friendly" in summary
        assert "Audio:" in summary
        assert "Visual:" in summary

    def test_get_preset_summary_unknown_returns_unknown(self):
        assert get_preset_summary("nonexistent") == "Unknown preset"

    def test_filter_preset_dataclass_fields(self):
        preset = FilterPreset(name="Test", description="A test", icon="T")
        assert preset.name == "Test"
        assert preset.description == "A test"
        assert preset.icon == "T"
        assert preset.settings == {}


# ---------------------------------------------------------------------------
# Feedback Tests (8)
# ---------------------------------------------------------------------------

class TestFeedback:
    def test_feedback_item_dataclass_fields(self):
        item = FeedbackItem(
            feedback_type="missed_profanity",
            video_title="Test Video",
            video_detection_id="abc-123",
            timestamp_start=10.0,
            timestamp_end=12.0,
            description="Missed a word",
            user_email="test@example.com",
        )
        assert item.feedback_type == "missed_profanity"
        assert item.video_title == "Test Video"
        assert item.video_detection_id == "abc-123"
        assert item.timestamp_start == 10.0
        assert item.timestamp_end == 12.0
        assert item.description == "Missed a word"
        assert item.user_email == "test@example.com"

    def test_feedback_item_default_email_is_none(self):
        item = FeedbackItem(
            feedback_type="custom",
            video_title="V",
            video_detection_id=None,
            timestamp_start=None,
            timestamp_end=None,
            description="desc",
        )
        assert item.user_email is None

    def test_process_feedback_not_available_returns_error(self):
        processor = FeedbackProcessor()
        # client property returns None by default (no cloud_db)
        with patch.object(type(processor), "client", new_callable=PropertyMock, return_value=None):
            result = processor.process_feedback(
                FeedbackItem("missed_profanity", "V", "id1", 1.0, 2.0, "desc")
            )
        assert result["status"] == "error"
        assert "not available" in result["message"].lower()

    def test_process_feedback_auto_fixable_calls_auto_fix(self):
        processor = FeedbackProcessor()
        mock_client = MagicMock()
        processor._client = mock_client

        item = FeedbackItem("missed_profanity", "V", "det-1", 5.0, 7.0, "missed word")
        result = processor.process_feedback(item)

        # _auto_fix inserts into feedback_queue
        mock_client.table.assert_any_call("feedback_queue")

    def test_process_feedback_non_auto_fixable_queues_for_review(self):
        processor = FeedbackProcessor()
        mock_client = MagicMock()
        processor._client = mock_client

        item = FeedbackItem("feature_request", "V", None, None, None, "Please add X")
        result = processor.process_feedback(item)

        mock_client.table.assert_any_call("admin_review_queue")
        assert result["status"] == "queued"

    def test_get_pending_fixes_not_available_returns_empty(self):
        processor = FeedbackProcessor()
        with patch.object(type(processor), "client", new_callable=PropertyMock, return_value=None):
            assert processor.get_pending_fixes() == []

    def test_get_stats_not_available(self):
        processor = FeedbackProcessor()
        with patch.object(type(processor), "client", new_callable=PropertyMock, return_value=None):
            stats = processor.get_stats()
        assert stats == {"available": False}

    def test_get_feedback_processor_returns_singleton(self):
        p1 = get_feedback_processor()
        p2 = get_feedback_processor()
        assert p1 is p2


# ---------------------------------------------------------------------------
# Sync Tests (5)
# ---------------------------------------------------------------------------

class TestSync:
    def test_sync_result_dataclass_defaults(self):
        result = SyncResult(success=True)
        assert result.success is True
        assert result.message == ""
        assert result.items_pushed == 0
        assert result.items_pulled == 0

    def test_sync_manager_is_configured_true(self):
        manager = SyncManager("https://example.supabase.co", "key123", "user1")
        assert manager.is_configured is True

    def test_sync_manager_is_configured_false_empty_url(self):
        manager = SyncManager("", "key123", "user1")
        assert manager.is_configured is False

    def test_sync_manager_is_configured_false_empty_key(self):
        manager = SyncManager("https://example.supabase.co", "", "user1")
        assert manager.is_configured is False

    def test_sync_manager_client_returns_none_when_supabase_not_installed(self):
        manager = SyncManager("https://example.supabase.co", "key123", "user1")
        with patch.dict("sys.modules", {"supabase": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'supabase'")):
                # Reset cached client
                manager._client = None
                assert manager.client is None


# ---------------------------------------------------------------------------
# Telemetry Tests (7)
# ---------------------------------------------------------------------------

class TestTelemetry:
    def test_session_info_post_init_sets_features_used(self):
        from datetime import datetime
        session = SessionInfo(session_id="abc", started_at=datetime.utcnow())
        assert session.features_used == []

    def test_start_session_creates_session(self):
        client = TelemetryClient(enabled=False)
        session_id = client.start_session()
        assert session_id is not None
        assert len(session_id) > 0
        assert client._session is not None
        assert client._session.session_id == session_id
        assert client._session.videos_processed == 0

    def test_track_video_processed_increments_counter(self):
        client = TelemetryClient(enabled=False)
        client.start_session()
        client.track_video_processed()
        client.track_video_processed()
        assert client._session.videos_processed == 2

    def test_track_video_processed_adds_unique_features(self):
        client = TelemetryClient(enabled=False)
        client.start_session()
        client.track_video_processed(features=["profanity", "nudity"])
        client.track_video_processed(features=["profanity", "violence"])
        assert sorted(client._session.features_used) == ["nudity", "profanity", "violence"]

    def test_telemetry_disabled_doesnt_call_client(self):
        client = TelemetryClient(enabled=False)
        mock_supabase = MagicMock()
        client._client = mock_supabase

        client.start_session()
        client.track_error("test", "msg")
        client.submit_feedback("det1", "false_positive")

        # Client table should never be called because enabled=False
        mock_supabase.table.assert_not_called()

    def test_get_telemetry_returns_singleton(self):
        t1 = get_telemetry()
        t2 = get_telemetry()
        assert t1 is t2

    def test_track_error_convenience_function(self):
        with patch("video_censor.telemetry.get_telemetry") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            track_error("render", "FFmpeg failed", {"file": "test.mp4"})
            mock_client.track_error.assert_called_once_with(
                "render", "FFmpeg failed", {"file": "test.mp4"}
            )
