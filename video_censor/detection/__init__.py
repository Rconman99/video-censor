"""
Detection utilities for video censoring.

Contains confidence scoring and signal merging logic.
"""

from .confidence_merger import (
    ConfidenceMerger,
    ConfidenceConfig,
    DetectionSignal,
    MergedDetection,
    create_merger_from_config,
)

__all__ = [
    'ConfidenceMerger',
    'ConfidenceConfig',
    'DetectionSignal',
    'MergedDetection',
    'create_merger_from_config',
]
