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


# NudeNet detection labels that indicate nudity
NUDITY_LABELS = {
    'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED', 
    'MALE_GENITALIA_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
    'FEMALE_BREAST_COVERED',  # Optional - can be configured
    'BELLY_EXPOSED',  # Optional - less severe
}

# Labels that definitely indicate nudity (high confidence)
DEFINITE_NUDITY_LABELS = {
    'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED',
    'MALE_GENITALIA_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
}


@dataclass
class NudityDetection:
    """A nudity detection result for a single frame."""
    frame: FrameInfo
    detections: List[Dict[str, Any]]
    max_score: float
    labels_found: List[str]
    is_nude: bool


class NudityDetector:
    """
    Wrapper for NudeNet detector.
    
    Handles model loading and frame analysis.
    """
    
    def __init__(self):
        self._detector = None
    
    def _load_model(self) -> None:
        """Load the NudeNet detector model."""
        if self._detector is not None:
            return
            
        logger.info("Loading NudeNet detector model...")
        
        try:
            # Try to configure ONNX Runtime for Apple Silicon acceleration
            try:
                import onnxruntime as ort
                available_providers = ort.get_available_providers()
                logger.info(f"Available ONNX providers: {available_providers}")
                
                # Prefer CoreML on macOS, then CUDA, then CPU
                if 'CoreMLExecutionProvider' in available_providers:
                    logger.info("Using CoreML provider for GPU acceleration")
                elif 'CUDAExecutionProvider' in available_providers:
                    logger.info("Using CUDA provider for GPU acceleration")
                else:
                    logger.info("Using CPU provider")
            except ImportError:
                pass  # onnxruntime not installed, nudenet will use defaults
            
            from nudenet import NudeDetector as NNDetector
            self._detector = NNDetector()
            logger.info("NudeNet model loaded successfully")
        except ImportError:
            raise RuntimeError(
                "NudeNet not installed. Run: pip install nudenet"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load NudeNet: {e}")
    
    def detect_frame(self, frame_path: Path) -> List[Dict[str, Any]]:
        """
        Run nudity detection on a single frame.
        
        Returns list of detections with format:
        [{'class': 'LABEL', 'score': 0.95, 'box': [x1, y1, x2, y2]}]
        """
        self._load_model()
        
        try:
            detections = self._detector.detect(str(frame_path))
            return detections
        except Exception as e:
            logger.warning(f"Failed to analyze frame {frame_path}: {e}")
            return []


# Global detector instance (lazy loaded)
_detector: Optional[NudityDetector] = None


def get_detector() -> NudityDetector:
    """Get or create the global NudityDetector instance."""
    global _detector
    if _detector is None:
        _detector = NudityDetector()
    return _detector


def analyze_frame(
    frame: FrameInfo,
    threshold: float = 0.6,
    labels: Optional[set] = None,
    body_parts: Optional[List[str]] = None
) -> NudityDetection:
    """
    Analyze a single frame for nudity.
    
    Args:
        frame: FrameInfo object with path and timestamp
        threshold: Minimum confidence score to consider a detection
        labels: Set of labels to consider as nudity (defaults to DEFINITE_NUDITY_LABELS)
        body_parts: List of specific body parts to detect (empty/None = all exposed parts)
        
    Returns:
        NudityDetection result
    """
    # Determine which labels to use
    if body_parts and len(body_parts) > 0:
        # Use user-specified body parts
        labels = set(body_parts)
        logger.debug(f"Using custom body parts filter: {labels}")
    elif labels is None:
        labels = DEFINITE_NUDITY_LABELS
    
    detector = get_detector()
    detections = detector.detect_frame(frame.path)
    
    # Filter detections above threshold
    relevant_detections = []
    labels_found = []
    max_score = 0.0
    
    for det in detections:
        label = det.get('class', '')
        score = det.get('score', 0.0)
        
        if label in labels and score >= threshold:
            relevant_detections.append(det)
            labels_found.append(label)
            max_score = max(max_score, score)
    
    is_nude = len(relevant_detections) > 0
    
    return NudityDetection(
        frame=frame,
        detections=relevant_detections,
        max_score=max_score,
        labels_found=labels_found,
        is_nude=is_nude
    )


def detect_nudity(
    frames: List[FrameInfo],
    threshold: float = 0.6,
    frame_interval: float = 0.25,
    min_segment_duration: float = 0.5,
    body_parts: Optional[List[str]] = None,
    min_cut_duration: float = 0.3,
    show_progress: bool = True
) -> List[TimeInterval]:
    """
    Detect nudity across a list of frames.
    
    Args:
        frames: List of FrameInfo objects to analyze
        threshold: Detection confidence threshold (0.0 to 1.0)
        frame_interval: Time between frames in seconds
        min_segment_duration: Minimum duration to create a segment
        body_parts: List of specific body parts to detect (empty = all exposed parts)
        min_cut_duration: Minimum duration for a cut (prevents micro-cuts)
        show_progress: Whether to show progress bar
        
    Returns:
        List of TimeInterval objects where nudity was detected
    """
    if not frames:
        return []
    
    # Log what we're detecting
    if body_parts and len(body_parts) > 0:
        logger.info(f"Analyzing {len(frames)} frames for nudity (threshold={threshold}, body_parts={body_parts})")
    else:
        logger.info(f"Analyzing {len(frames)} frames for nudity (threshold={threshold}, all exposed body parts)")
    
    # Analyze all frames
    nudity_frames: List[FrameInfo] = []
    nudity_results: Dict[int, NudityDetection] = {}
    
    frame_iter = tqdm(frames, desc="Analyzing frames", disable=not show_progress)
    
    for frame in frame_iter:
        result = analyze_frame(frame, threshold, body_parts=body_parts)
        
        if result.is_nude:
            nudity_frames.append(frame)
            nudity_results[frame.frame_number] = result
            logger.debug(
                f"Nudity detected at {frame.timestamp:.2f}s: "
                f"{result.labels_found} (score={result.max_score:.2f})"
            )
    
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
