"""
Serialization utilities for detection intervals.
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

# Use existing TimeInterval as the "Detection" type
from video_censor.editing.intervals import TimeInterval, Action, MatchSource

logger = logging.getLogger(__name__)

class DetectionSerializer:
    VERSION = "1.0"
    
    @staticmethod
    def get_video_hash(video_path: Union[str, Path]) -> str:
        """Quick hash based on file size + first/last 1MB"""
        path = Path(video_path)
        if not path.exists():
            return "unknown"
            
        size = path.stat().st_size
        try:
            with open(path, 'rb') as f:
                head = f.read(1024 * 1024)
                f.seek(max(0, size - 1024 * 1024))
                tail = f.read(1024 * 1024)
            return hashlib.md5(head + tail + str(size).encode()).hexdigest()[:12]
        except Exception:
            return "error"
    
    @staticmethod
    def serialize_interval(interval: TimeInterval) -> Dict[str, Any]:
        """Convert a TimeInterval into a serializable dictionary."""
        return {
            "start": interval.start,
            "end": interval.end,
            "reason": interval.reason,
            "action": interval.action.value if hasattr(interval.action, "value") else str(interval.action),
            "source": interval.source.value if hasattr(interval.source, "value") else str(interval.source),
            "metadata": interval.metadata
        }

    @staticmethod
    def deserialize_interval(data: Dict[str, Any]) -> TimeInterval:
        """Convert a dictionary back to a TimeInterval."""
        # Handle Action Enum
        action_str = data.get("action", Action.CUT.value)
        try:
            action = Action(action_str)
        except ValueError:
            action = Action.CUT

        # Handle Source Enum
        source_str = data.get("source", MatchSource.UNKNOWN.value)
        try:
            source = MatchSource(source_str)
        except ValueError:
            source = MatchSource.UNKNOWN

        return TimeInterval(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            reason=data.get("reason", ""),
            action=action,
            source=source,
            metadata=data.get("metadata", {})
        )

    @staticmethod
    def save(video_path: Union[str, Path, None], detections: List[TimeInterval], output_path: Union[str, Path, None] = None) -> str:
        """Save detections to JSON file"""
        video_path_str = str(video_path) if video_path else ""
        
        if output_path is None:
            if not video_path:
                raise ValueError("Either video_path or output_path must be provided")
            output_path = f"{video_path_str}.detections.json"
        
        output_path = str(output_path)
        
        data = {
            "version": DetectionSerializer.VERSION,
            "video_path": video_path_str,
            "video_hash": DetectionSerializer.get_video_hash(video_path) if video_path else None,
            "created_at": datetime.now().isoformat(),
            "detection_count": len(detections),
            "detections": [DetectionSerializer.serialize_interval(d) for d in detections]
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(detections)} detections to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save detections: {e}")
            raise

    @staticmethod
    def load(detection_path: Union[str, Path], video_path: Union[str, Path, None] = None) -> Tuple[List[TimeInterval], Dict[str, Any]]:
        """Load detections from JSON file. Returns (detections, metadata)"""
        detection_path = Path(detection_path)
        
        if not detection_path.exists():
            raise FileNotFoundError(f"Detection file not found: {detection_path}")
            
        with open(detection_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify video hash if video provided
        if video_path:
            current_hash = DetectionSerializer.get_video_hash(video_path)
            saved_hash = data.get("video_hash")
            
            # Only warn if hash exists in file and mismatch
            if saved_hash and current_hash != saved_hash:
                logger.warning(
                    f"Video hash mismatch. Expected: {saved_hash}, Got: {current_hash}. "
                    "Loading anyway but content may not match."
                )
        
        # Handle both legacy list format and new version wrapper format
        raw_list = []
        if isinstance(data, list):
            # Legacy format support
            raw_list = data
            metadata = {"version": "0.0", "legacy": True}
        else:
            raw_list = data.get("detections", [])
            metadata = {
                "version": data.get("version"),
                "video_path": data.get("video_path"),
                "created_at": data.get("created_at"),
                "detection_count": data.get("detection_count"),
            }

        detections = [DetectionSerializer.deserialize_interval(d) for d in raw_list]
        return detections, metadata
    
    @staticmethod
    def get_auto_path(video_path: Union[str, Path]) -> str:
        """Get default detection file path for a video"""
        return f"{str(video_path)}.detections.json"
    
    @staticmethod
    def has_saved_detections(video_path: Union[str, Path]) -> bool:
        """Check if detection file exists for video"""
        return Path(DetectionSerializer.get_auto_path(video_path)).exists()

# Maintain backward compatibility aliases
# Old signature: save_detections(path, intervals) -> None
save_detections = lambda p, i: DetectionSerializer.save(None, i, output_path=p)
load_detections = lambda p: DetectionSerializer.load(p)[0] # Extract list only
serialize_interval = DetectionSerializer.serialize_interval
deserialize_interval = DetectionSerializer.deserialize_interval
