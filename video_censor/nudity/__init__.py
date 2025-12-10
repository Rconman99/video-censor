"""Nudity detection subpackage."""

from .extractor import extract_frames, FrameInfo
from .detector import detect_nudity, NudityDetection

__all__ = ['extract_frames', 'FrameInfo', 'detect_nudity', 'NudityDetection']
