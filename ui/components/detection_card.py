"""
Detection Card Components.
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QWidget, QStyle
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor

# Import scene grouping utility if available
try:
    from video_censor.editing.intervals import Scene
except ImportError:
    Scene = None  # Handle gracefully or import generic type


class MiniDetectionCard(QFrame):
    """A compact card for kept/deleted sections."""
    
    restore_clicked = Signal(object)  # Emits segment
    card_clicked = Signal(object)  # For seeking to segment
    
    def __init__(self, segment: dict, status: str, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.status = status  # 'kept' or 'deleted'
        
        self.setStyleSheet(f"""
            QFrame {{
                background: {'#1a2e1a' if status == 'kept' else '#2e1a1a'};
                border: 1px solid {'#22c55e40' if status == 'kept' else '#ef444440'};
                border-radius: 6px;
                padding: 6px;
            }}
            QFrame:hover {{
                background: {'#1f3a1f' if status == 'kept' else '#3a1f1f'};
            }}
        """)
        self.setCursor(Qt.PointingHandCursor)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 6, 8, 6)
        
        # Status icon
        icon = "✓" if self.status == 'kept' else "✗"
        icon_color = "#22c55e" if self.status == 'kept' else "#ef4444"
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {icon_color}; font-size: 14px; font-weight: bold;")
        layout.addWidget(icon_label)
        
        # Time range
        start = self._format_time(self.segment.get('start', 0))
        end = self._format_time(self.segment.get('end', 0))
        time_label = QLabel(f"{start} → {end}")
        time_label.setStyleSheet("color: #a0a0b0; font-size: 10px;")
        layout.addWidget(time_label)
        
        # Reason (truncated)
        reason = self.segment.get('label', self.segment.get('reason', ''))[:30]
        if reason:
            reason_label = QLabel(reason)
            reason_label.setStyleSheet("color: #71717a; font-size: 10px;")
            layout.addWidget(reason_label)
        
        layout.addStretch()
        
        # Restore button
        restore_btn = QPushButton("↩")
        restore_btn.setToolTip("Restore to review")
        restore_btn.setFixedSize(24, 24)
        restore_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a48;
                color: #a0a0b0;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #4a4a58;
                color: #f0f0f0;
            }
        """)
        restore_btn.clicked.connect(lambda: self.restore_clicked.emit(self.segment))
        layout.addWidget(restore_btn)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.segment)
        super().mousePressEvent(event)
        
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class SceneCard(QFrame):
    """A card displaying a scene (group of detections) with expand/collapse."""
    
    keep_clicked = Signal(object)  # Emits scene
    delete_clicked = Signal(object)  # Emits scene
    card_clicked = Signal(object)  # For seeking to scene start
    selection_changed = Signal(object, bool)  # (scene, is_selected)
    
    def __init__(self, scene, index: int, total: int, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.index = index
        self.total = total
        self._is_selected = False
        self._is_expanded = False
        
        self.setProperty("class", "scene-card")
        self.setStyleSheet("""
            QFrame[class="scene-card"] {
                background: #1a1a24;
                border: 2px solid #8b5cf6;
                border-radius: 10px;
                padding: 12px;
            }
            QFrame[class="scene-card"]:hover {
                border-color: #a78bfa;
                background: #1f1f2a;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)
        
        # Header with checkbox, scene icon, and time range
        header = QHBoxLayout()
        
        # Selection checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #8b5cf6;
                background: #1a1a24;
            }
            QCheckBox::indicator:checked {
                background: #8b5cf6;
                border-color: #8b5cf6;
            }
        """)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        header.addWidget(self.checkbox)
        
        # Scene icon and number
        scene_label = QLabel(f"🎬 Scene {self.index + 1} of {self.total}")
        scene_label.setStyleSheet("color: #a78bfa; font-size: 12px; font-weight: 700;")
        header.addWidget(scene_label)
        
        header.addStretch()
        
        # Time range
        start = self._format_time(self.scene.start)
        end = self._format_time(self.scene.end)
        duration = self.scene.duration
        time_label = QLabel(f"⏱ {start} → {end} ({duration:.1f}s)")
        time_label.setStyleSheet("color: #8b5cf6; font-size: 11px; font-weight: 600;")
        header.addWidget(time_label)
        
        layout.addLayout(header)
        
        # Detection count info
        count_label = QLabel(f"Contains {self.scene.detection_count} detection{'s' if self.scene.detection_count != 1 else ''}")
        count_label.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        layout.addWidget(count_label)
        
        # Expand/collapse button and detections container
        self.expand_btn = QPushButton("▶ Show detections")
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #71717a;
                border: none;
                text-align: left;
                padding: 4px 0;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #a0a0b0;
            }
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        layout.addWidget(self.expand_btn)
        
        # Detections container (hidden by default)
        self.detections_container = QWidget()
        self.detections_layout = QVBoxLayout(self.detections_container)
        self.detections_layout.setSpacing(4)
        self.detections_layout.setContentsMargins(8, 4, 0, 4)
        self.detections_container.setVisible(False)
        
        # Populate with detection mini-cards
        for det in self.scene.detections:
            det_info = QLabel(f"• {self._format_time(det.start)} - {self._format_time(det.end)}: {det.reason[:40]}")
            det_info.setStyleSheet("color: #71717a; font-size: 10px;")
            self.detections_layout.addWidget(det_info)
        
        layout.addWidget(self.detections_container)
        
        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        
        self.keep_btn = QPushButton("✓ Keep Scene")
        self.keep_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
        """)
        self.keep_btn.clicked.connect(lambda: self.keep_clicked.emit(self.scene))
        actions.addWidget(self.keep_btn)
        
        self.delete_btn = QPushButton("✗ Delete Scene")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.scene))
        actions.addWidget(self.delete_btn)
        
        layout.addLayout(actions)
        
    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        self.detections_container.setVisible(self._is_expanded)
        self.expand_btn.setText("▼ Hide detections" if self._is_expanded else "▶ Show detections")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Create a segment-like dict for seeking
            self.card_clicked.emit({'start': self.scene.start, 'end': self.scene.end})
        super().mousePressEvent(event)
        
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def _on_checkbox_changed(self, state):
        self._is_selected = state == Qt.Checked
        self.selection_changed.emit(self.scene, self._is_selected)
        
    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(selected)
        self.checkbox.blockSignals(False)
        
    def is_selected(self) -> bool:
        return self._is_selected


class DetectionCard(QFrame):
    """A card displaying a single detection with actions and selection checkbox."""
    
    keep_clicked = Signal(object)  # Emits segment
    delete_clicked = Signal(object)  # Emits segment
    card_clicked = Signal(object)  # For seeking to segment
    selection_changed = Signal(object, bool)  # (segment, is_selected)
    hover_started = Signal(object) # Emits segment
    hover_ended = Signal()
    
    def __init__(self, segment: dict, index: int, total: int, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.index = index
        self.total = total
        self._is_selected = False
        
        # Determine confidence color (red=high, yellow=medium, green=low)
        confidence = segment.get('confidence', 0.8)
        if confidence >= 0.8:
            border_color = "#ef4444"  # Red - high confidence
        elif confidence >= 0.5:
            border_color = "#fbbf24"  # Yellow - medium
        else:
            border_color = "#22c55e"  # Green - low confidence
        
        self.setProperty("class", "detection-card")
        self.setStyleSheet(f"""
            QFrame[class="detection-card"] {{
                background: #1a1a24;
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame[class="detection-card"]:hover {{
                border-color: #3b82f6;
                background: #1f1f2a;
            }}
        """)
        self.setCursor(Qt.PointingHandCursor)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)
        
        # Header with checkbox, counter and time
        header = QHBoxLayout()
        
        # Selection checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #3a3a48;
                background: #1a1a24;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border-color: #3b82f6;
            }
            QCheckBox::indicator:hover {
                border-color: #3b82f6;
            }
        """)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        header.addWidget(self.checkbox)
        
        counter = QLabel(f"#{self.index + 1} of {self.total}")
        counter.setStyleSheet("color: #71717a; font-size: 11px; font-weight: 600;")
        header.addWidget(counter)
        
        header.addStretch()
        
        # Time range
        start = self._format_time(self.segment.get('start', 0))
        end = self._format_time(self.segment.get('end', 0))
        time_label = QLabel(f"⏱ {start} → {end}")
        time_label.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: 600;")
        header.addWidget(time_label)
        
        layout.addLayout(header)
        
        # Reason/Label
        reason = self.segment.get('label', self.segment.get('reason', 'Detection'))
        reason_label = QLabel(reason)
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet("color: #e0e0e8; font-size: 12px;")
        layout.addWidget(reason_label)
        
        # Info row
        info_row = QHBoxLayout()
        
        # Type Icon logic (replicated)
        det_type = self.segment.get('type', '')
        type_icon = ""
        if det_type == 'nudity' or 'nudity' in str(self.segment.get('source', '')):
            type_icon = "👁"  # Visual
        elif det_type == 'profanity' or 'profanity' in str(self.segment.get('source', '')):
            type_icon = "🔊"  # Audio
        elif det_type == 'both':
            type_icon = "⚠️"  # Both
        
        if type_icon:
            type_label = QLabel(type_icon)
            type_label.setStyleSheet("font-size: 14px;")
            info_row.addWidget(type_label)
        
        # Confidence if available
        confidence = self.segment.get('confidence')
        if confidence:
            conf_label = QLabel(f"Conf: {confidence:.0%}")
            conf_label.setStyleSheet("color: #71717a; font-size: 10px;")
            info_row.addWidget(conf_label)
        
        # Duration
        duration = self.segment.get('end', 0) - self.segment.get('start', 0)
        dur_label = QLabel(f"Dur: {duration:.1f}s")
        dur_label.setStyleSheet("color: #71717a; font-size: 10px;")
        info_row.addWidget(dur_label)
        
        info_row.addStretch()
        layout.addLayout(info_row)
        
        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        
        self.keep_btn = QPushButton("✓ Keep")
        self.keep_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
        """)
        self.keep_btn.clicked.connect(lambda: self.keep_clicked.emit(self.segment))
        actions.addWidget(self.keep_btn)
        
        self.delete_btn = QPushButton("✗ Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.segment))
        actions.addWidget(self.delete_btn)
        
        layout.addLayout(actions)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.segment)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        self.hover_started.emit(self.segment)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hover_ended.emit()
        super().leaveEvent(event)
        
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def set_highlighted(self, highlighted: bool):
        """Highlight this card as the current one."""
        confidence = self.segment.get('confidence', 0.8)
        if confidence >= 0.8:
            border_color = "#ef4444"
        elif confidence >= 0.5:
            border_color = "#fbbf24"
        else:
            border_color = "#22c55e"
            
        if highlighted:
            self.setStyleSheet(f"""
                QFrame[class="detection-card"] {{
                    background: #1f2937;
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame[class="detection-card"] {{
                    background: #1a1a24;
                    border: 2px solid {border_color};
                    border-radius: 8px;
                    padding: 12px;
                }}
                QFrame[class="detection-card"]:hover {{
                    border-color: #3b82f6;
                    background: #1f1f2a;
                }}
            """)
    
    def _on_checkbox_changed(self, state):
        """Handle checkbox state change."""
        self._is_selected = state == Qt.Checked
        self.selection_changed.emit(self.segment, self._is_selected)
        
    def set_selected(self, selected: bool):
        """Programmatically set the selection state."""
        self._is_selected = selected
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(selected)
        self.checkbox.blockSignals(False)
        
    def is_selected(self) -> bool:
        """Return current selection state."""
        return self._is_selected
