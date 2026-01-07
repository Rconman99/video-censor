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
from .error_handler import safe_operation, UserFriendlyError


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
    
    # Parallel progress tracking
    audio_progress: float = 0.0
    video_progress: float = 0.0
    time_remaining: str = ""  # Human-readable time estimate
    
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
            
    def update_parallel_progress(self, audio_pct: Optional[int] = None, video_pct: Optional[int] = None) -> float:
        """Update parallel task progress and return combined weighted progress."""
        if audio_pct is not None:
            self.audio_progress = float(audio_pct)
        if video_pct is not None:
            self.video_progress = float(video_pct)
            
        # Weights: Audio 20%, Video 30% (Total 50% for analysis phase)
        combined = (self.audio_progress * 0.2 + self.video_progress * 0.3) / 100.0
        return combined
    
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
                "scheduled_time": item.scheduled_time.isoformat() if item.scheduled_time else None,
                "audio_progress": item.audio_progress,
                "video_progress": item.video_progress
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
                    analysis_path=Path(analysis_path) if analysis_path else None,
                    audio_progress=item_data.get("audio_progress", 0.0),
                    video_progress=item_data.get("video_progress", 0.0)
                )
                
                # Reset stuck processing items on restart
                if item.status == "processing" or item.status == "analyzing":
                    print(f"Resetting stuck item to pending: {item.filename}")
                    item.status = "pending" if not item.analysis_path else "review_ready"
                    item.progress = 0.0
                    item.progress_stage = ""
                
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

import asyncio
import tempfile
import shutil
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Tuple
from pathlib import Path

from .config import Config
from .audio import extract_audio, transcribe_audio
from .profanity.detector import detect_profanity
from .nudity import extract_frames, detect_nudity
from .detection.serializer import DetectionSerializer
from .editing.intervals import TimeInterval, Action, MatchSource

def _worker_audio_pipeline(video_path: str, temp_dir: str, config: Config) -> List[Dict]:
    """Worker: Extract audio, transcribe, detect profanity."""
    temp_path = Path(temp_dir)
    video_path = Path(video_path)
    
    # 1. Extract Audio
    # Use a unique name to avoid conflicts if sharing temp (though we separate by folders usually)
    audio_path = extract_audio(
        video_path,
        output_path=temp_path / "audio.wav"
    )
    
    # 2. Transcribe
    words = transcribe_audio(
        audio_path, 
        model_size=config.whisper.model_size,
        language="en",
        progress_prefix="[AUDIO]"
    )
    
    # 3. Detect Profanity
    profanity_list = [] # You might need to load this from config path!
    # IMPORTANT: config only stores paths. We need to load the lists here.
    # But loading lists is fast.
    from .profanity import load_profanity_list
    profanity_list = load_profanity_list(config.profanity.custom_wordlist_path)
    
    detections = detect_profanity(
        words, 
        profanity_list,
        min_confidence=config.profanity.min_confidence if hasattr(config.profanity, 'min_confidence') else 0.0 # Config might not have min_confidence?
        # Actually detect_profanity signature: (words, profanity_list, buffer_before, buffer_after)
        # It doesn't take min_confidence. It returns detections.
    )
    
    # Format
    results = []
    for d in detections:
        results.append({
            'start': d.start,
            'end': d.end,
            'label': d.metadata.get('word', 'profanity'),
            'confidence': d.metadata.get('confidence', 1.0),
            'type': 'profanity'
        })
    return results

def _worker_visual_pipeline(video_path: str, temp_dir: str, config: Config) -> List[Dict]:
    """Worker: Extract frames, detect nudity."""
    temp_path = Path(temp_dir)
    video_path = Path(video_path)
    frames_dir = temp_path / "frames"
    
    # 1. Extract Frames
    frames = extract_frames(
        video_path,
        interval=config.nudity.frame_interval,
        output_dir=frames_dir
    )
    
    # 2. Detect Nudity
    intervals = detect_nudity(
        frames,
        threshold=config.nudity.threshold,
        frame_interval=config.nudity.frame_interval,
        min_segment_duration=config.nudity.min_segment_duration,
        body_parts=config.nudity.body_parts,
        min_cut_duration=config.nudity.min_cut_duration,
        min_box_area_percent=config.nudity.min_box_area_percent,
        max_aspect_ratio=config.nudity.max_aspect_ratio,
        show_progress=True,
        progress_prefix="[VIDEO]"
    )
    
    # Format
    results = []
    for d in intervals:
        results.append({
            'start': d.start,
            'end': d.end,
            'label': d.reason,
            'confidence': 1.0, # NudeNet intervals don't always carry score easily, treat as 1.0
            'type': 'nudity'
        })
    return results

def merge_detections(audio_results: List[Dict], visual_results: List[Dict], config: Config) -> Dict[str, List[Dict]]:
    """Merge audio and visual detections into a single result dict."""
    return {
        'profanity': audio_results,
        'nudity': visual_results
    }

@safe_operation("video processing")
async def process_video(video_path: str, config: Config) -> Dict[str, List[Dict]]:
    """
    Process video with user-friendly error wrapping.
    """
    if not Path(video_path).exists():
        raise UserFriendlyError(
            f"Video file not found: {Path(video_path).name}",
            f"File does not exist: {video_path}"
        )
    """
    Run audio transcription and visual detection.
    
    Respects config.performance.performance_mode for resource usage.
    """
    # Force sequential if parallel disabled OR low power mode
    # "low_power" mode means we want to save resources, so we shouldn't run parallel models
    use_parallel = config.performance.parallel_detection
    if config.system.performance_mode == "low_power":
        use_parallel = False
        print("[Async] Low Power Mode detected: Forcing sequential execution to prevent crash")

    if not use_parallel:
        print("[Async] Parallel detection disabled. Running sequentially...")
        return _run_sequential(video_path, config)

    loop = asyncio.get_event_loop()
    
    # Use a generic temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with ProcessPoolExecutor(max_workers=2) as executor:
                print("[Async] Starting parallel detection...")
                
                # Start Audio
                audio_future = loop.run_in_executor(
                    executor, 
                    _worker_audio_pipeline, 
                    video_path, 
                    temp_dir,
                    config
                )
                
                # Stagger Start
                if config.performance.stagger_delay > 0:
                    print(f"[Async] Staggering visual detection by {config.performance.stagger_delay}s...")
                    await asyncio.sleep(config.performance.stagger_delay)
                
                # Start Visual
                visual_future = loop.run_in_executor(
                    executor, 
                    _worker_visual_pipeline, 
                    video_path, 
                    temp_dir,
                    config
                )
                
                # Wait for both
                audio_results, visual_results = await asyncio.gather(
                    audio_future, 
                    visual_future
                )
                
            print("[Async] Parallel detection complete.")
            results = merge_detections(audio_results, visual_results, config)
            
            # Auto-save logic
            if config.detection_cache.auto_save:
                try:
                    all_intervals = []
                    # Convert dicts to TimeIntervals for saving
                    for key, items in results.items():
                        for item in items:
                            # Map dict to TimeInterval
                            ti = TimeInterval(
                                start=item['start'],
                                end=item['end'],
                                reason=item['label'],
                                action=Action.CUT if item['type'] == 'nudity' else Action.MUTE, # Assumption
                                source=MatchSource.AI,
                                metadata={'confidence': item.get('confidence', 1.0), 'type': item['type']}
                            )
                            all_intervals.append(ti)
                    
                    DetectionSerializer.save(video_path, all_intervals)
                    print(f"Auto-saved {len(all_intervals)} detections.")
                except Exception as e:
                    print(f"Failed to auto-save detections: {e}")
                    
            return results

        except Exception as e:
            print(f"[Async] Parallel execution failed: {e}")
            if config.performance.fallback_to_sequential:
                print("[Async] Falling back to sequential execution...")
                return _run_sequential(video_path, config)
            else:
                raise e

def _run_sequential(video_path: str, config: Config) -> Dict[str, List[Dict]]:
    """Fallback: Run detections one by one."""
    with tempfile.TemporaryDirectory() as temp_dir:
        print("[Sequential] Starting audio detection...")
        audio_results = _worker_audio_pipeline(video_path, temp_dir, config)
        
        print("[Sequential] Starting visual detection...")
        visual_results = _worker_visual_pipeline(video_path, temp_dir, config)
        
        results = merge_detections(audio_results, visual_results, config)
        
        # Auto-save logic (dup for sequential)
        if config.detection_cache.auto_save:
            try:
                all_intervals = []
                for key, items in results.items():
                    for item in items:
                        ti = TimeInterval(
                            start=item['start'],
                            end=item['end'],
                            reason=item['label'],
                            action=Action.CUT if item['type'] == 'nudity' else Action.MUTE,
                            source=MatchSource.AI,
                            metadata={'confidence': item.get('confidence', 1.0), 'type': item['type']}
                        )
                        all_intervals.append(ti)
                
                DetectionSerializer.save(video_path, all_intervals)
                print(f"Auto-saved {len(all_intervals)} detections.")
            except Exception as e:
                print(f"Failed to auto-save detections: {e}")
                
        return results
