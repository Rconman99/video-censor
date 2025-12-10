"""
Violence detection module.

Provides CLIP-based detection of violent content in video frames.
"""

from .detector import detect_violence, ViolenceDetector

__all__ = ['detect_violence', 'ViolenceDetector']
