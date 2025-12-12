"""
Feedback Dialog for Video Censor
Shows processed videos and allows users to:
- Rate the editing quality (Star Rating)
- Report timestamps where they heard/saw something that wasn't censored
- Provide additional comments
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit,
    QGroupBox, QWidget, QFrame, QScrollArea, QMessageBox,
    QGraphicsDropShadowEffect, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QBrush, QIcon
import json
import logging
from pathlib import Path
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


class StarRatingWidget(QWidget):
    """
    Custom 5-star rating widget with hover effects.
    """
    ratingChanged = Signal(int)

    def __init__(self, parent=None, size=32):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._rating = 0
        self._hover_rating = 0
        self._star_size = size
        self.setMinimumSize(size * 5 + 20, size + 10)
        
        # Colors
        self.color_active = QColor("#fbbf24")  # Amber-400
        self.color_inactive = QColor("#4b5563") # Gray-600
        self.color_hover = QColor("#f59e0b")    # Amber-500
        
    def setRating(self, rating: int):
        self._rating = rating
        self.update()

    def rating(self) -> int:
        return self._rating

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for i in range(1, 6):
            # Determine color
            if self._hover_rating >= i:
                color = self.color_hover
            elif self._rating >= i:
                color = self.color_active
            else:
                color = self.color_inactive
            
            self._draw_star(painter, i, color)

    def _draw_star(self, painter, index, color):
        size = self._star_size
        spacing = 4
        x = (index - 1) * (size + spacing)
        y = 2
        
        # Create star path
        path = QPainterPath()
        cx, cy = x + size/2, y + size/2
        outer_radius = size/2
        inner_radius = size/4
        
        import math
        angle = math.pi / 2 * 3  # Start at top
        step = math.pi / 5
        
        path.moveTo(cx + outer_radius * math.cos(angle), cy + outer_radius * math.sin(angle))
        for _ in range(5):
            angle += step
            path.lineTo(cx + inner_radius * math.cos(angle), cy + inner_radius * math.sin(angle))
            angle += step
            path.lineTo(cx + outer_radius * math.cos(angle), cy + outer_radius * math.sin(angle))
        path.closeSubpath()
        
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        width_per_star = self._star_size + 4
        hover_idx = min(5, max(1, int(x // width_per_star) + 1))
        
        if self._hover_rating != hover_idx:
            self._hover_rating = hover_idx
            self.update()

    def leaveEvent(self, event):
        self._hover_rating = 0
        self.update()

    def mousePressEvent(self, event):
        if self._hover_rating > 0:
            self._rating = self._hover_rating
            self.ratingChanged.emit(self._rating)
            self.update()


class VideoListItemWidget(QFrame):
    """Custom widget for detailed video list item."""
    
    def __init__(self, video: ProcessedVideo, parent=None):
        super().__init__(parent)
        self.video = video
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border-radius: 6px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Icon/Thumbnail placeholder
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("font-size: 24px; background: transparent;")
        layout.addWidget(icon_label)
        
        # Text info
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title = QLabel(video.title)
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f3f4f6; background: transparent;")
        text_layout.addWidget(title)
        
        date_str = video.processed_at.split('T')[0] if 'T' in video.processed_at else video.processed_at
        meta = QLabel(f"{date_str}")
        meta.setStyleSheet("color: #9ca3af; font-size: 11px; background: transparent;")
        text_layout.addWidget(meta)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Status
        if video.feedback_submitted:
            status = QLabel("✓")
            status.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px; background: transparent;")
            layout.addWidget(status)


class TimestampReportWidget(QFrame):
    """Widget for reporting a single timestamp issue."""
    
    removed = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: #18181b; /* Zinc-900 */
                border: 1px solid #27272a; /* Zinc-800 */
                border-radius: 6px;
                padding: 4px;
            }
            QLabel { background: transparent; color: #d4d4d8; } /* Zinc-300 */
            QLineEdit, QComboBox {
                background: #09090b; /* Zinc-950 */
                border: 1px solid #27272a; /* Zinc-800 */
                border-radius: 4px;
                color: #f3f4f6;
                padding: 4px;
            }
            QPushButton {
                background: transparent;
                color: #71717a; /* Zinc-500 */
                border: none;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover { 
                color: #ef4444; /* Red-500 */
                background: rgba(239, 68, 68, 0.1);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        
        # Timestamp input (using generic QLineEdit for hh:mm:ss format possibility)
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("00:00:00")
        self.time_input.setFixedWidth(80)
        layout.addWidget(self.time_input)
        
        # Issue type
        self.issue_type = QComboBox()
        self.issue_type.addItems([
            "Heard profanity",
            "Saw nudity",
            "Saw violence",
            "Other"
        ])
        layout.addWidget(self.issue_type, 1)
        
        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)
    
    def get_data(self) -> Dict[str, Any]:
        val = self.time_input.text().strip()
        # Convert HH:MM:SS to seconds for backend if needed, or keep as string
        # For now, simplistic parsing
        seconds = 0.0
        try:
            parts = val.split(':')
            if len(parts) == 3:
                seconds = int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
            elif len(parts) == 2:
                seconds = int(parts[0])*60 + float(parts[1])
            else:
                seconds = float(val)
        except:
            pass # Keep 0
            
        return {
            'timestamp': seconds,
            'timestamp_str': val,
            'issue_type': self.issue_type.currentText()
        }


class FeedbackDialog(QDialog):
    """Modern Dialog for submitting feedback."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feedback - Rate Editing")
        self.resize(850, 600)
        
        # Global dark styling
        self.setStyleSheet("""
            QDialog {
                background-color: #09090b; /* Zinc-950 */
                color: #f3f4f6;
            }
            QLabel {
                color: #e4e4e7; /* Zinc-200 */
            }
            QGroupBox {
                border: 1px solid #27272a; /* Zinc-800 */
                border-radius: 8px;
                margin-top: 24px;
                font-weight: 600;
                color: #a1a1aa; /* Zinc-400 */
                padding-top: 16px;
                background: #18181b; /* Zinc-900 */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #18181b;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3f3f46; /* Zinc-700 */
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #52525b; /* Zinc-600 */
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #09090b; /* Zinc-950 */
                border: 1px solid #27272a; /* Zinc-800 */
                border-radius: 6px;
                color: #f3f4f6;
                padding: 8px;
                selection-background-color: #f59e0b; /* Amber-500 */
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #f59e0b; /* Amber-500 */
            }
        """)
        
        self._timestamp_widgets: List[TimestampReportWidget] = []
        self._current_video: Optional[ProcessedVideo] = None
        self._setup_ui()
        self._load_videos()
    
    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- LEFT SIDEBAR (Video List) ---
        sidebar = QFrame()
        sidebar.setStyleSheet("background-color: #18181b; border-right: 1px solid #27272a;") # Zinc-900, Zinc-800
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        
        sidebar_header = QLabel("Processed Videos")
        sidebar_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        sidebar_header.setStyleSheet("color: #f4f4f5; padding-bottom: 10px; background: transparent;")
        sidebar_layout.addWidget(sidebar_header)
        
        self.video_list = QListWidget()
        self.video_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 6px;
                margin-bottom: 4px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #27272a; /* Zinc-800 */
                border: 1px solid #3f3f46; /* Zinc-700 */
            }
            QListWidget::item:hover:ab !selected {
                background: #27272a; /* Zinc-800 */
            }
        """)
        self.video_list.currentItemChanged.connect(self._on_video_selected)
        sidebar_layout.addWidget(self.video_list)
        
        main_layout.addWidget(sidebar)
        
        # --- RIGHT CONTENT ---
        content_area = QWidget()
        content_area.setStyleSheet("background-color: #09090b;") # Zinc-950
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(24)
        
        # Header Info
        self.video_title = QLabel("Select a video")
        self.video_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.video_title.setStyleSheet("color: #ffffff;")
        content_layout.addWidget(self.video_title)
        
        self.video_meta = QLabel("")
        self.video_meta.setStyleSheet("color: #9ca3af; font-size: 13px;")
        content_layout.addWidget(self.video_meta)
        
        # Rating Section (Custom Star Widget)
        rating_group = QGroupBox("Rate the Editing")
        rating_layout = QVBoxLayout(rating_group)
        rating_layout.setContentsMargins(20, 20, 20, 20)
        
        self.rating_widget = StarRatingWidget(size=36)
        self.rating_widget.ratingChanged.connect(self._on_rating_changed)
        
        # Center the stars
        stars_container = QHBoxLayout()
        stars_container.addStretch()
        stars_container.addWidget(self.rating_widget)
        stars_container.addStretch()
        rating_layout.addLayout(stars_container)
        
        self.rating_label = QLabel("Click to rate")
        self.rating_label.setAlignment(Qt.AlignCenter)
        self.rating_label.setStyleSheet("color: #6b7280; font-size: 12px; margin-top: 8px;")
        rating_layout.addWidget(self.rating_label)
        
        content_layout.addWidget(rating_group)
        
        # Missed Content Section
        issues_group = QGroupBox("Report Missed Content")
        issues_layout = QVBoxLayout(issues_group)
        issues_layout.setContentsMargins(20, 20, 20, 20)
        
        desc = QLabel("Did we miss anything? Add a timestamp and short note.")
        desc.setStyleSheet("color: #9ca3af; margin-bottom: 10px;")
        desc.setWordWrap(True)
        issues_layout.addWidget(desc)
        
        # Scroll area for dynamic inputs
        input_scroll = QScrollArea()
        input_scroll.setWidgetResizable(True)
        input_scroll.setFixedHeight(120)
        input_scroll.setStyleSheet("background: transparent;")
        
        self.issues_container = QWidget()
        self.issues_container.setStyleSheet("background: transparent;")
        self.issues_inner_layout = QVBoxLayout(self.issues_container)
        self.issues_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.issues_inner_layout.setSpacing(8)
        self.issues_inner_layout.addStretch()
        
        input_scroll.setWidget(self.issues_container)
        issues_layout.addWidget(input_scroll)
        
        # Add button
        add_btn = QPushButton("+ Add Issue")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #1f2937;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover { background: #374151; }
        """)
        add_btn.clicked.connect(self._add_timestamp_widget)
        issues_layout.addWidget(add_btn, alignment=Qt.AlignLeft)
        
        content_layout.addWidget(issues_group)
        
        # Comments Section
        comments_group = QGroupBox("Additional Comments")
        comments_layout = QVBoxLayout(comments_group)
        comments_layout.setContentsMargins(20, 20, 20, 20)
        
        self.comments_edit = QTextEdit()
        self.comments_edit.setPlaceholderText("Share your thoughts...")
        self.comments_edit.setFixedHeight(80)
        self.comments_edit.setStyleSheet("""
            QTextEdit {
                background: #111827;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #f3f4f6;
                padding: 8px;
            }
        """)
        comments_layout.addWidget(self.comments_edit)
        content_layout.addWidget(comments_group)
        
        content_layout.addStretch()
        
        # Footer Action
        self.submit_btn = QPushButton("Submit Feedback")
        self.submit_btn.setEnabled(False)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.setFixedHeight(44)
        # Gradient Style matching MainWindow
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309); /* Amber-600/700 */
                color: white;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706); /* Amber-500/600 */
            }
            QPushButton:disabled {
                background: #27272a; /* Zinc-800 */
                color: #52525b; /* Zinc-600 */
            }
        """)
        self.submit_btn.clicked.connect(self._submit_feedback)
        content_layout.addWidget(self.submit_btn)
        
        main_layout.addWidget(content_area, stretch=1)

    def _load_videos(self):
        self.video_list.clear()
        history = load_history()
        
        for video in history:
            item = QListWidgetItem(self.video_list)
            item.setSizeHint(QSize(200, 60))
            item.setData(Qt.UserRole, video)
            
            # Create Custom Widget
            widget = VideoListItemWidget(video)
            self.video_list.setItemWidget(item, widget)
            
        if not history:
             # Handle empty state if needed
             pass

    def _on_video_selected(self, current, previous):
        if not current:
            return
            
        video = current.data(Qt.UserRole)
        if not isinstance(video, ProcessedVideo):
            return
            
        self._current_video = video
        self.video_title.setText(video.title)
        self.video_meta.setText(f"Processed on {video.processed_at}")
        
        # Reset form
        self.rating_widget.setRating(video.rating if video.rating else 0)
        self._on_rating_changed(self.rating_widget.rating())
        self.comments_edit.clear()
        
        # Clear issues
        for w in self._timestamp_widgets:
            w.deleteLater()
        self._timestamp_widgets.clear()
        
        self.submit_btn.setEnabled(True)

    def _on_rating_changed(self, rating):
        labels = {
            0: "Click to rate",
            1: "Poor",
            2: "Fair",
            3: "Good",
            4: "Very Good",
            5: "Excellent"
        }
        self.rating_label.setText(labels.get(rating, ""))

    def _add_timestamp_widget(self):
        widget = TimestampReportWidget()
        widget.removed.connect(self._remove_timestamp_widget)
        self._timestamp_widgets.append(widget)
        # Add before the stretch
        count = self.issues_inner_layout.count()
        self.issues_inner_layout.insertWidget(count - 1, widget)

    def _remove_timestamp_widget(self, widget):
        if widget in self._timestamp_widgets:
            self._timestamp_widgets.remove(widget)
            widget.deleteLater()

    def _submit_feedback(self):
        if not self._current_video:
            return
            
        try:
            # Gather data
            rating = self.rating_widget.rating()
            comments = self.comments_edit.toPlainText()
            issues = [w.get_data() for w in self._timestamp_widgets]
            
            # TODO: actual telemetry submission can go here
            # from video_censor.telemetry import get_telemetry
            # telemetry = get_telemetry()
            # ...
            
            # Update local history
            self._current_video.rating = rating
            self._current_video.feedback_submitted = True
            
            history = load_history()
            for i, v in enumerate(history):
                if v.file_path == self._current_video.file_path:
                    history[i] = self._current_video
                    break
            save_history(history)
            
            QMessageBox.information(self, "Success", "Thank you for your feedback!")
            self._load_videos() # Refresh list to show checkmark
            
        except Exception as e:
            logger.error(f"Submit failed: {e}")
            QMessageBox.warning(self, "Error", f"Failed to submit: {e}")

