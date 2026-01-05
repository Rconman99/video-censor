"""
Project file management for the timeline editor.

Handles saving/loading project files (JSON sidecar next to source media),
file fingerprinting, and undo/redo stack.
"""

import hashlib
import json
import logging
import time as time_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .intervals import EditDecision, Action

logger = logging.getLogger(__name__)

# Project file version
PROJECT_VERSION = "1.0"


def compute_file_fingerprint(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute a fingerprint for a media file.
    
    Uses SHA256 of the first 1MB + filesize for fast identification
    without hashing the entire file.
    
    Args:
        file_path: Path to the media file
        chunk_size: Size of data to hash (default 1MB)
        
    Returns:
        Hex string fingerprint
    """
    if not file_path.exists():
        return ""
    
    hasher = hashlib.sha256()
    file_size = file_path.stat().st_size
    hasher.update(str(file_size).encode())
    
    with open(file_path, 'rb') as f:
        hasher.update(f.read(chunk_size))
    
    return hasher.hexdigest()


@dataclass
class UndoRedoStack:
    """
    Manages undo/redo operations for edit decisions.
    
    Each operation is a tuple of (action_type, EditDecision, previous_state).
    """
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    redo_stack: List[Dict[str, Any]] = field(default_factory=list)
    max_history: int = 100
    
    def push(self, action_type: str, edit: EditDecision, previous_state: Optional[EditDecision] = None):
        """
        Push an operation onto the undo stack.
        
        Args:
            action_type: 'add', 'remove', or 'modify'
            edit: The EditDecision being modified
            previous_state: For 'modify', the state before modification
        """
        self.undo_stack.append({
            'action': action_type,
            'edit': edit.to_dict(),
            'previous': previous_state.to_dict() if previous_state else None,
            'timestamp': time_module.time(),
        })
        
        # Clear redo stack on new action
        self.redo_stack.clear()
        
        # Trim if over limit
        if len(self.undo_stack) > self.max_history:
            self.undo_stack = self.undo_stack[-self.max_history:]
    
    def undo(self) -> Optional[Dict[str, Any]]:
        """Pop and return the last operation for undoing."""
        if not self.undo_stack:
            return None
        
        op = self.undo_stack.pop()
        self.redo_stack.append(op)
        return op
    
    def redo(self) -> Optional[Dict[str, Any]]:
        """Pop and return the last undone operation for redoing."""
        if not self.redo_stack:
            return None
        
        op = self.redo_stack.pop()
        self.undo_stack.append(op)
        return op
    
    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
    
    def clear(self):
        """Clear both stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()


@dataclass
class ProjectFile:
    """
    Project file for non-destructive timeline editing.
    
    Stored as a JSON sidecar file ({video_name}.vcproj.json) next to source media.
    Contains all edit decisions, detection metadata, and configuration.
    """
    version: str = PROJECT_VERSION
    
    # Source media info
    input_path: str = ""
    input_fingerprint: str = ""
    input_duration: float = 0.0
    input_fps: float = 24.0
    
    # Edit decisions
    edits: List[EditDecision] = field(default_factory=list)
    
    # Configuration
    profile_name: str = "default"
    ripple_mode: bool = True
    snap_enabled: bool = True
    snap_threshold: float = 0.5  # seconds
    
    # Detection metadata (cached to avoid re-detection)
    detection_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: float = field(default_factory=time_module.time)
    modified_at: float = field(default_factory=time_module.time)
    
    # Runtime state (not persisted)
    _undo_stack: UndoRedoStack = field(default_factory=UndoRedoStack, repr=False)
    _dirty: bool = field(default=False, repr=False)
    
    @classmethod
    def get_project_path(cls, video_path: Path) -> Path:
        """Get the project file path for a video."""
        return video_path.with_suffix('.vcproj.json')
    
    @classmethod
    def exists_for_video(cls, video_path: Path) -> bool:
        """Check if a project file exists for the video."""
        return cls.get_project_path(video_path).exists()
    
    @classmethod
    def load(cls, project_path: Path) -> "ProjectFile":
        """
        Load a project from a JSON file.
        
        Args:
            project_path: Path to the .vcproj.json file
            
        Returns:
            Loaded ProjectFile instance
            
        Raises:
            FileNotFoundError: If project file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        with open(project_path, 'r') as f:
            data = json.load(f)
        
        # Deserialize edits
        edits = [EditDecision.from_dict(e) for e in data.get('edits', [])]
        
        project = cls(
            version=data.get('version', PROJECT_VERSION),
            input_path=data.get('input_path', ''),
            input_fingerprint=data.get('input_fingerprint', ''),
            input_duration=data.get('input_duration', 0.0),
            input_fps=data.get('input_fps', 24.0),
            edits=edits,
            profile_name=data.get('profile_name', 'default'),
            ripple_mode=data.get('ripple_mode', True),
            snap_enabled=data.get('snap_enabled', True),
            snap_threshold=data.get('snap_threshold', 0.5),
            detection_metadata=data.get('detection_metadata', {}),
            created_at=data.get('created_at', time_module.time()),
            modified_at=data.get('modified_at', time_module.time()),
        )
        
        logger.info(f"Loaded project with {len(edits)} edits from {project_path}")
        return project
    
    @classmethod
    def load_for_video(cls, video_path: Path) -> Optional["ProjectFile"]:
        """
        Load project for a video if it exists.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            ProjectFile if exists, None otherwise
        """
        project_path = cls.get_project_path(video_path)
        if not project_path.exists():
            return None
        
        try:
            project = cls.load(project_path)
            
            # Verify fingerprint matches
            current_fingerprint = compute_file_fingerprint(video_path)
            if project.input_fingerprint and project.input_fingerprint != current_fingerprint:
                logger.warning(f"Video file has changed since project was saved")
            
            return project
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return None
    
    @classmethod
    def create_for_video(cls, video_path: Path, fps: float = 24.0, duration: float = 0.0) -> "ProjectFile":
        """
        Create a new project for a video.
        
        Args:
            video_path: Path to the video file
            fps: Video frame rate
            duration: Video duration in seconds
            
        Returns:
            New ProjectFile instance
        """
        return cls(
            input_path=str(video_path),
            input_fingerprint=compute_file_fingerprint(video_path),
            input_duration=duration,
            input_fps=fps,
        )
    
    def save(self, project_path: Optional[Path] = None) -> Path:
        """
        Save project to JSON file.
        
        Args:
            project_path: Path to save to (defaults to sidecar path)
            
        Returns:
            Path where project was saved
        """
        if project_path is None:
            project_path = self.get_project_path(Path(self.input_path))
        
        self.modified_at = time_module.time()
        
        data = {
            'version': self.version,
            'input_path': self.input_path,
            'input_fingerprint': self.input_fingerprint,
            'input_duration': self.input_duration,
            'input_fps': self.input_fps,
            'edits': [e.to_dict() for e in self.edits],
            'profile_name': self.profile_name,
            'ripple_mode': self.ripple_mode,
            'snap_enabled': self.snap_enabled,
            'snap_threshold': self.snap_threshold,
            'detection_metadata': self.detection_metadata,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
        }
        
        with open(project_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        self._dirty = False
        logger.info(f"Saved project with {len(self.edits)} edits to {project_path}")
        return project_path
    
    # === Edit Management ===
    
    def add_edit(self, edit: EditDecision):
        """Add an edit decision with undo support."""
        self._undo_stack.push('add', edit)
        self.edits.append(edit)
        self._recalculate_output_times()
        self._dirty = True
    
    def remove_edit(self, edit_id: str) -> Optional[EditDecision]:
        """Remove an edit by ID with undo support."""
        for i, edit in enumerate(self.edits):
            if edit.id == edit_id:
                removed = self.edits.pop(i)
                self._undo_stack.push('remove', removed)
                self._recalculate_output_times()
                self._dirty = True
                return removed
        return None
    
    def update_edit(self, edit_id: str, **kwargs) -> Optional[EditDecision]:
        """Update an edit's properties with undo support."""
        for edit in self.edits:
            if edit.id == edit_id:
                # Store previous state for undo
                previous = EditDecision.from_dict(edit.to_dict())
                
                # Apply updates
                for key, value in kwargs.items():
                    if hasattr(edit, key):
                        setattr(edit, key, value)
                
                self._undo_stack.push('modify', edit, previous)
                self._recalculate_output_times()
                self._dirty = True
                return edit
        return None
    
    def get_edit(self, edit_id: str) -> Optional[EditDecision]:
        """Get an edit by ID."""
        for edit in self.edits:
            if edit.id == edit_id:
                return edit
        return None
    
    def get_sorted_edits(self) -> List[EditDecision]:
        """Get edits sorted by source start time."""
        return sorted(self.edits, key=lambda e: e.source_start)
    
    def _recalculate_output_times(self):
        """Recalculate output times based on ripple mode."""
        if not self.ripple_mode:
            # In non-ripple mode, output times = source times
            for edit in self.edits:
                edit.output_start = edit.source_start
                edit.output_end = edit.source_end
            return
        
        # In ripple mode, cuts shift all subsequent content
        sorted_edits = self.get_sorted_edits()
        cut_offset = 0.0
        
        for edit in sorted_edits:
            if edit.action == Action.CUT:
                edit.output_start = edit.source_start - cut_offset
                edit.output_end = edit.source_end - cut_offset
                cut_offset += edit.duration
            else:
                # Non-cut edits (mute, blur) shift by accumulated cut offset
                edit.output_start = edit.source_start - cut_offset
                edit.output_end = edit.source_end - cut_offset
    
    # === Undo/Redo ===
    
    def undo(self) -> bool:
        """Undo the last operation. Returns True if successful."""
        op = self._undo_stack.undo()
        if not op:
            return False
        
        action = op['action']
        edit_data = op['edit']
        
        if action == 'add':
            # Undo add = remove
            self.edits = [e for e in self.edits if e.id != edit_data['id']]
        elif action == 'remove':
            # Undo remove = add back
            self.edits.append(EditDecision.from_dict(edit_data))
        elif action == 'modify':
            # Undo modify = restore previous state
            previous_data = op['previous']
            for i, edit in enumerate(self.edits):
                if edit.id == edit_data['id']:
                    self.edits[i] = EditDecision.from_dict(previous_data)
                    break
        
        self._recalculate_output_times()
        self._dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo the last undone operation. Returns True if successful."""
        op = self._undo_stack.redo()
        if not op:
            return False
        
        action = op['action']
        edit_data = op['edit']
        
        if action == 'add':
            # Redo add = add back
            self.edits.append(EditDecision.from_dict(edit_data))
        elif action == 'remove':
            # Redo remove = remove again
            self.edits = [e for e in self.edits if e.id != edit_data['id']]
        elif action == 'modify':
            # Redo modify = apply the modification again
            for i, edit in enumerate(self.edits):
                if edit.id == edit_data['id']:
                    self.edits[i] = EditDecision.from_dict(edit_data)
                    break
        
        self._recalculate_output_times()
        self._dirty = True
        return True
    
    @property
    def can_undo(self) -> bool:
        return self._undo_stack.can_undo
    
    @property
    def can_redo(self) -> bool:
        return self._undo_stack.can_redo
    
    @property
    def is_dirty(self) -> bool:
        return self._dirty
    
    # === Frame Helpers ===
    
    def time_to_frame(self, time_sec: float) -> int:
        """Convert time to frame index."""
        return int(round(time_sec * self.input_fps))
    
    def frame_to_time(self, frame: int) -> float:
        """Convert frame index to time."""
        return frame / self.input_fps
    
    def snap_to_frame(self, time_sec: float) -> float:
        """Snap time to nearest frame boundary."""
        return self.frame_to_time(self.time_to_frame(time_sec))
