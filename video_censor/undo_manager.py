"""
Undo Manager for Video Censor.

Provides undo/redo functionality for detection edits.
"""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional
from copy import deepcopy


@dataclass
class UndoAction:
    """Represents a single undoable action."""
    name: str
    undo_data: Any
    redo_data: Any


class UndoManager:
    """
    Manages undo/redo stack for detection edits.
    
    Usage:
        undo_manager = UndoManager()
        
        # Before modifying, save old state
        old_state = deepcopy(detections)
        # ... modify detections ...
        new_state = deepcopy(detections)
        undo_manager.push("Skip detection", old_state, new_state)
        
        # To undo
        if undo_manager.can_undo():
            state = undo_manager.undo()
            detections = state
    """
    
    MAX_UNDO_LEVELS = 50
    
    def __init__(self):
        self.undo_stack: List[UndoAction] = []
        self.redo_stack: List[UndoAction] = []
        self.on_change_callbacks: List[Callable] = []
    
    def push(self, name: str, undo_data: Any, redo_data: Any):
        """
        Push action onto undo stack. Clears redo stack.
        
        Args:
            name: Human-readable action name (e.g., "Skip 'damn'")
            undo_data: Data to restore when undoing
            redo_data: Data to restore when redoing
        """
        action = UndoAction(
            name=name,
            undo_data=deepcopy(undo_data),
            redo_data=deepcopy(redo_data)
        )
        self.undo_stack.append(action)
        self.redo_stack.clear()
        
        # Limit stack size
        if len(self.undo_stack) > self.MAX_UNDO_LEVELS:
            self.undo_stack.pop(0)
        
        self._notify_change()
    
    def undo(self) -> Optional[Any]:
        """
        Undo last action.
        
        Returns:
            undo_data to restore, or None if nothing to undo
        """
        if not self.can_undo():
            return None
        
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        self._notify_change()
        return action.undo_data
    
    def redo(self) -> Optional[Any]:
        """
        Redo last undone action.
        
        Returns:
            redo_data to restore, or None if nothing to redo
        """
        if not self.can_redo():
            return None
        
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        self._notify_change()
        return action.redo_data
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def get_undo_name(self) -> Optional[str]:
        """Get name of action that would be undone."""
        return self.undo_stack[-1].name if self.can_undo() else None
    
    def get_redo_name(self) -> Optional[str]:
        """Get name of action that would be redone."""
        return self.redo_stack[-1].name if self.can_redo() else None
    
    def get_undo_count(self) -> int:
        """Get number of undo steps available."""
        return len(self.undo_stack)
    
    def get_redo_count(self) -> int:
        """Get number of redo steps available."""
        return len(self.redo_stack)
    
    def clear(self):
        """Clear both undo and redo stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._notify_change()
    
    def on_change(self, callback: Callable):
        """
        Register callback for stack changes.
        Useful for updating UI (enable/disable buttons).
        """
        self.on_change_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback."""
        if callback in self.on_change_callbacks:
            self.on_change_callbacks.remove(callback)
    
    def _notify_change(self):
        """Notify all registered callbacks."""
        for cb in self.on_change_callbacks:
            try:
                cb()
            except Exception:
                pass
