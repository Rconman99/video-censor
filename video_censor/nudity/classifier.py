"""
NSFW Classification using Vision Transformers (Falconsai).

Provides a fast high-level check for NSFW content to skip safe frames
before running more expensive object detection.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

try:
    from PIL import Image
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

logger = logging.getLogger(__name__)

# Model to use from Hugging Face
MODEL_NAME = "Falconsai/nsfw_image_detection"

class NSFWClassifier:
    """
    Wrapper for Vision Transformer NSFW classification.
    """
    
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._pipe = None
        
    def _load_model(self):
        """Lazy load the classification pipeline."""
        if self._pipe is not None:
            return
            
        if not HAS_TRANSFORMERS:
            raise ImportError("transformers and pillow are required for NSFW classification.")
            
        logger.info(f"Loading NSFW classifier model: {self.model_name}...")
        try:
            # Load the pipeline
            self._pipe = pipeline("image-classification", model=self.model_name)
            logger.info("NSFW classifier loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load NSFW classifier: {e}")
            raise
            
    def classify_frame(self, frame_path: Path) -> Dict[str, float]:
        """
        Classify a frame as safe/nsfw.
        
        Returns:
            Dict mapping labels ('normal', 'nsfw') to confidence scores.
        """
        self._load_model()
        
        try:
            results = self._pipe(str(frame_path))
            
            # Convert pipeline results to simple dict
            # Example: [{'label': 'nsfw', 'score': 0.9}, {'label': 'normal', 'score': 0.1}]
            scores = {res['label']: res['score'] for res in results}
            return scores
        except Exception as e:
            logger.warning(f"Failed to classify frame {frame_path}: {e}")
            return {'normal': 1.0, 'nsfw': 0.0}

    def is_safe(self, frame_path: Path, nsfw_threshold: float = 0.5) -> bool:
        """
        Quick check if a frame is safe.
        """
        scores = self.classify_frame(frame_path)
        return scores.get('nsfw', 0.0) < nsfw_threshold

# Global instance
_classifier: Optional[NSFWClassifier] = None

def get_classifier() -> NSFWClassifier:
    global _classifier
    if _classifier is None:
        _classifier = NSFWClassifier()
    return _classifier
