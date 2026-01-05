"""
Multi-signal confirmation for detection accuracy.

Combines signals from multiple detectors to reduce false positives.
Requires agreement or high confidence before censoring.

Features:
- Weighted scoring from audio, visual, and transcript signals
- Confidence thresholds for different signal combinations
- Configurable weights and boost values
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class DetectionSignal:
    """A single detection signal from any detector."""
    detector: str  # 'profanity', 'nudity', 'sexual_content', 'llm_context'
    start: float
    end: float
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MergedDetection:
    """Result of merging multiple signals."""
    start: float
    end: float
    should_censor: bool
    total_score: float
    confidence: float
    signals: List[DetectionSignal] = field(default_factory=list)
    reason: str = ""


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring."""
    # Signal weights
    profanity_weight: float = 0.4
    nudity_weight: float = 0.4
    sexual_content_weight: float = 0.3
    llm_context_weight: float = 0.2
    
    # Thresholds
    single_signal_threshold: float = 0.9  # Very high for single signal
    multi_signal_threshold: float = 0.6   # Lower when signals agree
    
    # Boost when multiple modalities agree
    agreement_boost: float = 0.3
    
    # Require multi-signal (stricter mode)
    require_multi_signal: bool = False


class ConfidenceMerger:
    """
    Merges detection signals to determine censoring decisions.
    
    Reduces false positives by requiring multiple signals or
    very high confidence from a single detector.
    """
    
    def __init__(self, config: Optional[ConfidenceConfig] = None):
        self.config = config or ConfidenceConfig()
    
    def should_censor(self, signals: Dict[str, Any]) -> tuple[bool, float, str]:
        """
        Determine if content should be censored based on signals.
        
        Args:
            signals: Dict with keys like:
                - profanity_detected: bool
                - profanity_confidence: float (0-1)
                - nudity_score: float (0-1)
                - explicit_dialog: bool
                - context_confirmed: bool (from LLM)
                
        Returns:
            Tuple of (should_censor, confidence, reason)
        """
        score = 0.0
        reasons = []
        cfg = self.config
        
        # Audio/profanity signal
        if signals.get('profanity_detected'):
            profanity_conf = signals.get('profanity_confidence', 1.0)
            contribution = cfg.profanity_weight * profanity_conf
            score += contribution
            reasons.append(f"profanity({profanity_conf:.1f})")
        
        # Visual/nudity signal
        nudity_score = signals.get('nudity_score', 0)
        if nudity_score > 0.5:
            contribution = cfg.nudity_weight * nudity_score
            score += contribution
            reasons.append(f"nudity({nudity_score:.1f})")
        
        # Explicit dialog signal
        if signals.get('explicit_dialog') or signals.get('sexual_content_detected'):
            explicit_conf = signals.get('sexual_content_confidence', 0.8)
            contribution = cfg.sexual_content_weight * explicit_conf
            score += contribution
            reasons.append(f"sexual({explicit_conf:.1f})")
        
        # LLM context confirmation (positive signal)
        if signals.get('context_confirmed'):
            score += cfg.llm_context_weight
            reasons.append("context_confirmed")
        
        # Count active signal types
        signal_count = sum([
            signals.get('profanity_detected', False),
            signals.get('nudity_score', 0) > 0.5,
            signals.get('explicit_dialog', False) or signals.get('sexual_content_detected', False),
        ])
        
        # Apply agreement boost if multiple modalities
        if signal_count >= 2:
            score += cfg.agreement_boost
            reasons.append(f"multi_signal_boost(+{cfg.agreement_boost})")
        
        # Determine threshold based on signal count
        if signal_count >= 2:
            threshold = cfg.multi_signal_threshold
        else:
            threshold = cfg.single_signal_threshold
        
        # Strict mode: require multiple signals
        if cfg.require_multi_signal and signal_count < 2:
            return (False, score, f"Multi-signal required (only {signal_count} signal)")
        
        should_censor = score >= threshold
        reason = f"score={score:.2f} threshold={threshold:.2f} signals=[{', '.join(reasons)}]"
        
        return (should_censor, score, reason)
    
    def merge_overlapping(
        self,
        signals: List[DetectionSignal],
        time_tolerance: float = 0.5
    ) -> List[MergedDetection]:
        """
        Merge overlapping detection signals into unified detections.
        
        Args:
            signals: List of DetectionSignal from all detectors
            time_tolerance: Max gap between signals to consider overlapping
            
        Returns:
            List of MergedDetection with combined scores
        """
        if not signals:
            return []
        
        # Sort by start time
        sorted_signals = sorted(signals, key=lambda s: s.start)
        merged = []
        current_group: List[DetectionSignal] = []
        current_end = -1.0
        
        for signal in sorted_signals:
            if current_end < 0 or signal.start <= current_end + time_tolerance:
                # Add to current group
                current_group.append(signal)
                current_end = max(current_end, signal.end)
            else:
                # Finalize current group and start new
                if current_group:
                    merged.append(self._finalize_group(current_group))
                current_group = [signal]
                current_end = signal.end
        
        # Finalize last group
        if current_group:
            merged.append(self._finalize_group(current_group))
        
        return merged
    
    def _finalize_group(self, group: List[DetectionSignal]) -> MergedDetection:
        """Convert a group of signals into a MergedDetection."""
        if not group:
            raise ValueError("Cannot finalize empty group")
        
        start = min(s.start for s in group)
        end = max(s.end for s in group)
        
        # Build signals dict for should_censor
        signals_dict = {}
        for signal in group:
            if signal.detector == 'profanity':
                signals_dict['profanity_detected'] = True
                signals_dict['profanity_confidence'] = signal.confidence
            elif signal.detector == 'nudity':
                signals_dict['nudity_score'] = signal.confidence
            elif signal.detector == 'sexual_content':
                signals_dict['sexual_content_detected'] = True
                signals_dict['sexual_content_confidence'] = signal.confidence
            elif signal.detector == 'llm_context':
                signals_dict['context_confirmed'] = signal.confidence > 0.5
        
        should_censor, score, reason = self.should_censor(signals_dict)
        
        return MergedDetection(
            start=start,
            end=end,
            should_censor=should_censor,
            total_score=score,
            confidence=min(1.0, score),  # Cap at 1.0
            signals=group,
            reason=reason
        )


def create_merger_from_config(config) -> ConfidenceMerger:
    """
    Create a ConfidenceMerger from a Config object.
    
    Args:
        config: Main Config object with detection settings
        
    Returns:
        Configured ConfidenceMerger
    """
    # Get weights from sexual_content config if available
    if hasattr(config, 'sexual_content'):
        sc = config.sexual_content
        confidence_config = ConfidenceConfig(
            nudity_weight=getattr(sc, 'visual_weight', 0.6),
            profanity_weight=getattr(sc, 'audio_weight', 0.4),
            agreement_boost=getattr(sc, 'agreement_boost', 0.3),
            require_multi_signal=getattr(sc, 'use_multimodal_fusion', False)
        )
    else:
        confidence_config = ConfidenceConfig()
    
    return ConfidenceMerger(confidence_config)
