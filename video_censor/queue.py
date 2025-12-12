"""
Queue item model for video processing jobs.

Defines the QueueItem dataclass that holds a video's processing state,
including filter settings and progress information.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .preferences import ContentFilterSettings


@dataclass
class QueueItem:
    """
    A video in the processing queue.
    
    Attributes:
        id: Unique identifier for this queue item
        input_path: Path to the source video file
        output_path: Path where the censored video will be saved
        filters: Content filter settings for this specific video
        profile_name: Name of the profile used (for display)
        status: Current processing state
        progress: Processing progress (0.0 to 1.0)
        progress_stage: Current stage description (e.g., "Detecting profanity")
        error_message: Error details if status is "error"
        added_at: When the item was added to queue
        started_at: When processing began
        completed_at: When processing finished
        summary: Processing summary (populated after completion)
    """
    input_path: Path
    output_path: Path
    filters: ContentFilterSettings
    profile_name: str = "Default"
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "pending"  # pending, processing, complete, error, cancelled
    progress: float = 0.0
    progress_stage: str = ""
    error_message: str = ""
    added_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: Optional[Dict[str, Any]] = None
    notified_50: bool = False
    notified_90: bool = False
    analysis_path: Optional[Path] = None  # Path to analysis JSON for review step
    scheduled_time: Optional[datetime] = None # When to auto-start
    
    @property
    def filename(self) -> str:
        """Get the input video filename."""
        return self.input_path.name
    
    @property
    def is_scheduled(self) -> bool:
        """Check if item is scheduled for later."""
        return self.status == "scheduled"

    @property
    def is_pending(self) -> bool:
        """Check if item is pending processing."""
        return self.status == "pending"
    
    @property
    def is_processing(self) -> bool:
        """Check if item is currently processing."""
        return self.status in ("processing", "analyzing", "exporting")
    
    @property
    def is_review_ready(self) -> bool:
        """Check if item is ready for manual review."""
        return self.status == "review_ready"
    
    @property
    def is_complete(self) -> bool:
        """Check if item completed successfully."""
        return self.status == "complete"
    
    @property
    def is_error(self) -> bool:
        """Check if item failed with error."""
        return self.status == "error"
    
    @property
    def is_finished(self) -> bool:
        """Check if item is done (complete or error)."""
        return self.status in ("complete", "error", "cancelled")
    
    def filter_summary(self) -> str:
        """Get a human-readable summary of applied filters."""
        return self.filters.summary()
    
    def short_filter_summary(self) -> str:
        """Get a compact filter summary for queue display."""
        return self.filters.short_summary()
    
    def start_processing(self) -> None:
        """Mark the item as started."""
        self.status = "processing"
        self.started_at = datetime.now()
        self.progress = 0.0
    
    def update_progress(self, progress: float, stage: str = "") -> None:
        """Update processing progress."""
        self.progress = max(0.0, min(1.0, progress))
        if stage:
            self.progress_stage = stage
    
    def mark_review_ready(self, analysis_path: Path) -> None:
        """Mark item as ready for review."""
        self.status = "review_ready"
        self.analysis_path = analysis_path
        self.progress = 0.5 # Pause at 50%
        self.progress_stage = "Ready for Review"

    def complete(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """Mark the item as completed successfully."""
        self.status = "complete"
        self.progress = 1.0
        self.completed_at = datetime.now()
        self.summary = summary
    
    def fail(self, error_message: str) -> None:
        """Mark the item as failed."""
        self.status = "error"
        self.error_message = error_message
        self.completed_at = datetime.now()
    
    def cancel(self) -> None:
        """Cancel the item."""
        self.status = "cancelled"
        self.completed_at = datetime.now()
    
    @property
    def duration_str(self) -> str:
        """Get a formatted duration string if processing is complete."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            minutes, seconds = divmod(int(delta.total_seconds()), 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return ""
    
    def status_display(self) -> str:
        """Get a display string for the current status."""
        if self.status == "pending":
            return "⏳ Pending"
        elif self.status == "scheduled":
            time_str = self.scheduled_time.strftime("%I:%M %p") if self.scheduled_time else ""
            return f"⏰ Scheduled {time_str}"
        elif self.status == "processing":
            pct = int(self.progress * 100)
            if self.progress_stage:
                return f"◐ {pct}% - {self.progress_stage}"
            return f"◐ {pct}%"
        elif self.status == "review_ready": # New state
             return "⚠ Ready for Review"
        elif self.status == "analyzing": # New state
             pct = int(self.progress * 100)
             return f"🔍 Analysis {pct}%"
        elif self.status == "exporting": # New state
             pct = int(self.progress * 100)
             return f"💾 Exporting {pct}%"
        elif self.status == "complete":
            return f"✓ Complete ({self.duration_str})"
        elif self.status == "error":
            return f"✗ Error"
        elif self.status == "cancelled":
            return "⊘ Cancelled"
        return self.status


class ProcessingQueue:
    """
    Manages a list of queue items.
    
    Provides methods for adding, removing, and querying queue state.
    """
    
    def __init__(self):
        self._items: list[QueueItem] = []
        self.on_complete_callback = None  # Function to call when queue finishes
        self.sleep_when_done = False  # Auto-sleep when queue finishes

    
    def add(self, item: QueueItem) -> None:
        """Add an item to the queue."""
        self._items.append(item)
    
    def remove(self, item_id: str) -> bool:
        """Remove an item by ID. Returns True if found and removed."""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                del self._items[i]
                return True
        return False
    
    def get(self, item_id: str) -> Optional[QueueItem]:
        """Get an item by ID."""
        for item in self._items:
            if item.id == item_id:
                return item
        return None
    
    def get_next_pending(self) -> Optional[QueueItem]:
        """Get the next pending item, or None if queue is empty/all processed."""
        for item in self._items:
            if item.is_pending:
                return item
        return None
    
    def get_current_processing(self) -> Optional[QueueItem]:
        """Get the currently processing item, if any."""
        for item in self._items:
            if item.is_processing:
                return item
        return None
    
    @property
    def items(self) -> list[QueueItem]:
        """Get all queue items."""
        return self._items.copy()
    
    @property
    def pending_count(self) -> int:
        """Number of pending items."""
        return sum(1 for item in self._items if item.is_pending)
    
    @property
    def processing_count(self) -> int:
        """Number of currently processing items."""
        return sum(1 for item in self._items if item.is_processing)
    
    @property
    def complete_count(self) -> int:
        """Number of completed items."""
        return sum(1 for item in self._items if item.is_complete)
    
    @property
    def error_count(self) -> int:
        """Number of failed items."""
        return sum(1 for item in self._items if item.is_error)
    
    def clear_completed(self) -> int:
        """Remove all completed and cancelled items. Returns number removed."""
        before = len(self._items)
        self._items = [item for item in self._items if not item.is_finished]
        return before - len(self._items)
    
    def clear_all(self) -> None:
        """Remove all items from the queue."""
        self._items.clear()
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._items) == 0
    
    def has_pending_work(self) -> bool:
        """Check if there are items waiting to be processed."""
        return self.pending_count > 0 or self.processing_count > 0
    
    def check_all_complete(self) -> None:
        """Check if all items are finished and trigger callbacks."""
        if not self.has_pending_work() and len(self._items) > 0:
            # Trigger callback
            if self.on_complete_callback:
                try:
                    self.on_complete_callback()
                except Exception as e:
                    print(f"Error in on_complete_callback: {e}")
            
            # Handle sleep
            if self.sleep_when_done:
                self._trigger_sleep()
    
    def _trigger_sleep(self):
        """Put computer to sleep (macOS)."""
        import subprocess
        try:
            print("Queue complete - Sleeping computer...")
            subprocess.run(["pmset", "sleepnow"])
        except Exception as e:
            print(f"Failed to sleep computer: {e}")
    
    def save_state(self, filepath: Optional[Path] = None) -> None:
        """Save queue state to disk for crash recovery."""
        import json
        from pathlib import Path
        
        if filepath is None:
            filepath = Path("/Volumes/20tb/.video_censor_queue.json")
        
        # Save pending, processing AND review-ready items
        items_to_save = [item for item in self._items if item.is_pending or item.is_processing or item.is_review_ready]
        
        state = []
        for item in items_to_save:
            state.append({
                "id": item.id,
                "input_path": str(item.input_path),
                "output_path": str(item.output_path),
                "profile_name": item.profile_name,
                "status": item.status, # Persist exact status
                "analysis_path": str(item.analysis_path) if item.analysis_path else None,
                "filters": {
                    "filter_language": item.filters.filter_language,
                    "filter_sexual_content": item.filters.filter_sexual_content,
                    "filter_nudity": item.filters.filter_nudity,
                    "filter_romance_level": item.filters.filter_romance_level,
                    "filter_violence_level": item.filters.filter_violence_level,
                    "filter_mature_themes": item.filters.filter_mature_themes,
                    "custom_block_phrases": item.filters.custom_block_phrases,
                    "safe_cover_enabled": item.filters.safe_cover_enabled,
                },
                "scheduled_time": item.scheduled_time.isoformat() if item.scheduled_time else None
            })
        
        try:
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Failed to save queue state: {e}")
    
    def load_state(self, filepath: Optional[Path] = None) -> int:
        """Load queue state from disk. Returns number of items restored."""
        import json
        from pathlib import Path
        
        if filepath is None:
            filepath = Path("/Volumes/20tb/.video_censor_queue.json")
        
        if not filepath.exists():
            return 0
        
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)
            
            count = 0
            for item_data in state:
                filters = ContentFilterSettings(
                    filter_language=item_data["filters"].get("filter_language", True),
                    filter_sexual_content=item_data["filters"].get("filter_sexual_content", True),
                    filter_nudity=item_data["filters"].get("filter_nudity", True),
                    filter_romance_level=item_data["filters"].get("filter_romance_level", 0),
                    filter_violence_level=item_data["filters"].get("filter_violence_level", 0),
                    filter_mature_themes=item_data["filters"].get("filter_mature_themes", False),
                    custom_block_phrases=item_data["filters"].get("custom_block_phrases", []),
                    safe_cover_enabled=item_data["filters"].get("safe_cover_enabled", False),
                )
                
                

                
                start_time_iso = item_data.get("scheduled_time")
                start_time = datetime.fromisoformat(start_time_iso) if start_time_iso else None
                
                # Restore status if available, otherwise infer
                status = item_data.get("status", "pending")
                if "status" not in item_data:
                    # Backward compatibility for old saves
                    status = "scheduled" if start_time else "pending"
                
                analysis_path = item_data.get("analysis_path")
                
                item = QueueItem(
                    id=item_data["id"],
                    input_path=Path(item_data["input_path"]),
                    output_path=Path(item_data["output_path"]),
                    profile_name=item_data.get("profile_name", "Default"),
                    filters=filters,
                    scheduled_time=start_time,
                    status=status,
                    analysis_path=Path(analysis_path) if analysis_path else None
                )
                
                # If restoring in review state, trigger ready logic
                if item.is_review_ready:
                    item.progress = 0.5
                    item.progress_stage = "Ready for Review"
                self._items.append(item)
                count += 1
            
            # Clear the file after loading -> REMOVED to allow crash recovery
            # filepath.unlink() 
            return count
            
        except Exception as e:
            print(f"Failed to load queue state: {e}")
            return 0
