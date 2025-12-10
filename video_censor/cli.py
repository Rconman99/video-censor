#!/usr/bin/env python3
"""
Video Censor CLI Entry Point

This module provides the command-line interface for the video-censor package.
When installed via pip, users can run `video-censor` to launch the GUI.
"""

import sys
from pathlib import Path


def main():
    """Main entry point for the video-censor command."""
    # Ensure the package root is in the path
    package_root = Path(__file__).parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    
    # Import and run the GUI
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette, QColor
    
    from ui.main_window import MainWindow
    from ui.styles import DARK_STYLESHEET
    
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
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
