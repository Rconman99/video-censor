"""
Main Window for Video Censor Desktop App.

Provides the primary UI with drag-and-drop, preference manager, and processing queue.
"""

import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QComboBox, QCheckBox, QRadioButton, QButtonGroup, QPlainTextEdit,
    QScrollArea, QFileDialog, QListWidget, QListWidgetItem, QProgressBar,
    QSplitter, QSizePolicy, QGroupBox, QToolButton, QSpacerItem, QSlider, QLineEdit,
    QTabWidget, QStackedWidget, QTimeEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QMimeData, QTimer, QTime
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from .search_tab import SearchTab
from .review_panel import ReviewPanel
from video_censor.preferences import ContentFilterSettings, Profile
from video_censor.profile_manager import ProfileManager
from video_censor.queue import QueueItem, ProcessingQueue
from video_censor.config import Config
from video_censor.queue import QueueItem, ProcessingQueue


# Supported video formats
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm')
OUTPUT_DIR = "/Volumes/20tb/cleanmovies"


class DropZone(QFrame):
    """Drag-and-drop zone for video files - Cinema styled."""
    
    file_dropped = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("class", "drop-zone")
        self.setMinimumHeight(260)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 36, 28, 36)
        
        # Film reel icon - cinema themed
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("""
            font-size: 64px; 
            background: transparent;
        """)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        # Main text - movie poster style
        text_label = QLabel("Drop Your Film Here")
        text_label.setStyleSheet("""
            font-size: 20px; 
            font-weight: 800; 
            color: #f5f5f8;
            background: transparent;
            letter-spacing: -0.5px;
        """)
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)
        
        # Subtitle
        subtitle = QLabel("or browse your collection")
        subtitle.setStyleSheet("""
            font-size: 13px; 
            color: #5a5a6a; 
            background: transparent;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(12)
        
        # Supported formats - film strip style
        formats = QLabel("🎞  MP4 • MKV • AVI • MOV • WMV  🎞")
        formats.setStyleSheet("""
            font-size: 11px; 
            color: #5a5a6a; 
            background: #161620;
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid #282838;
        """)
        formats.setAlignment(Qt.AlignCenter)
        layout.addWidget(formats, alignment=Qt.AlignCenter)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #60a5fa;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #12121a, stop:1 #0e0e14);
                }
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(VIDEO_EXTENSIONS):
                self.file_dropped.emit(file_path)
                break


class PreferencePanel(QFrame):
    """Preference manager panel for configuring filters."""
    
    start_requested = Signal(str, ContentFilterSettings, str, object)  # path, settings, profile_name, scheduled_time
    
    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.current_video_path: Optional[str] = None
        self.setProperty("class", "panel")
        
        # Load global config
        try:
            config_path = Path(__file__).parent.parent / "config.yaml"
            self.config = Config.load(config_path)
        except Exception:
            self.config = Config()
        
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header with Title
        header = QHBoxLayout()
        header.setSpacing(12)
        
        title = QLabel("⚙️ Preferences")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f5f5f8; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Scroll Area for Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(24)
        self.content_layout.setContentsMargins(0, 0, 10, 0)
        
        # 1. Profile Section
        profile_layout = QHBoxLayout()
        profile_label = QLabel("Profile:")
        profile_label.setStyleSheet("font-weight: 600; color: #f5f5f8;")
        profile_layout.addWidget(profile_label)
        
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.addItems(self.profile_manager.list_names())
        self.profile_combo.currentTextChanged.connect(self._on_profile_change)
        profile_layout.addWidget(self.profile_combo)
        
        self.manage_btn = QPushButton("manage")
        self.manage_btn.setProperty("class", "link")
        profile_layout.addWidget(self.manage_btn)
        
        profile_layout.addStretch()
        self.content_layout.addLayout(profile_layout)
        
        # 2. Content Filters Section
        filters_label = QLabel("Content Filters")
        filters_label.setProperty("class", "pref-section-title")
        self.content_layout.addWidget(filters_label)
        
        filters_grid = QGridLayout()
        filters_grid.setSpacing(16)
        
        # Language
        self.cb_language = self._create_switch_card(
            "Language", "Mute profanity", "cb_language", True
        )
        filters_grid.addWidget(self.cb_language, 0, 0)
        
        # Sexual Content
        self.cb_sexual = self._create_switch_card(
            "Sexual Content", "Cut explicit scenes", "cb_sexual", True
        )
        filters_grid.addWidget(self.cb_sexual, 0, 1)
        
        # Nudity
        self.cb_nudity = self._create_switch_card(
            "Nudity", "Visual detection", "cb_nudity", True
        )
        filters_grid.addWidget(self.cb_nudity, 1, 0)
        
        # Mature Themes
        self.cb_mature = self._create_switch_card(
            "Mature Themes", "Drugs, self-harm", "cb_mature", False
        )
        filters_grid.addWidget(self.cb_mature, 1, 1)
        
        self.content_layout.addLayout(filters_grid)
        
        # 3. Filter Intensity Section
        intensity_label = QLabel("Filter Intensity")
        intensity_label.setProperty("class", "pref-section-title")
        self.content_layout.addWidget(intensity_label)
        
        self.romance_slider = self._create_intensity_slider(
            "Romance Level", "romance_slider", 
            ["Keep all", "Remove explicit", "Remove kissing"]
        )
        self.content_layout.addWidget(self.romance_slider)
        
        self.violence_slider = self._create_intensity_slider(
            "Violence Level", "violence_slider", 
            ["Keep all", "Graphic", "Fighting", "Max"]
        )
        self.content_layout.addWidget(self.violence_slider)
        
        # 4. Filter Actions Section
        actions_label = QLabel("Filter Actions")
        actions_label.setProperty("class", "pref-section-title")
        self.content_layout.addWidget(actions_label)
        
        actions_grid = QGridLayout()
        actions_grid.setSpacing(16)
        
        self.combo_profanity = self._create_action_card(
            "Profanity Action", "combo_profanity", ["Mute", "Beep"]
        )
        actions_grid.addWidget(self.combo_profanity, 0, 0)
        
        self.combo_nudity = self._create_action_card(
            "Nudity Action", "combo_nudity", ["Cut", "Blur", "Blackout"]
        )
        actions_grid.addWidget(self.combo_nudity, 0, 1)
        
        self.combo_sexual = self._create_action_card(
            "Sexual Content Action", "combo_sexual", ["Cut", "Blur", "Blackout"]
        )
        actions_grid.addWidget(self.combo_sexual, 1, 0)
        
        self.combo_violence = self._create_action_card(
            "Violence Action", "combo_violence", ["Cut", "Blur", "Blackout"]
        )
        actions_grid.addWidget(self.combo_violence, 1, 1)
        
        self.content_layout.addLayout(actions_grid)
        
        # 5. Additional Options
        options_label = QLabel("Additional Options")
        options_label.setProperty("class", "pref-section-title")
        self.content_layout.addWidget(options_label)
        
        options_grid = QGridLayout()
        options_grid.setSpacing(16)
        
        self.cb_censor_subs = self._create_switch_card("Censor Subtitle Profanity", "", "cb_censor_subs", True, horizontal=True)
        options_grid.addWidget(self.cb_censor_subs, 0, 0)
        
        self.cb_safe_cover = self._create_switch_card("Safe Cover Image", "", "cb_safe_cover", False, horizontal=True)
        options_grid.addWidget(self.cb_safe_cover, 0, 1)
        
        self.cb_force_eng = self._create_switch_card("Force English Subtitles", "", "cb_force_eng", False, horizontal=True)
        options_grid.addWidget(self.cb_force_eng, 1, 0)

        # Legacy items reserved in Additional Options
        self.cb_community = self._create_switch_card("Community Timestamps", "", "cb_community", True, horizontal=True)
        options_grid.addWidget(self.cb_community, 1, 1)
        
        # Whisper Model Selection (Advanced)
        whisper_widget = QFrame()
        whisper_widget.setProperty("class", "filter-card")
        w_layout = QHBoxLayout(whisper_widget)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_label = QLabel("Speech Model:")
        w_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #a0a0b0;")
        w_layout.addWidget(w_label)
        
        self.whisper_models = [
            ("Large-v3", "large-v3"),
            ("Medium", "medium"),
            ("Small", "small"),
            ("Base", "base"),
            ("Tiny", "tiny"),
        ]
        
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems([name for name, _ in self.whisper_models])
        w_layout.addWidget(self.whisper_combo)
        options_grid.addWidget(whisper_widget, 2, 0)
        
        # Performance Mode (Advanced)
        perf_widget = QFrame()
        perf_widget.setProperty("class", "filter-card")
        p_layout = QHBoxLayout(perf_widget)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_label = QLabel("Performance:")
        p_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #a0a0b0;")
        p_layout.addWidget(p_label)
        
        self.performance_combo = QComboBox()
        self.performance_combo.addItem("Balanced", "balanced")
        self.performance_combo.addItem("Performance", "performance")
        self.performance_combo.addItem("High Quality", "quality")
        p_layout.addWidget(self.performance_combo)
        options_grid.addWidget(perf_widget, 2, 1)

        self.content_layout.addLayout(options_grid)
        
        # Custom Phrases (Preserved functionality)
        phrases_widget = QFrame()
        phrases_widget.setProperty("class", "filter-card")
        ph_layout = QVBoxLayout(phrases_widget)
        ph_layout.setContentsMargins(12, 12, 12, 12)
        ph_layout.setSpacing(6)
        
        ph_header = QHBoxLayout()
        ph_title = QLabel("Custom Block Phrases")
        ph_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #a0a0b0;")
        ph_header.addWidget(ph_title)
        ph_hit = QLabel("(one per line)")
        ph_hit.setStyleSheet("font-size: 10px; color: #5a5a6a;")
        ph_header.addWidget(ph_hit)
        ph_header.addStretch()
        ph_layout.addLayout(ph_header)
        
        self.phrases_edit = QPlainTextEdit()
        self.phrases_edit.setPlaceholderText("e.g. stupid, shut up")
        self.phrases_edit.setMaximumHeight(60)
        self.phrases_edit.setStyleSheet("""
            QPlainTextEdit {
                background: #0f0f14;
                color: #e0e0e0;
                border: 1px solid #282838;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QPlainTextEdit:focus { border-color: #3b82f6; }
        """)
        ph_layout.addWidget(self.phrases_edit)
        self.content_layout.addWidget(phrases_widget)
        
        # Notifications (Preserved functionality)
        notify_widget = QFrame()
        notify_widget.setProperty("class", "filter-card")
        n_layout = QVBoxLayout(notify_widget)
        n_layout.setContentsMargins(12, 12, 12, 12)
        n_layout.setSpacing(8)
        
        n_header = QHBoxLayout()
        n_label = QLabel("Notifications")
        n_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #a0a0b0;")
        n_header.addWidget(n_label)
        n_header.addStretch()
        self.cb_notify_enabled = QCheckBox("Enable Push")
        self.cb_notify_enabled.setStyleSheet("color: #b0b0c0; font-size: 11px;")
        self.cb_notify_enabled.stateChanged.connect(self._save_settings)
        n_header.addWidget(self.cb_notify_enabled)
        n_layout.addLayout(n_header)
        
        # Topic Input
        topic_row = QHBoxLayout()
        self.notify_topic_input = QLineEdit()
        self.notify_topic_input.setPlaceholderText("Ntfy Topic ID")
        self.notify_topic_input.setStyleSheet("background: #0f0f14; border: 1px solid #282838; border-radius: 4px; padding: 4px; color: #e0e0e0; font-size: 11px;")
        self.notify_topic_input.editingFinished.connect(self._save_settings)
        topic_row.addWidget(self.notify_topic_input)
        
        test_btn = QPushButton("Test")
        test_btn.setFixedWidth(50)
        test_btn.setStyleSheet("background: #3b82f6; border: none; border-radius: 4px; padding: 4px; font-size: 10px; color: white;")
        test_btn.clicked.connect(self._test_notification)
        topic_row.addWidget(test_btn)
        n_layout.addLayout(topic_row)
        
        # Checkboxes
        opts_row = QHBoxLayout()
        self.cb_notify_complete = QCheckBox("Done")
        self.cb_notify_complete.setStyleSheet("color: #b0b0c0; font-size: 10px;")
        self.cb_notify_complete.stateChanged.connect(self._save_settings)
        opts_row.addWidget(self.cb_notify_complete)
        
        self.cb_notify_error = QCheckBox("Error")
        self.cb_notify_error.setStyleSheet("color: #b0b0c0; font-size: 10px;")
        self.cb_notify_error.stateChanged.connect(self._save_settings)
        opts_row.addWidget(self.cb_notify_error)
        
        self.cb_notify_batch = QCheckBox("Batch")
        self.cb_notify_batch.setStyleSheet("color: #b0b0c0; font-size: 10px;")
        self.cb_notify_batch.stateChanged.connect(self._save_settings)
        opts_row.addWidget(self.cb_notify_batch)
        
        n_layout.addLayout(opts_row)
        self.content_layout.addWidget(notify_widget)
        
        # Cloud Sync Section
        sync_widget = QFrame()
        sync_widget.setProperty("class", "filter-card")
        s_layout = QVBoxLayout(sync_widget)
        s_layout.setContentsMargins(12, 12, 12, 12)
        s_layout.setSpacing(8)
        
        s_header = QHBoxLayout()
        s_label = QLabel("Cloud Sync")
        s_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #a0a0b0;")
        s_header.addWidget(s_label)
        s_header.addStretch()
        self.cb_sync_enabled = QCheckBox("Enable Sync")
        self.cb_sync_enabled.setStyleSheet("color: #b0b0c0; font-size: 11px;")
        self.cb_sync_enabled.stateChanged.connect(self._save_settings)
        s_header.addWidget(self.cb_sync_enabled)
        s_layout.addLayout(s_header)
        
        # User ID
        uid_row = QHBoxLayout()
        self.sync_uid_input = QLineEdit()
        self.sync_uid_input.setPlaceholderText("User ID (UUID)")
        self.sync_uid_input.setStyleSheet("background: #0f0f14; border: 1px solid #282838; border-radius: 4px; padding: 4px; color: #e0e0e0; font-size: 11px;")
        self.sync_uid_input.editingFinished.connect(self._save_settings)
        uid_row.addWidget(self.sync_uid_input)
        
        gen_uid_btn = QPushButton("Generate")
        gen_uid_btn.setFixedWidth(60)
        gen_uid_btn.setStyleSheet("background: #282838; border: none; border-radius: 4px; padding: 4px; font-size: 10px; color: #b0b0c0;")
        gen_uid_btn.clicked.connect(self._generate_user_id)
        uid_row.addWidget(gen_uid_btn)
        s_layout.addLayout(uid_row)
        
        # Sync Now Button & Status
        sync_action_row = QHBoxLayout()
        self.sync_now_btn = QPushButton("Sync Now")
        self.sync_now_btn.setStyleSheet("background: #3b82f6; border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; color: white;")
        self.sync_now_btn.clicked.connect(self._sync_now)
        sync_action_row.addWidget(self.sync_now_btn)
        
        self.sync_status_label = QLabel("Offline")
        self.sync_status_label.setStyleSheet("color: #71717a; font-size: 10px; font-style: italic;")
        sync_action_row.addWidget(self.sync_status_label)
        sync_action_row.addStretch()
        
        s_layout.addLayout(sync_action_row)
        self.content_layout.addWidget(sync_widget)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Footer Section
        footer = QVBoxLayout()
        footer.setSpacing(12)
        
        # Start button
        self.start_btn = QPushButton("▶  Start Filtering")
        self.start_btn.setProperty("class", "primary")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(48)
        self.start_btn.clicked.connect(self._on_start)
        footer.addWidget(self.start_btn)
        
        # Schedule
        schedule_layout = QHBoxLayout()
        self.schedule_cb = QCheckBox("Schedule Start:")
        self.schedule_cb.setStyleSheet("color: #b0b0c0; font-size: 11px;")
        self.schedule_cb.toggled.connect(self._toggle_schedule)
        schedule_layout.addWidget(self.schedule_cb)
        
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("h:mm AP")
        self.time_edit.setTime(QTime.currentTime().addSecs(3600))
        self.time_edit.setEnabled(False)
        self.time_edit.setStyleSheet("""
            QTimeEdit {
                background: #1f1f2e;
                color: #e0e0e0;
                border: 1px solid #383850;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QTimeEdit:disabled { color: #555; border-color: #2a2a35; }
        """)
        schedule_layout.addWidget(self.time_edit)
        schedule_layout.addStretch()
        footer.addLayout(schedule_layout)
        
        layout.addLayout(footer)
        
        # Initialize
        self._init_quality_from_config()
        self._apply_profile_settings()

    def _create_switch_card(self, title, subtitle, object_name, checked=False, horizontal=False):
        """Create a card with title, subtitle and switch."""
        card = QFrame()
        card.setProperty("class", "filter-card")
        
        if horizontal:
            layout = QHBoxLayout(card)
            layout.setContentsMargins(0, 0, 0, 0)
            
            label = QLabel(title)
            label.setStyleSheet("font-weight: 600; font-size: 12px;")
            layout.addWidget(label)
            
            layout.addStretch()
            
            switch = QCheckBox()
            switch.setObjectName(object_name)
            switch.setProperty("class", "switch")
            switch.setChecked(checked)
            layout.addWidget(switch)
            
            # Store reference
            setattr(self, object_name, switch)
        else:
            layout = QHBoxLayout(card)
            layout.setContentsMargins(0, 0, 0, 0)
            
            text_layout = QVBoxLayout()
            text_layout.setSpacing(4)
            
            t_label = QLabel(title)
            t_label.setStyleSheet("font-weight: 600; font-size: 12px;")
            text_layout.addWidget(t_label)
            
            if subtitle:
                s_label = QLabel(subtitle)
                s_label.setStyleSheet("color: #71717a; font-size: 10px;")
                text_layout.addWidget(s_label)
            
            layout.addLayout(text_layout)
            layout.addStretch()
            
            switch = QCheckBox()
            switch.setObjectName(object_name)
            switch.setProperty("class", "switch")
            switch.setChecked(checked)
            layout.addWidget(switch)
            
            # Store reference
            setattr(self, object_name, switch)
            
        return card

    def _create_intensity_slider(self, title, object_name, steps):
        """Create a slider card with labels."""
        card = QFrame()
        card.setProperty("class", "filter-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        t_label = QLabel(title)
        t_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        header.addWidget(t_label)
        header.addStretch()
        
        status_label = QLabel(steps[-1])
        status_label.setStyleSheet("color: #3b82f6; font-size: 10px; font-weight: 600;")
        header.addWidget(status_label)
        layout.addLayout(header)
        
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(len(steps) - 1)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(1)
        slider.setValue(len(steps) - 1)
        layout.addWidget(slider)
        
        # Labels row
        labels_layout = QHBoxLayout()
        labels_layout.setContentsMargins(4, 0, 4, 0)
        for i, step in enumerate(steps):
            lbl = QLabel(step)
            lbl.setStyleSheet("color: #71717a; font-size: 9px;")
            if i == 0:
                lbl.setAlignment(Qt.AlignLeft)
            elif i == len(steps) - 1:
                lbl.setAlignment(Qt.AlignRight)
            else:
                lbl.setAlignment(Qt.AlignCenter)
            labels_layout.addWidget(lbl)
            if i < len(steps) - 1:
                labels_layout.addStretch()
                
        layout.addLayout(labels_layout)
        
        # Update status label on change
        def update_status(val):
            status_label.setText(steps[val])
            
        slider.valueChanged.connect(update_status)
        update_status(slider.value())
        
        setattr(self, object_name, slider)
        return card

    def _create_action_card(self, title, object_name, options):
        """Create a card for filter actions."""
        card = QFrame()
        card.setProperty("class", "filter-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        t_label = QLabel(title)
        t_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #a0a0b0;")
        layout.addWidget(t_label)
        
        combo = QComboBox()
        combo.addItems(options)
        layout.addWidget(combo)
        
        setattr(self, object_name, combo)
        return card

    def _toggle_schedule(self, checked):
        self.time_edit.setEnabled(checked)
        if checked:
            self.start_btn.setText("⏰  Schedule Job")
            self.time_edit.setFocus()
            self.time_edit.setSelectedSection(QTimeEdit.Section.HourSection)
        else:
            self.start_btn.setText("▶  Start Filtering")
    
    def set_video(self, path: str):
        """Set the current video file."""
        self.current_video_path = path
        self.start_btn.setEnabled(True)
    
    def _on_profile_change(self, name: str):
        self._apply_profile_settings()
    
    def _apply_profile_settings(self):
        profile_name = self.profile_combo.currentText()
        profile = self.profile_manager.get_or_default(profile_name)
        settings = profile.settings
        
        self.cb_language.findChild(QCheckBox).setChecked(settings.filter_language)
        self.cb_sexual.findChild(QCheckBox).setChecked(settings.filter_sexual_content)
        self.cb_nudity.findChild(QCheckBox).setChecked(settings.filter_nudity)
        self.cb_mature.findChild(QCheckBox).setChecked(settings.filter_mature_themes)
        
        # Map levels to slider values
        # Assuming backend stores level 0-N
        self.romance_slider.findChild(QSlider).setValue(settings.filter_romance_level)
        self.violence_slider.findChild(QSlider).setValue(settings.filter_violence_level)
        
        # Safe Cover
        self.cb_safe_cover.findChild(QCheckBox).setChecked(settings.safe_cover_enabled)
        
        # Custom Phrases
        self.phrases_edit.setPlainText("\n".join(settings.custom_block_phrases))
    
    def get_current_settings(self) -> ContentFilterSettings:
        """Get the current filter settings from controls."""
        phrases = [p.strip() for p in self.phrases_edit.toPlainText().split("\n") if p.strip()]
        
        return ContentFilterSettings(
            filter_language=self.cb_language.findChild(QCheckBox).isChecked(),
            filter_sexual_content=self.cb_sexual.findChild(QCheckBox).isChecked(),
            filter_nudity=self.cb_nudity.findChild(QCheckBox).isChecked(),
            filter_romance_level=self.romance_slider.findChild(QSlider).value(),
            filter_violence_level=self.violence_slider.findChild(QSlider).value(),
            filter_mature_themes=self.cb_mature.findChild(QCheckBox).isChecked(),
            custom_block_phrases=phrases,
            safe_cover_enabled=self.cb_safe_cover.findChild(QCheckBox).isChecked()
        )
    
    def _save_defaults(self):
        profile_name = self.profile_combo.currentText()
        profile = self.profile_manager.get(profile_name)
        if profile:
            profile.settings = self.get_current_settings()
            self.profile_manager.update(profile_name, profile)
    
    def _on_start(self):
        if self.current_video_path:
            self.save_quality_to_config()
            
            scheduled_time = None
            if self.schedule_cb.isChecked():
                from datetime import datetime, timedelta
                qtime = self.time_edit.time()
                now = datetime.now()
                scheduled_time = now.replace(hour=qtime.hour(), minute=qtime.minute(), second=0, microsecond=0)
                if scheduled_time < now:
                    scheduled_time += timedelta(days=1)
            
            settings = self.get_current_settings()
            self.start_requested.emit(
                self.current_video_path,
                settings,
                self.profile_combo.currentText(),
                scheduled_time
            )
            self.current_video_path = None
            self.start_btn.setEnabled(False)
            self.schedule_cb.setChecked(False)
            
    def refresh_profiles(self):
        current = self.profile_combo.currentText()
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.list_names())
        idx = self.profile_combo.findText(current)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
            
    def _init_quality_from_config(self):
        # Set whisper model
        whisper_model = getattr(self.config.whisper, 'model_size', 'large-v3')
        for i, (display_name, key) in enumerate(self.whisper_models):
            if key == whisper_model:
                self.whisper_combo.setCurrentIndex(i)
                break
        
        # Set notifications
        self.cb_notify_enabled.setChecked(self.config.notifications.enabled)
        self.notify_topic_input.setText(self.config.notifications.ntfy_topic)
        self.cb_notify_complete.setChecked(getattr(self.config.notifications, 'notify_on_complete', True))
        self.cb_notify_error.setChecked(getattr(self.config.notifications, 'notify_on_error', True))
        self.cb_notify_batch.setChecked(getattr(self.config.notifications, 'notify_on_batch_done', True))
        
        # Set performance mode
        perf_mode = getattr(self.config.system, 'performance_mode', 'balanced')
        index = self.performance_combo.findData(perf_mode)
        if index >= 0:
            self.performance_combo.setCurrentIndex(index)

        # Set sync settings
        self.cb_sync_enabled.setChecked(self.config.sync.enabled)
        self.sync_uid_input.setText(self.config.sync.user_id)
        if self.config.sync.enabled:
            self.sync_status_label.setText("Enabled") # Or check last sync time?
        else:
            self.sync_status_label.setText("Disabled")        
        
    def _save_settings(self):
        """Save notification and other settings when changed."""
        # Save notifications
        self.config.notifications.enabled = self.cb_notify_enabled.isChecked()
        self.config.notifications.ntfy_topic = self.notify_topic_input.text().strip()
        self.config.notifications.notify_on_complete = self.cb_notify_complete.isChecked()
        self.config.notifications.notify_on_error = self.cb_notify_error.isChecked()
        self.config.notifications.notify_on_batch_done = self.cb_notify_batch.isChecked()
        
        # Save performance mode
        self.config.system.performance_mode = self.performance_combo.currentData()
        
        # Save sync settings
        self.config.sync.enabled = self.cb_sync_enabled.isChecked()
        self.config.sync.user_id = self.sync_uid_input.text().strip()
        
        try:
            config_path = Path(__file__).parent.parent / "config.yaml"
            self.config.save(config_path)
            
            # Update UI status
            if self.config.sync.enabled:
                self.sync_status_label.setText("Enabled (Auto-sync on start/exit)")
            else:
                self.sync_status_label.setText("Disabled")
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def save_quality_to_config(self):
        """Save current quality settings to self.config and disk."""
        # Save whisper model
        whisper_idx = self.whisper_combo.currentIndex()
        if 0 <= whisper_idx < len(self.whisper_models):
            _, model_key = self.whisper_models[whisper_idx]
            self.config.whisper.model_size = model_key
            
        # Save notifications
        self.config.notifications.enabled = self.cb_notify_enabled.isChecked()
        self.config.notifications.ntfy_topic = self.notify_topic_input.text().strip()
        self.config.notifications.notify_on_complete = self.cb_notify_complete.isChecked()
        self.config.notifications.notify_on_error = self.cb_notify_error.isChecked()
        self.config.notifications.notify_on_batch_done = self.cb_notify_batch.isChecked()
        
        # Save performance mode
        self.config.system.performance_mode = self.performance_combo.currentData()

        # Save sync settings
        self.config.sync.enabled = self.cb_sync_enabled.isChecked()
        self.config.sync.user_id = self.sync_uid_input.text().strip()
        
        try:
            config_path = Path(__file__).parent.parent / "config.yaml"
            self.config.save(config_path)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def _test_notification(self):
        """Send a test notification to verify setup."""
        topic = self.notify_topic_input.text().strip()
        if not topic:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Topic", "Please enter a topic ID first!")
            return
        
        try:
            import requests
            url = f"https://ntfy.sh/{topic}"
            response = requests.post(
                url,
                data="🎬 Test notification from Video Censor! If you see this, notifications are working.",
                headers={
                    "Title": "✅ Test Successful!",
                    "Tags": "white_check_mark,movie_camera"
                },
                timeout=5
            )
            
            if response.status_code == 200:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Test notification sent! Check your phone.")
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Server returned status {response.status_code}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to send: {str(e)}")
    
    def _open_community_dialog(self):
        """Open the community timestamps browser dialog."""
        from video_censor.community_dialog import CommunityDialog
        
        dialog = CommunityDialog(self)
        dialog.timestamps_selected.connect(self._on_community_timestamps_selected)
        dialog.exec()
    
    def _on_community_timestamps_selected(self, detection_data: dict):
        """Handle selection of community timestamps."""
        # Store the selected community data for use during processing
        self._community_detection = detection_data
        
        from PySide6.QtWidgets import QMessageBox
        title = detection_data.get('title', 'Unknown')
        nudity = len(detection_data.get('nudity_segments', []))
        profanity = len(detection_data.get('profanity_segments', []))
        sexual = len(detection_data.get('sexual_content_segments', []))
        
        QMessageBox.information(
            self,
            "Timestamps Loaded",
            f"Loaded community timestamps for '{title}':\n\n"
            f"• {profanity} profanity segments\n"
            f"• {nudity} nudity segments\n"
            f"• {sexual} sexual content segments\n\n"
            "These will be applied when processing starts."
        )

    def _generate_user_id(self):
        """Generate a random UUID for sync."""
        import uuid
        uid = str(uuid.uuid4())
        self.sync_uid_input.setText(uid)
        self._save_settings()

    def _sync_now(self):
        """Perform manual sync."""
        if not self.config.sync.enabled:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Sync Disabled", "Please enable sync first.")
            return

        if not self.config.sync.user_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Missing User ID", "Please generate or enter a User ID.")
            return

        self.sync_now_btn.setEnabled(False)
        self.sync_status_label.setText("Syncing...")
        
        # Run in thread
        threading.Thread(target=self._run_sync_thread, daemon=True).start()

    def _run_sync_thread(self):
        """Worker thread for sync."""
        try:
            # We need to update config object first since it's passed around
            # Actually self.config is already updated by _save_settings signals
            
            from video_censor.profanity.wordlist import sync_custom_wordlist
            from video_censor.presets import sync_presets
            
            # 1. Sync Wordlist
            w_success = sync_custom_wordlist(self.config)
            
            # 2. Sync Presets
            p_success = sync_presets(self.config)
            
            # Update UI on main thread
            # Since we are in a QFrame not QMainWindow, we should be careful.
            # But simple text updates might work or use signals.
            # Safest is to use QTimer.singleShot(0, lambda: ...)
            
            status_msg = "Synced just now" if (w_success and p_success) else "Sync Failed"
            
            QTimer.singleShot(0, lambda: self._on_sync_complete(status_msg))
            
        except Exception as e:
            print(f"Sync error: {e}")
            QTimer.singleShot(0, lambda: self._on_sync_complete(f"Error: {str(e)[:20]}"))

    def _on_sync_complete(self, message):
        """Handle sync completion on main thread."""
        self.sync_now_btn.setEnabled(True)
        self.sync_status_label.setText(message)



class QueueItemWidget(QFrame):
    """Widget representing a single queue item."""
    
    def __init__(self, item: QueueItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setStyleSheet("background: #0f0f14; border-radius: 6px; padding: 8px;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Filename (elided)
        name_label = QLabel(item.filename)
        name_label.setStyleSheet("font-weight: bold; background: transparent; font-size: 12px;")
        name_label.setWordWrap(False)
        name_label.setMaximumWidth(280)
        # Use QLabel's elide capability via style
        layout.addWidget(name_label)
        
        # Profile and tags row
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)
        
        profile_tag = QLabel(item.profile_name)
        profile_tag.setStyleSheet("background: #1e1e28; color: #71717a; padding: 2px 6px; border-radius: 4px; font-size: 10px;")
        tags_layout.addWidget(profile_tag)
        
        # Filter tags
        summary = item.filters.short_summary()
        if summary and summary != "None":
            for tag in summary.split()[:3]:  # Limit tags
                tag_label = QLabel(tag)
                tag_label.setStyleSheet("background: #252530; color: #a0a0aa; padding: 2px 6px; border-radius: 4px; font-size: 10px;")
                tags_layout.addWidget(tag_label)
        
        tags_layout.addStretch()
        layout.addLayout(tags_layout)
        
        # Status
        self.status_label = QLabel(item.status_display())
        self.status_label.setStyleSheet(f"color: {self._status_color()}; font-size: 11px; background: transparent;")
        layout.addWidget(self.status_label)
        
        # Review Button (only shown if ready)
        self.review_btn = QPushButton("Review Edits")
        self.review_btn.setStyleSheet("""
            QPushButton {
                background: #eab308;
                color: #000;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #facc15;
            }
        """)
        self.review_btn.clicked.connect(self._on_review_clicked)
        self.review_btn.setVisible(item.is_review_ready)
        layout.addWidget(self.review_btn)
        
        # Progress row (bar + cancel button)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(int(item.progress * 100))
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(6)
        progress_row.addWidget(self.progress_bar, 1)  # Stretch to fill
        
        # Cancel Button (compact)
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setToolTip("Cancel Processing")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #2e1f1f;
                color: #ff5555;
                border: 1px solid #382828;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #382828;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.setVisible(item.is_processing)
        progress_row.addWidget(self.cancel_btn)
        
        # Delete Button (always visible for non-processing items)
        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setToolTip("Remove from Queue")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #71717a;
                border: 1px solid #282838;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3a2424;
                color: #ff6666;
                border-color: #483030;
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setVisible(not item.is_processing)
        progress_row.addWidget(self.delete_btn)
        
        layout.addLayout(progress_row)
        
    def _on_review_clicked(self):
        # Find main window to call method
        window = self.window()
        if hasattr(window, '_start_review'):
            window._start_review(self.item.id)
            
    def _on_cancel_clicked(self):
        window = self.window()
        if hasattr(window, '_cancel_current_job'):
            window._cancel_current_job(self.item.id)
    
    def _on_delete_clicked(self):
        """Delete this item from the queue."""
        window = self.window()
        if hasattr(window, '_delete_queue_item'):
            window._delete_queue_item(self.item.id)
    
    def _status_color(self) -> str:
        colors = {
            'pending': "#71717a",
            'processing': "#3b82f6",
            'complete': "#22c55e",
            'error': "#ef4444",
            'cancelled': "#71717a"
        }
        return colors.get(self.item.status, "#71717a")
    
    def update_display(self):
        self.status_label.setText(self.item.status_display())
        self.status_label.setStyleSheet(f"color: {self._status_color()}; font-size: 11px; background: transparent;")
        self.progress_bar.setValue(int(self.item.progress * 100))
        
        if hasattr(self, 'review_btn'):
            self.review_btn.setVisible(self.item.is_review_ready)
            
        if hasattr(self, 'cancel_btn'):
            self.cancel_btn.setVisible(self.item.is_processing)
        
        if hasattr(self, 'delete_btn'):
            # Show delete for anything not actively processing
            self.delete_btn.setVisible(not self.item.is_processing)


class QueuePanel(QFrame):
    """Queue panel showing processing jobs."""
    
    def __init__(self, queue: ProcessingQueue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self.setProperty("class", "panel")
        self._item_widgets = {}
        self.paused = False
        
        self._create_ui()
    
    def _toggle_pause(self):
        """Toggle pause state."""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.setText("▶")
            self.pause_btn.setToolTip("Resume Processing")
            self.pause_btn.setStyleSheet("background: #2e1f1f; border-radius: 4px; border: 1px solid #382828; color: #ff5555;")
        else:
            self.pause_btn.setText("⏸")
            self.pause_btn.setToolTip("Pause Processing")
            self.pause_btn.setStyleSheet("background: #1f1f2e; border-radius: 4px; border: 1px solid #282838;")
        
        # Trigger processing update in main window if resuming
        if not self.paused:
            parent = self.window()
            if hasattr(parent, '_process_next') and not parent.processing:
                parent._process_next()
    
    def _on_sleep_changed(self, checked):
        """Update sleep setting."""
        self.queue.sleep_when_done = checked
        # Icon-only button, tooltip shows state
        self.sleep_btn.setToolTip(f"Auto-Sleep: {'ON - Computer will sleep when done' if checked else 'OFF'}")
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header - compact single row
        header = QHBoxLayout()
        header.setSpacing(8)
        
        title = QLabel("Processing")
        title.setProperty("class", "section-header")
        title.setStyleSheet("font-size: 14px; font-weight: bold; background: transparent;")
        header.addWidget(title)
        
        self.count_label = QLabel("0/0 complete")
        self.count_label.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        header.addWidget(self.count_label)
        
        header.addStretch()
        
        # Pause button
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setToolTip("Pause Processing")
        self.pause_btn.setFixedSize(32, 28)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #a0a0aa;
                border-radius: 4px;
                border: 1px solid #282838;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #282838;
            }
        """)
        self.pause_btn.clicked.connect(self._toggle_pause)
        header.addWidget(self.pause_btn)
        
        # Sleep Toggle Button - compact
        self.sleep_btn = QPushButton("🌙")
        self.sleep_btn.setCheckable(True)
        self.sleep_btn.setToolTip("Auto-Sleep: Put computer to sleep when queue completes")
        self.sleep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sleep_btn.setFixedSize(32, 28)
        self.sleep_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #71717a;
                border: 1px solid #282838;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:checked {
                background: #4c1d95;
                color: #ffffff;
                border: 1px solid #5b21b6;
            }
            QPushButton:hover {
                border-color: #3f3f46;
            }
        """)
        self.sleep_btn.toggled.connect(self._on_sleep_changed)
        header.addWidget(self.sleep_btn)
        
        layout.addLayout(header)
        
        # Scroll area for items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout(self.items_widget)
        self.items_layout.setSpacing(8)
        self.items_layout.addStretch()
        
        scroll.setWidget(self.items_widget)
        layout.addWidget(scroll, 1)
        
        # Empty state
        self.empty_label = QLabel("🎬\n\nYour queue is empty\nAdd videos to get started")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #71717a; font-size: 12px; background: transparent;")
        self.items_layout.insertWidget(0, self.empty_label)
    
    def refresh(self):
        """Refresh the queue display."""
        # Clear existing widgets
        for widget in self._item_widgets.values():
            widget.deleteLater()
        self._item_widgets.clear()
        
        items = self.queue.items
        
        self.empty_label.setVisible(len(items) == 0)
        
        if items:
            complete = self.queue.complete_count
            total = len(items)
            self.count_label.setText(f"{complete}/{total} complete")
        else:
            self.count_label.setText("No videos in queue")
        
        for item in items:
            widget = QueueItemWidget(item)
            self._item_widgets[item.id] = widget
            self.items_layout.insertWidget(self.items_layout.count() - 1, widget)
    
    def update_item(self, item_id: str):
        """Update a specific item."""
        if item_id in self._item_widgets:
            self._item_widgets[item_id].update_display()


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals for thread-safe updates
    progress_update = Signal(str, float, str)  # id, progress, status
    item_complete = Signal(str)  # id
    item_failed = Signal(str, str)  # id, error
    item_review_ready = Signal(str)  # id
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Censor")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)
        
        # Force dark background on window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #06060a;
            }
        """)
        
        # Initialize managers
        self.profile_manager = ProfileManager()
        self.processing_queue = ProcessingQueue()
        
        # Processing state
        self.processing = False
        self.current_item: Optional[QueueItem] = None
        self.current_process = None # Handle to running subprocess
        
        # Connect signals
        self.progress_update.connect(self.on_progress_update)
        self.item_complete.connect(self.on_item_complete)
        self.item_failed.connect(self.on_item_failed)
        self.item_review_ready.connect(self.on_item_review_ready)
        
        self._create_ui()
        
        # Connect queue callback for batch notifications
        self.processing_queue.on_complete_callback = self._on_queue_complete
        
        # Restore any saved queue state (crash recovery)
        restored = self.processing_queue.load_state()
        if restored > 0:
            self.queue_panel.refresh()
            print(f"Restored {restored} pending item(s) from previous session")
            # Auto-start processing restored items
            if not self.processing:
                QTimer.singleShot(1000, self._process_next)
        
        # Scheduler timer (check every minute)
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self._check_scheduled_items)
        self.scheduler_timer.start(60000) # 1 minute
        
        # Check disk space on startup
        self._check_disk_space()
    
    def _create_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: #06060a;")
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 24, 28, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(16)
        
        # Cinema title section
        title_section = QVBoxLayout()
        title_section.setSpacing(6)
        
        # Title with film icon
        title = QLabel("🎬  Video Censor")
        title.setStyleSheet("""
            font-size: 36px; 
            font-weight: 800; 
            color: #ffffff;
            background: transparent;
            letter-spacing: -1px;
        """)
        title_section.addWidget(title)
        
        subtitle = QLabel("FAMILY-SAFE SCREENING  •  FULLY LOCAL  •  PRIVATE")
        subtitle.setStyleSheet("""
            font-size: 11px; 
            color: #5a5a6a; 
            background: transparent;
            letter-spacing: 2px;
        """)
        title_section.addWidget(subtitle)
        
        header.addLayout(title_section)
        header.addStretch()
        
        # Feedback button
        self.feedback_btn = QPushButton("📝 Feedback")
        self.feedback_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2a;
                color: #a0a0aa;
                padding: 10px 16px;
                border-radius: 8px;
                font-size: 12px;
                border: 1px solid #282838;
            }
            QPushButton:hover {
                background: #282838;
                color: #f5f5f8;
            }
        """)
        self.feedback_btn.clicked.connect(self._show_feedback_dialog)
        header.addWidget(self.feedback_btn)
        
        # Status badge - movie screening style
        self.status_label = QLabel("🎞  Ready to Screen")
        self.status_label.setProperty("class", "status-idle")
        self.status_label.setStyleSheet("""
            background: #161620; 
            color: #5a5a6a; 
            padding: 10px 18px; 
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid #282838;
        """)
        header.addWidget(self.status_label)
        
        main_layout.addLayout(header)
        
        # Separator - film strip style
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0a0a0e, stop:0.3 #383850, stop:0.5 #6366f1, stop:0.7 #383850, stop:1 #0a0a0e);")
        main_layout.addWidget(sep)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #282838;
                border-radius: 8px;
                background: #0f0f14;
            }
            QTabBar::tab {
                background: #161620;
                color: #71717a;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #3b82f6;
                color: white;
            }
        """)
        main_layout.addWidget(self.tabs, 1)

        # Tab 1: Processing
        self.process_tab = QWidget()
        self.tabs.addTab(self.process_tab, "🎞  Process Video")
        
        content = QHBoxLayout(self.process_tab)
        content.setContentsMargins(20, 20, 20, 20)
        content.setSpacing(24)
        
        # Stack for Setup vs Review
        self.stack = QStackedWidget()
        
        # Page 0: Setup (Left + Center)
        setup_page = QWidget()
        setup_layout = QHBoxLayout(setup_page)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(24)
        
        # Left: Drop zone
        left_panel = QVBoxLayout()
        left_panel.setSpacing(14)
        
        drop_title = QLabel("📽  Select Film")
        drop_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f5f5f8; background: transparent;")
        left_panel.addWidget(drop_title)
        
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._on_file_dropped)
        left_panel.addWidget(self.drop_zone)
        
        self.choose_btn = QPushButton("📂  Browse Collection")
        self.choose_btn.setProperty("class", "secondary")
        self.choose_btn.setMinimumHeight(48)
        self.choose_btn.clicked.connect(self._browse_files)
        left_panel.addWidget(self.choose_btn)
        
        # Separator
        left_sep = QFrame()
        left_sep.setFixedHeight(1)
        left_sep.setStyleSheet("background: #2a2a35; margin-top: 10px; margin-bottom: 10px;")
        left_panel.addWidget(left_sep)
        
        # Output Options Section
        options_title = QLabel("⚙️  Output Options")
        options_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f5f8; background: transparent;")
        left_panel.addWidget(options_title)
        
        # Quality Preset
        quality_row = QHBoxLayout()
        quality_label = QLabel("Quality:")
        quality_label.setStyleSheet("color: #b0b0c0; font-size: 12px; background: transparent;")
        quality_label.setFixedWidth(55)
        quality_row.addWidget(quality_label)
        
        self.quality_preset_combo = QComboBox()
        self.quality_preset_combo.setMinimumWidth(180)
        
        # Quality presets
        self.quality_presets = [
            ("Original Quality", "original"),
            ("Auto Convert", "auto"),
            ("4K UHD (High) 40 Mbps", "4k_high"),
            ("4K UHD (Med) 24 Mbps", "4k_med"),
            ("4K UHD 18 Mbps", "4k_low"),
            ("1080p HD (High) 20 Mbps", "1080p_high"),
            ("1080p HD (Med) 12 Mbps", "1080p_med"),
            ("1080p HD 10 Mbps", "1080p_10"),
            ("1080p HD 8 Mbps", "1080p_low"),
            ("720p HD (High) 4 Mbps", "720p_high"),
            ("720p HD (Med) 3 Mbps", "720p_med"),
            ("720p HD 2 Mbps", "720p_low"),
            ("480p 1.5 Mbps", "480p"),
            ("328p 0.7 Mbps", "328p"),
            ("240p 0.3 Mbps", "240p"),
            ("160p 0.2 Mbps", "160p"),
        ]
        
        for display_name, _ in self.quality_presets:
            self.quality_preset_combo.addItem(display_name)
        
        quality_row.addWidget(self.quality_preset_combo)
        left_panel.addLayout(quality_row)
        
        # Output Format
        format_row = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setStyleSheet("color: #b0b0c0; font-size: 12px; background: transparent;")
        format_label.setFixedWidth(55)
        format_row.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "avi", "mov"])
        self.format_combo.setFixedWidth(80)
        format_row.addWidget(self.format_combo)
        format_row.addStretch()
        left_panel.addLayout(format_row)
        
        left_panel.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(300)
        setup_layout.addWidget(left_widget)
        
        # Center: Preference panel
        self.preference_panel = PreferencePanel(self.profile_manager)
        self.preference_panel.start_requested.connect(self._on_start_filtering)
        self.preference_panel.manage_btn.clicked.connect(self._open_profile_manager)
        setup_layout.addWidget(self.preference_panel, 1) # Give it stretch
        
        self.stack.addWidget(setup_page)
        
        # Page 1: Review Panel
        self.review_panel = ReviewPanel()
        self.review_panel.export_requested.connect(self._on_export_confirmed)
        self.review_panel.cancel_requested.connect(self._on_review_cancelled)
        self.review_panel.editor_requested.connect(self._on_editor_requested)
        self.stack.addWidget(self.review_panel)
        
        # Page 2: Editor Panel
        from .editor_panel import EditorPanel
        self.editor_panel = EditorPanel()
        self.editor_panel.export_requested.connect(self._on_editor_export)
        self.editor_panel.close_requested.connect(self._on_editor_closed)
        self.stack.addWidget(self.editor_panel)
        
        content.addWidget(self.stack, 1)
        
        # Right: Queue panel
        self.queue_panel = QueuePanel(self.processing_queue)
        self.queue_panel.setFixedWidth(320)
        content.addWidget(self.queue_panel)
        
        # Tab 2: Search
        self.search_tab = SearchTab()
        self.tabs.addTab(self.search_tab, "🔍  Is It Safe? (Beta Search)")
        
        # Footer
        footer = QHBoxLayout()
        
        output_label = QLabel(f"Output folder: {OUTPUT_DIR}")
        output_label.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        footer.addWidget(output_label)
        
        footer.addStretch()
        
        main_layout.addLayout(footer)
        
        # Load saved output settings
        self._load_output_settings()
        
        # Trigger auto-sync shortly after startup
        QTimer.singleShot(2000, self._auto_sync)
    
    def _load_output_settings(self):
        """Load quality and format settings from config."""
        try:
            config = self.preference_panel.config
            
            # Load quality preset
            preset_key = getattr(config.output, 'quality_preset', 'original')
            for i, (_, key) in enumerate(self.quality_presets):
                if key == preset_key:
                    self.quality_preset_combo.setCurrentIndex(i)
                    break
            
            # Load format
            self.format_combo.setCurrentText(config.output.video_format)
        except Exception as e:
            print(f"Failed to load output settings: {e}")
    
    def _save_output_settings(self):
        """Save quality and format settings to config."""
        try:
            config = self.preference_panel.config
            
            # Save quality preset
            idx = self.quality_preset_combo.currentIndex()
            if 0 <= idx < len(self.quality_presets):
                _, preset_key = self.quality_presets[idx]
                config.output.quality_preset = preset_key
            
            # Save format
            config.output.video_format = self.format_combo.currentText()
            
            # Persist to disk
            config_path = Path(__file__).parent.parent / "config.yaml"
            config.save(config_path)
        except Exception as e:
            print(f"Failed to save output settings: {e}")
    
    def _check_disk_space(self):
        """Check if output drive has sufficient free space."""
        import shutil
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            usage = shutil.disk_usage(OUTPUT_DIR)
            free_gb = usage.free / (1024 ** 3)
            
            if free_gb < 50:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Low Disk Space",
                    f"Warning: Only {free_gb:.1f} GB free on output drive.\n\n"
                    f"For overnight batch processing, consider freeing up space or using a different output location."
                )
        except Exception as e:
            print(f"Failed to check disk space: {e}")
    
    def _browse_files(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.m4v *.wmv);;All Files (*)"
        )
        if file_path:
            self._on_file_dropped(file_path)
    
    def _on_file_dropped(self, path: str):
        self.preference_panel.set_video(path)
    
    def _show_feedback_dialog(self):
        """Show the feedback dialog for rating processed videos."""
        try:
            from video_censor.feedback_dialog import FeedbackDialog
            dialog = FeedbackDialog(self)
            dialog.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Could not open feedback dialog: {e}")
    
    def _on_start_filtering(self, video_path: str, settings: ContentFilterSettings, profile_name: str, scheduled_time=None):
        # Save quality settings to config before processing
        self._save_output_settings()
        
        # Create output path
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        video_path_obj = Path(video_path)
        
        # Get selected output format from MainWindow's dropdown
        output_format = self.format_combo.currentText()
        output_path = Path(OUTPUT_DIR) / f"{video_path_obj.stem}.CENSORED.{output_format}"
        
        status = "scheduled" if scheduled_time else "pending"
        
        # Check for existing analysis to resume
        analysis_file = output_path.with_suffix('.analysis.json')
        existing_analysis = analysis_file if analysis_file.exists() else None
        
        # Create queue item
        # Subtitle detection
        sub_path = None
        # Check for .srt or .en.srt
        potential_subs = [
            video_path_obj.with_suffix('.srt'),
            video_path_obj.with_suffix('.en.srt')
        ]
        for p in potential_subs:
            if p.exists():
                sub_path = p
                print(f"Found subtitle file: {sub_path}")
                break
        
        item = QueueItem(
            input_path=video_path_obj,
            output_path=output_path,
            filters=settings,
            profile_name=profile_name,
            scheduled_time=scheduled_time,
            status=status,
            analysis_path=existing_analysis # Auto-resume analysis if exists
        )
        # Manually attach subtitle path (dynamically added attribute)
        if sub_path:
            item.subtitles_path = sub_path
        
        # Add to queue
        self.processing_queue.add(item)
        self.queue_panel.refresh()
        
        # Save queue state for crash recovery
        self.processing_queue.save_state()
        
        # Start processing if not scheduled and not already busy
        if not scheduled_time:
            if not self.processing:
                self._process_next()
        else:
            # Confirm schedule
            from PySide6.QtWidgets import QMessageBox
            time_str = scheduled_time.strftime('%I:%M %p')
            QMessageBox.information(self, "Job Scheduled", f"Video has been scheduled for {time_str}")
    
    def _process_next(self):
        # Check if processing is paused
        if hasattr(self, 'queue_panel') and self.queue_panel.paused:
            self.processing = False
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("""
                background: #2e1f1f; 
                color: #ff5555; 
                padding: 10px 18px; 
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #382828;
            """)
            return
            
        # Find next ready item (not scheduled)
        item = self.processing_queue.get_next_pending()
        
        # Skip scheduled items
        if item and item.is_scheduled:
            # Check if any other items are ready? 
            # get_next_pending implementation likely returns first match.
            # We need to find the first *ready* pending item.
            found_ready = None
            for q_item in self.processing_queue.items:
                if q_item.is_pending and not q_item.is_scheduled:
                    found_ready = q_item
                    break
            item = found_ready

        if not item:
            self.processing = False
            self.status_label.setText("Idle")
            return
        
        self.processing = True
        self.current_item = item
        item.start_processing()
        self.queue_panel.refresh()
        self.status_label.setText("Processing...")
        
        # Run in background thread
        thread = threading.Thread(target=self._run_censor, args=(item,))
        thread.daemon = True
        thread.start()
        
    def _check_scheduled_items(self):
        """Check for scheduled items that are due."""
        from datetime import datetime
        now = datetime.now()
        updated = False
        
        for item in self.processing_queue.items:
            if item.is_scheduled and item.scheduled_time and now >= item.scheduled_time:
                # Activate item
                item.status = "pending"
                item.scheduled_time = None # Clear schedule
                updated = True
        
        if updated:
            self.queue_panel.refresh()
            if not self.processing:
                self._process_next()
    
    @Slot(str, float, str)
    def on_progress_update(self, item_id: str, progress: float, status: str):
        """Handle progress updates from background thread."""
        item = self.processing_queue.get(item_id)
        if item:
            item.update_progress(progress, status)
            self.queue_panel.update_item(item_id)
            
            # Check for progress notifications (50% and 90%)
            self._check_progress_notification(item)
    
    def _check_progress_notification(self, item: QueueItem):
        """Send notification at 50% and 90% completion with ETA."""
        try:
            # Only if notifications enabled
            config = self.preference_panel.config
            if not config.notifications.enabled or not config.notifications.ntfy_topic:
                return
            
            progress_pct = int(item.progress * 100)
            target_pct = 0
            
            # Check thresholds
            if progress_pct >= 90 and not item.notified_90:
                target_pct = 90
                item.notified_90 = True
            elif progress_pct >= 50 and not item.notified_90 and not item.notified_50:
                target_pct = 50
                item.notified_50 = True
            
            if target_pct > 0:
                # Calculate ETA
                import datetime
                elapsed = (datetime.datetime.now() - item.started_at).total_seconds()
                if elapsed > 0 and item.progress > 0:
                    total_estimated = elapsed / item.progress
                    remaining = total_estimated - elapsed
                    
                    # Format ETA
                    if remaining < 60:
                        eta_str = "< 1 min"
                    elif remaining < 3600:
                        eta_str = f"{int(remaining / 60)}m"
                    else:
                        hours = int(remaining / 3600)
                        mins = int((remaining % 3600) / 60)
                        eta_str = f"{hours}h {mins}m"
                    
                    from video_censor.notifications import notify_progress
                    notify_progress(config.notifications.ntfy_topic, item.filename, target_pct, eta_str)
                    
        except Exception as e:
            print(f"Failed to check progress notification: {e}")

    def _on_export_confirmed(self):
        """User confirmed export in Review Panel."""
        if not self.current_item or not hasattr(self.current_item, 'analysis_path'):
            return
            
        item = self.current_item
        
        # Update current item status
        item.status = "exporting"
        item.progress = 0.5
        
        # Get edits from timeline
        edits = self.review_panel.get_data()
        
        # Save edits back to analysis path (overwrite)
        try:
            import json
            with open(item.analysis_path, 'w') as f:
                json.dump(edits, f, indent=2)
        except Exception as e:
            print(f"Failed to save timeline edits: {e}")
            
        # Switch back to setup
        self.stack.setCurrentIndex(0) 
        
        # Resume processing
        self.queue_panel.refresh()
        self.status_label.setText("Processing...")
        self.processing = True
        
        # Run export in background thread
        thread = threading.Thread(target=self._run_censor, args=(item,))
        thread.daemon = True
        thread.start()

    def _on_review_cancelled(self):
        """User cancelled review."""
        if self.current_item:
            self.current_item.cancel()
            self.queue_panel.refresh()
            
        self.stack.setCurrentIndex(0)
        self.processing = False
        self.status_label.setText("Idle")
        self.current_item = None
        
        # Process next
        QTimer.singleShot(100, self._process_next)
    
    def _on_editor_requested(self):
        """User wants to open the Timeline Editor."""
        if not self.current_item:
            return
            
        item = self.current_item
        
        # Load analysis data for editor
        try:
            import json
            with open(item.analysis_path, 'r') as f:
                data = json.load(f)
            
            # Estimate duration
            duration = 0
            for type_list in data.values():
                for seg in type_list:
                    duration = max(duration, seg.get('end', 0))
            duration = max(duration, 100)
            
            # Load into editor panel
            from pathlib import Path
            self.editor_panel.load_video(Path(item.input_path), data, duration)
            self.stack.setCurrentIndex(2)  # Switch to editor
            self.status_label.setText("✂️ Editing...")
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to open editor: {e}")
    
    def _on_editor_export(self, project):
        """Handle export from editor."""
        if not self.current_item or not project:
            return
            
        item = self.current_item
        
        # Build edits from project
        from video_censor.editing.intervals import Action
        
        # Convert project edits to detection format
        edited_data = {}
        for edit in project.edits:
            # Group by action type
            if edit.action == Action.CUT:
                key = 'cuts'
            elif edit.action in (Action.MUTE, Action.BEEP):
                key = 'profanity'
            else:
                key = 'visual_edits'
            
            if key not in edited_data:
                edited_data[key] = []
            
            edited_data[key].append({
                'start': edit.source_start,
                'end': edit.source_end,
                'reason': edit.reason,
                'action': edit.action.value,
            })
        
        # Save project-based edits to analysis path
        try:
            import json
            with open(item.analysis_path, 'w') as f:
                json.dump(edited_data, f, indent=2)
        except Exception as e:
            print(f"Failed to save editor edits: {e}")
        
        # Switch back to setup
        self.stack.setCurrentIndex(0)
        self.status_label.setText("Exporting...")
        
        # Update item status and start export
        item.status = "exporting"
        item.progress = 0.5
        self.queue_panel.refresh()
        
        # Run export in background
        import threading
        thread = threading.Thread(target=self._run_censor, args=(item,))
        thread.daemon = True
        thread.start()
    
    def _on_editor_closed(self):
        """User closed the editor without exporting."""
        self.stack.setCurrentIndex(1)  # Back to review panel
        self.status_label.setText("🎬 Reviewing...")
        
    def _start_review(self, item_id: str):
        """Open the review panel for an item."""
        item = self.processing_queue.get(item_id)
        if not item or not item.analysis_path or not item.analysis_path.exists():
            print(f"Cannot review item {item_id}: Missing analysis data")
            return
            
        self.current_item = item
        
        # Load data
        try:
            import json
            with open(item.analysis_path, 'r') as f:
                data = json.load(f)
            
            # Estimate duration
            duration = 0
            for type_list in data.values():
                for seg in type_list:
                    duration = max(duration, seg.get('end', 0))
            
            duration = max(duration, 100) # Minimum
            
            self.review_panel.load_data(str(item.input_path), duration, data)
            self.stack.setCurrentIndex(1)
            
        except Exception as e:
            print(f"Failed to load review data: {e}")
            
    @Slot(str)
    def on_item_review_ready(self, item_id: str):
        """Handle item ready for review."""
        item = self.processing_queue.get(item_id)
        if item:
            self.queue_panel.update_item(item_id)
            self.processing = False 
            
            # Notify user
            try:
                from video_censor.notifications import notify_progress
                if self.preference_panel.config.notifications.enabled:
                     notify_progress(
                         self.preference_panel.config.notifications.ntfy_topic, 
                         item.filename, 
                         50, 
                         "Ready for review"
                     )
            except Exception:
                pass
            
            self._process_next()

    def _cancel_current_job(self, item_id: str):
        """Cancel the currently running job."""
        if self.current_item and self.current_item.id == item_id:
            msg = f"Cancelling job: {self.current_item.filename}"
            print(msg)
            
            # Kill subprocess if running
            if self.current_process:
                try:
                    self.current_process.terminate()
                    # Give it a moment to die gracefully
                    QTimer.singleShot(1000, lambda: self._force_kill_if_needed())
                except Exception as e:
                    print(f"Error terminating process: {e}")
            
            # Update item state
            self.current_item.cancel()
            self.queue_panel.update_item(self.current_item.id)
            self.processing = False
            self.current_process = None
            self.status_label.setText("Cancelled")
            
            # Trigger next
            QTimer.singleShot(1000, self._process_next)
            
    def _force_kill_if_needed(self):
        """Force kill process if it didn't terminate."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.kill()
            except:
                pass
        self.current_process = None
    
    def _delete_queue_item(self, item_id: str):
        """Delete an item from the queue."""
        item = self.processing_queue.get(item_id)
        if item:
            # Don't delete if currently processing
            if item.is_processing:
                return
            
            self.processing_queue.remove(item_id)
            self.processing_queue.save_state()
            self.queue_panel.refresh()
            print(f"Deleted queue item: {item.filename}")

    @Slot(str)
    def on_item_complete(self, item_id: str):
        """Handle item completion."""
        item = self.processing_queue.get(item_id)
        if item:
            item.complete()
            self.queue_panel.update_item(item_id)
            
            # Log completion for audit trail
            self._log_batch_result(item, "complete")
            
            # Send push notification
            self._send_notification("complete", item)
            
            # Save queue state (remove completed from persistence)
            self.processing_queue.save_state()
            
            # Auto-clear this item after 30 seconds to free memory
            QTimer.singleShot(30000, lambda: self._auto_clear_item(item_id))
            
            # Check if batch is done (trigger notifications/sleep)
            self.processing_queue.check_all_complete()
            
            # Trigger next item
            QTimer.singleShot(100, self._process_next)
    
    def _log_batch_result(self, item: QueueItem, status: str):
        """Log processing result to batch_log.txt for audit trail."""
        from datetime import datetime
        log_path = Path(OUTPUT_DIR) / "batch_log.txt"
        try:
            with open(log_path, 'a') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                duration = item.duration_str if hasattr(item, 'duration_str') else ""
                f.write(f"[{timestamp}] {status.upper()}: {item.input_path.name} -> {item.output_path.name} ({duration})\n")

        except Exception as e:
            print(f"Failed to write batch log: {e}")
    
    def _auto_clear_item(self, item_id: str):
        """Remove a completed item from the queue to free memory."""
        item = self.processing_queue.get(item_id)
        if item and item.is_finished:
            self.processing_queue.remove(item_id)
            self.queue_panel.refresh()
    
    def _on_queue_complete(self):
        """Handle queue completion (notifications, sleep)."""
        # Run on main thread just in case
        QTimer.singleShot(0, self._send_batch_complete_notification)

    def _send_notification(self, status: str, item: QueueItem, error: str = ""):
        """Send push notification via ntfy.sh if enabled."""
        try:
            config = self.preference_panel.config
            print(f"[NOTIFY DEBUG] Attempting notification: status={status}")
            print(f"[NOTIFY DEBUG] enabled={config.notifications.enabled}")
            print(f"[NOTIFY DEBUG] topic={config.notifications.ntfy_topic}")
            print(f"[NOTIFY DEBUG] notify_on_complete={config.notifications.notify_on_complete}")
            
            if not config.notifications.enabled:
                print("[NOTIFY DEBUG] Skipped: notifications disabled")
                return
            
            if not config.notifications.ntfy_topic:
                print("[NOTIFY DEBUG] Skipped: no ntfy topic configured")
                return
            
            from video_censor.notifier import get_notifier
            notifier = get_notifier(config)
            
            if status == "complete" and config.notifications.notify_on_complete:
                print(f"[NOTIFY DEBUG] Sending completion notification for {item.filename}")
                notifier.send(
                    title=f"✅ {item.filename}",
                    message=f"Processing complete! Finished in {item.duration_str}",
                )
                print("[NOTIFY DEBUG] Notification sent successfully")
            elif status == "failed" and config.notifications.notify_on_error:
                print(f"[NOTIFY DEBUG] Sending error notification for {item.filename}")
                notifier.send(
                    title=f"❌ {item.filename}",
                    message=f"Error: {error[:100]}",
                    priority="high"
                )
        except Exception as e:
            print(f"[NOTIFY DEBUG] Failed to send notification: {e}")
    
    def _send_batch_complete_notification(self):
        """Send notification when entire batch is finished."""
        try:
            config = self.preference_panel.config
            if not config.notifications.enabled or not config.notifications.notify_on_batch_done:
                return
            
            from video_censor.notifier import get_notifier
            notifier = get_notifier(config)
            
            total = len(self.processing_queue.items)
            successful = self.processing_queue.complete_count
            failed = self.processing_queue.error_count
            
            notifier.send(
                title="Batch Processing Complete",
                message=f"Processed {total} videos\n✅ {successful} successful\n❌ {failed} failed",
                priority="high" if failed > 0 else "default"
            )
        except Exception as e:
            print(f"Failed to send batch notification: {e}")

    @Slot(str, str)
    def on_item_failed(self, item_id: str, error: str):
        """Handle item failure."""
        item = self.processing_queue.get(item_id)
        if item:
            item.fail(error)
            self.queue_panel.update_item(item_id)
            
            # Log failure for audit trail
            self._log_batch_result(item, f"failed: {error[:50]}")
            
            # Send push notification
            self._send_notification("failed", item, error)
            
            # Save queue state
            self.processing_queue.save_state()
            
            # Check if batch is done (trigger notifications/sleep)
            self.processing_queue.check_all_complete()
            
            # Trigger next item
            QTimer.singleShot(100, self._process_next)

    def _run_censor(self, item: QueueItem):
        try:
            import subprocess
            import traceback
            import os
            from pathlib import Path
            from datetime import datetime
            
            def log_debug(msg):
                try:
                    with open("/tmp/vc_debug.log", "a") as f:
                        f.write(f"[{datetime.now()}] {msg}\n")
                except:
                    pass

            log_debug(f"Starting _run_censor for item {item.id}")
            
            try:
                log_debug(f"File: {__file__}")
                project_root = Path(__file__).resolve().parent.parent
                log_debug(f"Root: {project_root}")
                
                VENV_PYTHON = str(project_root / "venv" / "bin" / "python")
                CENSOR_SCRIPT = str(project_root / "censor_video.py")
                
                log_debug(f"Python: {VENV_PYTHON}")
                log_debug(f"Script: {CENSOR_SCRIPT}")
            except Exception as e:
                log_debug(f"Error resolving paths: {e}")
                raise e
            
            if not os.path.exists(VENV_PYTHON):
                log_debug(f"ERROR: VENV_PYTHON not found at {VENV_PYTHON}")
                self.item_failed.emit(item.id, f"Python interpreter not found: {VENV_PYTHON}")
                return

            if not os.path.exists(CENSOR_SCRIPT):
                log_debug(f"ERROR: CENSOR_SCRIPT not found at {CENSOR_SCRIPT}")
                self.item_failed.emit(item.id, f"Script not found: {CENSOR_SCRIPT}")
                return
            
            env = os.environ.copy()
            env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            
            cmd = [
                "arch", "-arm64", # Explicitly force arm64 to match venv libraries
                VENV_PYTHON, "-u",
                CENSOR_SCRIPT,
                str(item.input_path), str(item.output_path),
                "--save-summary", str(item.output_path.with_suffix('.json')),
                "-y"
            ]
            
            # If we have an analysis file and we are starting fresh (pending/scheduled), use it to speed up
            # If status is 'review_ready', we assume logic elsewhere handles it, but for auto-processing:
            if item.analysis_path and item.analysis_path.exists():
                 cmd.extend(["--import-intervals", str(item.analysis_path)])
            
            # Subtitle injection
            if hasattr(item, 'subtitles_path') and item.subtitles_path:
                cmd.extend(["--subtitles", str(item.subtitles_path)])

            # Add filter arguments
            # WORKFLOW LOGIC
            is_analysis_pass = False
            
            if item.status == "pending" or item.status == "processing" or item.status == "analyzing":
                # Run Analysis Only
                is_analysis_pass = True
                cmd.append("--analyze-only")
                
                # Analysis path
                analysis_path = item.output_path.with_suffix(".analysis.json")
                cmd.extend(["--export-intervals", str(analysis_path)])
                
                # Update item state
                item.analysis_path = analysis_path
                self.progress_update.emit(item.id, 0.01, "Starting analysis...")
                
            elif item.status == "exporting":
                 # Run Import & Render
                 if item.analysis_path and item.analysis_path.exists():
                     cmd.extend(["--import-intervals", str(item.analysis_path)])
                     self.progress_update.emit(item.id, 0.50, "Starting export...")
                 else:
                     self.item_failed.emit(item.id, "Missing analysis file for export")
                     return
            
            if not item.filters.filter_language:
                cmd.append("--no-profanity")
            if not item.filters.filter_nudity:
                cmd.append("--no-nudity")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                universal_newlines=True,
                bufsize=1
            )
            
            # Store reference in main window for cancellation
            self.current_process = process
            
            # Log file for debugging
            debug_log = Path(__file__).parent.parent / "ui_debug.log"
            
            # Read output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                    
                if not line:
                    continue
                    
                line = line.strip()
                
                # Log to file
                with open(debug_log, "a") as f:
                    f.write(f"[PIPE] {line}\n")
                
                # Update progress based on step markers
                # Update progress based on step markers
                if is_analysis_pass:
                    # Analysis Phases (0-50%)
                    if "STEP 1" in line:
                         self.progress_update.emit(item.id, 0.05, "Starting parallel analysis...")
                    
                    # Parallel Progress Parsing
                    elif "[AUDIO] PROGRESS:" in line:
                        try:
                            # [AUDIO] PROGRESS: 45% -> Parse percent
                            pct = int(line.split("PROGRESS:")[1].split("%")[0].strip())
                            # Store audio progress on item (temporary attribute)
                            if not hasattr(item, 'audio_progress'): item.audio_progress = 0
                            item.audio_progress = pct
                            
                            # Calculate combined progress (approx.)
                            # Audio 0-100 scales to 0-50 overall (Phase 1)
                            # Video 0-100 scales to 0-50 overall (Phase 2, now parallel)
                            # We'll average them for display if both running?
                            # For simplicity:
                            # Audio accounts for 20% of effort
                            # Video accounts for 30% of effort
                            # Total Analysis = 50%
                            
                            v_pct = getattr(item, 'video_progress', 0)
                            combined = (pct * 0.2 + v_pct * 0.3) / 100.0
                            
                            msg = f"Analyzing: Audio {pct}% | Video {v_pct}%"
                            self.progress_update.emit(item.id, combined, msg)
                        except:
                            pass
                            
                    elif "[VIDEO] PROGRESS:" in line:
                        try:
                            # [VIDEO] PROGRESS: 30%
                            pct = int(line.split("PROGRESS:")[1].split("%")[0].strip())
                            if not hasattr(item, 'video_progress'): item.video_progress = 0
                            item.video_progress = pct
                            
                            a_pct = getattr(item, 'audio_progress', 0)
                            combined = (a_pct * 0.2 + pct * 0.3) / 100.0
                            
                            msg = f"Analyzing: Audio {a_pct}% | Video {pct}%"
                            self.progress_update.emit(item.id, combined, msg)
                        except:
                            pass
                    
                    elif "STEP 2.5" in line:
                         self.progress_update.emit(item.id, 0.50, "Sexual content detection...")
                    elif "STEP 2.7" in line:
                         self.progress_update.emit(item.id, 0.51, "Violence detection...")
                    elif "STEP 3" in line:
                         self.progress_update.emit(item.id, 0.52, "Planning edits...")



                    elif "Analysis complete" in line:
                        self.progress_update.emit(item.id, 0.50, "Analysis complete")
                        
                else:
                    # Export Phases (50-100%)
                    if "STEP 3" in line:
                        self.progress_update.emit(item.id, 0.55, "Planning edits...")
                    elif "STEP 4" in line:
                        self.progress_update.emit(item.id, 0.60, "Rendering video...")
                    elif "Extracting" in line and "segments" in line:
                        # Parse segment count for progress base
                        try:
                            parts = line.split()
                            for i, p in enumerate(parts):
                                if p == "Extracting" and i+1 < len(parts):
                                    self._total_segments = int(parts[i+1])
                                    self._current_segment = 0
                                    break
                        except: pass
                    elif "Extracted segment" in line or "stream-copy" in line or "copy-video" in line or "hw-encode" in line:
                        # Each segment extraction
                        self._current_segment = getattr(self, '_current_segment', 0) + 1
                        total_segs = getattr(self, '_total_segments', 50)
                        # Map segments to 60-90% range
                        pct = 0.60 + (self._current_segment / total_segs) * 0.30
                        self.progress_update.emit(item.id, min(pct, 0.90), f"Extracting segment {self._current_segment}/{total_segs}...")
                    elif "Concatenating" in line:
                        self.progress_update.emit(item.id, 0.92, "Stitching segments...")
                    elif "Concatenated" in line:
                        self.progress_update.emit(item.id, 0.95, "Finalizing...")
                    elif "Complete" in line or "SUCCESS" in line or "saved to" in line.lower():
                        self.progress_update.emit(item.id, 1.0, "Complete")
            
            # Clear process reference when done
            self.current_process = None

            rc = process.poll()
            
            if rc == 0:
                if is_analysis_pass:
                    # Mark review ready
                    item.mark_review_ready(item.analysis_path)
                    self.item_review_ready.emit(item.id)
                else:
                    self.item_complete.emit(item.id)
            else:
                # Check if it was just cancelled/killed
                if item.status != "cancelled":
                    self.item_failed.emit(item.id, "Process exited with error")
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                with open(Path(__file__).parent.parent / "ui_debug.log", "a") as f:
                    f.write(f"[CRITICAL] {str(e)}\n")
            except:
                pass
            self.item_failed.emit(item.id, str(e))
    
    def _open_profile_manager(self):
        from .profile_dialog import ProfileDialog
        dialog = ProfileDialog(self.profile_manager, self)
        dialog.exec()
        self.preference_panel.refresh_profiles()

    def _auto_sync(self):
        """Run auto-sync if enabled."""
        try:
            config = self.preference_panel.config
            if not config.sync.enabled or not config.sync.auto_sync or not config.sync.user_id:
                return

            if self.preference_panel.sync_status_label:
                self.preference_panel.sync_status_label.setText("Syncing...")
            
            # Use the existing thread logic?
            # Or duplicative lightweight thread
            threading.Thread(target=self._run_auto_sync_thread, daemon=True).start()
        except Exception as e:
            print(f"Auto-sync failed to start: {e}")

    def _run_auto_sync_thread(self):
        """Worker for auto-sync."""
        try:
            config = self.preference_panel.config
            from video_censor.profanity.wordlist import sync_custom_wordlist
            from video_censor.presets import sync_presets
            
            sync_custom_wordlist(config)
            sync_presets(config)
            
            # Update UI if alive
            QTimer.singleShot(0, lambda: self._on_auto_sync_complete())
        except Exception as e:
            print(f"Auto-sync error: {e}")

    def _on_auto_sync_complete(self):
        try:
            if self.preference_panel.sync_status_label:
                self.preference_panel.sync_status_label.setText("Synced (Auto)")
        except:
            pass

    def closeEvent(self, event):
        """Handle application close."""
        # Trigger sync on close if enabled
        # Note: This might not finish if we exit immediately.
        # We can try running it synchronously or just kick it off and hope OS gives it a second.
        # Ideally we block for a second or two.
        try:
            config = self.preference_panel.config
            if config.sync.enabled and config.sync.auto_sync and config.sync.user_id:
                print("Performing exit sync...")
                # Run synchronously for exit
                from video_censor.profanity.wordlist import sync_custom_wordlist
                from video_censor.presets import sync_presets
                sync_custom_wordlist(config)
                sync_presets(config)
        except Exception as e:
            print(f"Exit sync failed: {e}")
            
        event.accept()
