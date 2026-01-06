#!/usr/bin/env python3
"""
Video Censor Desktop Application - Main Entry Point

Launch with: python main.py
"""

import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from ui.main_window import MainWindow
from ui.styles import DARK_STYLESHEET

from video_censor.error_handler import handle_error, logger
from ui.error_dialog import show_error

def global_exception_handler(exc_type, exc_value, exc_tb):
    """Handle uncaught exceptions globally"""
    # Don't catch keyboard interrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    
    # Log and show error
    import traceback
    details = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    title, message = handle_error(exc_value, "uncaught exception")
    
    logger.critical(f"Uncaught exception: {exc_value}")
    logger.critical(details)
    
    # Show dialog if app is running
    app = QApplication.instance()
    if app:
        show_error(title, message, details)

# Install global handler
sys.excepthook = global_exception_handler


def main():
    """Main entry point for the Video Censor desktop app."""
    # Create application
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Video Censor")
    app.setApplicationDisplayName("Video Censor")
    app.setOrganizationName("VideoCensor")
    
    # Force dark palette for the entire application
    dark_palette = QPalette()
    
    # Primary colors
    bg_darkest = QColor("#06060a")
    bg_dark = QColor("#0c0c12")
    bg_panel = QColor("#12121a")
    fg_primary = QColor("#f8f8fc")
    fg_secondary = QColor("#b8b8c8")
    accent = QColor("#3b82f6")
    
    # Set palette colors
    dark_palette.setColor(QPalette.Window, bg_darkest)
    dark_palette.setColor(QPalette.WindowText, fg_primary)
    dark_palette.setColor(QPalette.Base, bg_panel)
    dark_palette.setColor(QPalette.AlternateBase, bg_dark)
    dark_palette.setColor(QPalette.ToolTipBase, bg_panel)
    dark_palette.setColor(QPalette.ToolTipText, fg_primary)
    dark_palette.setColor(QPalette.Text, fg_primary)
    dark_palette.setColor(QPalette.Button, bg_panel)
    dark_palette.setColor(QPalette.ButtonText, fg_primary)
    dark_palette.setColor(QPalette.BrightText, Qt.white)
    dark_palette.setColor(QPalette.Link, accent)
    dark_palette.setColor(QPalette.Highlight, accent)
    dark_palette.setColor(QPalette.HighlightedText, Qt.white)
    dark_palette.setColor(QPalette.PlaceholderText, fg_secondary)
    
    # Apply palette
    app.setPalette(dark_palette)
    
    # Apply dark stylesheet
    app.setStyleSheet(DARK_STYLESHEET)
    
    # Create and show main window - checks for first run first
    from video_censor.first_run import FirstRunManager
    
    # Check for first run
    if FirstRunManager.is_first_run():
        from ui.setup_wizard import SetupWizard
        
        wizard = SetupWizard()
        result = wizard.exec()
        
        if result == SetupWizard.Accepted:
            # Save settings from wizard
            _apply_wizard_settings(wizard)
            FirstRunManager.mark_setup_complete()
        else:
            # User cancelled setup - exit app
            sys.exit(0)

    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


def _apply_wizard_settings(wizard):
    """Apply settings chosen in wizard to config."""
    from video_censor.config import Config
    
    try:
        use_case = wizard.field("use_case")
        performance = wizard.field("performance")
        
        # Map use case to preset
        preset_map = {
            0: "family_friendly",
            1: "youtube_safe",
            2: "default",
            3: "minimal"
        }
        
        # Map performance to mode
        perf_map = {
            0: "low_power",
            1: "balanced",
            2: "high_performance"
        }
        
        # Load, update, and save config
        config = Config.load()
        if hasattr(wizard, 'use_case_value'): # Manual prop check
             use_case = wizard.use_case_value
             
        preset_key = preset_map.get(use_case, "default")
        # Note: preset application logic would go here if Config supported quick storage
        # For now we just set individual prefs or print logger (stub implementation)
        # config.apply_preset(preset_key)
        
        config.performance.hardware_acceleration = "auto"
        # Map performance mode to specific settings
        mode = perf_map.get(performance, "low_power")
        
        if mode == "low_power":
            config.performance.parallel_detection = False
            config.performance.stagger_delay = 2.0
        elif mode == "high_performance":
             config.performance.parallel_detection = True
             config.performance.stagger_delay = 0.5
        
        config.save()
        
    except Exception as e:
        print(f"Error applying wizard settings: {e}")


if __name__ == "__main__":
    main()
