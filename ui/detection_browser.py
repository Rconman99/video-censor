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

# Import card components
from ui.components.detection_card import MiniDetectionCard, SceneCard, DetectionCard
from ui.components.hover_preview import HoverPreview
from ui.components.detection_group_header import DetectionGroupHeader
from ui.components.tier_header import TierHeader
from video_censor.profanity.severity import get_severity
from video_censor.undo_manager import UndoManager
from collections import defaultdict
from copy import deepcopy
from video_censor.config import Config


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
        self.video_path = None # For preview
        
        self.current_track = None
        self.current_index = 0
        self.current_card_index = 0  # For keyboard navigation
        self.cards = []  # Current review card widgets
        self.selected_segments = set()  # Track selected segment IDs
        self.scene_mode = False  # Scene grouping mode
        self.group_by_word = False # Group by word mode
        self.scene_gap = 5.0  # Default scene gap in seconds
        self.scenes = []  # Grouped scenes for current track
        
        self.hover_preview = HoverPreview(self)
        
        # Load config for severity overrides
        try:
            self.config = Config.load(Path(__file__).parent.parent / "config.yaml")
        except Exception as e:
            print(f"Error loading config in DetectionBrowser: {e}")
            self.config = Config()
        
        # Undo/Redo manager
        self.undo_manager = UndoManager()
        
        # Enable keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)
        
        self._create_ui()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        
        # Group toggle
        if key == Qt.Key_G:
           self.group_toggle.click()
           return

        # Tier batch actions (only in tiered group mode)
        if self.group_by_word:
            if key == Qt.Key_1:
                 # Keep Severe (Order 1)
                 self._on_batch_tier_keep("severe")
            elif key == Qt.Key_2:
                 # Keep Moderate (Order 2)
                 self._on_batch_tier_keep("moderate")
            elif key == Qt.Key_3:
                 # Keep Mild (Order 3)
                 self._on_batch_tier_keep("mild")
            elif key == Qt.Key_4:
                 # Skip Religious (Order 4)
                 self._on_batch_tier_skip("religious")
            
        super().keyPressEvent(event)
        
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
        
        # Quick Actions Toolbar (Batch)
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(4)
        
        actions_label = QLabel("Batch:")
        actions_label.setStyleSheet("color: #71717a; font-size: 10px; font-weight: bold;")
        actions_bar.addWidget(actions_label)
        
        btn_skip_low = QPushButton("Skip Low Conf")
        btn_skip_low.setToolTip("Skip all < 50% confidence")
        btn_skip_low.clicked.connect(lambda: self.skip_low_confidence(0.5))
        btn_skip_low.setStyleSheet("background: #2a2a35; color: #a0a0b0; border: none; font-size: 10px; padding: 4px 8px; border-radius: 4px;")
        actions_bar.addWidget(btn_skip_low)
        
        btn_confirm_high = QPushButton("Keep High Conf")
        btn_confirm_high.setToolTip("Keep all > 80% confidence")
        btn_confirm_high.clicked.connect(lambda: self.confirm_high_confidence(0.8))
        btn_confirm_high.setStyleSheet("background: #2a2a35; color: #a0a0b0; border: none; font-size: 10px; padding: 4px 8px; border-radius: 4px;")
        actions_bar.addWidget(btn_confirm_high)
        
        # Skip false positive types (nudity track only)
        self.btn_skip_fp = QPushButton("🧹 Skip False Positives")
        self.btn_skip_fp.setToolTip("Skip MALE_GENITALIA, BUTTOCKS, ANUS (high false positive rate)")
        self.btn_skip_fp.clicked.connect(self.skip_false_positive_types)
        self.btn_skip_fp.setStyleSheet("background: #7c3aed; color: white; border: none; font-size: 10px; padding: 4px 8px; border-radius: 4px;")
        self.btn_skip_fp.setVisible(False)  # Only show for nudity track
        actions_bar.addWidget(self.btn_skip_fp)
        
        actions_bar.addStretch()
        layout.addLayout(actions_bar)

        
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
        
        # Group by Word Toggle (for Profanity)
        self.group_word_toggle = QCheckBox("🔡 Group Words")
        self.group_word_toggle.setToolTip("Group detections by word for batch review")
        self.group_word_toggle.setStyleSheet("""
            QCheckBox {
                color: #3b82f6;
                font-size: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #3b82f6;
                background: #1a1a24;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
            }
        """)
        self.group_word_toggle.setVisible(False) 
        self.group_word_toggle.stateChanged.connect(self._on_group_word_toggle)
        selection_bar.addWidget(self.group_word_toggle)
        
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
                background: #2a2a35;
                color: #52525b;
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
                background: #2a2a35;
                color: #52525b;
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
        
    def set_data(self, data: dict, video_path: str = None):
        """Set detection data and refresh sections."""
        self.data = data
        
        # Reset hover preview when switching videos
        if video_path != self.video_path:
            self.hover_preview.reset_video()
        self.video_path = video_path
        
        self.kept = {}
        self.deleted = {}
        self.selected_segments.clear()
        
        # Refresh tabs
        while self.tab_bar.count():
            self.tab_bar.removeTab(0)
            
        tracks = list(data.keys())
        if tracks:
            for track in tracks:
                name = track.replace('_', ' ').title()
                self.tab_bar.addTab(name)
            
            self.current_track = tracks[0]
            self.scene_mode = False # Reset scene mode
            self.scene_toggle.setChecked(False)
            self._on_tab_changed(0)
        else:
            self._clear_all()
            
    def _on_tab_changed(self, index: int):
        if index < 0:
            return
            
        track_key = list(self.data.keys())[index]
        self.current_track = track_key
        
        # Show scene toggle only for nudity
        self.scene_toggle.setVisible(track_key == 'nudity' and HAS_SCENE_GROUPING)
        self.scene_mode = self.scene_toggle.isChecked() and track_key == 'nudity'
        
        # Show group by word only for profanity
        self.group_word_toggle.setVisible(track_key == 'profanity')
        self.group_by_word = self.group_word_toggle.isChecked() and track_key == 'profanity'
        
        # Show Skip False Positives button only for nudity
        if hasattr(self, 'btn_skip_fp'):
            self.btn_skip_fp.setVisible(track_key == 'nudity')
        
        self._refresh_all_sections()

        
    def _refresh_all_sections(self):
        """Rebuild all sections based on current state."""
        if not self.current_track:
            return
            
        # Get lists
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.get(self.current_track, [])
        deleted = self.deleted.get(self.current_track, [])
        
        # Clear UI
        # Remove all items from review layout
        while self.review_layout.count():
            item = self.review_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self.cards = []
        self.kept_section.clear()
        self.deleted_section.clear()
        self.selected_segments.clear()
        self._update_selection_ui()
        
        # Build To Review
        if self.scene_mode and HAS_SCENE_GROUPING:
            self._build_scene_cards(to_review)
        elif self.group_by_word:
            self._build_tiered_grouped_cards(to_review)
        else:
            self._build_detection_cards(to_review)
        
        # Build Kept
        self.kept_section.set_count(len(kept))
        for segment in kept:
            card = MiniDetectionCard(segment, 'kept')
            card.restore_clicked.connect(lambda s: self._restore_segment(s, 'kept'))
            card.card_clicked.connect(self._on_card_clicked)
            self.kept_section.add_widget(card)
            
        # Build Deleted
        self.deleted_section.set_count(len(deleted))
        for segment in deleted:
            card = MiniDetectionCard(segment, 'deleted')
            card.restore_clicked.connect(lambda s: self._restore_segment(s, 'deleted'))
            card.card_clicked.connect(self._on_card_clicked)
            self.deleted_section.add_widget(card)
            
        self._update_tab_counts()
        
    def _build_detection_cards(self, to_review: list):
        """Build individual detection cards."""
        total = len(to_review)
        for i, segment in enumerate(to_review):
            card = DetectionCard(segment, i, total)
            card.keep_clicked.connect(self._on_keep)
            card.delete_clicked.connect(self._on_delete)
            card.card_clicked.connect(self._on_card_clicked)
            card.selection_changed.connect(self._on_selection_changed)
            # Hover events
            card.hover_started.connect(self._on_card_hover_start)
            card.hover_ended.connect(self._on_card_hover_end)
            
            self.review_layout.addWidget(card)
            self.cards.append(card)
            
    def _build_scene_cards(self, to_review: list):
        """Build grouped scene cards."""
        # Group detections into scenes
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

        self.scenes = group_into_scenes(intervals, scene_gap=self.scene_gap)
        total = len(self.scenes)
        
        for i, scene in enumerate(self.scenes):
            card = SceneCard(scene, i, total)
            card.keep_clicked.connect(self._on_scene_keep)
            card.delete_clicked.connect(self._on_scene_delete)
            card.card_clicked.connect(lambda s: self._on_card_clicked(s.detections[0].metadata['segment'])) # Seek to start of first detection in scene
            card.selection_changed.connect(self._on_scene_selection_changed)
            
            self.review_layout.addWidget(card)
            self.cards.append(card)
            

    def _build_tiered_grouped_cards(self, to_review: list):
        """Builds detections grouped by severity tier, then by word."""
        # 1. Group data: Tier -> Word -> [segments]
        # keys: (tier_order, tier_name, tier_color)
        tiers = defaultdict(lambda: defaultdict(list))
        
        for segment in to_review:
            # Determine word
            meta = segment.get('metadata', {})
            word = meta.get('matched_pattern') or meta.get('word') or segment.get('label') or "Unknown"
            
            # Determine severity with overrides and custom tiers
            overrides = self.config.profanity.severity_overrides
            custom_tiers = self.config.profanity.custom_tiers
            
            tier_name, order, color = get_severity(word, overrides, custom_tiers)
            
            # No skipping - everything gets grouped
            tiers[(order, tier_name, color)][word.lower()].append(segment)
            
        # 2. Sort tiers by order
        sorted_tiers = sorted(tiers.items(), key=lambda x: x[0][0])
        
        # 3. Create Widgets
        total = len(to_review)
        global_idx = 0
        
        for (order, tier_name, color), word_groups in sorted_tiers:
            # Tier Header
            # Calculate total detections in this tier
            tier_total = sum(len(segs) for segs in word_groups.values())
            
            tier_header = TierHeader(tier_name, color, tier_total)
            tier_header.keep_all_tier_requested.connect(lambda t=tier_name: self._on_batch_tier_keep(t))
            tier_header.skip_all_tier_requested.connect(lambda t=tier_name: self._on_batch_tier_skip(t))
            self.review_layout.addWidget(tier_header)
            
            # Sort words within tier by count (descending)
            sorted_words = sorted(word_groups.items(), key=lambda x: len(x[1]), reverse=True)
            
            for word, segments in sorted_words:
                # Word Group Header
                # Pass explicit tier color to header
                header = DetectionGroupHeader(word.title(), len(segments), color=color)
                header.keep_all_requested.connect(self._on_batch_group_keep)
                header.skip_all_requested.connect(self._on_batch_group_skip)
                
                self.review_layout.addWidget(header)
                
                for segment in segments:
                    card = DetectionCard(segment, global_idx, total)
                    card.keep_clicked.connect(self._on_keep)
                    card.delete_clicked.connect(self._on_delete)
                    card.card_clicked.connect(self._on_card_clicked)
                    card.selection_changed.connect(self._on_selection_changed)
                    
                    # Initially hidden? Header defaults to collapsed=False (Wait, I set it to False/collapsed in prev step)
                    # So cards need to be added to layout but might need to be hidden initially if header controls logic
                    # The header implementation `set_expanded` toggles visibility. 
                    # If we add them to layout, they are visible by default unless we hide them.
                    # We should align with header state.
                    if not header.expanded:
                        card.setVisible(False)
                        
                    self.review_layout.addWidget(card)
                    self.cards.append(card)
                    
                    header.add_child_card(card)
                    
                    global_idx += 1

    def _on_batch_tier_keep(self, tier_name):
        """Keep all items in a named tier."""
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        overrides = self.config.profanity.severity_overrides
        custom_tiers = self.config.profanity.custom_tiers
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        
        for segment in to_review:
             meta = segment.get('metadata', {})
             word = meta.get('matched_pattern') or meta.get('word') or segment.get('label') or "Unknown"
             t_name, _, _ = get_severity(word, overrides, custom_tiers)
             
             if t_name == tier_name:
                 self._on_keep(segment, refresh=False)
                 count += 1
                 
        if count > 0:
            self.push_undo(f"Keep all {tier_name} ({count})", old_state)
        self._refresh_all_sections()
        
    def _on_batch_tier_skip(self, tier_name):
        """Skip (delete) all items in a named tier."""
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        overrides = self.config.profanity.severity_overrides
        custom_tiers = self.config.profanity.custom_tiers
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        
        for segment in to_review:
             meta = segment.get('metadata', {})
             word = meta.get('matched_pattern') or meta.get('word') or segment.get('label') or "Unknown"
             t_name, _, _ = get_severity(word, overrides, custom_tiers)
             
             if t_name == tier_name:
                 self._on_delete(segment, refresh=False)
                 count += 1
                 
        if count > 0:
            self.push_undo(f"Skip all {tier_name} ({count})", old_state)
        self._refresh_all_sections()
                
    def _on_batch_group_keep(self, word):
        """Keep all items in a named group."""
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        # Find all segments matching this word
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        for segment in to_review:
             meta = segment.get('metadata', {})
             w = meta.get('matched_pattern') or meta.get('word') or segment.get('label') or "Unknown"
             if w.lower() == word.lower():
                 self._on_keep(segment, refresh=False)
                 count += 1
                 
        if count > 0:
            self.push_undo(f"Keep all '{word}' ({count})", old_state)
        self._refresh_all_sections()
        
    def _on_batch_group_skip(self, word):
        """Delete all items in a named group."""
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        for segment in to_review:
             meta = segment.get('metadata', {})
             w = meta.get('matched_pattern') or meta.get('word') or segment.get('label') or "Unknown"
             if w.lower() == word.lower():
                 self._on_delete(segment, refresh=False)
                 count += 1
                 
        if count > 0:
            self.push_undo(f"Skip all '{word}' ({count})", old_state)
        self._refresh_all_sections()

    def _on_group_word_toggle(self, state):
        self.group_by_word = (state == Qt.Checked)
        self._refresh_all_sections()

    def _on_card_hover_start(self, segment):
        """Show hover preview."""
        if self.video_path:
            # Map global position
            cursor_pos = self.cursor().pos()
            self.hover_preview.start_preview(self.video_path, segment.get('start', 0), cursor_pos)

    def _on_card_hover_end(self):
        """Hide hover preview."""
        self.hover_preview.stop_preview()

    def _on_scene_toggle(self, state):
        self.scene_mode = (state == Qt.Checked)
        self._refresh_all_sections()
        
    def _on_scene_keep(self, scene):
        # Keep all detections in scene
        for det_interval in scene.detections:
            seg = det_interval.metadata.get('segment')
            if seg:
                self._on_keep(seg, refresh=False)
        self._refresh_all_sections()
        
    def _on_scene_delete(self, scene):
        # Delete all detections in scene
        for det_interval in scene.detections:
            seg = det_interval.metadata.get('segment')
            if seg:
                self._on_delete(seg, refresh=False)
        self._refresh_all_sections()
        
    def _on_scene_selection_changed(self, scene, is_selected: bool):
        # Add/remove all detection IDs in scene
        ids = [id(d.metadata['segment']) for d in scene.detections if 'segment' in d.metadata]
        if is_selected:
            self.selected_segments.update(ids)
        else:
            self.selected_segments.difference_update(ids)
        self._update_selection_ui()

    def _clear_all(self):
        while self.review_layout.count():
            item = self.review_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.kept_section.clear()
        self.deleted_section.clear()
        
    def _on_card_clicked(self, segment):
        self.seek_to_segment.emit(segment)
        # Highlight card
        # Find card if exists
        idx = -1
        # Simple lookup
        for i, card in enumerate(self.cards):
            if isinstance(card, DetectionCard) and card.segment == segment:
                idx = i
                break
            elif isinstance(card, SceneCard):
                # For scene cards, check if the segment is part of this scene
                for det_interval in card.scene.detections:
                    if det_interval.metadata.get('segment') == segment:
                        idx = i
                        break
                if idx != -1:
                    break
        if idx != -1:
            self.current_card_index = idx
            self._highlight_current_card()
        
    def _on_keep(self, segment, refresh=True):
        if not self.current_track:
            return
            
        to_review = self.data.get(self.current_track, [])
        kept = self.kept.setdefault(self.current_track, [])
        
        if segment in to_review:
            to_review.remove(segment)
            kept.append(segment)
            # Mark as ignored so it's not censored
            if 'original_label' not in segment:
                segment['original_label'] = segment.get('label', '')
            segment['ignored'] = True
            
            self.segment_kept.emit(self.current_track, segment)
            
            if refresh:
                self._update_tab_counts()
                self._refresh_all_sections()
                
    def _on_delete(self, segment, refresh=True):
        if not self.current_track:
            return
            
        to_review = self.data.get(self.current_track, [])
        deleted = self.deleted.setdefault(self.current_track, [])
        
        if segment in to_review:
            to_review.remove(segment)
            deleted.append(segment)
            self.segment_deleted.emit(self.current_track, segment)
            
            if refresh:
                self._update_tab_counts()
                self._refresh_all_sections()
                
    def _restore_segment(self, segment, from_section: str):
        if not self.current_track:
            return
            
        target_list = self.kept.get(self.current_track, []) if from_section == 'kept' else self.deleted.get(self.current_track, [])
        to_review = self.data.setdefault(self.current_track, [])
        
        if segment in target_list:
            target_list.remove(segment)
            to_review.append(segment)
            
            # Reset ignored status if returning from kept
            if from_section == 'kept':
                segment['ignored'] = False
            
            # Re-sort to review list by start time
            to_review.sort(key=lambda x: x.get('start', 0))
            
            self._refresh_all_sections()
            
    def _update_tab_counts(self):
        track_display = {
            'nudity': '👁 Nudity',
            'profanity': '🤬 Profanity',
            'sexual_content': '💋 Sexual',
            'violence': '⚔️ Violence',
        }
        
        for i in range(self.tab_bar.count()):
            key = list(self.data.keys())[i] # Get the actual track key
            to_review_count = len(self.data.get(key, []))
            display = track_display.get(key, key.title())
            self.tab_bar.setTabText(i, f"{display} ({to_review_count})")

        # Update progress summary
        to_review_total = len(self.data.get(self.current_track, []))
        kept_total = len(self.kept.get(self.current_track, []))
        deleted_total = len(self.deleted.get(self.current_track, []))
        
        total_segments = to_review_total + kept_total + deleted_total
        reviewed_segments = kept_total + deleted_total
        
        if total_segments > 0:
            pct = (reviewed_segments / total_segments) * 100
            self.progress_summary.setText(f"Progress: {reviewed_segments}/{total_segments} reviewed ({pct:.0f}%)")
        else:
            self.progress_summary.setText("No detections")

    def _keep_all(self):
        # Keep all remaining
        if not self.current_track: return
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        count = len(to_review)
        for s in to_review:
            self._on_keep(s, refresh=False)
        if count > 0:
            self.push_undo(f"Keep all ({count})", old_state)
        self._refresh_all_sections()
        
    def _delete_all(self):
        if not self.current_track: return
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        count = len(to_review)
        for s in to_review:
            self._on_delete(s, refresh=False)
        if count > 0:
            self.push_undo(f"Skip all ({count})", old_state)
        self._refresh_all_sections()
        
    def _on_selection_changed(self, segment, is_selected: bool):
        seg_id = id(segment)
        if is_selected:
            self.selected_segments.add(seg_id)
        elif seg_id in self.selected_segments:
            self.selected_segments.remove(seg_id)
        self._update_selection_ui()
        
    def _update_selection_ui(self):
        count = len(self.selected_segments)
        self.selection_label.setText(f"{count} selected")
        self.keep_selected_btn.setEnabled(count > 0)
        self.delete_selected_btn.setEnabled(count > 0)
        self.keep_selected_btn.setText(f"✓ Keep ({count})")
        self.delete_selected_btn.setText(f"✗ Delete ({count})")
        
        # Update Select All button text
        total_review_items = len(self.cards)
        if count == total_review_items and total_review_items > 0:
            self.select_all_btn.setText("☑ Deselect All")
        else:
            self.select_all_btn.setText("☐ Select All")
        
    def _toggle_select_all(self):
        if not self.cards: return
        
        # Check if all currently selected
        all_selected = len(self.selected_segments) == sum(
            len(card.scene.detections) if isinstance(card, SceneCard) else 1
            for card in self.cards
        ) and len(self.cards) > 0
        
        target_state = not all_selected
        for card in self.cards:
            if hasattr(card, 'set_selected'):
                card.set_selected(target_state)
                
    def _keep_selected(self):
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        segments_to_keep = [s for s in to_review if id(s) in self.selected_segments]
        count = len(segments_to_keep)
        
        for segment in segments_to_keep:
            self._on_keep(segment, refresh=False)
        
        if count > 0:
            self.push_undo(f"Keep selected ({count})", old_state)
        self.selected_segments.clear()
        self._refresh_all_sections()
        
    def _delete_selected(self):
        if not self.current_track: return
        
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        segments_to_delete = [s for s in to_review if id(s) in self.selected_segments]
        count = len(segments_to_delete)
        
        for segment in segments_to_delete:
            self._on_delete(segment, refresh=False)
        
        if count > 0:
            self.push_undo(f"Skip selected ({count})", old_state)
        self.selected_segments.clear()
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
    
    # ========== UNDO/REDO ==========
    
    def _get_state_snapshot(self) -> dict:
        """Get a snapshot of current state for undo."""
        return {
            'data': deepcopy(self.data),
            'kept': deepcopy(self.kept),
            'deleted': deepcopy(self.deleted),
        }
    
    def _restore_state(self, state: dict):
        """Restore state from a snapshot."""
        self.data = deepcopy(state['data'])
        self.kept = deepcopy(state['kept'])
        self.deleted = deepcopy(state['deleted'])
        self._update_tab_counts()
        self._refresh_all_sections()
    
    def push_undo(self, action_name: str, old_state: dict):
        """Push an undo action after making changes."""
        new_state = self._get_state_snapshot()
        self.undo_manager.push(action_name, old_state, new_state)
    
    def undo(self):
        """Undo last action."""
        state = self.undo_manager.undo()
        if state:
            self._restore_state(state)
    
    def redo(self):
        """Redo last undone action."""
        state = self.undo_manager.redo()
        if state:
            self._restore_state(state)
    
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
        
        # Determine the actual segment for the current card
        current_segment = None
        if isinstance(current_card, DetectionCard):
            current_segment = current_card.segment
        elif isinstance(current_card, SceneCard) and current_card.scene.detections:
            current_segment = current_card.scene.detections[0].metadata.get('segment') # Use first segment in scene
        
        if key == Qt.Key_Space:
            if current_segment:
                self.seek_to_segment.emit(current_segment)
            event.accept()
        elif key == Qt.Key_Left:
            self._navigate_prev()
            event.accept()
        elif key == Qt.Key_Right:
            self._navigate_next()
            event.accept()
        elif key == Qt.Key_K:
            if current_segment:
                if isinstance(current_card, SceneCard):
                    self._on_scene_keep(current_card.scene)
                else:
                    self._on_keep(current_segment)
                self._navigate_next()
            event.accept()
        elif key == Qt.Key_S:
            if current_segment:
                if isinstance(current_card, SceneCard):
                    self._on_scene_delete(current_card.scene)
                else:
                    self._on_delete(current_segment)
            event.accept()
        elif key == Qt.Key_E:
            if current_segment:
                self._expand_region(current_segment)
            event.accept()
        elif key == Qt.Key_R:
            if current_segment:
                self._reduce_region(current_segment)
            event.accept()
        elif key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            if event.modifiers() & Qt.ShiftModifier:
                self.redo()  # Ctrl+Shift+Z = Redo
            else:
                self.undo()  # Ctrl+Z = Undo
            event.accept()
        elif key == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            self.redo()  # Ctrl+Y = Redo (Windows style)
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
            
            current_segment = None
            if isinstance(card, DetectionCard):
                current_segment = card.segment
            elif isinstance(card, SceneCard) and card.scene.detections:
                current_segment = card.scene.detections[0].metadata.get('segment')

            if current_segment:
                self.seek_to_segment.emit(current_segment)
    
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
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        for s in to_review:
            if s.get('confidence', 1.0) < threshold:
                self._on_delete(s, refresh=False)
                count += 1
        if count > 0:
            self.push_undo(f"Skip low confidence ({count})", old_state)
        self._refresh_all_sections()
    
    def confirm_high_confidence(self, threshold: float = 0.8):
        """Confirm all detections with confidence above threshold."""
        if not self.current_track:
            return
        old_state = self._get_state_snapshot()
        to_review = list(self.data.get(self.current_track, []))
        count = 0
        for s in to_review:
            if s.get('confidence', 1.0) >= threshold:
                self._on_keep(s, refresh=False)
                count += 1
        if count > 0:
            self.push_undo(f"Keep high confidence ({count})", old_state)
        self._refresh_all_sections()
    
    def skip_audio_only(self):
        """Skip all audio-only (profanity) detections."""
        if self.current_track == 'profanity':
            old_state = self._get_state_snapshot()
            to_skip = list(self.data.get(self.current_track, []))
            count = len(to_skip)
            for s in to_skip:
                self._on_delete(s, refresh=False)
            if count > 0:
                self.push_undo(f"Skip all audio ({count})", old_state)
        self._refresh_all_sections()
    
    def skip_visual_only(self):
        """Skip all visual-only (nudity) detections."""
        if self.current_track == 'nudity':
            old_state = self._get_state_snapshot()
            to_skip = list(self.data.get(self.current_track, []))
            count = len(to_skip)
            for s in to_skip:
                self._on_delete(s, refresh=False)
            if count > 0:
                self.push_undo(f"Skip all visual ({count})", old_state)
        self._refresh_all_sections()
    
    def skip_by_body_part(self, body_part: str):
        """Skip all nudity detections of a specific body part type.
        
        Args:
            body_part: e.g., 'MALE_GENITALIA_EXPOSED', 'BUTTOCKS_EXPOSED'
        """
        if self.current_track != 'nudity':
            return
            
        old_state = self._get_state_snapshot()
        to_review = self.data.get('nudity', [])
        to_skip = []
        
        for segment in to_review:
            reason = segment.get('reason', '')
            if body_part in reason:
                to_skip.append(segment)
        
        for s in to_skip:
            self._on_delete(s, refresh=False)
        
        if to_skip:
            self.push_undo(f"Skip {body_part} ({len(to_skip)})", old_state)
        self._refresh_all_sections()
    
    def skip_male_genitalia(self):
        """Skip all MALE_GENITALIA_EXPOSED detections (high false positive rate)."""
        self.skip_by_body_part('MALE_GENITALIA_EXPOSED')
    
    def skip_buttocks(self):
        """Skip all BUTTOCKS_EXPOSED detections (often triggers on clothing)."""
        self.skip_by_body_part('BUTTOCKS_EXPOSED')
    
    def skip_anus(self):
        """Skip all ANUS_EXPOSED detections."""
        self.skip_by_body_part('ANUS_EXPOSED')
    
    def skip_false_positive_types(self):
        """Skip all high false positive nudity types at once."""
        if self.current_track != 'nudity':
            return
            
        old_state = self._get_state_snapshot()
        to_review = self.data.get('nudity', [])
        to_skip = []
        
        # These body parts have high false positive rates
        false_positive_types = ['MALE_GENITALIA_EXPOSED', 'BUTTOCKS_EXPOSED', 'ANUS_EXPOSED']
        
        for segment in to_review:
            reason = segment.get('reason', '')
            for fp_type in false_positive_types:
                if fp_type in reason:
                    to_skip.append(segment)
                    break
        
        for s in to_skip:
            self._on_delete(s, refresh=False)
        
        if to_skip:
            self.push_undo(f"Skip false positive types ({len(to_skip)})", old_state)
        self._refresh_all_sections()

    def mark_covered_by_edit(self, start: float, end: float, category: str = None):

        """Mark detections as handled when covered by a timeline edit.
        
        Args:
            start: Edit start time in seconds
            end: Edit end time in seconds
            category: Optional category filter (e.g., 'nudity', 'profanity')
                      If None, checks all categories
        """
        categories = [category] if category else list(self.data.keys())
        covered_count = 0
        
        for track in categories:
            if track not in self.data:
                continue
                
            to_review = self.data.get(track, [])
            to_delete = []
            
            for segment in to_review:
                seg_start = segment.get('start', 0)
                seg_end = segment.get('end', 0)
                
                # Check if edit covers this detection (any overlap)
                if seg_start < end and seg_end > start:
                    to_delete.append(segment)
            
            # Move covered segments to deleted
            old_track = self.current_track
            self.current_track = track
            
            for segment in to_delete:
                segment['covered_by_edit'] = True  # Mark as handled by edit
                self._on_delete(segment, refresh=False)
                covered_count += 1
            
            self.current_track = old_track
        
        if covered_count > 0:
            self._update_tab_counts()
            self._refresh_all_sections()
            
        return covered_count
    
    def sync_with_edits(self, edits: list):
        """Sync review list with a list of EditDecision objects.
        
        Args:
            edits: List of EditDecision objects from the timeline editor
        """
        covered_count = 0
        
        for edit in edits:
            # Map edit action to category if possible
            # BLUR → nudity/sexual_content, MUTE → profanity
            category = None  # Check all for now
            
            count = self.mark_covered_by_edit(
                edit.source_start,
                edit.source_end,
                category
            )
            covered_count += count
        
        return covered_count

