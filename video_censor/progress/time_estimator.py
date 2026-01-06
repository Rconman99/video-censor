"""
Time estimator for progress tracking.
Estimates remaining time based on progress history.
"""

import time
from collections import deque
from typing import Optional


class TimeEstimator:
    """Estimates remaining time based on progress history"""
    
    def __init__(self, window_size: int = 10):
        self.start_time: Optional[float] = None
        self.history: deque = deque(maxlen=window_size)
        self.last_progress: float = 0
        self.last_time: float = 0
    
    def start(self):
        """Call when processing starts"""
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_progress = 0
        self.history.clear()
    
    def update(self, progress: float) -> Optional[int]:
        """
        Update with current progress (0-100).
        Returns estimated seconds remaining, or None if not enough data.
        """
        now = time.time()
        
        if progress <= self.last_progress:
            return None
        
        # Calculate rate: progress per second
        delta_progress = progress - self.last_progress
        delta_time = now - self.last_time
        
        if delta_time > 0:
            rate = delta_progress / delta_time
            self.history.append(rate)
        
        self.last_progress = progress
        self.last_time = now
        
        # Need at least 3 samples for estimate
        if len(self.history) < 3:
            return None
        
        # Average rate from recent history
        avg_rate = sum(self.history) / len(self.history)
        
        if avg_rate <= 0:
            return None
        
        remaining_progress = 100 - progress
        seconds_remaining = remaining_progress / avg_rate
        
        return int(seconds_remaining)
    
    def get_elapsed(self) -> int:
        """Get elapsed seconds since start"""
        if self.start_time is None:
            return 0
        return int(time.time() - self.start_time)
    
    @staticmethod
    def format_time(seconds: Optional[int]) -> str:
        """Format seconds into human-readable string"""
        if seconds is None or seconds < 0:
            return "Calculating..."
        
        if seconds < 60:
            return f"~{seconds}s remaining"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"~{minutes}m remaining"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"~{hours}h {minutes}m remaining"
