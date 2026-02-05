"""
Tests for video_censor/queue.py

Tests QueueItem state transitions, progress tracking, ProcessingQueue
management, and state persistence.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from video_censor.preferences import ContentFilterSettings
from video_censor.queue import QueueItem, ProcessingQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(**overrides) -> QueueItem:
    defaults = dict(
        input_path=Path("/tmp/video.mp4"),
        output_path=Path("/tmp/video_censored.mp4"),
        filters=ContentFilterSettings(),
    )
    defaults.update(overrides)
    return QueueItem(**defaults)


# ---------------------------------------------------------------------------
# QueueItem — properties and state transitions
# ---------------------------------------------------------------------------

class TestQueueItemProperties:
    def test_default_status_is_pending(self):
        item = _make_item()
        assert item.status == "pending"
        assert item.is_pending

    def test_filename_from_path(self):
        item = _make_item(input_path=Path("/media/My Movie.mp4"))
        assert item.filename == "My Movie.mp4"

    def test_is_processing_statuses(self):
        for status in ("processing", "analyzing", "exporting"):
            item = _make_item(status=status)
            assert item.is_processing

    def test_is_finished_covers_terminal_states(self):
        for status in ("complete", "error", "cancelled"):
            item = _make_item(status=status)
            assert item.is_finished

    def test_is_scheduled(self):
        item = _make_item(status="scheduled")
        assert item.is_scheduled

    def test_not_finished_while_pending(self):
        assert not _make_item().is_finished


class TestQueueItemStateTransitions:
    def test_start_processing(self):
        item = _make_item()
        item.start_processing()
        assert item.status == "processing"
        assert item.started_at is not None
        assert item.progress == 0.0

    def test_update_progress_clamps(self):
        item = _make_item()
        item.update_progress(1.5, "Transcribing")
        assert item.progress == 1.0
        item.update_progress(-0.5)
        assert item.progress == 0.0

    def test_update_progress_sets_stage(self):
        item = _make_item()
        item.update_progress(0.3, "Detecting nudity")
        assert item.progress_stage == "Detecting nudity"

    def test_update_progress_preserves_stage_when_empty(self):
        item = _make_item()
        item.update_progress(0.3, "Stage A")
        item.update_progress(0.5)
        assert item.progress_stage == "Stage A"

    def test_complete(self):
        item = _make_item()
        item.start_processing()
        item.complete(summary={"cuts": 5})
        assert item.is_complete
        assert item.progress == 1.0
        assert item.summary == {"cuts": 5}
        assert item.completed_at is not None

    def test_fail(self):
        item = _make_item()
        item.fail("FFmpeg crashed")
        assert item.is_error
        assert item.error_message == "FFmpeg crashed"
        assert item.completed_at is not None

    def test_cancel(self):
        item = _make_item()
        item.cancel()
        assert item.status == "cancelled"
        assert item.is_finished

    def test_mark_review_ready(self):
        item = _make_item()
        item.mark_review_ready(Path("/tmp/analysis.json"))
        assert item.is_review_ready
        assert item.progress == 0.5
        assert item.analysis_path == Path("/tmp/analysis.json")


class TestQueueItemParallelProgress:
    def test_update_parallel_progress(self):
        item = _make_item()
        combined = item.update_parallel_progress(audio_pct=50, video_pct=50)
        assert item.audio_progress == 50.0
        assert item.video_progress == 50.0
        # Audio 20% weight, Video 30% weight → (50*0.2 + 50*0.3)/100 = 0.25
        assert abs(combined - 0.25) < 0.001

    def test_update_parallel_partial(self):
        item = _make_item()
        item.update_parallel_progress(audio_pct=100)
        assert item.audio_progress == 100.0
        assert item.video_progress == 0.0

    def test_full_parallel_progress(self):
        item = _make_item()
        combined = item.update_parallel_progress(audio_pct=100, video_pct=100)
        # (100*0.2 + 100*0.3)/100 = 0.5
        assert abs(combined - 0.5) < 0.001


class TestQueueItemDuration:
    def test_duration_str_seconds_only(self):
        item = _make_item()
        item.started_at = datetime(2025, 1, 1, 12, 0, 0)
        item.completed_at = datetime(2025, 1, 1, 12, 0, 45)
        assert item.duration_str == "45s"

    def test_duration_str_minutes(self):
        item = _make_item()
        item.started_at = datetime(2025, 1, 1, 12, 0, 0)
        item.completed_at = datetime(2025, 1, 1, 12, 3, 15)
        assert item.duration_str == "3m 15s"

    def test_duration_str_hours(self):
        item = _make_item()
        item.started_at = datetime(2025, 1, 1, 12, 0, 0)
        item.completed_at = datetime(2025, 1, 1, 14, 5, 30)
        assert item.duration_str == "2h 5m 30s"

    def test_duration_str_empty_without_times(self):
        assert _make_item().duration_str == ""


class TestQueueItemStatusDisplay:
    def test_pending_display(self):
        assert "Pending" in _make_item().status_display()

    def test_processing_with_stage(self):
        item = _make_item()
        item.start_processing()
        item.update_progress(0.42, "Detecting profanity")
        display = item.status_display()
        assert "42%" in display
        assert "Detecting profanity" in display

    def test_complete_display(self):
        item = _make_item()
        item.started_at = datetime(2025, 1, 1, 12, 0, 0)
        item.completed_at = datetime(2025, 1, 1, 12, 1, 0)
        item.status = "complete"
        item.progress = 1.0
        display = item.status_display()
        assert "Complete" in display
        assert "1m 0s" in display

    def test_error_display(self):
        item = _make_item(status="error")
        assert "Error" in item.status_display()

    def test_cancelled_display(self):
        item = _make_item(status="cancelled")
        assert "Cancelled" in item.status_display()

    def test_review_ready_display(self):
        item = _make_item(status="review_ready")
        assert "Review" in item.status_display()

    def test_scheduled_display(self):
        item = _make_item(status="scheduled", scheduled_time=datetime(2025, 1, 1, 14, 30))
        display = item.status_display()
        assert "Scheduled" in display

    def test_filter_summary_delegates(self):
        item = _make_item()
        # Should not raise
        summary = item.filter_summary()
        assert isinstance(summary, str)


# ---------------------------------------------------------------------------
# ProcessingQueue
# ---------------------------------------------------------------------------

class TestProcessingQueue:
    def test_add_and_get(self):
        q = ProcessingQueue()
        item = _make_item(id="abc")
        q.add(item)
        assert q.get("abc") is item

    def test_get_missing_returns_none(self):
        q = ProcessingQueue()
        assert q.get("nonexistent") is None

    def test_remove(self):
        q = ProcessingQueue()
        item = _make_item(id="xyz")
        q.add(item)
        assert q.remove("xyz") is True
        assert q.get("xyz") is None

    def test_remove_missing_returns_false(self):
        q = ProcessingQueue()
        assert q.remove("nope") is False

    def test_get_next_pending(self):
        q = ProcessingQueue()
        item1 = _make_item(id="a")
        item2 = _make_item(id="b")
        q.add(item1)
        q.add(item2)
        assert q.get_next_pending().id == "a"

    def test_get_next_pending_skips_processing(self):
        q = ProcessingQueue()
        item1 = _make_item(id="a")
        item1.start_processing()
        item2 = _make_item(id="b")
        q.add(item1)
        q.add(item2)
        assert q.get_next_pending().id == "b"

    def test_get_next_pending_empty(self):
        q = ProcessingQueue()
        assert q.get_next_pending() is None

    def test_get_current_processing(self):
        q = ProcessingQueue()
        item = _make_item(id="x")
        item.start_processing()
        q.add(item)
        assert q.get_current_processing().id == "x"

    def test_get_current_processing_none(self):
        q = ProcessingQueue()
        q.add(_make_item())
        assert q.get_current_processing() is None


class TestProcessingQueueCounts:
    def test_pending_count(self):
        q = ProcessingQueue()
        q.add(_make_item())
        q.add(_make_item())
        assert q.pending_count == 2

    def test_processing_count(self):
        q = ProcessingQueue()
        item = _make_item()
        item.start_processing()
        q.add(item)
        assert q.processing_count == 1

    def test_complete_count(self):
        q = ProcessingQueue()
        item = _make_item()
        item.complete()
        q.add(item)
        assert q.complete_count == 1

    def test_error_count(self):
        q = ProcessingQueue()
        item = _make_item()
        item.fail("oops")
        q.add(item)
        assert q.error_count == 1

    def test_items_returns_copy(self):
        q = ProcessingQueue()
        q.add(_make_item())
        items = q.items
        items.clear()
        assert len(q.items) == 1


class TestProcessingQueueManagement:
    def test_clear_completed(self):
        q = ProcessingQueue()
        done = _make_item(id="done")
        done.complete()
        pending = _make_item(id="pending")
        q.add(done)
        q.add(pending)
        removed = q.clear_completed()
        assert removed == 1
        assert len(q.items) == 1
        assert q.items[0].id == "pending"

    def test_clear_completed_removes_errors_and_cancelled(self):
        q = ProcessingQueue()
        err = _make_item()
        err.fail("x")
        canc = _make_item()
        canc.cancel()
        q.add(err)
        q.add(canc)
        removed = q.clear_completed()
        assert removed == 2

    def test_clear_all(self):
        q = ProcessingQueue()
        q.add(_make_item())
        q.add(_make_item())
        q.clear_all()
        assert q.is_empty()

    def test_is_empty(self):
        q = ProcessingQueue()
        assert q.is_empty()
        q.add(_make_item())
        assert not q.is_empty()

    def test_has_pending_work(self):
        q = ProcessingQueue()
        assert not q.has_pending_work()
        q.add(_make_item())
        assert q.has_pending_work()

    def test_has_pending_work_processing(self):
        q = ProcessingQueue()
        item = _make_item()
        item.start_processing()
        q.add(item)
        assert q.has_pending_work()


class TestProcessingQueuePersistence:
    def test_save_and_load_roundtrip(self):
        q = ProcessingQueue()
        item = _make_item(id="test1", profile_name="Family")
        q.add(item)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = Path(f.name)

        try:
            q.save_state(filepath)
            assert filepath.exists()

            q2 = ProcessingQueue()
            count = q2.load_state(filepath)
            assert count == 1
            restored = q2.items[0]
            assert restored.id == "test1"
            assert restored.profile_name == "Family"
        finally:
            filepath.unlink(missing_ok=True)

    def test_load_resets_stuck_processing(self):
        """Items stuck in 'processing' should be reset to 'pending' on load."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = Path(f.name)
            json.dump([{
                "id": "stuck",
                "input_path": "/tmp/v.mp4",
                "output_path": "/tmp/v_out.mp4",
                "profile_name": "Default",
                "status": "processing",
                "filters": {
                    "filter_language": True,
                    "filter_sexual_content": True,
                    "filter_nudity": True,
                    "filter_romance_level": 0,
                    "filter_violence_level": 0,
                    "filter_mature_themes": False,
                    "custom_block_phrases": [],
                    "safe_cover_enabled": False,
                },
            }], f)

        try:
            q = ProcessingQueue()
            q.load_state(filepath)
            item = q.items[0]
            assert item.status == "pending"
        finally:
            filepath.unlink(missing_ok=True)

    def test_load_nonexistent_file_returns_zero(self):
        q = ProcessingQueue()
        assert q.load_state(Path("/nonexistent/path.json")) == 0

    def test_save_only_saves_pending_and_processing(self):
        q = ProcessingQueue()
        pending = _make_item(id="p")
        done = _make_item(id="d")
        done.complete()
        q.add(pending)
        q.add(done)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = Path(f.name)

        try:
            q.save_state(filepath)
            data = json.loads(filepath.read_text())
            assert len(data) == 1
            assert data[0]["id"] == "p"
        finally:
            filepath.unlink(missing_ok=True)

    def test_load_corrupt_file_returns_zero(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("not json{{{")
            filepath = Path(f.name)

        try:
            q = ProcessingQueue()
            assert q.load_state(filepath) == 0
        finally:
            filepath.unlink(missing_ok=True)
