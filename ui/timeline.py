"""
Interactive Timeline Widget for Video Censor.
Visualizes detected content segments and allows user interaction.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, 
    QToolTip, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRectF, QPoint, QSize
from PySide6.QtCore import Qt, Signal, QRectF, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QMouseEvent

class TimelineTrack(QWidget):
    """A single track in the timeline (e.g., Nudity, Profanity)."""
    
    segment_clicked = Signal(object)  # Emits segment data
    
    def __init__(self, title: str, color: QColor, duration: float, segments: list, parent=None):
        super().__init__(parent)
        self.track_title = title
        self.base_color = color
        self.duration = max(0.1, duration)
        self.segments = segments
        self.setFixedHeight(30)
        self.setMouseTracking(True)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#1f1f2a"))
        
        # Draw segments
        width = self.width()
        height = self.height()
        
        for seg in self.segments:
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            
            x1 = (start / self.duration) * width
            x2 = (end / self.duration) * width
            w = max(2, x2 - x1)
            
            # Check if ignored/overridden
            is_ignored = seg.get('ignored', False)
            color = QColor(self.base_color)
            if is_ignored:
                color.setAlpha(50) # Dimmed
            else:
                color.setAlpha(200)
                
            rect = QRectF(x1, 2, w, height - 4)
            painter.fillRect(rect, color)
            
            # Border if hovered (not implemented per segment yet, simple hover handled globally)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            width = self.width()
            time = (x / width) * self.duration
            
            # Find clicked segment
            for seg in self.segments:
                if seg.get('start', 0) <= time <= seg.get('end', 0):
                    self.segment_clicked.emit(seg)
                    self.update() # Repaint
                    return
                    
    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        width = self.width()
        time = (x / width) * self.duration
        
        # Tooltip
        found = False
        for seg in self.segments:
            if seg.get('start', 0) <= time <= seg.get('end', 0):
                label = seg.get('label', self.track_title)
                start = self._format_time(seg['start'])
                end = self._format_time(seg['end'])
                QToolTip.showText(event.globalPosition().toPoint(), f"{label}\n{start} - {end}", self)
                found = True
                break
        
        if not found:
            QToolTip.hideText()
            
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class TimelineWidget(QWidget):
    """Main timeline widget containing multiple tracks."""
    
    seek_requested = Signal(int)  # Emitted when user clicks to seek (ms)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header / Ruler
        self.header_layout = QHBoxLayout()
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: #71717a; font-family: monospace;")
        self.header_layout.addWidget(self.time_label)
        self.header_layout.addStretch()
        self.layout.addLayout(self.header_layout)
        
        # Tracks container
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout(self.tracks_container)
        self.tracks_layout.setSpacing(4)
        self.tracks_layout.setContentsMargins(0,0,0,0)
        self.layout.addWidget(self.tracks_container)
        
        self.duration = 0
        self.current_position = 0 # in ms
        self.tracks = {}

    def set_position(self, position_ms: int):
        """Update current playback position."""
        self.current_position = position_ms
        self.time_label.setText(self._format_time(position_ms / 1000))
        self.update() # Trigger repaint for playhead

    def paintEvent(self, event):
        """Draw the playhead overlay."""
        super().paintEvent(event)
        
        if self.duration <= 0:
            return
            
        # Draw tracks first (handled by children widgets)
        # We need to draw the playhead ON TOP of everything
        # Since child widgets paint over this widget, we can't easily draw on top efficiently without an overlay.
        # Alternative: Ask tracks to draw the line? No.
        # Better: Use a transparent overlay widget OR simply handle mouse clicks here and let the container manage the line.
        # Actually, simpler approach for now:
        # Just update the time label.
        # Drawing a line across multiple child widgets is tricky in Qt without an overlay.
        # Let's add a "PlayheadOverlay" class if needed, or just draw it on the tracks themselves?
        
        # New approach: Pass current position to tracks and let them draw it?
        pass

    def mousePressEvent(self, event: QMouseEvent):
        """Handle clicking on the background/header to seek."""
        if self.duration > 0 and event.button() == Qt.LeftButton:
            x = event.position().x()
            width = self.width()
            seek_time_ms = int((x / width) * (self.duration * 1000))
            self.seek_requested.emit(seek_time_ms)

    def set_data(self, duration: float, data: dict):
        """
        Load detection data.
        data = {
            'nudity': [...],
            'profanity': [...],
            ...
        }
        """
        self.duration = duration
        self._clear_tracks()
        
        # Nudity
        if data.get('nudity'):
            self._add_track("Nudity", "#f43f5e", data['nudity'])
            
        # Profanity
        if data.get('profanity'):
            self._add_track("Profanity", "#fbbf24", data['profanity'])
            
        # Sexual Content
        if data.get('sexual_content'):
            self._add_track("Sexual Content", "#d946ef", data['sexual_content'])
            
        # Violence
        if data.get('violence'):
            self._add_track("Violence", "#ef4444", data['violence'])
            
    def _add_track(self, title: str, color_hex: str, segments: list):
        # Label
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold;")
        self.tracks_layout.addWidget(lbl)
        
        # Track
        track = TimelineTrack(title, QColor(color_hex), self.duration, segments)
        track.segment_clicked.connect(self._on_segment_clicked)
        self.tracks_layout.addWidget(track)
        self.tracks[title] = track
        
    def _clear_tracks(self):
        while self.tracks_layout.count():
            item = self.tracks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.tracks = {}
        
    def _on_segment_clicked(self, segment):
        # Toggle 'ignored' state
        segment['ignored'] = not segment.get('ignored', False)
        # In a real app, we'd emit a signal that something changed
        # For not, just repaint
        self.sender().update()

    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
