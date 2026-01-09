"""
Nudity detection using NudeNet.

Analyzes extracted frames for NSFW content and returns time intervals.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from tqdm import tqdm

from .extractor import FrameInfo
from ..editing.intervals import TimeInterval

logger = logging.getLogger(__name__)


# Nudity detection labels that indicate nudity
NUDITY_LABELS = {
    'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED', 
    'MALE_GENITALIA_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
    'FEMALE_BREAST_COVERED',  # Optional - can be configured
    'BELLY_EXPOSED',  # Optional - less severe
    'SEXUAL_ACTIVITY',  # Added for YOLO v11 support
}

# Labels that definitely indicate nudity (high confidence)
DEFINITE_NUDITY_LABELS = {
    'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED',
    'MALE_GENITALIA_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
    'SEXUAL_ACTIVITY',
}



@dataclass
class NudityDetection:
    """A nudity detection result for a single frame."""
    frame: FrameInfo
    detections: List[Dict[str, Any]]
    max_score: float
    labels_found: List[str]
    is_nude: bool
    engine: str = "unknown"


class NudityDetector:
    """
    Coordinator for nudity detection engines.
    
    Supports:
    - 'precision' (Default): ViT Classifier + YOLOv11 Detector
    - 'yolo': YOLOv11 Detector only
    - 'nudenet': Original NudeNet detector
    """
    
    def __init__(self, engine: str = "precision"):
        self.engine = engine
        self._nudenet = None
        self._yolo = None
        self._classifier = None
    
    def _load_engine(self) -> None:
        """Load the required models based on engine type."""
        if self.engine == "precision":
            from .classifier import get_classifier
            from .yolo_detector import get_yolo_detector
            self._classifier = get_classifier()
            self._yolo = get_yolo_detector()
            logger.info("Using Precision (ViT + YOLOv11) nudity engine")
            
        elif self.engine == "yolo":
            from .yolo_detector import get_yolo_detector
            self._yolo = get_yolo_detector()
            logger.info("Using YOLOv11 nudity engine")
            
        else: # nudenet
            logger.info("Loading NudeNet detector model...")
            try:
                from nudenet import NudeDetector as NNDetector
                self._nudenet = NNDetector()
                logger.info("NudeNet model loaded successfully")
            except ImportError:
                raise RuntimeError("NudeNet not installed. Run: pip install nudenet")

    def detect_frame(self, frame_path: Path) -> List[Dict[str, Any]]:
        """Run detection using the selected engine."""
        if self.engine == "precision":
            # Stage 1: Fast classification
            if self._classifier is None: self._load_engine()
            
            # If classifier says safe with high confidence, skip heavy detection
            # threshold 0.2 means very sensitive (only skip if < 20% nsfw)
            if self._classifier.is_safe(frame_path, nsfw_threshold=0.2):
                return []
                
            # Stage 2: Precise object detection
            return self._yolo.detect_frame(frame_path)
            
        elif self.engine == "yolo":
            if self._yolo is None: self._load_engine()
            return self._yolo.detect_frame(frame_path)
            
        else: # nudenet
            if self._nudenet is None: self._load_engine()
            try:
                detections = self._nudenet.detect(str(frame_path))
                return detections
            except Exception as e:
                logger.warning(f"Failed to analyze frame {frame_path}: {e}")
                return []


# Global detector instance (lazy loaded)
_detector_map: Dict[str, NudityDetector] = {}


def get_detector(engine: str = "precision") -> NudityDetector:
    """Get or create a NudityDetector for the specified engine."""
    if engine not in _detector_map:
        _detector_map[engine] = NudityDetector(engine)
    return _detector_map[engine]


def analyze_frame(
    frame: FrameInfo,
    threshold: float = 0.75,
    labels: Optional[set] = None,
    body_parts: Optional[List[str]] = None,
    min_box_area_percent: float = 3.0,
    max_aspect_ratio: float = 4.0,
    frame_width: int = 1920,
    frame_height: int = 1080,
    engine: str = "precision"
) -> NudityDetection:
    """
    Analyze a single frame for nudity.
    """
    # Use global config if available to determine engine
    try:
        from ..config import Config
        config = Config.load()
        engine = config.nudity.engine
    except:
        pass

    # Default labels for YOLO vs NudeNet
    if labels is None and body_parts is None:
        if engine in ('precision', 'yolo'):
            labels = {'FEMALE_BREAST_EXPOSED', 'FEMALE_GENITALIA_EXPOSED', 
                     'MALE_GENITALIA_EXPOSED', 'ANUS_EXPOSED', 'SEXUAL_ACTIVITY'}
        else:
            labels = DEFINITE_NUDITY_LABELS

    if body_parts and len(body_parts) > 0:
        labels = set(body_parts)
    
    detector = get_detector(engine)
    detections = detector.detect_frame(frame.path)
    
    # Calculate minimum box area threshold
    frame_area = frame_width * frame_height
    min_box_area = (min_box_area_percent / 100.0) * frame_area
    
    relevant_detections = []
    labels_found = []
    max_score = 0.0
    
    for det in detections:
        label = det.get('class', '')
        score = det.get('score', 0.0)
        box = det.get('box', [])
        
        # Check against filtered labels and score threshold
        if labels and label not in labels:
            continue
        if score < threshold:
            continue
        
        # Bounding box filter (reject tiny detections)
        if len(box) >= 4:
            box_width = abs(box[2] - box[0])
            box_height = abs(box[3] - box[1])
            box_area = box_width * box_height
            
            if box_area < min_box_area:
                continue
            
            # Aspect ratio filter (reject extreme noise)
            if box_height > 0:
                aspect_ratio = max(box_width / box_height, box_height / box_width)
                if aspect_ratio > max_aspect_ratio:
                    continue
        
        relevant_detections.append(det)
        labels_found.append(label)
        max_score = max(max_score, score)
    
    is_nude = len(relevant_detections) > 0
    
    return NudityDetection(
        frame=frame,
        detections=relevant_detections,
        max_score=max_score,
        labels_found=labels_found,
        is_nude=is_nude,
        engine=engine
    )


def detect_nudity(
    frames: List[FrameInfo],
    threshold: float = 0.75,
    frame_interval: float = 0.25,
    min_segment_duration: float = 0.5,
    body_parts: Optional[List[str]] = None,
    min_cut_duration: float = 0.3,
    min_box_area_percent: float = 3.0,
    max_aspect_ratio: float = 4.0,
    show_progress: bool = True,
    progress_callback: Optional[callable] = None,
    progress_prefix: str = "",
    engine: str = "precision"
) -> List[TimeInterval]:
    """
    Detect nudity across a list of frames.
    """
    if not frames:
        return []
    
    # Log what we're detecting
    logger.info(f"Analyzing {len(frames)} frames using '{engine}' engine (threshold={threshold})")
    
    # Analyze all frames
    nudity_frames: List[FrameInfo] = []
    nudity_results: Dict[int, NudityDetection] = {}
    
    frame_iter = tqdm(frames, desc="Analyzing frames", disable=not show_progress)
    
    for frame in frame_iter:
        result = analyze_frame(
            frame, 
            threshold, 
            body_parts=body_parts,
            min_box_area_percent=min_box_area_percent,
            max_aspect_ratio=max_aspect_ratio,
            engine=engine
        )
        
        if result.is_nude:
            nudity_frames.append(frame)
            nudity_results[frame.frame_number] = result
            logger.debug(
                f"Nudity detected at {frame.timestamp:.2f}s: "
                f"{result.labels_found} (score={result.max_score:.2f})"
            )
        
        # Report progress
        if show_progress:
            # Calculate % complete
            current_idx = frame_iter.n
            total_frames = len(frames)
            if total_frames > 0:
                percent = int((current_idx / total_frames) * 100)
                if percent % 5 == 0:  # Don't flood output
                   if progress_callback:
                       progress_callback(percent)
                   else:
                       # Tqdm handles stderr, but we want stdout for parsing if running headless
                       # But here we are inside a function that might be called with show_progress=True (tqdm)
                       # If we have a prefix, we should print it to stdout for the parent process to catch
                       if progress_prefix:
                           print(f"{progress_prefix} PROGRESS: {percent}%")
                           import sys
                           sys.stdout.flush()
    
    logger.info(f"Found nudity in {len(nudity_frames)} of {len(frames)} frames")
    
    if not nudity_frames:
        return []
    
    # Convert frames to time intervals
    # Each frame represents a window of time around it
    half_interval = frame_interval / 2
    
    intervals: List[TimeInterval] = []
    for frame in nudity_frames:
        result = nudity_results.get(frame.frame_number)
        labels_str = ", ".join(result.labels_found) if result else "nudity"
        
        interval = TimeInterval(
            start=max(0, frame.timestamp - half_interval),
            end=frame.timestamp + half_interval,
            reason=f"{labels_str} at {frame.timestamp:.2f}s"
        )
        intervals.append(interval)
    
    # Filter out intervals shorter than min_cut_duration after merging
    # This will be handled during the merge step in the planner
    logger.info(f"Created {len(intervals)} raw nudity intervals (min_cut_duration={min_cut_duration}s)")
    
    return intervals
