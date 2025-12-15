"""
Review Panel for Video Censor.
Wraps the TimelineWidget and Detection Browser for reviewing and exporting edits.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QSplitter
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent
from .timeline import TimelineWidget
from .player import VideoPlayerWidget
from .detection_browser import DetectionBrowserPanel


class ReviewPanel(QFrame):
    """
    Panel for reviewing analysis results before export.
    Contains video player, timeline, detection browser, and action buttons.
    """
    
    export_requested = Signal()  # Emitted when user clicks Export
    cancel_requested = Signal()  # Emitted when user clicks Cancel
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "panel")
        self.setVisible(False)
        self._data = {}  # Store data for detection browser
        self._video_path = None
        self._duration = 0
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        
        title_section = QVBoxLayout()
        title = QLabel("📝 Review & Edit")
        title.setProperty("class", "section-header")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f5f5f8;")
        title_section.addWidget(title)
        
        subtitle = QLabel("Review detections • Keep or Delete • Click timeline to preview")
        subtitle.setStyleSheet("color: #71717a; font-size: 11px;")
        title_section.addWidget(subtitle)
        
        header.addLayout(title_section)
        header.addStretch()
        
        # Keyboard hints
        hints = QLabel("K = Keep • D = Delete • ←→ = Navigate")
        hints.setStyleSheet("""
            color: #52525b; 
            font-size: 10px; 
            background: #1a1a24; 
            padding: 6px 12px; 
            border-radius: 4px;
        """)
        header.addWidget(hints)
        
        layout.addLayout(header)
        
        # Main horizontal splitter: Left (player + timeline) | Right (detection browser)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(2)
        main_splitter.setStyleSheet("QSplitter::handle { background: #2a2a35; }")
        
        # Left side: Player + Timeline
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Vertical splitter for Player and Timeline
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setHandleWidth(1)
        v_splitter.setStyleSheet("QSplitter::handle { background: #2a2a35; }")
        
        # Player Container
        self.player = VideoPlayerWidget()
        self.player.setMinimumHeight(280)
        self.player.position_changed.connect(self._on_player_position)
        self.player.duration_changed.connect(self._on_player_duration)
        v_splitter.addWidget(self.player)
        
        # Timeline Container
        t_widget = QWidget()
        t_layout = QVBoxLayout(t_widget)
        t_layout.setContentsMargins(0, 10, 0, 0)
        t_layout.setSpacing(8)
        
        # Editing Toolbar
        toolbar = QHBoxLayout()
        
        lbl_edit = QLabel("Edit Controls:")
        lbl_edit.setStyleSheet("color: #71717a; font-weight: bold; font-size: 11px;")
        toolbar.addWidget(lbl_edit)
        
        self.btn_mark_nudity = QPushButton("👁 Mark Nudity")
        self.btn_mark_nudity.setToolTip("Mark current position as start/end of nudity")
        self.btn_mark_nudity.clicked.connect(lambda: self._mark_segment("nudity"))
        self.btn_mark_nudity.setStyleSheet("""
            QPushButton {
                background: #2a2a38;
                color: #f43f5e;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: #3a3a48; }
        """)
        toolbar.addWidget(self.btn_mark_nudity)
        
        self.btn_mark_profanity = QPushButton("🤬 Mark Profanity")
        self.btn_mark_profanity.clicked.connect(lambda: self._mark_segment("profanity"))
        self.btn_mark_profanity.setStyleSheet("""
            QPushButton {
                background: #2a2a38;
                color: #fbbf24;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: #3a3a48; }
        """)
        toolbar.addWidget(self.btn_mark_profanity)
        
        toolbar.addStretch()
        t_layout.addLayout(toolbar)
        
        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.player.set_position)
        t_layout.addWidget(self.timeline)
        
        v_splitter.addWidget(t_widget)
        v_splitter.setSizes([400, 200])
        
        left_layout.addWidget(v_splitter)
        main_splitter.addWidget(left_widget)
        
        # Right side: Detection Browser
        self.detection_browser = DetectionBrowserPanel()
        self.detection_browser.segment_deleted.connect(self._on_segment_deleted)
        self.detection_browser.segment_kept.connect(self._on_segment_kept)
        self.detection_browser.seek_to_segment.connect(self._on_seek_to_segment)
        main_splitter.addWidget(self.detection_browser)
        
        # Set splitter sizes (70% left, 30% right)
        main_splitter.setSizes([700, 300])
        
        layout.addWidget(main_splitter, 1)
        
        # Actions Footer
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()
        
        self.cancel_btn = QPushButton("Discard")
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a38;
                color: #a0a0b0;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3a3a48; }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_click)
        actions.addWidget(self.cancel_btn)
        
        self.export_btn = QPushButton("▶ Export Censored Video")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #16a34a);
                font-weight: 600;
                padding: 12px 24px;
                border: none; 
                border-radius: 6px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ade80, stop:1 #22c55e);
            }
        """)
        self.export_btn.clicked.connect(self._on_export_click)
        actions.addWidget(self.export_btn)
        
        layout.addLayout(actions)
        
        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts for detection review."""
        key = event.key()
        
        if key == Qt.Key_K:
            # Keep current detection
            self._browser_keep_current()
        elif key == Qt.Key_D:
            # Delete current detection
            self._browser_delete_current()
        elif key == Qt.Key_Left and event.modifiers() == Qt.ControlModifier:
            # Previous detection
            self.detection_browser._go_previous()
        elif key == Qt.Key_Right and event.modifiers() == Qt.ControlModifier:
            # Next detection
            self.detection_browser._go_next()
        else:
            super().keyPressEvent(event)
            
    def _browser_keep_current(self):
        """Keep the first remaining detection in the to-review list."""
        to_review = self.detection_browser.data.get(self.detection_browser.current_track, [])
        if to_review:
            self.detection_browser._on_keep(to_review[0])
            
    def _browser_delete_current(self):
        """Delete the first remaining detection in the to-review list."""
        to_review = self.detection_browser.data.get(self.detection_browser.current_track, [])
        if to_review:
            self.detection_browser._on_delete(to_review[0])
        
    def load_data(self, video_path: str, duration: float, data: dict):
        """Load data into the timeline, player, and detection browser."""
        self._video_path = video_path
        self._duration = duration
        self._data = data
        
        self.player.load_video(video_path)
        self.timeline.set_data(duration, data)
        self.detection_browser.set_data(data)
        self.setVisible(True)
        
    def _on_player_position(self, ms: int):
        self.timeline.set_position(ms)
        
    def _on_player_duration(self, ms: int):
        pass  # Timeline uses float seconds, typically set via load_data
        
    def _mark_segment(self, track_type: str):
        """Mark in/out point for new segment."""
        print(f"Mark requested for {track_type} at {self.timeline.time_label.text()}")
        
    def _on_segment_deleted(self, track_key: str, segment: dict):
        """Handle segment deletion from browser."""
        # Update timeline
        self.timeline.remove_segment(track_key, segment)
        
    def _on_segment_kept(self, track_key: str, segment: dict):
        """Handle segment kept (ignored) from browser."""
        # Update timeline visualization
        self.timeline.update()
        
    def _on_seek_to_segment(self, segment: dict):
        """Seek video to segment start."""
        start_ms = int(segment.get('start', 0) * 1000)
        self.player.set_position(start_ms)
        # Highlight segment in timeline
        self.timeline.highlight_segment(segment)
    
    def stop_playback(self):
        """Stop video playback and release media."""
        self.player.media_player.stop()
        
    def _on_export_click(self):
        """Handle export button click - stop video first."""
        self.stop_playback()
        self.export_requested.emit()
        
    def _on_cancel_click(self):
        """Handle cancel button click - stop video first."""
        self.stop_playback()
        self.cancel_requested.emit()
        
    def get_data(self) -> dict:
        """Get the current edit state (with deleted segments removed, kept segments marked as ignored)."""
        return self.detection_browser.get_final_data()
