"""
Review Panel for Video Censor.
Wraps the TimelineWidget and provides controls for reviewing and exporting edits.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QSplitter
)
from PySide6.QtCore import Signal, Qt
from .timeline import TimelineWidget
from .player import VideoPlayerWidget

class ReviewPanel(QFrame):
    """
    Panel for reviewing analysis results before export.
    Contains the timeline and action buttons.
    """
    
    export_requested = Signal()  # Emitted when user clicks Export
    cancel_requested = Signal()  # Emitted when user clicks Cancel
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "panel")
        self.setVisible(False)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        
        title_section = QVBoxLayout()
        title = QLabel("📝 Review & Edit")
        title.setProperty("class", "section-header")
        title_section.addWidget(title)
        
        subtitle = QLabel("Click segments to toggle them (dimmed = kept)")
        subtitle.setStyleSheet("color: #71717a; font-size: 11px;")
        title_section.addWidget(subtitle)
        
        header.addLayout(title_section)
        header.addStretch()
        layout.addLayout(header)
        
        header.addLayout(title_section)
        header.addStretch()
        layout.addLayout(header)
        
        # Splitter for Player and Timeline
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #2a2a35; }")
        
        # Player Container
        self.player = VideoPlayerWidget()
        self.player.setMinimumHeight(300)
        self.player.position_changed.connect(self._on_player_position)
        self.player.duration_changed.connect(self._on_player_duration)
        splitter.addWidget(self.player)
        
        # Timeline Container
        t_widget = QWidget()
        t_layout = QVBoxLayout(t_widget)
        t_layout.setContentsMargins(0, 10, 0, 0)
        
        # Editing Toolbar
        toolbar = QHBoxLayout()
        
        lbl_edit = QLabel("Edit Controls:")
        lbl_edit.setStyleSheet("color: #71717a; font-weight: bold; font-size: 11px;")
        toolbar.addWidget(lbl_edit)
        
        self.btn_mark_nudity = QPushButton("👁 Mark Nudity")
        self.btn_mark_nudity.setToolTip("Mark current position as start/end of nudity")
        self.btn_mark_nudity.clicked.connect(lambda: self._mark_segment("nudity"))
        toolbar.addWidget(self.btn_mark_nudity)
        
        self.btn_mark_profanity = QPushButton("🤬 Mark Profanity")
        self.btn_mark_profanity.clicked.connect(lambda: self._mark_segment("profanity"))
        toolbar.addWidget(self.btn_mark_profanity)
        
        toolbar.addStretch()
        t_layout.addLayout(toolbar)
        
        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.player.set_position)
        t_layout.addWidget(self.timeline)
        
        splitter.addWidget(t_widget)
        
        layout.addWidget(splitter, 1)
        
        # Actions
        actions = QHBoxLayout()
        actions.addStretch()
        
        self.cancel_btn = QPushButton("Discard")
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        actions.addWidget(self.cancel_btn)
        
        self.export_btn = QPushButton("▶ Export Censored Video")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #16a34a);
                font-weight: 600;
                padding: 10px 20px;
                border: none; 
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ade80, stop:1 #22c55e);
            }
        """)
        self.export_btn.clicked.connect(self.export_requested.emit)
        actions.addWidget(self.export_btn)
        
        layout.addLayout(actions)
        
    def load_data(self, video_path: str, duration: float, data: dict):
        """Load data into the timeline and player."""
        self.player.load_video(video_path)
        self.timeline.set_data(duration, data)
        self.setVisible(True)
        
    def _on_player_position(self, ms: int):
        self.timeline.set_position(ms)
        
    def _on_player_duration(self, ms: int):
        pass # Timeline uses float seconds, typically set via load_data
        
    def _mark_segment(self, track_type: str):
        # TODO: Implement mark in/out logic
        # For prototype: Just print
        print(f"Mark requested for {track_type} at {self.timeline.time_label.text()}")
        
    def get_data(self) -> dict:
        """Get the current edit state (ignored segments)."""
        # TimelineWidget keeps track of state in its self.tracks[title].segments
        # We need to collect it back
        
        result = {}
        for title, track in self.timeline.tracks.items():
            # Map title back to key? (TimelineWidget titles are "Nudity", "Profanity")
            key = title.lower().replace(" ", "_") # Profanity -> profanity, Sexual Content -> sexual_content
            result[key] = track.segments
            
        return result
