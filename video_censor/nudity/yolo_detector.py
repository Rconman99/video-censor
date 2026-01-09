"""
Nudity detection using YOLOv11 (EraX-NSFW).

Provides precise object-level detection for explicit body parts.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    HAS_ULTRALYTICS = False

logger = logging.getLogger(__name__)

# EraX-NSFW categories: 
# 0: anus, 1: make_love, 2: nipple (female), 3: penis (male), 4: vagina (female)
MODEL_NAME = "erax-ai/EraX-NSFW-V1.0"

# Map YOLO class indices to our labels
CLASS_MAP = {
    0: 'ANUS_EXPOSED',
    1: 'SEXUAL_ACTIVITY',
    2: 'FEMALE_BREAST_EXPOSED',
    3: 'MALE_GENITALIA_EXPOSED',
    4: 'FEMALE_GENITALIA_EXPOSED'
}

class YOLONudityDetector:
    """
    Wrapper for YOLOv11 NSFW detector.
    """
    
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None
        
    def _load_model(self):
        """Lazy load the YOLO model."""
        if self._model is not None:
            return
            
        if not HAS_ULTRALYTICS:
            raise ImportError("ultralytics is required for YOLO nudity detection.")
            
        logger.info(f"Loading YOLO NSFW model: {self.model_name}...")
        try:
            # Load model (will download if not present)
            self._model = YOLO(self.model_name)
            logger.info("YOLO NSFW model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
            
    def detect_frame(self, frame_path: Path) -> List[Dict[str, Any]]:
        """
        Run nudity detection on a single frame.
        
        Returns list of detections with format:
        [{'class': 'LABEL', 'score': 0.95, 'box': [x1, y1, x2, y2]}]
        """
        self._load_model()
        
        try:
            # Run inference
            results = self._model(str(frame_path), verbose=False)
            
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_idx = int(box.cls[0])
                    label = CLASS_MAP.get(cls_idx, f'UNKNOWN_{cls_idx}')
                    score = float(box.conf[0])
                    coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                    
                    detections.append({
                        'class': label,
                        'score': score,
                        'box': coords
                    })
                    
            return detections
        except Exception as e:
            logger.warning(f"Failed to analyze frame {frame_path}: {e}")
            return []

# Global instance
_yolo_detector: Optional[YOLONudityDetector] = None

def get_yolo_detector() -> YOLONudityDetector:
    global _yolo_detector
    if _yolo_detector is None:
        _yolo_detector = YOLONudityDetector()
    return _yolo_detector
