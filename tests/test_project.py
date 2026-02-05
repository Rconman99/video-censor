"""
Tests for video_censor/editing/project.py

Tests project file creation, save/load roundtrip, edit management,
undo/redo, file fingerprinting, and frame helpers.
"""

import json
import tempfile
from pathlib import Path

import pytest

from video_censor.editing.intervals import EditDecision, Action
from video_censor.editing.project import (
    compute_file_fingerprint,
    UndoRedoStack,
    ProjectFile,
    PROJECT_VERSION,
)


# ---------------------------------------------------------------------------
# compute_file_fingerprint
# ---------------------------------------------------------------------------

class TestComputeFileFingerprint:
    def test_fingerprint_of_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world" * 100)
            path = Path(f.name)
        try:
            fp = compute_file_fingerprint(path)
            assert isinstance(fp, str)
            assert len(fp) == 64  # SHA256 hex digest
        finally:
            path.unlink()

    def test_same_content_same_fingerprint(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(b"identical content")
            p1 = Path(f1.name)
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(b"identical content")
            p2 = Path(f2.name)
        try:
            assert compute_file_fingerprint(p1) == compute_file_fingerprint(p2)
        finally:
            p1.unlink()
            p2.unlink()

    def test_different_content_different_fingerprint(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(b"content A")
            p1 = Path(f1.name)
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(b"content B")
            p2 = Path(f2.name)
        try:
            assert compute_file_fingerprint(p1) != compute_file_fingerprint(p2)
        finally:
            p1.unlink()
            p2.unlink()

    def test_nonexistent_file_returns_empty(self):
        assert compute_file_fingerprint(Path("/nonexistent/file")) == ""


# ---------------------------------------------------------------------------
# UndoRedoStack
# ---------------------------------------------------------------------------

class TestUndoRedoStack:
    def _make_edit(self, **kwargs):
        defaults = dict(
            source_start=0.0,
            source_end=1.0,
            action=Action.CUT,
            reason="test",
        )
        defaults.update(kwargs)
        return EditDecision(**defaults)

    def test_push_and_undo(self):
        stack = UndoRedoStack()
        edit = self._make_edit()
        stack.push("add", edit)
        assert stack.can_undo
        op = stack.undo()
        assert op is not None
        assert op["action"] == "add"

    def test_undo_and_redo(self):
        stack = UndoRedoStack()
        edit = self._make_edit()
        stack.push("add", edit)
        stack.undo()
        assert stack.can_redo
        op = stack.redo()
        assert op is not None
        assert op["action"] == "add"

    def test_push_clears_redo(self):
        stack = UndoRedoStack()
        stack.push("add", self._make_edit())
        stack.undo()
        assert stack.can_redo
        stack.push("add", self._make_edit())
        assert not stack.can_redo

    def test_max_history_enforced(self):
        stack = UndoRedoStack(max_history=5)
        for i in range(10):
            stack.push("add", self._make_edit())
        assert len(stack.undo_stack) == 5

    def test_empty_undo_returns_none(self):
        assert UndoRedoStack().undo() is None

    def test_empty_redo_returns_none(self):
        assert UndoRedoStack().redo() is None

    def test_clear(self):
        stack = UndoRedoStack()
        stack.push("add", self._make_edit())
        stack.undo()
        stack.clear()
        assert not stack.can_undo
        assert not stack.can_redo

    def test_modify_with_previous_state(self):
        stack = UndoRedoStack()
        edit = self._make_edit(reason="original")
        previous = self._make_edit(reason="before")
        stack.push("modify", edit, previous_state=previous)
        op = stack.undo()
        assert op["previous"] is not None


# ---------------------------------------------------------------------------
# ProjectFile — creation and save/load
# ---------------------------------------------------------------------------

class TestProjectFileCreation:
    def test_default_values(self):
        project = ProjectFile()
        assert project.version == PROJECT_VERSION
        assert project.edits == []
        assert project.ripple_mode is True
        assert project.snap_enabled is True

    def test_create_for_video(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            f.write(b"fake video")
            path = Path(f.name)
        try:
            project = ProjectFile.create_for_video(path, fps=30.0, duration=120.0)
            assert project.input_path == str(path)
            assert project.input_fps == 30.0
            assert project.input_duration == 120.0
            assert len(project.input_fingerprint) == 64
        finally:
            path.unlink()

    def test_get_project_path(self):
        path = ProjectFile.get_project_path(Path("/videos/movie.mp4"))
        assert path == Path("/videos/movie.vcproj.json")


class TestProjectFileSaveLoad:
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            project_path = Path(td) / "test.vcproj.json"
            project = ProjectFile(
                input_path="/tmp/video.mp4",
                input_duration=120.0,
                input_fps=24.0,
                profile_name="Family",
            )
            edit = EditDecision(
                source_start=5.0,
                source_end=10.0,
                action=Action.CUT,
                reason="nudity",
            )
            project.edits.append(edit)
            project.save(project_path)

            loaded = ProjectFile.load(project_path)
            assert loaded.input_path == "/tmp/video.mp4"
            assert loaded.input_duration == 120.0
            assert loaded.profile_name == "Family"
            assert len(loaded.edits) == 1
            assert loaded.edits[0].reason == "nudity"
            assert loaded.edits[0].action == Action.CUT

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            ProjectFile.load(Path("/nonexistent/project.vcproj.json"))

    def test_load_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{{{")
            path = Path(f.name)
        try:
            with pytest.raises(json.JSONDecodeError):
                ProjectFile.load(path)
        finally:
            path.unlink()

    def test_save_sets_dirty_false(self):
        with tempfile.TemporaryDirectory() as td:
            project = ProjectFile(input_path=str(Path(td) / "video.mp4"))
            project._dirty = True
            project.save(Path(td) / "test.vcproj.json")
            assert project.is_dirty is False


# ---------------------------------------------------------------------------
# ProjectFile — edit management
# ---------------------------------------------------------------------------

class TestProjectFileEditManagement:
    def _make_project(self):
        return ProjectFile(input_path="/tmp/v.mp4", input_duration=60.0)

    def test_add_edit(self):
        project = self._make_project()
        edit = EditDecision(source_start=1.0, source_end=2.0, action=Action.CUT)
        project.add_edit(edit)
        assert len(project.edits) == 1
        assert project.is_dirty

    def test_remove_edit(self):
        project = self._make_project()
        edit = EditDecision(source_start=1.0, source_end=2.0, action=Action.CUT)
        project.add_edit(edit)
        removed = project.remove_edit(edit.id)
        assert removed is not None
        assert len(project.edits) == 0

    def test_remove_nonexistent_returns_none(self):
        project = self._make_project()
        assert project.remove_edit("nonexistent") is None

    def test_update_edit(self):
        project = self._make_project()
        edit = EditDecision(source_start=1.0, source_end=2.0, reason="profanity")
        project.add_edit(edit)
        updated = project.update_edit(edit.id, reason="nudity")
        assert updated.reason == "nudity"

    def test_update_nonexistent_returns_none(self):
        project = self._make_project()
        assert project.update_edit("nonexistent", reason="x") is None

    def test_get_edit(self):
        project = self._make_project()
        edit = EditDecision(source_start=1.0, source_end=2.0)
        project.add_edit(edit)
        assert project.get_edit(edit.id) is edit

    def test_get_sorted_edits(self):
        project = self._make_project()
        e1 = EditDecision(source_start=5.0, source_end=6.0)
        e2 = EditDecision(source_start=1.0, source_end=2.0)
        project.add_edit(e1)
        project.add_edit(e2)
        sorted_edits = project.get_sorted_edits()
        assert sorted_edits[0].source_start == 1.0
        assert sorted_edits[1].source_start == 5.0


class TestProjectFileRippleMode:
    def test_ripple_mode_adjusts_output_times(self):
        project = ProjectFile(
            input_path="/tmp/v.mp4",
            input_duration=60.0,
            ripple_mode=True,
        )
        cut = EditDecision(source_start=10.0, source_end=15.0, action=Action.CUT)
        mute = EditDecision(source_start=20.0, source_end=21.0, action=Action.MUTE)
        project.add_edit(cut)
        project.add_edit(mute)
        # After the 5s cut, mute should shift 5s earlier in output
        assert mute.output_start == 15.0
        assert mute.output_end == 16.0

    def test_non_ripple_mode_preserves_times(self):
        project = ProjectFile(
            input_path="/tmp/v.mp4",
            input_duration=60.0,
            ripple_mode=False,
        )
        cut = EditDecision(source_start=10.0, source_end=15.0, action=Action.CUT)
        mute = EditDecision(source_start=20.0, source_end=21.0, action=Action.MUTE)
        project.add_edit(cut)
        project.add_edit(mute)
        assert mute.output_start == 20.0
        assert mute.output_end == 21.0


class TestProjectFileUndoRedo:
    def test_undo_add(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        edit = EditDecision(source_start=1.0, source_end=2.0, action=Action.CUT)
        project.add_edit(edit)
        assert len(project.edits) == 1
        assert project.undo()
        assert len(project.edits) == 0

    def test_redo_add(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        edit = EditDecision(source_start=1.0, source_end=2.0, action=Action.CUT)
        project.add_edit(edit)
        project.undo()
        assert project.redo()
        assert len(project.edits) == 1

    def test_undo_remove(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        edit = EditDecision(source_start=1.0, source_end=2.0, action=Action.CUT)
        project.add_edit(edit)
        project.remove_edit(edit.id)
        assert len(project.edits) == 0
        assert project.undo()
        assert len(project.edits) == 1

    def test_can_undo_can_redo(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        assert not project.can_undo
        edit = EditDecision(source_start=1.0, source_end=2.0)
        project.add_edit(edit)
        assert project.can_undo
        assert not project.can_redo
        project.undo()
        assert not project.can_undo
        assert project.can_redo

    def test_undo_empty_returns_false(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        assert project.undo() is False

    def test_redo_empty_returns_false(self):
        project = ProjectFile(input_path="/tmp/v.mp4")
        assert project.redo() is False


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------

class TestProjectFileFrameHelpers:
    def test_time_to_frame(self):
        project = ProjectFile(input_fps=24.0)
        assert project.time_to_frame(1.0) == 24

    def test_frame_to_time(self):
        project = ProjectFile(input_fps=24.0)
        assert abs(project.frame_to_time(24) - 1.0) < 0.001

    def test_snap_to_frame_roundtrip(self):
        project = ProjectFile(input_fps=30.0)
        snapped = project.snap_to_frame(1.05)
        frame = project.time_to_frame(snapped)
        assert abs(project.frame_to_time(frame) - snapped) < 0.001

    def test_time_to_frame_zero(self):
        project = ProjectFile(input_fps=24.0)
        assert project.time_to_frame(0.0) == 0
