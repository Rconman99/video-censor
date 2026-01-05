"""
Detection Browser Panel for Video Censor.
Provides an easy sequential workflow for reviewing detected content segments.
Now with To Review, Kept, and Deleted sections for proper checklist functionality.
Supports batch selection with checkboxes for mass delete/keep operations.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QTabBar, QStackedWidget, QSizePolicy, QScrollArea, QSpacerItem, QCheckBox, QSlider
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QFont

# Import scene grouping utility
try:
    from video_censor.editing.intervals import group_into_scenes, Scene, TimeInterval
    HAS_SCENE_GROUPING = True
except ImportError:
    HAS_SCENE_GROUPING = False


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
        
        # Determine detection type icon
        det_type = segment.get('type', '')
        if det_type == 'nudity' or 'nudity' in str(segment.get('source', '')):
            self.type_icon = "👁"  # Visual
        elif det_type == 'profanity' or 'profanity' in str(segment.get('source', '')):
            self.type_icon = "🔊"  # Audio
        elif det_type == 'both':
            self.type_icon = "⚠️"  # Both
        else:
            self.type_icon = "🔍"  # Unknown
        
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
        
    def _format_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def set_highlighted(self, highlighted: bool):
        """Highlight this card as the current one."""
        if highlighted:
            self.setStyleSheet("""
                QFrame[class="detection-card"] {
                    background: #1f2937;
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame[class="detection-card"] {
                    background: #1a1a24;
                    border: 1px solid #2a2a38;
                    border-radius: 8px;
                    padding: 12px;
                }
                QFrame[class="detection-card"]:hover {
                    border-color: #3b82f6;
                    background: #1f1f2a;
                }
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


class CollapsibleSection(QFrame):
    """A collapsible section with header and content."""
    
    def __init__(self, title: str, icon: str, color: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.icon = icon
        self.color = color
        self.is_collapsed = True
        self.count = 0
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (clickable)
        self.header = QPushButton()
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self._toggle)
        self._update_header()
        layout.addWidget(self.header)
        
        # Content (hidden by default)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(4)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content.setVisible(False)
        layout.addWidget(self.content)
        
    def _update_header(self):
        arrow = "▼" if not self.is_collapsed else "▶"
        self.header.setText(f"{arrow} {self.icon} {self.title_text} ({self.count})")
        self.header.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.color};
                border: none;
                text-align: left;
                padding: 6px 8px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: #1f1f2a;
                border-radius: 4px;
            }}
        """)
        
    def _toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self._update_header()
        
    def set_count(self, count: int):
        self.count = count
        self._update_header()
        
    def add_widget(self, widget):
        self.content_layout.addWidget(widget)
        
    def clear(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class DetectionBrowserPanel(QFrame):
    """
    Panel for browsing and reviewing detected content segments.
    Provides tabbed navigation by type with To Review, Kept, and Deleted sections.
    Supports batch selection with checkboxes for mass delete/keep operations.
    """
    
    segment_deleted = Signal(str, object)  # (track_key, segment)
    segment_kept = Signal(str, object)  # (track_key, segment)
    seek_to_segment = Signal(object)  # segment
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "browser-panel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        
        # Data storage per track
        self.data = {}  # {track_key: [segments]} - original data (to review)
        self.kept = {}  # {track_key: [segments]}
        self.deleted = {}  # {track_key: [segments]}
        
        self.current_track = None
        self.current_index = 0
        self.current_card_index = 0  # For keyboard navigation
        self.cards = []  # Current review card widgets
        self.selected_segments = set()  # Track selected segment IDs
        self.scene_mode = False  # Scene grouping mode
        self.scene_gap = 5.0  # Default scene gap in seconds
        self.scenes = []  # Grouped scenes for current track
        
        # Enable keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("🔍 Detection Browser")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f5f5f8;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        
        # Tab bar for detection types
        self.tab_bar = QTabBar()
        self.tab_bar.setStyleSheet("""
            QTabBar::tab {
                background: #1a1a24;
                color: #71717a;
                border: 1px solid #2a2a38;
                border-bottom: none;
                padding: 8px 12px;
                margin-right: 4px;
                border-radius: 6px 6px 0 0;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #252530;
                color: #f5f5f8;
                border-color: #3b82f6;
            }
            QTabBar::tab:hover:!selected {
                background: #1f1f2a;
                color: #a0a0b0;
            }
        """)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_bar)
        
        # Progress summary
        self.progress_summary = QLabel()
        self.progress_summary.setStyleSheet("color: #71717a; font-size: 11px; padding: 4px 0;")
        layout.addWidget(self.progress_summary)
        
        # Selection toolbar
        selection_bar = QHBoxLayout()
        selection_bar.setSpacing(8)
        
        self.select_all_btn = QPushButton("☐ Select All")
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #3b82f6;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 6px 10px;
                font-weight: 600;
                font-size: 10px;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.1);
            }
        """)
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        selection_bar.addWidget(self.select_all_btn)
        
        self.selection_label = QLabel("0 selected")
        self.selection_label.setStyleSheet("color: #71717a; font-size: 10px;")
        selection_bar.addWidget(self.selection_label)
        
        selection_bar.addStretch()
        
        # Scene grouping toggle (only for nudity)
        self.scene_toggle = QCheckBox("🎬 Group Scenes")
        self.scene_toggle.setToolTip("Group nearby detections into scenes for easier review")
        self.scene_toggle.setStyleSheet("""
            QCheckBox {
                color: #8b5cf6;
                font-size: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #8b5cf6;
                background: #1a1a24;
            }
            QCheckBox::indicator:checked {
                background: #8b5cf6;
            }
        """)
        self.scene_toggle.setVisible(False)  # Only shown for nudity
        self.scene_toggle.stateChanged.connect(self._on_scene_toggle)
        selection_bar.addWidget(self.scene_toggle)
        
        layout.addLayout(selection_bar)
        
        # Scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #15151d;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a4a;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4a5a;
            }
        """)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(12)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # TO REVIEW Section Header
        review_header = QLabel("📋 TO REVIEW")
        review_header.setStyleSheet("""
            color: #3b82f6; 
            font-weight: 700; 
            font-size: 12px; 
            padding: 8px 0 4px 0;
            border-bottom: 1px solid #2a2a38;
        """)
        self.content_layout.addWidget(review_header)
        
        # To Review cards container
        self.review_container = QWidget()
        self.review_layout = QVBoxLayout(self.review_container)
        self.review_layout.setSpacing(8)
        self.review_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addWidget(self.review_container)
        
        # KEPT Section (collapsible)
        self.kept_section = CollapsibleSection("KEPT", "✓", "#22c55e")
        self.content_layout.addWidget(self.kept_section)
        
        # DELETED Section (collapsible)
        self.deleted_section = CollapsibleSection("DELETED", "✗", "#ef4444")
        self.content_layout.addWidget(self.deleted_section)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll, 1)
        
        # Batch action buttons (for selected items)
        batch_actions = QHBoxLayout()
        batch_actions.setSpacing(8)
        
        self.keep_selected_btn = QPushButton("✓ Keep Selected")
        self.keep_selected_btn.setEnabled(False)
        self.keep_selected_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
            QPushButton:disabled {
                background: #1a2e1a;
                color: #4a5a4a;
            }
        """)
        self.keep_selected_btn.clicked.connect(self._keep_selected)
        batch_actions.addWidget(self.keep_selected_btn)
        
        self.delete_selected_btn = QPushButton("✗ Delete Selected")
        self.delete_selected_btn.setEnabled(False)
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
            QPushButton:disabled {
                background: #2e1a1a;
                color: #5a4a4a;
            }
        """)
        self.delete_selected_btn.clicked.connect(self._delete_selected)
        batch_actions.addWidget(self.delete_selected_btn)
        
        layout.addLayout(batch_actions)
        
        # Quick all actions row (smaller, secondary)
        quick_all = QHBoxLayout()
        quick_all.setSpacing(8)
        
        self.keep_all_btn = QPushButton("Keep All")
        self.keep_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #22c55e;
                border: none;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        self.keep_all_btn.clicked.connect(self._keep_all)
        quick_all.addWidget(self.keep_all_btn)
        
        separator = QLabel("|")
        separator.setStyleSheet("color: #3a3a48; font-size: 10px;")
        quick_all.addWidget(separator)
        
        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ef4444;
                border: none;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        self.delete_all_btn.clicked.connect(self._delete_all)
        quick_all.addWidget(self.delete_all_btn)
        
        quick_all.addStretch()
        layout.addLayout(quick_all)
        
    def set_data(self, data: dict):
        """Load detection data. Expected format: {track_key: [segments]}"""
        # Deep copy segments to avoid modifying original
        self.data = {k: list(v) for k, v in data.items() if v}
        self.kept = {k: [] for k in self.data.keys()}
        self.deleted = {k: [] for k in self.data.keys()}
        self.current_index = 0
        
        # Clear tabs
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)
        
        # Add tabs for each detection type
        track_display = {
            'nudity': ('👁 Nudity', '#f43f5e'),
            'profanity': ('🤬 Profanity', '#fbbf24'),
            'sexual_content': ('💋 Sexual', '#d946ef'),
            'violence': ('⚔️ Violence', '#ef4444'),
        }
        
        for key, segments in self.data.items():
            display_name, color = track_display.get(key, (key.title(), '#888'))
            total = len(segments)
            self.tab_bar.addTab(f"{display_name} ({total})")
            self.tab_bar.setTabData(self.tab_bar.count() - 1, key)
        
        # Select first tab
        if self.tab_bar.count() > 0:
            self.tab_bar.setCurrentIndex(0)
            self._on_tab_changed(0)
        else:
            self._clear_all()
            self.progress_summary.setText("No detections found")
            
    def _on_tab_changed(self, index: int):
        """Handle tab selection."""
        if index < 0:
            return
            
        self.current_track = self.tab_bar.tabData(index)
        self.current_index = 0
        
        # Show scene toggle only for nudity track
        is_nudity = self.current_track == 'nudity'
        self.scene_toggle.setVisible(is_nudity and HAS_SCENE_GROUPING)
        
        # Reset scene mode if switching away from nudity
        if not is_nudity:
            self.scene_mode = False
            self.scene_toggle.setChecked(False)
        
        self._refresh_all_sections()
        
    def _refresh_all_sections(self):
        """Rebuild all sections for current track."""
        self._clear_all()
        self.selected_segments.clear()  # Reset selection
        self._update_selection_ui()
        
        if not self.current_track:
            return
        
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        total = len(to_review) + len(kept) + len(deleted)
        reviewed = len(kept) + len(deleted)
        
        if total > 0:
            pct = (reviewed / total) * 100
            self.progress_summary.setText(f"Progress: {reviewed}/{total} reviewed ({pct:.0f}%)")
        else:
            self.progress_summary.setText("No detections")
        
        # Build To Review section
        if to_review:
            # Check if we should group into scenes (only for nudity)
            if self.scene_mode and self.current_track == 'nudity' and HAS_SCENE_GROUPING:
                self._build_scene_cards(to_review)
            else:
                self._build_detection_cards(to_review)
        else:
            done_label = QLabel("✅ All reviewed!")
            done_label.setStyleSheet("color: #22c55e; font-size: 12px; padding: 12px; text-align: center;")
            done_label.setAlignment(Qt.AlignCenter)
            self.review_layout.addWidget(done_label)
        
        # Build Kept section
        self.kept_section.clear()
        self.kept_section.set_count(len(kept))
        for segment in kept:
            mini_card = MiniDetectionCard(segment, 'kept')
            mini_card.restore_clicked.connect(lambda seg: self._restore_segment(seg, 'kept'))
            mini_card.card_clicked.connect(self._on_card_clicked)
            self.kept_section.add_widget(mini_card)
        
        # Build Deleted section
        self.deleted_section.clear()
        self.deleted_section.set_count(len(deleted))
        for segment in deleted:
            mini_card = MiniDetectionCard(segment, 'deleted')
            mini_card.restore_clicked.connect(lambda seg: self._restore_segment(seg, 'deleted'))
            mini_card.card_clicked.connect(self._on_card_clicked)
            self.deleted_section.add_widget(mini_card)
    
    def _build_detection_cards(self, to_review: list):
        """Build individual detection cards (normal mode)."""
        for i, segment in enumerate(to_review):
            card = DetectionCard(segment, i, len(to_review))
            card.keep_clicked.connect(self._on_keep)
            card.delete_clicked.connect(self._on_delete)
            card.card_clicked.connect(self._on_card_clicked)
            card.selection_changed.connect(self._on_selection_changed)
            self.review_layout.addWidget(card)
            self.cards.append(card)
            
        # Highlight first card
        if self.cards:
            self.cards[0].set_highlighted(True)
    
    def _build_scene_cards(self, to_review: list):
        """Build scene cards (grouped mode) for nudity."""
        # Convert segments to TimeIntervals for grouping
        intervals = []
        for seg in to_review:
            ti = TimeInterval(
                start=seg.get('start', 0),
                end=seg.get('end', 0),
                reason=seg.get('label', seg.get('reason', 'nudity')),
            )
            # Store reference to original segment
            ti.metadata['segment'] = seg
            intervals.append(ti)
        
        # Group into scenes
        self.scenes = group_into_scenes(intervals, scene_gap=self.scene_gap)
        
        # Create scene cards
        for i, scene in enumerate(self.scenes):
            card = SceneCard(scene, i, len(self.scenes))
            card.keep_clicked.connect(self._on_scene_keep)
            card.delete_clicked.connect(self._on_scene_delete)
            card.card_clicked.connect(self._on_card_clicked)
            card.selection_changed.connect(self._on_scene_selection_changed)
            self.review_layout.addWidget(card)
            self.cards.append(card)
    
    def _on_scene_toggle(self, state):
        """Handle scene grouping toggle."""
        self.scene_mode = state == Qt.Checked
        self._refresh_all_sections()
    
    def _on_scene_keep(self, scene):
        """Keep all detections in a scene."""
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        
        # Keep all segments within this scene
        for detection in scene.detections:
            seg = detection.metadata.get('segment')
            if seg and seg in to_review:
                to_review.remove(seg)
                seg['ignored'] = True
                kept.append(seg)
                self.segment_kept.emit(self.current_track, seg)
        
        self._update_tab_counts()
        self._refresh_all_sections()
        
        # Seek to next scene if available
        if to_review:
            self.seek_to_segment.emit(to_review[0])
    
    def _on_scene_delete(self, scene):
        """Delete all detections in a scene."""
        to_review = self.data.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        # Delete all segments within this scene
        for detection in scene.detections:
            seg = detection.metadata.get('segment')
            if seg and seg in to_review:
                to_review.remove(seg)
                deleted.append(seg)
                self.segment_deleted.emit(self.current_track, seg)
        
        self._update_tab_counts()
        self._refresh_all_sections()
        
        # Seek to next scene if available
        if to_review:
            self.seek_to_segment.emit(to_review[0])
    
    def _on_scene_selection_changed(self, scene, is_selected: bool):
        """Handle scene selection change."""
        scene_id = id(scene)
        if is_selected:
            self.selected_segments.add(scene_id)
        else:
            self.selected_segments.discard(scene_id)
        self._update_selection_ui()
    
    def _clear_all(self):
        """Clear all card widgets."""
        for card in self.cards:
            card.deleteLater()
        self.cards = []
        
        # Clear review layout
        while self.review_layout.count():
            item = self.review_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.kept_section.clear()
        self.deleted_section.clear()
        
    def _on_card_clicked(self, segment):
        """Handle clicking on any card to seek."""
        self.seek_to_segment.emit(segment)
        
    def _on_keep(self, segment):
        """Move segment from to-review to kept."""
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        
        if segment in to_review:
            to_review.remove(segment)
            segment['ignored'] = True  # Mark as ignored for censoring
            kept.append(segment)
            self.segment_kept.emit(self.current_track, segment)
            
            self._update_tab_counts()
            self._refresh_all_sections()
            
            # Seek to next if available
            if to_review:
                self.seek_to_segment.emit(to_review[0])
                
    def _on_delete(self, segment):
        """Move segment from to-review to deleted."""
        to_review = self.data.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        if segment in to_review:
            to_review.remove(segment)
            deleted.append(segment)
            self.segment_deleted.emit(self.current_track, segment)
            
            self._update_tab_counts()
            self._refresh_all_sections()
            
            # Seek to next if available
            if to_review:
                self.seek_to_segment.emit(to_review[0])
                
    def _restore_segment(self, segment, from_section: str):
        """Restore a segment back to the to-review list."""
        to_review = self.data.get(self.current_track, [])
        
        if from_section == 'kept':
            kept = self.kept.get(self.current_track, [])
            if segment in kept:
                kept.remove(segment)
                segment['ignored'] = False  # Un-ignore
                to_review.append(segment)
        elif from_section == 'deleted':
            deleted = self.deleted.get(self.current_track, [])
            if segment in deleted:
                deleted.remove(segment)
                to_review.append(segment)
        
        self._update_tab_counts()
        self._refresh_all_sections()
        
    def _update_tab_counts(self):
        """Update tab labels with remaining to-review counts."""
        track_display = {
            'nudity': '👁 Nudity',
            'profanity': '🤬 Profanity',
            'sexual_content': '💋 Sexual',
            'violence': '⚔️ Violence',
        }
        
        for i in range(self.tab_bar.count()):
            key = self.tab_bar.tabData(i)
            to_review = len(self.data.get(key, []))
            display = track_display.get(key, key.title())
            self.tab_bar.setTabText(i, f"{display} ({to_review})")
            
    def _keep_all(self):
        """Keep all remaining to-review items."""
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        
        for segment in list(to_review):
            segment['ignored'] = True
            kept.append(segment)
            self.segment_kept.emit(self.current_track, segment)
        to_review.clear()
        
        self._update_tab_counts()
        self._refresh_all_sections()
        
    def _delete_all(self):
        """Delete all remaining to-review items."""
        to_review = self.data.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        for segment in list(to_review):
            deleted.append(segment)
            self.segment_deleted.emit(self.current_track, segment)
        to_review.clear()
        
        self._update_tab_counts()
        self._refresh_all_sections()
    
    # ===== SELECTION HANDLING =====
    
    def _on_selection_changed(self, segment, is_selected: bool):
        """Handle selection change from a card."""
        seg_id = id(segment)
        if is_selected:
            self.selected_segments.add(seg_id)
        else:
            self.selected_segments.discard(seg_id)
        self._update_selection_ui()
        
    def _update_selection_ui(self):
        """Update selection-related UI elements."""
        count = len(self.selected_segments)
        total = len(self.cards)
        
        # Update selection label
        self.selection_label.setText(f"{count} selected")
        
        # Update Select All button text
        if count == total and total > 0:
            self.select_all_btn.setText("☑ Deselect All")
        else:
            self.select_all_btn.setText("☐ Select All")
        
        # Enable/disable batch action buttons
        has_selection = count > 0
        self.keep_selected_btn.setEnabled(has_selection)
        self.delete_selected_btn.setEnabled(has_selection)
        
        # Update button text with count
        if has_selection:
            self.keep_selected_btn.setText(f"✓ Keep Selected ({count})")
            self.delete_selected_btn.setText(f"✗ Delete Selected ({count})")
        else:
            self.keep_selected_btn.setText("✓ Keep Selected")
            self.delete_selected_btn.setText("✗ Delete Selected")
    
    def _toggle_select_all(self):
        """Toggle select all / deselect all."""
        if len(self.selected_segments) == len(self.cards) and len(self.cards) > 0:
            # Deselect all
            self.selected_segments.clear()
            for card in self.cards:
                card.set_selected(False)
        else:
            # Select all
            self.selected_segments.clear()
            for card in self.cards:
                card.set_selected(True)
                self.selected_segments.add(id(card.segment))
        self._update_selection_ui()
    
    def _keep_selected(self):
        """Keep all selected items."""
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        
        segments_to_keep = []
        for card in self.cards:
            if id(card.segment) in self.selected_segments:
                segments_to_keep.append(card.segment)
        
        for segment in segments_to_keep:
            if segment in to_review:
                to_review.remove(segment)
                segment['ignored'] = True
                kept.append(segment)
                self.segment_kept.emit(self.current_track, segment)
        
        self._update_tab_counts()
        self._refresh_all_sections()
    
    def _delete_selected(self):
        """Delete all selected items."""
        to_review = self.data.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        segments_to_delete = []
        for card in self.cards:
            if id(card.segment) in self.selected_segments:
                segments_to_delete.append(card.segment)
        
        for segment in segments_to_delete:
            if segment in to_review:
                to_review.remove(segment)
                deleted.append(segment)
                self.segment_deleted.emit(self.current_track, segment)
        
        self._update_tab_counts()
        self._refresh_all_sections()
        
    def get_final_data(self) -> dict:
        """Get the final data with kept segments (ignored) and deleted removed."""
        result = {}
        
        for track_key in self.data.keys():
            # Include kept segments (they have ignored=True)
            kept = self.kept.get(track_key, [])
            # Include remaining to-review (not yet reviewed = keep as-is)
            to_review = self.data.get(track_key, [])
            
            # Combine - deleted segments are excluded
            result[track_key] = kept + to_review
            
        return result
    
    # ========== KEYBOARD SHORTCUTS ==========
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for quick review.
        
        Shortcuts:
            Space - Seek to current detection
            ← → - Navigate prev/next detection
            K - Keep current detection
            S - Skip (delete) current detection
            E - Expand region +0.5s each side
            R - Reduce region -0.5s each side
        """
        key = event.key()
        
        # Get current card if available
        current_card = None
        if self.cards and 0 <= self.current_card_index < len(self.cards):
            current_card = self.cards[self.current_card_index]
        
        if key == Qt.Key_Space:
            if current_card and hasattr(current_card, 'segment'):
                self.seek_to_segment.emit(current_card.segment)
            event.accept()
        elif key == Qt.Key_Left:
            self._navigate_prev()
            event.accept()
        elif key == Qt.Key_Right:
            self._navigate_next()
            event.accept()
        elif key == Qt.Key_K:
            if current_card and hasattr(current_card, 'segment'):
                self._on_keep(current_card.segment)
                self._navigate_next()
            event.accept()
        elif key == Qt.Key_S:
            if current_card and hasattr(current_card, 'segment'):
                self._on_delete(current_card.segment)
            event.accept()
        elif key == Qt.Key_E:
            if current_card and hasattr(current_card, 'segment'):
                self._expand_region(current_card.segment)
            event.accept()
        elif key == Qt.Key_R:
            if current_card and hasattr(current_card, 'segment'):
                self._reduce_region(current_card.segment)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def _navigate_prev(self):
        """Navigate to previous detection card."""
        if self.cards and self.current_card_index > 0:
            self.current_card_index -= 1
            self._highlight_current_card()
    
    def _navigate_next(self):
        """Navigate to next detection card."""
        if self.cards and self.current_card_index < len(self.cards) - 1:
            self.current_card_index += 1
            self._highlight_current_card()
    
    def _highlight_current_card(self):
        """Highlight the current card and seek to it."""
        for i, card in enumerate(self.cards):
            if hasattr(card, 'set_highlighted'):
                card.set_highlighted(i == self.current_card_index)
        
        if self.cards and 0 <= self.current_card_index < len(self.cards):
            card = self.cards[self.current_card_index]
            if hasattr(card, 'segment'):
                self.seek_to_segment.emit(card.segment)
    
    def _expand_region(self, segment: dict):
        """Expand detection region by 0.5s on each side."""
        if 'start' in segment and 'end' in segment:
            segment['start'] = max(0, segment['start'] - 0.5)
            segment['end'] = segment['end'] + 0.5
            self._refresh_all_sections()
    
    def _reduce_region(self, segment: dict):
        """Reduce detection region by 0.5s on each side."""
        if 'start' in segment and 'end' in segment:
            new_start = segment['start'] + 0.5
            new_end = segment['end'] - 0.5
            if new_start < new_end:
                segment['start'] = new_start
                segment['end'] = new_end
                self._refresh_all_sections()
    
    # ========== BATCH ACTIONS ==========
    
    def skip_low_confidence(self, threshold: float = 0.5):
        """Skip all detections with confidence below threshold."""
        if not self.current_track:
            return
        to_review = list(self.data.get(self.current_track, []))
        for s in to_review:
            if s.get('confidence', 1.0) < threshold:
                self._on_delete(s)
    
    def confirm_high_confidence(self, threshold: float = 0.8):
        """Confirm all detections with confidence above threshold."""
        if not self.current_track:
            return
        to_review = list(self.data.get(self.current_track, []))
        for s in to_review:
            if s.get('confidence', 1.0) >= threshold:
                self._on_keep(s)
    
    def skip_audio_only(self):
        """Skip all audio-only (profanity) detections."""
        if self.current_track == 'profanity':
            for s in list(self.data.get(self.current_track, [])):
                self._on_delete(s)
    
    def skip_visual_only(self):
        """Skip all visual-only (nudity) detections."""
        if self.current_track == 'nudity':
            for s in list(self.data.get(self.current_track, [])):
                self._on_delete(s)

