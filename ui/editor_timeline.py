"""
Editor Timeline Widget for Video Censor.

Extends TimelineWidget with drag selection, resizable handles, 
snapping to markers, and an edits lane for non-destructive editing.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal, QRectF, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QMouseEvent, QLinearGradient, QCursor
)
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .timeline import TimelineWidget, TimelineTrack, TimeRuler
from video_censor.editing.intervals import EditDecision, Action


@dataclass
class SelectionRange:
    """Represents a drag selection on the timeline."""
    start: float = 0.0
    end: float = 0.0
    is_provisional: bool = True  # True while dragging
    
    @property
    def duration(self) -> float:
        return abs(self.end - self.start)
    
    @property
    def normalized_start(self) -> float:
        return min(self.start, self.end)
    
    @property
    def normalized_end(self) -> float:
        return max(self.start, self.end)


class EditsLaneWidget(QWidget):
    """Widget showing finalized edit decisions."""
    
    edit_clicked = Signal(object)  # Emits EditDecision
    edit_double_clicked = Signal(object)  # For editing
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0.0
        self.edits: List[EditDecision] = []
        self.hovered_edit: Optional[EditDecision] = None
        self.playhead_pos = 0.0
        self.setFixedHeight(40)
        self.setMouseTracking(True)
        
        # Action colors
        self.action_colors = {
            Action.CUT: QColor("#ef4444"),      # Red
            Action.MUTE: QColor("#fbbf24"),     # Yellow
            Action.BEEP: QColor("#f97316"),     # Orange
            Action.BLUR: QColor("#a855f7"),     # Purple
            Action.NONE: QColor("#71717a"),     # Gray
        }
    
    def set_duration(self, duration: float):
        self.duration = max(0.1, duration)
        self.update()
    
    def set_edits(self, edits: List[EditDecision]):
        self.edits = edits
        self.update()
    
    def set_playhead(self, position_sec: float):
        self.playhead_pos = position_sec
        self.update()
    
    def paintEvent(self, event):
        if self.duration <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor("#252530"))
        gradient.setColorAt(1, QColor("#1f1f28"))
        painter.fillRect(self.rect(), gradient)
        
        # Draw "Edits" label area
        painter.setPen(QColor("#71717a"))
        painter.drawText(5, height // 2 + 4, "✂️ Edits")
        
        # Edit rendering starts after label
        edit_start_x = 60
        edit_width = width - edit_start_x - 5
        
        # Draw edits
        for edit in self.edits:
            if edit.is_provisional:
                continue  # Don't draw provisional edits here
                
            x1 = edit_start_x + (edit.source_start / self.duration) * edit_width
            x2 = edit_start_x + (edit.source_end / self.duration) * edit_width
            w = max(4, x2 - x1)
            
            color = self.action_colors.get(edit.action, QColor("#71717a"))
            is_hovered = edit == self.hovered_edit
            
            if is_hovered:
                color = color.lighter(120)
            
            # Draw edit block
            rect = QRectF(x1, 6, w, height - 12)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 3, 3)
            
            # Action icon
            if w > 20:
                icon = {"cut": "✂️", "mute": "🔇", "beep": "🔊", "blur": "🔲"}.get(edit.action.value, "")
                painter.setPen(QColor("#ffffff"))
                painter.drawText(int(x1 + 4), height // 2 + 4, icon)
        
        # Draw playhead
        if self.playhead_pos > 0:
            playhead_x = edit_start_x + (self.playhead_pos / self.duration) * edit_width
            painter.setPen(QPen(QColor("#3b82f6"), 2))
            painter.drawLine(int(playhead_x), 0, int(playhead_x), height)


class SelectionOverlayWidget(QWidget):
    """Transparent overlay for drawing selection and handles."""
    
    selection_changed = Signal(float, float)  # start, end
    selection_finalized = Signal(float, float)  # start, end
    handle_dragging = Signal(str, float)  # 'start' or 'end', new position
    
    HANDLE_WIDTH = 8
    HANDLE_HIT_AREA = 12
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0.0
        self.selection: Optional[SelectionRange] = None
        
        # Drag state
        self._dragging = False
        self._drag_start_x = 0
        self._drag_handle = None  # 'start', 'end', or None for new selection
        
        # Snapping
        self.snap_enabled = True
        self.snap_threshold = 0.5  # seconds
        self.snap_markers: List[float] = []  # Detection marker times
        
        # Visual
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
    
    def set_duration(self, duration: float):
        self.duration = max(0.1, duration)
    
    def set_snap_markers(self, markers: List[float]):
        """Set detection marker times for snapping."""
        self.snap_markers = sorted(markers)
    
    def clear_selection(self):
        self.selection = None
        self.update()
    
    def set_selection(self, start: float, end: float, provisional: bool = True):
        self.selection = SelectionRange(start, end, provisional)
        self.update()
    
    def _x_to_time(self, x: float) -> float:
        """Convert x coordinate to time."""
        if self.duration <= 0 or self.width() <= 0:
            return 0.0
        return (x / self.width()) * self.duration
    
    def _time_to_x(self, time: float) -> float:
        """Convert time to x coordinate."""
        if self.duration <= 0:
            return 0.0
        return (time / self.duration) * self.width()
    
    def _snap_time(self, time: float) -> float:
        """Snap time to nearest marker if within threshold."""
        if not self.snap_enabled or not self.snap_markers:
            return time
        
        closest = time
        closest_dist = self.snap_threshold
        
        for marker in self.snap_markers:
            dist = abs(marker - time)
            if dist < closest_dist:
                closest = marker
                closest_dist = dist
        
        return closest
    
    def _hit_test_handle(self, x: float) -> Optional[str]:
        """Check if x is over a selection handle."""
        if not self.selection:
            return None
        
        start_x = self._time_to_x(self.selection.normalized_start)
        end_x = self._time_to_x(self.selection.normalized_end)
        
        if abs(x - start_x) <= self.HANDLE_HIT_AREA:
            return 'start'
        if abs(x - end_x) <= self.HANDLE_HIT_AREA:
            return 'end'
        return None
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        
        x = event.position().x()
        
        # Check if clicking on a handle
        handle = self._hit_test_handle(x)
        if handle:
            self._dragging = True
            self._drag_handle = handle
            self._drag_start_x = x
            return
        
        # Start new selection
        self._dragging = True
        self._drag_handle = None
        time = self._x_to_time(x)
        self.selection = SelectionRange(time, time, True)
        self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        
        # Update cursor
        handle = self._hit_test_handle(x)
        if handle:
            self.setCursor(Qt.SizeHorCursor)
        elif self.selection and self._is_over_selection(x):
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)
        
        # Handle dragging
        if self._dragging and self.selection:
            time = self._snap_time(self._x_to_time(x))
            
            if self._drag_handle == 'start':
                self.selection.start = time
            elif self._drag_handle == 'end':
                self.selection.end = time
            else:
                # New selection drag
                self.selection.end = time
            
            self.selection_changed.emit(
                self.selection.normalized_start,
                self.selection.normalized_end
            )
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        
        self._dragging = False
        
        if self.selection and self.selection.duration > 0.1:
            # Normalize selection
            self.selection.start = self.selection.normalized_start
            self.selection.end = self.selection.normalized_end
            self.selection.is_provisional = False
            self.update()
    
    def _is_over_selection(self, x: float) -> bool:
        if not self.selection:
            return False
        start_x = self._time_to_x(self.selection.normalized_start)
        end_x = self._time_to_x(self.selection.normalized_end)
        return start_x <= x <= end_x
    
    def paintEvent(self, event):
        if not self.selection or self.duration <= 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        start_x = self._time_to_x(self.selection.normalized_start)
        end_x = self._time_to_x(self.selection.normalized_end)
        sel_width = end_x - start_x
        
        # Selection fill
        if self.selection.is_provisional:
            fill_color = QColor("#3b82f6")
            fill_color.setAlpha(60)
        else:
            fill_color = QColor("#22c55e")
            fill_color.setAlpha(80)
        
        painter.fillRect(QRectF(start_x, 0, sel_width, height), fill_color)
        
        # Selection border
        border_color = QColor("#3b82f6") if self.selection.is_provisional else QColor("#22c55e")
        painter.setPen(QPen(border_color, 2, Qt.DashLine if self.selection.is_provisional else Qt.SolidLine))
        painter.drawRect(QRectF(start_x, 0, sel_width, height))
        
        # Draw handles
        if not self.selection.is_provisional:
            handle_color = QColor("#ffffff")
            
            # Start handle
            painter.setBrush(handle_color)
            painter.setPen(QPen(border_color, 2))
            painter.drawRoundedRect(
                QRectF(start_x - self.HANDLE_WIDTH/2, height/2 - 12, self.HANDLE_WIDTH, 24),
                2, 2
            )
            
            # End handle
            painter.drawRoundedRect(
                QRectF(end_x - self.HANDLE_WIDTH/2, height/2 - 12, self.HANDLE_WIDTH, 24),
                2, 2
            )
        
        # Time labels
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        
        start_label = self._format_time(self.selection.normalized_start)
        end_label = self._format_time(self.selection.normalized_end)
        dur_label = f"{self.selection.duration:.1f}s"
        
        painter.drawText(int(start_x + 4), 14, start_label)
        painter.drawText(int(end_x - 40), 14, end_label)
        
        # Duration in center
        if sel_width > 80:
            painter.drawText(int((start_x + end_x) / 2 - 15), height - 6, dur_label)
    
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        ms = int((seconds % 1) * 100)
        return f"{m}:{s:02d}.{ms:02d}"


class EditorTimelineWidget(TimelineWidget):
    """
    Enhanced timeline widget for the drag-to-cut editor.
    
    Adds:
    - Drag selection with provisional range preview
    - Resizable handles at start/end
    - Detection marker snapping
    - Edits lane showing finalized cuts/mutes/blurs
    """
    
    selection_created = Signal(float, float)  # start, end in seconds
    edit_action_requested = Signal(str, float, float)  # action, start, end
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Edits lane
        self.edits_lane = EditsLaneWidget()
        
        # Find tracks container and add edits lane before it
        layout = self.layout()
        # Insert after ruler (index 1)
        layout.insertWidget(2, self.edits_lane)
        
        # Selection overlay (covers tracks area)
        self.selection_overlay = SelectionOverlayWidget(self.tracks_container)
        self.selection_overlay.selection_changed.connect(self._on_selection_changed)
        
        # Quick action buttons (hidden until selection made)
        self._create_action_buttons()
        
        # Project integration
        self._edits: List[EditDecision] = []
        self._snap_enabled = True
        self._snap_threshold = 0.5
    
    def _create_action_buttons(self):
        """Create quick action buttons bar."""
        self.actions_bar = QWidget()
        self.actions_bar.setVisible(False)
        actions_layout = QHBoxLayout(self.actions_bar)
        actions_layout.setContentsMargins(0, 4, 0, 4)
        actions_layout.setSpacing(8)
        
        actions_layout.addStretch()
        
        # Cut button
        self.btn_cut = QPushButton("✂️ Cut")
        self.btn_cut.setStyleSheet(self._action_btn_style("#ef4444"))
        self.btn_cut.clicked.connect(lambda: self._apply_action(Action.CUT))
        actions_layout.addWidget(self.btn_cut)
        
        # Mute button
        self.btn_mute = QPushButton("🔇 Mute")
        self.btn_mute.setStyleSheet(self._action_btn_style("#fbbf24"))
        self.btn_mute.clicked.connect(lambda: self._apply_action(Action.MUTE))
        actions_layout.addWidget(self.btn_mute)
        
        # Bleep button
        self.btn_bleep = QPushButton("🔊 Bleep")
        self.btn_bleep.setStyleSheet(self._action_btn_style("#f97316"))
        self.btn_bleep.clicked.connect(lambda: self._apply_action(Action.BEEP))
        actions_layout.addWidget(self.btn_bleep)
        
        # Blur button
        self.btn_blur = QPushButton("🔲 Blur")
        self.btn_blur.setStyleSheet(self._action_btn_style("#a855f7"))
        self.btn_blur.clicked.connect(lambda: self._apply_action(Action.BLUR))
        actions_layout.addWidget(self.btn_blur)
        
        actions_layout.addStretch()
        
        # Cancel button
        self.btn_cancel = QPushButton("✕")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #3a3a48;
                color: #a0a0b0;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4a4a58; }
        """)
        self.btn_cancel.clicked.connect(self._cancel_selection)
        actions_layout.addWidget(self.btn_cancel)
        
        # Add to layout
        self.layout().addWidget(self.actions_bar)
    
    def _action_btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {color};
                filter: brightness(1.2);
            }}
        """
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep selection overlay sized to tracks container
        if hasattr(self, 'selection_overlay'):
            self.selection_overlay.setGeometry(self.tracks_container.geometry())
    
    def set_data(self, duration: float, data: dict):
        """Load detection data and update all components."""
        super().set_data(duration, data)
        
        self.edits_lane.set_duration(duration)
        self.selection_overlay.set_duration(duration)
        
        # Collect all detection marker times for snapping
        markers = []
        for segments in data.values():
            if isinstance(segments, list):
                for seg in segments:
                    markers.append(seg.get('start', 0))
                    markers.append(seg.get('end', 0))
        
        self.selection_overlay.set_snap_markers(markers)
    
    def set_edits(self, edits: List[EditDecision]):
        """Set the edit decisions to display."""
        self._edits = edits
        self.edits_lane.set_edits(edits)
    
    def set_position(self, position_ms: int):
        """Update playback position."""
        super().set_position(position_ms)
        self.edits_lane.set_playhead(position_ms / 1000)
    
    def _on_selection_changed(self, start: float, end: float):
        """Handle selection change from overlay."""
        self.actions_bar.setVisible(True)
        self.selection_created.emit(start, end)
    
    def _apply_action(self, action: Action):
        """Apply an action to the current selection."""
        if not self.selection_overlay.selection:
            return
        
        sel = self.selection_overlay.selection
        self.edit_action_requested.emit(
            action.value,
            sel.normalized_start,
            sel.normalized_end
        )
        
        # Clear selection after action
        self._cancel_selection()
    
    def _cancel_selection(self):
        """Clear the current selection."""
        self.selection_overlay.clear_selection()
        self.actions_bar.setVisible(False)
    
    def set_snap_enabled(self, enabled: bool):
        """Enable/disable snapping."""
        self._snap_enabled = enabled
        self.selection_overlay.snap_enabled = enabled
    
    def set_snap_threshold(self, threshold: float):
        """Set snap threshold in seconds."""
        self._snap_threshold = threshold
        self.selection_overlay.snap_threshold = threshold
