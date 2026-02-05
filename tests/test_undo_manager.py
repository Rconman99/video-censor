"""
Tests for video_censor/undo_manager.py

Tests undo/redo stack operations, max levels, callbacks, and edge cases.
"""

import pytest

from video_censor.undo_manager import UndoAction, UndoManager


class TestUndoManagerBasic:
    def test_empty_manager(self):
        mgr = UndoManager()
        assert not mgr.can_undo()
        assert not mgr.can_redo()
        assert mgr.get_undo_count() == 0
        assert mgr.get_redo_count() == 0

    def test_push_and_undo(self):
        mgr = UndoManager()
        mgr.push("action1", undo_data="old", redo_data="new")
        assert mgr.can_undo()
        assert not mgr.can_redo()
        result = mgr.undo()
        assert result == "old"
        assert not mgr.can_undo()
        assert mgr.can_redo()

    def test_undo_then_redo(self):
        mgr = UndoManager()
        mgr.push("action1", undo_data="old", redo_data="new")
        mgr.undo()
        result = mgr.redo()
        assert result == "new"
        assert mgr.can_undo()
        assert not mgr.can_redo()

    def test_undo_empty_returns_none(self):
        mgr = UndoManager()
        assert mgr.undo() is None

    def test_redo_empty_returns_none(self):
        mgr = UndoManager()
        assert mgr.redo() is None

    def test_push_clears_redo_stack(self):
        mgr = UndoManager()
        mgr.push("a1", "old1", "new1")
        mgr.push("a2", "old2", "new2")
        mgr.undo()  # redo stack now has a2
        assert mgr.can_redo()
        mgr.push("a3", "old3", "new3")
        assert not mgr.can_redo()  # redo cleared


class TestUndoManagerMultiple:
    def test_multiple_undo_redo(self):
        mgr = UndoManager()
        mgr.push("a1", "old1", "new1")
        mgr.push("a2", "old2", "new2")
        mgr.push("a3", "old3", "new3")

        assert mgr.get_undo_count() == 3
        assert mgr.undo() == "old3"
        assert mgr.undo() == "old2"
        assert mgr.undo() == "old1"
        assert not mgr.can_undo()

        assert mgr.redo() == "new1"
        assert mgr.redo() == "new2"
        assert mgr.redo() == "new3"
        assert not mgr.can_redo()


class TestUndoManagerMaxLevels:
    def test_max_undo_levels(self):
        mgr = UndoManager()
        for i in range(60):
            mgr.push(f"a{i}", f"old{i}", f"new{i}")
        assert mgr.get_undo_count() == UndoManager.MAX_UNDO_LEVELS
        # Oldest action should have been discarded
        # The earliest remaining is a10 (pushed at index 10)
        # After 60 pushes, the first 10 are dropped
        for _ in range(UndoManager.MAX_UNDO_LEVELS):
            mgr.undo()
        assert mgr.undo() is None  # no more


class TestUndoManagerNames:
    def test_get_undo_name(self):
        mgr = UndoManager()
        mgr.push("Skip 'damn'", "old", "new")
        assert mgr.get_undo_name() == "Skip 'damn'"

    def test_get_redo_name(self):
        mgr = UndoManager()
        mgr.push("Skip 'damn'", "old", "new")
        mgr.undo()
        assert mgr.get_redo_name() == "Skip 'damn'"

    def test_get_undo_name_empty(self):
        assert UndoManager().get_undo_name() is None

    def test_get_redo_name_empty(self):
        assert UndoManager().get_redo_name() is None


class TestUndoManagerCallbacks:
    def test_on_change_called_on_push(self):
        mgr = UndoManager()
        calls = []
        mgr.on_change(lambda: calls.append("change"))
        mgr.push("a1", "old", "new")
        assert len(calls) == 1

    def test_on_change_called_on_undo(self):
        mgr = UndoManager()
        calls = []
        mgr.push("a1", "old", "new")
        mgr.on_change(lambda: calls.append("change"))
        mgr.undo()
        assert len(calls) == 1

    def test_on_change_called_on_redo(self):
        mgr = UndoManager()
        mgr.push("a1", "old", "new")
        mgr.undo()
        calls = []
        mgr.on_change(lambda: calls.append("change"))
        mgr.redo()
        assert len(calls) == 1

    def test_on_change_called_on_clear(self):
        mgr = UndoManager()
        mgr.push("a1", "old", "new")
        calls = []
        mgr.on_change(lambda: calls.append("change"))
        mgr.clear()
        assert len(calls) == 1

    def test_remove_callback(self):
        mgr = UndoManager()
        calls = []
        cb = lambda: calls.append("change")
        mgr.on_change(cb)
        mgr.push("a1", "old", "new")
        mgr.remove_callback(cb)
        mgr.push("a2", "old", "new")
        assert len(calls) == 1  # only first push triggered

    def test_failing_callback_doesnt_break(self):
        mgr = UndoManager()
        mgr.on_change(lambda: 1 / 0)  # will raise
        # Should not raise
        mgr.push("a1", "old", "new")


class TestUndoManagerClear:
    def test_clear_empties_both_stacks(self):
        mgr = UndoManager()
        mgr.push("a1", "old", "new")
        mgr.push("a2", "old", "new")
        mgr.undo()
        assert mgr.can_undo()
        assert mgr.can_redo()
        mgr.clear()
        assert not mgr.can_undo()
        assert not mgr.can_redo()
        assert mgr.get_undo_count() == 0
        assert mgr.get_redo_count() == 0


class TestUndoManagerDeepCopy:
    def test_push_deep_copies_data(self):
        """Modifying the original data after push should not affect undo."""
        mgr = UndoManager()
        data = {"items": [1, 2, 3]}
        mgr.push("a1", undo_data=data, redo_data={"items": [4, 5]})
        data["items"].append(99)  # mutate original
        result = mgr.undo()
        assert result == {"items": [1, 2, 3]}  # not mutated
