"""
Keyboard Shortcuts Overlay for Video Censor.

A semi-transparent overlay showing all available keyboard shortcuts.
Toggle with ? or F1.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame
)
from PySide6.QtCore import Qt


class ShortcutsOverlay(QWidget):
    """Semi-transparent overlay showing all keyboard shortcuts."""
    
    SHORTCUTS = {
        "General": [
            ("Ctrl+O", "Open video"),
            ("Ctrl+1-9", "Open recent files"),
            ("Ctrl+Shift+F", "Open output folder"),
            ("Ctrl+,", "Preferences"),
            ("?", "Toggle this help"),
            ("Esc", "Close help / Cancel"),
        ],
        "Detection Review": [
            ("K", "Keep detection"),
            ("S", "Skip detection"),
            ("E", "Expand region (+0.5s)"),
            ("R", "Reduce region (-0.5s)"),
            ("←", "Previous detection"),
            ("→", "Next detection"),
            ("Space", "Seek to detection"),
        ],
        "Editing": [
            ("Ctrl+Z", "Undo"),
            ("Ctrl+Shift+Z", "Redo"),
            ("Ctrl+Y", "Redo (Windows)"),
            ("Ctrl+S", "Save detections"),
            ("Ctrl+Shift+S", "Save detections as..."),
        ],
        "Playback": [
            ("Space", "Play/pause"),
            ("J", "Jump back 5s"),
            ("L", "Jump forward 5s"),
            ("Home", "Go to start"),
            ("End", "Go to end"),
        ],
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._setup_ui()
    
    def _setup_ui(self):
        # Semi-transparent background
        self.setStyleSheet("""
            ShortcutsOverlay {
                background-color: rgba(6, 6, 10, 0.95);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 50, 60, 50)
        
        # Header
        header = QLabel("⌨️ Keyboard Shortcuts")
        header.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #ffffff;
            background: transparent;
        """)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Press ? or Esc to close")
        subtitle.setStyleSheet("color: #6b7280; font-size: 13px; background: transparent;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(30)
        
        # Shortcuts grid - 2 columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(50)
        
        categories = list(self.SHORTCUTS.keys())
        mid = (len(categories) + 1) // 2
        
        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(20)
        for cat in categories[:mid]:
            left_col.addWidget(self._create_category(cat, self.SHORTCUTS[cat]))
        left_col.addStretch()
        columns_layout.addLayout(left_col)
        
        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(20)
        for cat in categories[mid:]:
            right_col.addWidget(self._create_category(cat, self.SHORTCUTS[cat]))
        right_col.addStretch()
        columns_layout.addLayout(right_col)
        
        layout.addLayout(columns_layout)
        layout.addStretch()
    
    def _create_category(self, name: str, shortcuts: list) -> QFrame:
        """Create a category section with shortcuts."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(31, 31, 42, 0.8);
                border-radius: 12px;
                border: 1px solid #282838;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        
        # Category header
        header = QLabel(name)
        header.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #6366f1;
            background: transparent;
            padding-bottom: 6px;
        """)
        layout.addWidget(header)
        
        # Shortcuts
        for key, description in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(12)
            
            key_label = QLabel(key)
            key_label.setStyleSheet("""
                background-color: #374151;
                color: #f9fafb;
                padding: 5px 10px;
                border-radius: 6px;
                font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
                font-size: 12px;
                font-weight: 600;
            """)
            key_label.setAlignment(Qt.AlignCenter)
            key_label.setFixedWidth(110)
            
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #d1d5db; font-size: 13px; background: transparent;")
            
            row.addWidget(key_label)
            row.addWidget(desc_label)
            row.addStretch()
            
            layout.addLayout(row)
        
        return frame
    
    def toggle(self):
        """Toggle visibility."""
        if self.isVisible():
            self.hide()
        else:
            # Resize to parent
            if self.parent():
                self.setGeometry(self.parent().rect())
            self.show()
            self.raise_()
            self.setFocus()
    
    def keyPressEvent(self, event):
        """Close on Esc or ?"""
        if event.key() in (Qt.Key_Escape, Qt.Key_Question):
            self.hide()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Close on click."""
        self.hide()
