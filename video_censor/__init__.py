"""
Video Censor Tool
=================

A fully local, offline video editing tool that automatically detects and 
censors profanity and nudity from video files.

All processing happens on-device with no cloud API calls.
"""

__version__ = "0.1.0"
__author__ = "Video Censor Tool"

# Export key classes for convenience
from .preferences import ContentFilterSettings, Profile
from .profile_manager import ProfileManager
from .queue import QueueItem, ProcessingQueue
