"""
Feedback Dialog for Video Censor

Shows processed videos and allows users to:
- Rate the editing quality
- Report timestamps where they heard/saw something that wasn't censored
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QSpinBox,
    QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox,
    QWidget, QFrame, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Local history file
HISTORY_FILE = Path.home() / ".video_censor_history.json"


class ProcessedVideo:
    """Represents a processed video in history."""
    
    def __init__(
        self,
        title: str,
        file_path: str,
        processed_at: str,
        duration_seconds: float = 0,
        detection_id: str = None,
        rating: int = 0,
        feedback_submitted: bool = False
    ):
        self.title = title
        self.file_path = file_path
        self.processed_at = processed_at
        self.duration_seconds = duration_seconds
        self.detection_id = detection_id
        self.rating = rating
        self.feedback_submitted = feedback_submitted
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'file_path': self.file_path,
            'processed_at': self.processed_at,
            'duration_seconds': self.duration_seconds,
            'detection_id': self.detection_id,
            'rating': self.rating,
            'feedback_submitted': self.feedback_submitted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessedVideo':
        return cls(**data)


def load_history() -> List[ProcessedVideo]:
    """Load processed video history from local file."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
        return [ProcessedVideo.from_dict(v) for v in data]
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return []


def save_history(videos: List[ProcessedVideo]):
    """Save processed video history to local file."""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump([v.to_dict() for v in videos], f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


def add_to_history(video: ProcessedVideo):
    """Add a video to the processing history."""
    history = load_history()
    # Check if already exists, update if so
    for i, v in enumerate(history):
        if v.file_path == video.file_path:
            history[i] = video
            save_history(history)
            return
    history.insert(0, video)  # Add to front
    history = history[:50]  # Keep last 50
    save_history(history)


class TimestampReportWidget(QWidget):
    """Widget for reporting a single timestamp issue."""
    
    removed = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # Timestamp input
        self.timestamp_spin = QDoubleSpinBox()
        self.timestamp_spin.setRange(0, 99999)
        self.timestamp_spin.setSuffix(" sec")
        self.timestamp_spin.setDecimals(1)
        self.timestamp_spin.setMinimumWidth(100)
        layout.addWidget(QLabel("At:"))
        layout.addWidget(self.timestamp_spin)
        
        # Issue type
        self.issue_type = QComboBox()
        self.issue_type.addItems([
            "Heard profanity",
            "Saw nudity",
            "Saw violence",
            "Other"
        ])
        layout.addWidget(self.issue_type)
        
        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedWidth(30)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)
    
    def get_data(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp_spin.value(),
            'issue_type': self.issue_type.currentText()
        }


class FeedbackDialog(QDialog):
    """Dialog for submitting feedback on processed videos."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feedback - Rate Your Cleaned Videos")
        self.setMinimumSize(600, 500)
        self._timestamp_widgets: List[TimestampReportWidget] = []
        self._current_video: Optional[ProcessedVideo] = None
        self._setup_ui()
        self._load_videos()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(15)
        
        # Left side - Video list
        left_panel = QVBoxLayout()
        
        left_label = QLabel("📽️ Processed Videos")
        left_label.setFont(QFont("", 14, QFont.Bold))
        left_panel.addWidget(left_label)
        
        self.video_list = QListWidget()
        self.video_list.currentItemChanged.connect(self._on_video_selected)
        left_panel.addWidget(self.video_list)
        
        layout.addLayout(left_panel, 1)
        
        # Right side - Feedback form
        right_panel = QVBoxLayout()
        
        # Selected video info
        self.video_title = QLabel("Select a video")
        self.video_title.setFont(QFont("", 16, QFont.Bold))
        right_panel.addWidget(self.video_title)
        
        self.video_info = QLabel("")
        self.video_info.setStyleSheet("color: #888;")
        right_panel.addWidget(self.video_info)
        
        right_panel.addSpacing(10)
        
        # Rating section
        rating_group = QGroupBox("⭐ Rate the Editing")
        rating_layout = QHBoxLayout(rating_group)
        
        rating_layout.addWidget(QLabel("Rating:"))
        self.rating_spin = QSpinBox()
        self.rating_spin.setRange(1, 5)
        self.rating_spin.setValue(5)
        self.rating_spin.setSuffix(" / 5")
        rating_layout.addWidget(self.rating_spin)
        rating_layout.addStretch()
        
        right_panel.addWidget(rating_group)
        
        # Timestamp issues section
        issues_group = QGroupBox("🕐 Report Missed Content")
        issues_layout = QVBoxLayout(issues_group)
        
        issues_layout.addWidget(QLabel("Did you hear or see something that wasn't censored?"))
        
        # Scroll area for timestamp reports
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(150)
        
        self.timestamps_container = QWidget()
        self.timestamps_layout = QVBoxLayout(self.timestamps_container)
        self.timestamps_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.timestamps_container)
        issues_layout.addWidget(scroll)
        
        add_timestamp_btn = QPushButton("+ Add Timestamp Report")
        add_timestamp_btn.clicked.connect(self._add_timestamp_widget)
        issues_layout.addWidget(add_timestamp_btn)
        
        right_panel.addWidget(issues_group)
        
        # Additional comments
        comments_group = QGroupBox("💬 Additional Comments")
        comments_layout = QVBoxLayout(comments_group)
        self.comments_edit = QTextEdit()
        self.comments_edit.setPlaceholderText("Any other feedback about the editing...")
        self.comments_edit.setMaximumHeight(80)
        comments_layout.addWidget(self.comments_edit)
        right_panel.addWidget(comments_group)
        
        right_panel.addStretch()
        
        # Submit button
        self.submit_btn = QPushButton("📤 Submit Feedback")
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self._submit_feedback)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        right_panel.addWidget(self.submit_btn)
        
        layout.addLayout(right_panel, 2)
    
    def _load_videos(self):
        """Load processed videos into the list."""
        self.video_list.clear()
        history = load_history()
        
        for video in history:
            item = QListWidgetItem()
            status = "✅" if video.feedback_submitted else "📝"
            item.setText(f"{status} {video.title}")
            item.setData(Qt.UserRole, video)
            self.video_list.addItem(item)
        
        if not history:
            item = QListWidgetItem("No videos processed yet")
            item.setFlags(Qt.NoItemFlags)
            self.video_list.addItem(item)
    
    def _on_video_selected(self, current, previous):
        """Handle video selection."""
        if not current:
            return
        
        video = current.data(Qt.UserRole)
        if not isinstance(video, ProcessedVideo):
            return
        
        self._current_video = video
        self.video_title.setText(video.title)
        
        # Format duration
        mins = int(video.duration_seconds // 60)
        secs = int(video.duration_seconds % 60)
        duration_str = f"{mins}:{secs:02d}"
        
        self.video_info.setText(f"Processed: {video.processed_at} | Duration: {duration_str}")
        self.rating_spin.setValue(video.rating if video.rating else 5)
        self.submit_btn.setEnabled(True)
        
        # Clear timestamp widgets
        for w in self._timestamp_widgets:
            w.deleteLater()
        self._timestamp_widgets.clear()
    
    def _add_timestamp_widget(self):
        """Add a new timestamp report widget."""
        widget = TimestampReportWidget()
        widget.removed.connect(self._remove_timestamp_widget)
        self._timestamp_widgets.append(widget)
        self.timestamps_layout.addWidget(widget)
    
    def _remove_timestamp_widget(self, widget):
        """Remove a timestamp report widget."""
        if widget in self._timestamp_widgets:
            self._timestamp_widgets.remove(widget)
            widget.deleteLater()
    
    def _submit_feedback(self):
        """Submit feedback to the cloud."""
        if not self._current_video:
            return
        
        try:
            from video_censor.telemetry import get_telemetry
            telemetry = get_telemetry()
            
            # Collect timestamp reports
            timestamp_reports = [w.get_data() for w in self._timestamp_widgets]
            
            # Submit each timestamp as feedback
            for report in timestamp_reports:
                telemetry.submit_feedback(
                    detection_id=self._current_video.detection_id,
                    feedback_type='missed_content',
                    segment_start=report['timestamp'],
                    segment_end=report['timestamp'] + 1,
                    comment=f"{report['issue_type']}: {self.comments_edit.toPlainText()}"
                )
            
            # Update local history
            self._current_video.rating = self.rating_spin.value()
            self._current_video.feedback_submitted = True
            
            history = load_history()
            for i, v in enumerate(history):
                if v.file_path == self._current_video.file_path:
                    history[i] = self._current_video
                    break
            save_history(history)
            
            QMessageBox.information(
                self,
                "Feedback Submitted",
                "Thank you! Your feedback helps improve the app."
            )
            
            # Refresh list
            self._load_videos()
            
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            QMessageBox.warning(
                self,
                "Submission Failed",
                f"Could not submit feedback: {str(e)}"
            )
