import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Tuple
from functools import wraps

from .logging_config import get_logger, get_log_dir

logger = get_logger(__name__)

LOG_FILE = get_log_dir() / "videocensor.log"


class UserFriendlyError(Exception):
    """Exception with a user-friendly message"""
    def __init__(self, user_message: str, technical_message: str = None):
        self.user_message = user_message
        self.technical_message = technical_message or user_message
        super().__init__(self.technical_message)


# Error message mappings
ERROR_MESSAGES = {
    # File errors
    FileNotFoundError: lambda e: (
        "File not found",
        f"The file could not be found. It may have been moved or deleted.\n\n"
        f"Path: {e.filename if hasattr(e, 'filename') else 'Unknown'}"
    ),
    PermissionError: lambda e: (
        "Permission denied", 
        "Unable to access this file. Please check that you have permission "
        "to read/write to this location."
    ),
    IsADirectoryError: lambda e: (
        "Invalid file",
        "Expected a file but got a folder. Please select a video file."
    ),
    
    # Video/FFmpeg errors
    "ffmpeg": lambda e: (
        "Video processing error",
        "There was a problem processing the video. This might happen if:\n\n"
        "• The video file is corrupted\n"
        "• The format isn't supported\n"
        "• FFmpeg isn't installed correctly\n\n"
        "Try a different video file or convert to MP4."
    ),
    
    # Memory errors
    MemoryError: lambda e: (
        "Out of memory",
        "Your computer ran out of memory. Try:\n\n"
        "• Closing other applications\n"
        "• Using 'Low Power' mode in Preferences\n"
        "• Processing a shorter video"
    ),
    "CUDA out of memory": lambda e: (
        "GPU memory full",
        "Not enough GPU memory. The app will continue using CPU mode (slower).\n\n"
        "To avoid this, use 'Low Power' mode in Preferences."
    ),
    
    # Network errors
    ConnectionError: lambda e: (
        "Connection failed",
        "Unable to connect to the internet. Please check your connection.\n\n"
        "Note: Video processing works offline. Only cloud sync requires internet."
    ),
    TimeoutError: lambda e: (
        "Connection timed out",
        "The connection took too long. Please try again."
    ),
    
    # Model errors
    "model": lambda e: (
        "AI model error",
        "There was a problem with the AI model. Try:\n\n"
        "• Restarting the app\n"
        "• Re-running the setup wizard (Help > Re-run Setup)\n"
        "• Using a smaller model in Preferences"
    ),
    "whisper": lambda e: (
        "Speech recognition error",
        "Unable to analyze audio. The file might not have an audio track, "
        "or the audio format isn't supported."
    ),
    "nudenet": lambda e: (
        "Visual detection error", 
        "Unable to analyze video frames. The video format might not be supported."
    ),
    
    # Config errors
    "yaml": lambda e: (
        "Settings file error",
        "Your settings file is corrupted. Would you like to reset to defaults?\n\n"
        "Your custom wordlists will be preserved."
    ),
    
    # Disk errors
    OSError: lambda e: (
        "Disk error",
        "Unable to read or write files. Please check:\n\n"
        "• You have enough disk space\n"
        "• The drive isn't disconnected\n"
        "• You have write permission to the output folder"
    ),
}


def get_friendly_message(error: Exception) -> Tuple[str, str]:
    """Get user-friendly title and message for an error"""
    error_str = str(error).lower()
    
    # Check exact type matches first
    for error_type, msg_func in ERROR_MESSAGES.items():
        if isinstance(error_type, type) and isinstance(error, error_type):
            return msg_func(error)
    
    # Check string matches in error message (case-insensitive)
    for key, msg_func in ERROR_MESSAGES.items():
        if isinstance(key, str) and key.lower() in error_str:
            return msg_func(error)
    
    # Default fallback
    return (
        "Something went wrong",
        f"An unexpected error occurred:\n\n{str(error)[:200]}\n\n"
        "Please try again. If the problem persists, check the log file:\n"
        f"{LOG_FILE}"
    )


def handle_error(error: Exception, context: str = "") -> Tuple[str, str]:
    """Log error and return friendly message"""
    # Log full technical details
    logger.error(f"Error in {context}: {error}")
    logger.debug(traceback.format_exc())
    
    # Return friendly message
    return get_friendly_message(error)


def safe_operation(context: str = "operation"):
    """Decorator for safe error handling"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except UserFriendlyError:
                raise  # Already friendly, pass through
            except Exception as e:
                title, message = handle_error(e, context)
                raise UserFriendlyError(message, str(e)) from e
        return wrapper
    return decorator
