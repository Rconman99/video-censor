"""
Detection Browser Panel for Video Censor.
Provides an easy sequential workflow for reviewing detected content segments.
Now with To Review, Kept, and Deleted sections for proper checklist functionality.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QTabBar, QStackedWidget, QSizePolicy, QScrollArea, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QFont


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


class DetectionCard(QFrame):
    """A card displaying a single detection with actions."""
    
    keep_clicked = Signal(object)  # Emits segment
    delete_clicked = Signal(object)  # Emits segment
    card_clicked = Signal(object)  # For seeking to segment
    
    def __init__(self, segment: dict, index: int, total: int, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.index = index
        self.total = total
        
        self.setProperty("class", "detection-card")
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
        self.setCursor(Qt.PointingHandCursor)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)
        
        # Header with counter and time
        header = QHBoxLayout()
        
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
        self.cards = []  # Current review card widgets
        
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
        
        # Quick actions footer
        quick = QHBoxLayout()
        quick.setSpacing(8)
        
        self.keep_all_btn = QPushButton("Keep All Remaining")
        self.keep_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #22c55e;
                border: 1px solid #22c55e;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(34, 197, 94, 0.1);
            }
        """)
        self.keep_all_btn.clicked.connect(self._keep_all)
        quick.addWidget(self.keep_all_btn)
        
        self.delete_all_btn = QPushButton("Delete All Remaining")
        self.delete_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ef4444;
                border: 1px solid #ef4444;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.1);
            }
        """)
        self.delete_all_btn.clicked.connect(self._delete_all)
        quick.addWidget(self.delete_all_btn)
        
        layout.addLayout(quick)
        
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
        self._refresh_all_sections()
        
    def _refresh_all_sections(self):
        """Rebuild all sections for current track."""
        self._clear_all()
        
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
            for i, segment in enumerate(to_review):
                card = DetectionCard(segment, i, len(to_review))
                card.keep_clicked.connect(self._on_keep)
                card.delete_clicked.connect(self._on_delete)
                card.card_clicked.connect(self._on_card_clicked)
                self.review_layout.addWidget(card)
                self.cards.append(card)
                
            # Highlight first card
            if self.cards:
                self.cards[0].set_highlighted(True)
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
