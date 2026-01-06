"""
VideoCard component for queue items.
Clean, professional display of video processing status.
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from pathlib import Path


class VideoCard(QFrame):
    """A card displaying video processing status with clean UI."""
    
    pause_clicked = Signal()
    cancel_clicked = Signal()
    remove_clicked = Signal()
    
    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.is_paused = False
        self.is_processing = True
        
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header row: filename + actions
        header = QHBoxLayout()
        header.setSpacing(8)
        
        # Filename with ellipsis
        self.filename_label = QLabel()
        self.filename_label.setFont(QFont("", 14, QFont.Weight.Bold))
        self._set_filename(self.video_path)
        header.addWidget(self.filename_label, 1)
        
        # Pause button
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setFixedWidth(100)
        self.pause_btn.setFixedHeight(32)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #b0b0c0;
                border: 1px solid #303040;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #282840;
                border-color: #404060;
            }
        """)
        header.addWidget(self.pause_btn)
        
        # Cancel/Remove button
        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setToolTip("Cancel processing")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #2a1f1f;
                color: #ff6b6b;
                border: 1px solid #403030;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3a2020;
                border-color: #5a3030;
            }
        """)
        header.addWidget(self.cancel_btn)
        
        layout.addLayout(header)
        
        # Progress section
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(6)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1a1a25;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # Status row: stage + percentage
        status_row = QHBoxLayout()
        
        self.stage_label = QLabel("Preparing...")
        self.stage_label.setStyleSheet("color: #71717a; font-size: 12px;")
        status_row.addWidget(self.stage_label)
        
        status_row.addStretch()
        
        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("", 13, QFont.Weight.Bold))
        self.percent_label.setStyleSheet("color: #f5f5f8;")
        status_row.addWidget(self.percent_label)
        
        progress_layout.addLayout(status_row)
        layout.addLayout(progress_layout)
        
        # Time estimate (optional)
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        layout.addWidget(self.time_label)
    
    def _apply_style(self):
        self.setStyleSheet("""
            VideoCard {
                background-color: #161620;
                border: 1px solid #282838;
                border-radius: 12px;
            }
            VideoCard:hover {
                border-color: #383850;
            }
        """)
    
    def _set_filename(self, path: str):
        """Set filename with smart truncation"""
        name = Path(path).stem
        
        # Truncate middle if too long
        max_len = 45
        if len(name) > max_len:
            half = (max_len - 3) // 2
            name = f"{name[:half]}...{name[-half:]}"
        
        self.filename_label.setText(name)
        self.filename_label.setToolTip(Path(path).name)
    
    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_btn.setText("▶ Resume")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background: #1f2e1f;
                    color: #90d090;
                    border: 1px solid #304030;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #284028;
                }
            """)
        else:
            self.pause_btn.setText("⏸ Pause")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background: #1f1f2e;
                    color: #b0b0c0;
                    border: 1px solid #303040;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #282840;
                    border-color: #404060;
                }
            """)
        self.pause_clicked.emit()
    
    def _on_cancel(self):
        if self.is_processing:
            self.cancel_clicked.emit()
        else:
            self.remove_clicked.emit()
    
    def set_progress(self, percent: int, stage: str = None):
        """Update progress display"""
        self.progress_bar.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        
        if stage:
            self.stage_label.setText(stage)
    
    def set_time_estimate(self, seconds_remaining: int):
        """Show time estimate"""
        if seconds_remaining > 0:
            if seconds_remaining > 3600:
                time_str = f"~{seconds_remaining // 3600}h {(seconds_remaining % 3600) // 60}m remaining"
            elif seconds_remaining > 60:
                time_str = f"~{seconds_remaining // 60}m remaining"
            else:
                time_str = f"~{seconds_remaining}s remaining"
            self.time_label.setText(time_str)
        else:
            self.time_label.setText("")
    
    def set_processing(self, is_processing: bool):
        """Update processing state"""
        self.is_processing = is_processing
        if is_processing:
            self.cancel_btn.setText("✕ Cancel")
            self.cancel_btn.setToolTip("Cancel processing")
            self.pause_btn.setVisible(True)
        else:
            self.cancel_btn.setText("🗑 Remove")
            self.cancel_btn.setToolTip("Remove from queue")
            self.pause_btn.setVisible(False)
    
    def set_complete(self):
        """Mark as complete"""
        self.progress_bar.setValue(100)
        self.percent_label.setText("✓ Complete")
        self.percent_label.setStyleSheet("color: #22c55e; font-weight: bold;")
        self.stage_label.setText("Ready for review")
        self.pause_btn.setVisible(False)
        self.time_label.setText("")
        self.set_processing(False)
    
    def set_error(self, message: str):
        """Show error state"""
        self.percent_label.setText("✕ Error")
        self.percent_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        self.stage_label.setText(message[:50] + "..." if len(message) > 50 else message)
        self.pause_btn.setVisible(False)
        self.set_processing(False)
