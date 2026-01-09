"""
Interactive Timeline Widget for Video Censor.
Visualizes detected content segments and allows user interaction.
Enhanced with playhead, time ruler, and segment editing controls.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, 
    QToolTip, QSizePolicy, QPushButton
)
from PySide6.QtCore import Qt, Signal, QRectF, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QMouseEvent, QLinearGradient


class TimeRuler(QWidget):
    """Time ruler showing tick marks and time labels."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0
        self.setFixedHeight(24)
        
    def set_duration(self, duration: float):
        self.duration = duration
        self.update()
        
    def paintEvent(self, event):
        if self.duration <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        painter.fillRect(self.rect(), QColor("#15151d"))
        
        # Calculate tick intervals based on duration
        if self.duration < 60:  # < 1 min: every 5 sec
            interval = 5
        elif self.duration < 600:  # < 10 min: every 30 sec
            interval = 30
        elif self.duration < 3600:  # < 1 hr: every minute
            interval = 60
        else:  # > 1 hr: every 5 min
            interval = 300
            
        # Draw ticks and labels
        painter.setPen(QPen(QColor("#4a4a5a"), 1))
        font = painter.font()
        font.setPixelSize(9)
        painter.setFont(font)
        
        t = 0
        while t <= self.duration:
            x = (t / self.duration) * width
            
            # Major tick
            painter.drawLine(int(x), height - 8, int(x), height)
            
            # Time label
            m, s = divmod(int(t), 60)
            h, m = divmod(m, 60)
            if h > 0:
                label = f"{h}:{m:02d}:{s:02d}"
            else:
                label = f"{m}:{s:02d}"
            
            painter.setPen(QColor("#71717a"))
            painter.drawText(int(x) + 3, height - 10, label)
            painter.setPen(QPen(QColor("#4a4a5a"), 1))
            
            t += interval


class TimelineTrack(QWidget):
    """A single track in the timeline (e.g., Nudity, Profanity)."""
    
    segment_clicked = Signal(object)  # Emits segment data
    segment_deleted = Signal(object)  # Emits segment to delete
    detection_clicked = Signal(float, float, str)  # start, end, category - for creating edits
    
    def __init__(self, title: str, color: QColor, duration: float, segments: list, category: str = None, parent=None):
        super().__init__(parent)
        self.track_title = title
        self.category = category or title.lower().replace(' ', '_')  # 'nudity', 'profanity', etc.
        self.base_color = color
        self.duration = max(0.1, duration)
        self.segments = segments
        self.hovered_segment = None
        self.playhead_pos = 0  # Playhead position in seconds
        self.setFixedHeight(36)
        self.setMouseTracking(True)
        
    def set_playhead(self, position_sec: float):
        """Update playhead position."""
        self.playhead_pos = position_sec
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background with subtle gradient
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor("#1f1f2a"))
        gradient.setColorAt(1, QColor("#18181f"))
        painter.fillRect(self.rect(), gradient)
        
        # Draw segments
        for seg in self.segments:
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            
            x1 = (start / self.duration) * width
            x2 = (end / self.duration) * width
            w = max(4, x2 - x1)
            
            # Check if ignored/overridden
            is_ignored = seg.get('ignored', False)
            is_hovered = seg == self.hovered_segment
            
            color = QColor(self.base_color)
            if is_ignored:
                color.setAlpha(40)
            elif is_hovered:
                color.setAlpha(255)
            else:
                color.setAlpha(180)
            
            # Rounded rectangle for segment
            rect = QRectF(x1, 4, w, height - 8)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 4, 4)
            
            # Border for hovered segment
            if is_hovered:
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect, 4, 4)
                
            # Strikethrough for ignored segments
            if is_ignored:
                painter.setPen(QPen(QColor("#ef4444"), 2, Qt.DashLine))
                painter.drawLine(int(x1), int(height/2), int(x1 + w), int(height/2))
        
        # Draw playhead line
        if self.playhead_pos > 0:
            playhead_x = (self.playhead_pos / self.duration) * width
            painter.setPen(QPen(QColor("#3b82f6"), 2))
            painter.drawLine(int(playhead_x), 0, int(playhead_x), height)
            
            # Playhead triangle
            painter.setBrush(QColor("#3b82f6"))
            painter.setPen(Qt.NoPen)
            triangle = [
                QPoint(int(playhead_x) - 5, 0),
                QPoint(int(playhead_x) + 5, 0),
                QPoint(int(playhead_x), 6)
            ]
            painter.drawPolygon(triangle)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            width = self.width()
            time = (x / width) * self.duration
            
            # Find clicked segment
            for seg in self.segments:
                if seg.get('start', 0) <= time <= seg.get('end', 0):
                    self.segment_clicked.emit(seg)
                    # Also emit detection_clicked for creating edits
                    self.detection_clicked.emit(
                        seg.get('start', 0),
                        seg.get('end', 0),
                        self.category
                    )
                    self.update()
                    return
        elif event.button() == Qt.RightButton:
            # Right-click to delete segment
            x = event.position().x()
            width = self.width()
            time = (x / width) * self.duration
            
            for seg in self.segments:
                if seg.get('start', 0) <= time <= seg.get('end', 0):
                    self.segment_deleted.emit(seg)
                    return
                    
    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        width = self.width()
        time = (x / width) * self.duration
        
        # Find hovered segment
        old_hovered = self.hovered_segment
        self.hovered_segment = None
        
        for seg in self.segments:
            if seg.get('start', 0) <= time <= seg.get('end', 0):
                self.hovered_segment = seg
                label = seg.get('label', seg.get('reason', self.track_title))
                start = self._format_time(seg['start'])
                end = self._format_time(seg['end'])
                status = " (kept)" if seg.get('ignored') else " (censored)"
                QToolTip.showText(
                    event.globalPosition().toPoint(), 
                    f"{label}{status}\n{start} → {end}\n\nClick to toggle • Right-click to delete",
                    self
                )
                break
        
        if self.hovered_segment is None:
            QToolTip.hideText()
            
        if old_hovered != self.hovered_segment:
            self.update()
            
    def leaveEvent(self, event):
        self.hovered_segment = None
        self.update()
            
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class TimelineWidget(QWidget):
    """Main timeline widget containing multiple tracks with playhead."""
    
    seek_requested = Signal(int)  # Emitted when user clicks to seek (ms)
    data_changed = Signal()  # Emitted when segment data is modified
    
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header with current time
        header = QHBoxLayout()
        self.time_label = QLabel("00:00.000")
        self.time_label.setStyleSheet("color: #3b82f6; font-family: monospace; font-size: 14px; font-weight: bold;")
        header.addWidget(self.time_label)
        
        self.duration_label = QLabel("/ 00:00")
        self.duration_label.setStyleSheet("color: #71717a; font-family: monospace; font-size: 12px;")
        header.addWidget(self.duration_label)
        
        header.addStretch()
        
        # Keyboard hints
        hints = QLabel("Space: Play • ←→: Frame • J/K/L: Shuttle • Click: Toggle")
        hints.setStyleSheet("color: #52525b; font-size: 10px;")
        header.addWidget(hints)
        
        main_layout.addLayout(header)
        
        # Time ruler
        self.ruler = TimeRuler()
        main_layout.addWidget(self.ruler)
        
        # Tracks container
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout(self.tracks_container)
        self.tracks_layout.setSpacing(2)
        self.tracks_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.addWidget(self.tracks_container)
        
        self.duration = 0
        self.current_position = 0  # in ms
        self.tracks = {}

    def set_position(self, position_ms: int):
        """Update current playback position."""
        self.current_position = position_ms
        position_sec = position_ms / 1000
        
        # Update time label with milliseconds
        m, s = divmod(position_sec, 60)
        h, m = divmod(int(m), 60)
        ms_part = int((position_sec % 1) * 1000)
        if h > 0:
            self.time_label.setText(f"{int(h)}:{int(m):02d}:{int(s):02d}.{ms_part:03d}")
        else:
            self.time_label.setText(f"{int(m):02d}:{int(s):02d}.{ms_part:03d}")
        
        # Update playhead on all tracks
        for track in self.tracks.values():
            track.set_playhead(position_sec)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle clicking on the timeline to seek."""
        if self.duration > 0 and event.button() == Qt.LeftButton:
            x = event.position().x()
            width = self.width()
            seek_time_ms = int((x / width) * (self.duration * 1000))
            self.seek_requested.emit(seek_time_ms)

    def set_data(self, duration: float, data: dict):
        """Load detection data."""
        self.duration = duration
        self._clear_tracks()
        
        # Update labels
        self.ruler.set_duration(duration)
        m, s = divmod(int(duration), 60)
        h, m = divmod(m, 60)
        if h > 0:
            self.duration_label.setText(f"/ {h}:{m:02d}:{s:02d}")
        else:
            self.duration_label.setText(f"/ {m}:{s:02d}")
        
        # Add tracks for each content type
        track_config = [
            ("Nudity", "#f43f5e", "nudity"),
            ("Profanity", "#fbbf24", "profanity"),
            ("Sexual Content", "#d946ef", "sexual_content"),
            ("Violence", "#ef4444", "violence"),
        ]
        
        for title, color, key in track_config:
            if data.get(key):
                self._add_track(title, color, data[key], category_key=key)
            
    def _add_track(self, title: str, color_hex: str, segments: list, category_key: str = None):
        # Container for label + track
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        
        # Label (fixed width)
        lbl = QLabel(title)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold;")
        row_layout.addWidget(lbl)
        
        # Track - pass category_key for detection_clicked signal
        track = TimelineTrack(title, QColor(color_hex), self.duration, segments, category=category_key)
        track.segment_clicked.connect(self._on_segment_clicked)
        track.segment_deleted.connect(self._on_segment_deleted)
        row_layout.addWidget(track, 1)
        
        self.tracks_layout.addWidget(row)
        self.tracks[title] = track
        
    def _clear_tracks(self):
        while self.tracks_layout.count():
            item = self.tracks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.tracks = {}
        
    def _on_segment_clicked(self, segment):
        """Toggle 'ignored' state on click."""
        segment['ignored'] = not segment.get('ignored', False)
        self.sender().update()
        self.data_changed.emit()
        
    def _on_segment_deleted(self, segment):
        """Remove segment from track."""
        track = self.sender()
        if segment in track.segments:
            track.segments.remove(segment)
            track.update()
            self.data_changed.emit()

    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def highlight_segment(self, segment: dict):
        """Highlight a specific segment across all tracks."""
        # Find which track contains this segment and highlight it
        for title, track in self.tracks.items():
            if segment in track.segments:
                track.hovered_segment = segment
                track.update()
                
                # Seek the playhead to segment start
                self.set_position(int(segment.get('start', 0) * 1000))
            else:
                # Clear highlight from other tracks
                track.hovered_segment = None
                track.update()
                
    def remove_segment(self, track_key: str, segment: dict):
        """Remove a segment from a track by key."""
        # Map track_key to title
        key_to_title = {
            'nudity': 'Nudity',
            'profanity': 'Profanity',
            'sexual_content': 'Sexual Content',
            'violence': 'Violence',
        }
        
        title = key_to_title.get(track_key, track_key.title())
        track = self.tracks.get(title)
        
        if track and segment in track.segments:
            track.segments.remove(segment)
            track.update()
            self.data_changed.emit()

