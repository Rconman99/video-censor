"""
Violence detector using CLIP for zero-shot frame classification.

Uses OpenAI's CLIP model to classify video frames for violent content
based on text descriptions. Runs fully locally with no API calls.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import os

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_clip_model = None
_clip_processor = None
_torch = None


@dataclass
class ViolenceInterval:
    """A time interval containing violent content."""
    start: float
    end: float
    level: int  # 1 = graphic, 2 = fighting
    confidence: float
    description: str = ""


# Text prompts for violence detection - cumulative levels
# Level 1: Gore only (blood, graphic wounds)
GORE_PROMPTS = [
    "blood and gore",
    "bloody wound",
    "graphic injury",
    "blood splatter",
    "gruesome bloody scene",
    "mutilated body",
    "severed limb",
    "open wound with blood",
]

# Level 2: Death/killing (adds to Level 1)
DEATH_PROMPTS = [
    "person being killed",
    "person being shot",
    "person being stabbed",
    "dead body",
    "murder scene",
    "execution scene",
    "fatal shooting",
    "lethal violence",
]

# Level 3: Fighting/combat (adds to Levels 1 & 2)
FIGHTING_PROMPTS = [
    "people fighting",
    "physical combat",
    "fist fight",
    "punching someone",
    "kicking someone",
    "violent brawl",
    "martial arts fighting",
    "sword fight",
    "gun fight shootout",
    "physical assault",
    "beating someone up",
    "wrestling violently",
]

# Combined prompt sets for each level
LEVEL_1_PROMPTS = GORE_PROMPTS  # Gore only
LEVEL_2_PROMPTS = GORE_PROMPTS + DEATH_PROMPTS  # Gore + Death
LEVEL_3_PROMPTS = GORE_PROMPTS + DEATH_PROMPTS + FIGHTING_PROMPTS  # All violence

SAFE_PROMPTS = [
    "peaceful scene",
    "people talking calmly",
    "nature landscape",
    "happy family",
    "normal conversation",
    "everyday activity",
]


def _load_clip():
    """Load CLIP model lazily."""
    global _clip_model, _clip_processor, _torch
    
    if _clip_model is not None:
        return _clip_model, _clip_processor
    
    try:
        import torch
        from transformers import CLIPProcessor, CLIPModel
        
        _torch = torch
        
        logger.info("Loading CLIP model for violence detection...")
        model_name = "openai/clip-vit-base-patch32"
        
        _clip_processor = CLIPProcessor.from_pretrained(model_name)
        _clip_model = CLIPModel.from_pretrained(model_name)
        
        # Use MPS on Apple Silicon if available
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            _clip_model = _clip_model.to("mps")
            logger.info("Using Apple Silicon GPU (MPS) for CLIP")
        
        _clip_model.eval()
        logger.info("CLIP model loaded successfully")
        
        return _clip_model, _clip_processor
        
    except ImportError as e:
        logger.error(f"Failed to import CLIP dependencies: {e}")
        logger.error("Install with: pip install transformers torch")
        raise


class ViolenceDetector:
    """
    Detects violent content in video frames using CLIP.
    
    Uses zero-shot classification against text prompts describing
    violence at different intensity levels.
    """
    
    def __init__(
        self,
        level: int = 1,
        threshold: float = 0.3,
        batch_size: int = 8
    ):
        """
        Initialize the violence detector.
        
        Args:
            level: Detection level (1 = graphic only, 2 = all fighting)
            threshold: Confidence threshold for detection (0.0-1.0)
            batch_size: Number of frames to process at once
        """
        self.level = level
        self.threshold = threshold
        self.batch_size = batch_size
        self.model = None
        self.processor = None
        
        # Select prompts based on level
        # Level 0: Keep all (no prompts)
        # Level 1: Gore only
        # Level 2: Gore + Death
        # Level 3: Gore + Death + Fighting (all violence)
        if level >= 3:
            self.violence_prompts = LEVEL_3_PROMPTS
        elif level == 2:
            self.violence_prompts = LEVEL_2_PROMPTS
        elif level == 1:
            self.violence_prompts = LEVEL_1_PROMPTS
        else:
            self.violence_prompts = []  # Level 0 - keep all
    
    def _ensure_model(self):
        """Ensure CLIP model is loaded."""
        if self.model is None:
            self.model, self.processor = _load_clip()
    
    def classify_frame(self, image) -> Tuple[bool, float, str]:
        """
        Classify a single frame for violence.
        
        Args:
            image: PIL Image to classify
            
        Returns:
            Tuple of (is_violent, confidence, description)
        """
        self._ensure_model()
        
        # Combine all prompts
        all_prompts = self.violence_prompts + SAFE_PROMPTS
        
        # Process image and text
        inputs = self.processor(
            text=all_prompts,
            images=image,
            return_tensors="pt",
            padding=True
        )
        
        # Move to same device as model
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Get predictions
        with _torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
        
        # Sum probabilities for violence vs safe prompts
        n_violence = len(self.violence_prompts)
        violence_prob = probs[0, :n_violence].sum().item()
        safe_prob = probs[0, n_violence:].sum().item()
        
        # Normalize
        total = violence_prob + safe_prob
        if total > 0:
            violence_confidence = violence_prob / total
        else:
            violence_confidence = 0.0
        
        is_violent = violence_confidence >= self.threshold
        
        # Get top matching violence prompt if violent
        description = ""
        if is_violent:
            top_idx = probs[0, :n_violence].argmax().item()
            description = self.violence_prompts[top_idx]
        
        return is_violent, violence_confidence, description
    
    def detect_intervals(
        self,
        frame_paths: List[Tuple[float, Path]],
        min_segment_duration: float = 0.5,
        buffer_before: float = 0.25,
        buffer_after: float = 0.25,
        merge_gap: float = 1.0,
        show_progress: bool = True
    ) -> List[ViolenceInterval]:
        """
        Detect violence intervals from a list of frame paths with timestamps.
        
        Args:
            frame_paths: List of (timestamp, path) tuples
            min_segment_duration: Minimum duration for a violence segment
            buffer_before: Seconds to add before detected segments
            buffer_after: Seconds to add after detected segments
            merge_gap: Merge segments closer than this
            show_progress: Show progress bar
            
        Returns:
            List of ViolenceInterval objects
        """
        from PIL import Image
        
        self._ensure_model()
        
        if not frame_paths:
            return []
        
        # Sort by timestamp
        frame_paths = sorted(frame_paths, key=lambda x: x[0])
        
        # Detect violence in each frame
        detections = []
        total = len(frame_paths)
        
        for i, (timestamp, path) in enumerate(frame_paths):
            if show_progress and i % 10 == 0:
                pct = int(100 * i / total)
                logger.info(f"Analyzing frames for violence... {pct}%")
            
            try:
                image = Image.open(path).convert("RGB")
                is_violent, confidence, desc = self.classify_frame(image)
                
                if is_violent:
                    detections.append((timestamp, confidence, desc))
                    
            except Exception as e:
                logger.warning(f"Failed to process frame {path}: {e}")
        
        if show_progress:
            logger.info("Analyzing frames for violence... 100%")
        
        logger.info(f"Found {len(detections)} violent frames out of {total}")
        
        if not detections:
            return []
        
        # Convert detections to intervals
        intervals = self._detections_to_intervals(
            detections,
            frame_paths,
            min_segment_duration,
            buffer_before,
            buffer_after,
            merge_gap
        )
        
        return intervals
    
    def _detections_to_intervals(
        self,
        detections: List[Tuple[float, float, str]],
        frame_paths: List[Tuple[float, Path]],
        min_duration: float,
        buffer_before: float,
        buffer_after: float,
        merge_gap: float
    ) -> List[ViolenceInterval]:
        """Convert frame detections to time intervals."""
        if not detections:
            return []
        
        # Calculate frame interval
        if len(frame_paths) >= 2:
            frame_interval = frame_paths[1][0] - frame_paths[0][0]
        else:
            frame_interval = 0.25  # Default
        
        # Create initial intervals around each detection
        raw_intervals = []
        for timestamp, confidence, desc in detections:
            start = max(0, timestamp - buffer_before)
            end = timestamp + frame_interval + buffer_after
            raw_intervals.append(ViolenceInterval(
                start=start,
                end=end,
                level=self.level,
                confidence=confidence,
                description=desc
            ))
        
        # Merge overlapping/close intervals
        merged = self._merge_intervals(raw_intervals, merge_gap)
        
        # Filter by minimum duration
        result = [iv for iv in merged if (iv.end - iv.start) >= min_duration]
        
        logger.info(f"Created {len(result)} violence intervals")
        return result
    
    def _merge_intervals(
        self,
        intervals: List[ViolenceInterval],
        gap: float
    ) -> List[ViolenceInterval]:
        """Merge overlapping or close intervals."""
        if not intervals:
            return []
        
        sorted_ivs = sorted(intervals, key=lambda x: x.start)
        merged = [sorted_ivs[0]]
        
        for iv in sorted_ivs[1:]:
            last = merged[-1]
            if iv.start <= last.end + gap:
                # Merge
                merged[-1] = ViolenceInterval(
                    start=last.start,
                    end=max(last.end, iv.end),
                    level=max(last.level, iv.level),
                    confidence=max(last.confidence, iv.confidence),
                    description=last.description or iv.description
                )
            else:
                merged.append(iv)
        
        return merged


def detect_violence(
    frame_paths: List[Tuple[float, Path]],
    level: int = 1,
    threshold: float = 0.3,
    min_segment_duration: float = 0.5,
    buffer_before: float = 0.25,
    buffer_after: float = 0.25,
    merge_gap: float = 1.0,
    show_progress: bool = True
) -> List[ViolenceInterval]:
    """
    Convenience function to detect violence in video frames.
    
    Args:
        frame_paths: List of (timestamp, path) tuples
        level: Detection level (1 = graphic only, 2 = all fighting)
        threshold: Confidence threshold (0.0-1.0)
        min_segment_duration: Minimum segment duration in seconds
        buffer_before: Buffer time before detected segments
        buffer_after: Buffer time after detected segments
        merge_gap: Merge segments closer than this
        show_progress: Show progress indicators
        
    Returns:
        List of ViolenceInterval objects
    """
    detector = ViolenceDetector(level=level, threshold=threshold)
    return detector.detect_intervals(
        frame_paths,
        min_segment_duration=min_segment_duration,
        buffer_before=buffer_before,
        buffer_after=buffer_after,
        merge_gap=merge_gap,
        show_progress=show_progress
    )
