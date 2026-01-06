"""
Progress reporter for unified progress tracking.
Central reporter that tracks stage, progress, and time estimates.
"""

from typing import Callable, Optional, List
from .stages import ProcessingStage, get_stage_label, get_overall_progress
from .time_estimator import TimeEstimator


class ProgressReporter:
    """
    Central progress reporter that tracks stage, progress, and time estimates.
    Emits updates to registered callbacks.
    """
    
    def __init__(self):
        self.stage = ProcessingStage.INITIALIZING
        self.stage_progress = 0.0
        self.detail = ""
        self.estimator = TimeEstimator()
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        """Register callback: callback(overall_percent, stage_label, time_remaining)"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def start(self):
        """Call when processing begins"""
        self.stage = ProcessingStage.INITIALIZING
        self.stage_progress = 0
        self.estimator.start()
        self._emit()
    
    def set_stage(self, stage: ProcessingStage, detail: str = ""):
        """Move to a new stage"""
        self.stage = stage
        self.stage_progress = 0
        self.detail = detail
        self._emit()
    
    def update(self, progress: float, detail: str = None):
        """Update progress within current stage (0-100)"""
        self.stage_progress = min(max(progress, 0), 100)
        if detail is not None:
            self.detail = detail
        self._emit()
    
    def increment(self, amount: float = 1):
        """Increment progress by amount"""
        self.update(self.stage_progress + amount)
    
    def complete(self):
        """Mark as complete"""
        self.stage = ProcessingStage.COMPLETE
        self.stage_progress = 100
        self._emit()
    
    def error(self, message: str = ""):
        """Mark as error"""
        self.stage = ProcessingStage.ERROR
        self.detail = message
        self._emit()
    
    def _emit(self):
        """Emit progress update to all callbacks"""
        overall = get_overall_progress(self.stage, self.stage_progress)
        label = get_stage_label(self.stage, self.detail)
        remaining = self.estimator.update(overall)
        time_str = TimeEstimator.format_time(remaining)
        
        for callback in self.callbacks:
            try:
                callback(overall, label, time_str)
            except Exception:
                pass  # Don't let callback errors stop processing
    
    def get_current_state(self) -> tuple:
        """Get current state as (overall_percent, stage_label, time_str)"""
        overall = get_overall_progress(self.stage, self.stage_progress)
        label = get_stage_label(self.stage, self.detail)
        remaining = self.estimator.update(overall) if self.estimator.last_progress > 0 else None
        time_str = TimeEstimator.format_time(remaining)
        return (overall, label, time_str)
