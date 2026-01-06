"""
Centralized logging configuration for VideoCensor.

This module provides a single logging setup path that works for both CLI and GUI modes.
Logs are stored in ~/.videocensor/logs/ with rotation.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


# Global flag to prevent duplicate initialization
_logging_initialized = False

# Default log directory
LOG_DIR = Path.home() / ".videocensor" / "logs"


def get_log_dir() -> Path:
    """Get the log directory, creating it if necessary."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True,
    force: bool = False,
    debug_mode: bool = False,
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional custom log file path. If None, uses default.
        console: Whether to log to console/stderr
        force: Force reconfiguration even if already initialized
        debug_mode: Enable verbose debug logging with file rotation
    
    Returns:
        The root logger
    """
    global _logging_initialized
    
    if _logging_initialized and not force:
        return logging.getLogger("video_censor")
    
    # Determine log level
    if debug_mode:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Get root logger for our namespace
    root_logger = logging.getLogger("video_censor")
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
    else:
        log_dir = get_log_dir()
        log_path = log_dir / "videocensor.log"
    
    # Create parent directory if needed
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Rotating file handler: 5MB max, keep 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG if debug_mode else log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Debug file for detailed logging (only in debug mode)
    if debug_mode:
        debug_path = get_log_dir() / "videocensor_debug.log"
        debug_handler = logging.handlers.RotatingFileHandler(
            debug_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=2,
            encoding="utf-8",
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        debug_handler.setFormatter(debug_formatter)
        root_logger.addHandler(debug_handler)
    
    _logging_initialized = True
    
    root_logger.debug(f"Logging initialized: level={level}, file={log_path}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Usage:
        from video_censor.logging_config import get_logger
        logger = get_logger(__name__)
    """
    # Ensure logging is set up with defaults
    if not _logging_initialized:
        setup_logging()
    
    return logging.getLogger(name)


def enable_debug_logging():
    """Enable debug logging mode (can be called at runtime)."""
    setup_logging(level="DEBUG", debug_mode=True, force=True)


def get_log_file_path() -> Path:
    """Get the path to the main log file."""
    return get_log_dir() / "videocensor.log"
