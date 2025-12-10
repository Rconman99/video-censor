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
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QCheckBox, QRadioButton, QButtonGroup, QPlainTextEdit,
    QScrollArea, QFileDialog, QListWidget, QListWidgetItem, QProgressBar,
    QSplitter, QSizePolicy, QGroupBox, QToolButton, QSpacerItem, QSlider, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QMimeData, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class CollapsibleSection(QWidget):
    """A collapsible section widget."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header
        header = QHBoxLayout()
        
        self.toggle_btn = QToolButton()
        self.toggle_btn.setArrowType(Qt.DownArrow)
        self.toggle_btn.setStyleSheet("background: transparent; border: none;")
        self.toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self.toggle_btn)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; background: transparent;")
        header.addWidget(title_label)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Content container
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(self.content)
        
        self._expanded = True
    
    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
    
    def add_widget(self, widget):
        self.content_layout.addWidget(widget)


class PreferencePanel(QFrame):
    """Preference manager panel for configuring filters."""
    
    start_requested = Signal(str, ContentFilterSettings, str)  # path, settings, profile_name
    
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
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Preference Manager")
        title.setProperty("class", "section-header")
        layout.addWidget(title)
        
        # Video info (initially hidden)
        self.video_info = QFrame()
        self.video_info.setStyleSheet("background: #0f0f14; border-radius: 6px; padding: 12px;")
        video_layout = QHBoxLayout(self.video_info)
        
        self.video_icon = QLabel("📹")
        self.video_icon.setStyleSheet("font-size: 24px; background: transparent;")
        video_layout.addWidget(self.video_icon)
        
        video_text = QVBoxLayout()
        self.video_name = QLabel("No video selected")
        self.video_name.setStyleSheet("font-weight: bold; background: transparent;")
        video_text.addWidget(self.video_name)
        
        self.video_details = QLabel("")
        self.video_details.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        video_text.addWidget(self.video_details)
        
        video_layout.addLayout(video_text)
        video_layout.addStretch()
        layout.addWidget(self.video_info)
        
        # Profile selector
        profile_layout = QHBoxLayout()
        profile_label = QLabel("Profile:")
        profile_label.setStyleSheet("background: transparent;")
        profile_layout.addWidget(profile_label)
        
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(self.profile_manager.list_names())
        self.profile_combo.currentTextChanged.connect(self._on_profile_change)
        profile_layout.addWidget(self.profile_combo, 1)
        
        self.manage_btn = QPushButton("Manage")
        self.manage_btn.setProperty("class", "secondary")
        self.manage_btn.setFixedWidth(80)
        profile_layout.addWidget(self.manage_btn)
        
        layout.addLayout(profile_layout)
        
        # Scroll area for filters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        filters_widget = QWidget()
        filters_layout = QVBoxLayout(filters_widget)
        filters_layout.setSpacing(12)
        
        # Content filter checkboxes
        filters_header = QLabel("Content Filters")
        filters_header.setProperty("class", "section-header")
        filters_layout.addWidget(filters_header)
        
        self.cb_language = QCheckBox("🗣  Language (profanity, slurs)")
        self.cb_language.setChecked(True)
        filters_layout.addWidget(self.cb_language)
        
        self.cb_sexual = QCheckBox("💬  Sexual Content (dialogue)")
        self.cb_sexual.setChecked(True)
        filters_layout.addWidget(self.cb_sexual)
        
        self.cb_nudity = QCheckBox("👁  Nudity (visual)")
        self.cb_nudity.setChecked(True)
        filters_layout.addWidget(self.cb_nudity)
        
        self.cb_mature = QCheckBox("🚫  Mature Themes")
        self.cb_mature.setEnabled(False)
        self.cb_mature.setStyleSheet("color: #71717a;")
        filters_layout.addWidget(self.cb_mature)
        
        # Romance intensity
        romance_group = QGroupBox("💕  Romance Intensity")
        romance_layout = QVBoxLayout(romance_group)
        
        self.romance_group = QButtonGroup(self)
        self.rb_romance_keep = QRadioButton("Keep all")
        self.rb_romance_heavy = QRadioButton("Remove explicit/heavy")
        self.rb_romance_strict = QRadioButton("Remove kissing & strong romance")
        
        self.romance_group.addButton(self.rb_romance_keep, 0)
        self.romance_group.addButton(self.rb_romance_heavy, 1)
        self.romance_group.addButton(self.rb_romance_strict, 2)
        
        self.rb_romance_keep.setChecked(True)
        
        romance_layout.addWidget(self.rb_romance_keep)
        romance_layout.addWidget(self.rb_romance_heavy)
        romance_layout.addWidget(self.rb_romance_strict)
        
        filters_layout.addWidget(romance_group)
        
        # Violence intensity
        violence_group = QGroupBox("🗡  Violence Intensity")
        violence_layout = QVBoxLayout(violence_group)
        
        self.violence_group = QButtonGroup(self)
        self.rb_violence_keep = QRadioButton("Keep all")
        self.rb_violence_gore = QRadioButton("Remove graphic (gore, blood)")
        self.rb_violence_death = QRadioButton("Remove death scenes")
        self.rb_violence_fight = QRadioButton("Remove all fighting")
        
        self.violence_group.addButton(self.rb_violence_keep, 0)
        self.violence_group.addButton(self.rb_violence_gore, 1)
        self.violence_group.addButton(self.rb_violence_death, 2)
        self.violence_group.addButton(self.rb_violence_fight, 3)
        
        self.rb_violence_keep.setChecked(True)
        
        violence_layout.addWidget(self.rb_violence_keep)
        violence_layout.addWidget(self.rb_violence_gore)
        violence_layout.addWidget(self.rb_violence_death)
        violence_layout.addWidget(self.rb_violence_fight)
        
        filters_layout.addWidget(violence_group)
        
        # Custom phrases section
        phrases_section = CollapsibleSection("📝  Custom Phrases")
        
        phrases_hint = QLabel("Words or sentences to mute/cut (one per line)")
        phrases_hint.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        phrases_section.add_widget(phrases_hint)
        
        self.phrases_edit = QPlainTextEdit()
        self.phrases_edit.setPlaceholderText(
            "Type or paste any words or sentences here\n"
            "One per line\n"
            "Example: stupid, oh my gosh, shut up"
        )
        self.phrases_edit.setMaximumHeight(100)
        phrases_section.add_widget(self.phrases_edit)
        
        phrases_actions = QHBoxLayout()
        open_file_btn = QPushButton("Open as text file…")
        open_file_btn.setProperty("class", "link")
        phrases_actions.addWidget(open_file_btn)
        phrases_actions.addStretch()
        
        phrases_section.content_layout.addLayout(phrases_actions)
        
        filters_layout.addWidget(phrases_section)
        
        # Safe cover section
        safe_cover_layout = QHBoxLayout()
        safe_cover_label = QLabel("🖼  Generate kid-friendly cover image")
        safe_cover_label.setStyleSheet("background: transparent;")
        safe_cover_layout.addWidget(safe_cover_label)
        safe_cover_layout.addStretch()
        
        self.cb_safe_cover = QCheckBox()
        safe_cover_layout.addWidget(self.cb_safe_cover)
        
        filters_layout.addLayout(safe_cover_layout)
        
        # Save defaults button
        save_defaults = QPushButton("💾  Save as profile defaults")
        save_defaults.setProperty("class", "link")
        save_defaults.clicked.connect(self._save_defaults)
        filters_layout.addWidget(save_defaults)

        # Output Quality Section
        tk_sep = QFrame()
        tk_sep.setFrameShape(QFrame.HLine)
        tk_sep.setFrameShadow(QFrame.Sunken)
        tk_sep.setStyleSheet("background: #2a2a35; margin-top: 10px; margin-bottom: 10px;")
        filters_layout.addWidget(tk_sep)
        
        quality_header = QLabel("Output Quality")
        quality_header.setProperty("class", "section-header")
        filters_layout.addWidget(quality_header)
        
        # Quality Preset Dropdown (replaces CRF/Target Size)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Quality:"))
        
        self.quality_preset_combo = QComboBox()
        self.quality_preset_combo.setMinimumWidth(250)
        
        # Quality presets with resolution and bitrate info
        self.quality_presets = [
            ("Play Original Quality", "original"),
            ("Convert Automatically", "auto"),
            ("Convert to 4K UHD (High)  40 Mbps", "4k_high"),
            ("Convert to 4K UHD (Medium)  24 Mbps", "4k_med"),
            ("Convert to 4K UHD  18 Mbps", "4k_low"),
            ("Convert to 1080p HD (High)  20 Mbps", "1080p_high"),
            ("Convert to 1080p HD (Medium)  12 Mbps", "1080p_med"),
            ("Convert to 1080p HD  10 Mbps", "1080p_10"),
            ("Convert to 1080p HD  8 Mbps", "1080p_low"),
            ("Convert to 720p HD (High)  4 Mbps", "720p_high"),
            ("Convert to 720p HD (Medium)  3 Mbps", "720p_med"),
            ("Convert to 720p HD  2 Mbps", "720p_low"),
            ("Convert to 480p  1.5 Mbps", "480p"),
            ("Convert to 328p  0.7 Mbps", "328p"),
            ("Convert to 240p  0.3 Mbps", "240p"),
            ("Convert to 160p  0.2 Mbps", "160p"),
        ]
        
        for display_name, _ in self.quality_presets:
            self.quality_preset_combo.addItem(display_name)
        
        preset_row.addWidget(self.quality_preset_combo)
        preset_row.addStretch()
        
        filters_layout.addLayout(preset_row)
        
        # Resolution & Speed Row
        res_speed_row = QHBoxLayout()
        
        # Resolution
        res_speed_row.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["Original", "4K (2160p)", "1080p", "720p", "480p"])
        self.resolution_combo.setFixedWidth(120)
        res_speed_row.addWidget(self.resolution_combo)
        
        res_speed_row.addSpacing(20)
        
        # Encoding Speed
        res_speed_row.addWidget(QLabel("Speed:"))
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([
            "veryslow", "slower", "slow", "medium", "fast", "faster", "veryfast", "superfast", "ultrafast"
        ])
        self.speed_combo.setFixedWidth(110)
        res_speed_row.addWidget(self.speed_combo)
        
        res_speed_row.addStretch()
        filters_layout.addLayout(res_speed_row)
        
        # Video Codec Row
        codec_row = QHBoxLayout()
        codec_row.addWidget(QLabel("Video Codec:"))
        
        self.codec_combo = QComboBox()
        self.video_codecs = [
            ("H.264 (Best Compatibility)", "libx264"),
            ("H.265/HEVC (Smaller Files)", "libx265"),
        ]
        for display_name, _ in self.video_codecs:
            self.codec_combo.addItem(display_name)
        self.codec_combo.setMinimumWidth(200)
        codec_row.addWidget(self.codec_combo)
        
        codec_hint = QLabel("H.265 = ~40% smaller, slightly less compatible")
        codec_hint.setStyleSheet("color: #71717a; font-size: 10px; font-style: italic;")
        codec_row.addWidget(codec_hint)
        
        codec_row.addStretch()
        filters_layout.addLayout(codec_row)
        
        # Output Format Row
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Output Format:"))
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "avi", "mov"])
        self.format_combo.setFixedWidth(80)
        format_row.addWidget(self.format_combo)
        
        format_hint = QLabel("(Container format for output file)")
        format_hint.setStyleSheet("color: #71717a; font-size: 10px; font-style: italic;")
        format_row.addWidget(format_hint)
        
        format_row.addStretch()
        filters_layout.addLayout(format_row)
        
        # Whisper Model Size Row (Speech Recognition)
        whisper_sep = QFrame()
        whisper_sep.setFrameShape(QFrame.HLine)
        whisper_sep.setFrameShadow(QFrame.Sunken)
        whisper_sep.setStyleSheet("background: #2a2a35; margin-top: 10px; margin-bottom: 10px;")
        filters_layout.addWidget(whisper_sep)
        
        whisper_header = QLabel("Speech Recognition")
        whisper_header.setProperty("class", "section-header")
        filters_layout.addWidget(whisper_header)
        
        whisper_row = QHBoxLayout()
        whisper_row.addWidget(QLabel("Whisper Model:"))
        
        self.whisper_combo = QComboBox()
        self.whisper_models = [
            ("Large-v3 (Most Accurate)", "large-v3"),
            ("Medium (Balanced)", "medium"),
            ("Small (Faster)", "small"),
            ("Base (Fast)", "base"),
            ("Tiny (Fastest)", "tiny"),
        ]
        for display_name, _ in self.whisper_models:
            self.whisper_combo.addItem(display_name)
        self.whisper_combo.setMinimumWidth(200)
        whisper_row.addWidget(self.whisper_combo)
        
        whisper_hint = QLabel("Larger = more accurate, slower")
        whisper_hint.setStyleSheet("color: #71717a; font-size: 10px; font-style: italic;")
        whisper_row.addWidget(whisper_hint)
        
        whisper_row.addStretch()
        filters_layout.addLayout(whisper_row)
        
        # Initialize values from config
        self._init_quality_from_config()
        
        filters_layout.addStretch()
        
        scroll.setWidget(filters_widget)
        layout.addWidget(scroll, 1)
        
        # Start button - primary gradient style
        self.start_btn = QPushButton("▶  Start Filtering")
        self.start_btn.setProperty("class", "primary")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(52)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:0.5 #6366f1, stop:1 #8b5cf6);
                font-size: 15px;
                font-weight: 600;
                border-radius: 10px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #60a5fa, stop:0.5 #818cf8, stop:1 #a78bfa);
            }
            QPushButton:disabled {
                background: #1f1f2a;
                color: #4a4a5a;
            }
        """)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)
        
        # Apply initial profile
        self._apply_profile_settings()
    
    def set_video(self, path: str):
        """Set the current video file."""
        self.current_video_path = path
        filename = Path(path).name
        
        # Get file size
        try:
            size = os.path.getsize(path)
            if size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
        except:
            size_str = ""
        
        self.video_name.setText(filename)
        self.video_details.setText(size_str)
        self.start_btn.setEnabled(True)
    
    def _on_profile_change(self, name: str):
        self._apply_profile_settings()
    
    def _apply_profile_settings(self):
        profile_name = self.profile_combo.currentText()
        profile = self.profile_manager.get_or_default(profile_name)
        settings = profile.settings
        
        self.cb_language.setChecked(settings.filter_language)
        self.cb_sexual.setChecked(settings.filter_sexual_content)
        self.cb_nudity.setChecked(settings.filter_nudity)
        self.cb_mature.setChecked(settings.filter_mature_themes)
        
        self.romance_group.button(settings.filter_romance_level).setChecked(True)
        self.violence_group.button(settings.filter_violence_level).setChecked(True)
        
        self.phrases_edit.setPlainText("\n".join(settings.custom_block_phrases))
        self.cb_safe_cover.setChecked(settings.safe_cover_enabled)
    
    def get_current_settings(self) -> ContentFilterSettings:
        """Get the current filter settings from controls."""
        phrases = [p.strip() for p in self.phrases_edit.toPlainText().split("\n") if p.strip()]
        
        return ContentFilterSettings(
            filter_language=self.cb_language.isChecked(),
            filter_sexual_content=self.cb_sexual.isChecked(),
            filter_nudity=self.cb_nudity.isChecked(),
            filter_romance_level=self.romance_group.checkedId(),
            filter_violence_level=self.violence_group.checkedId(),
            filter_mature_themes=self.cb_mature.isChecked(),
            custom_block_phrases=phrases,
            safe_cover_enabled=self.cb_safe_cover.isChecked()
        )
    
    def _save_defaults(self):
        profile_name = self.profile_combo.currentText()
        profile = self.profile_manager.get(profile_name)
        if profile:
            profile.settings = self.get_current_settings()
            self.profile_manager.update(profile_name, profile)
    
    def _on_start(self):
        if self.current_video_path:
            # Save global quality settings first
            self.save_quality_to_config()
            
            settings = self.get_current_settings()
            self.start_requested.emit(
                self.current_video_path,
                settings,
                self.profile_combo.currentText()
            )
            self.current_video_path = None
            self.video_name.setText("No video selected")
            self.video_details.setText("")
            self.start_btn.setEnabled(False)
    
    def refresh_profiles(self):
        """Refresh the profile dropdown."""
        current = self.profile_combo.currentText()
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.list_names())
        
        idx = self.profile_combo.findText(current)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
            
    def _init_quality_from_config(self):
        # Set values from self.config
        preset_key = getattr(self.config.output, 'quality_preset', 'original')
        
        # Find matching preset index
        for i, (display_name, key) in enumerate(self.quality_presets):
            if key == preset_key:
                self.quality_preset_combo.setCurrentIndex(i)
                break
        
        # Set video format
        self.format_combo.setCurrentText(self.config.output.video_format)
        
        # Set video codec
        codec_key = getattr(self.config.output, 'video_codec', 'libx264')
        for i, (display_name, key) in enumerate(self.video_codecs):
            if key == codec_key:
                self.codec_combo.setCurrentIndex(i)
                break
        
        # Set whisper model
        whisper_model = getattr(self.config.whisper, 'model_size', 'large-v3')
        for i, (display_name, key) in enumerate(self.whisper_models):
            if key == whisper_model:
                self.whisper_combo.setCurrentIndex(i)
                break
        
    def save_quality_to_config(self):
        """Save current quality settings to self.config and disk."""
        # Get selected preset key
        idx = self.quality_preset_combo.currentIndex()
        if 0 <= idx < len(self.quality_presets):
            _, preset_key = self.quality_presets[idx]
            self.config.output.quality_preset = preset_key
        
        # Save video format
        self.config.output.video_format = self.format_combo.currentText()
        
        # Save video codec
        codec_idx = self.codec_combo.currentIndex()
        if 0 <= codec_idx < len(self.video_codecs):
            _, codec_key = self.video_codecs[codec_idx]
            self.config.output.video_codec = codec_key
        
        # Save whisper model
        whisper_idx = self.whisper_combo.currentIndex()
        if 0 <= whisper_idx < len(self.whisper_models):
            _, model_key = self.whisper_models[whisper_idx]
            self.config.whisper.model_size = model_key
        
        try:
            config_path = Path(__file__).parent.parent / "config.yaml"
            self.config.save(config_path)
        except Exception as e:
            print(f"Failed to save config: {e}")


class QueueItemWidget(QFrame):
    """Widget representing a single queue item."""
    
    def __init__(self, item: QueueItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setStyleSheet("background: #0f0f14; border-radius: 6px; padding: 8px;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Filename
        name_label = QLabel(item.filename)
        name_label.setStyleSheet("font-weight: bold; background: transparent;")
        layout.addWidget(name_label)
        
        # Profile and tags
        tags_layout = QHBoxLayout()
        
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
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(int(item.progress * 100))
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(6)
        layout.addWidget(self.progress_bar)
    
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


class QueuePanel(QFrame):
    """Queue panel showing processing jobs."""
    
    def __init__(self, queue: ProcessingQueue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self.setProperty("class", "panel")
        self._item_widgets = {}
        
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Processing Queue")
        title.setProperty("class", "section-header")
        header.addWidget(title)
        
        self.count_label = QLabel("No videos in queue")
        self.count_label.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        header.addWidget(self.count_label)
        header.addStretch()
        
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
        
        # Connect signals
        self.progress_update.connect(self.on_progress_update)
        self.item_complete.connect(self.on_item_complete)
        self.item_failed.connect(self.on_item_failed)
        
        self._create_ui()
        
        # Restore any saved queue state (crash recovery)
        restored = self.processing_queue.load_state()
        if restored > 0:
            self.queue_panel.refresh()
            print(f"Restored {restored} pending item(s) from previous session")
            # Auto-start processing restored items
            if not self.processing:
                QTimer.singleShot(1000, self._process_next)
        
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
        
        # Main content - 3 columns
        content = QHBoxLayout()
        content.setSpacing(24)
        
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
        content.addWidget(left_widget)
        
        # Center: Preference panel
        self.preference_panel = PreferencePanel(self.profile_manager)
        self.preference_panel.start_requested.connect(self._on_start_filtering)
        self.preference_panel.manage_btn.clicked.connect(self._open_profile_manager)
        content.addWidget(self.preference_panel, 2)
        
        # Right: Queue panel
        self.queue_panel = QueuePanel(self.processing_queue)
        self.queue_panel.setFixedWidth(320)
        content.addWidget(self.queue_panel)
        
        main_layout.addLayout(content, 1)
        
        # Footer
        footer = QHBoxLayout()
        
        output_label = QLabel(f"Output folder: {OUTPUT_DIR}")
        output_label.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        footer.addWidget(output_label)
        
        footer.addStretch()
        
        main_layout.addLayout(footer)
        
        # Load saved output settings
        self._load_output_settings()
    
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
    
    def _on_start_filtering(self, video_path: str, settings: ContentFilterSettings, profile_name: str):
        # Save quality settings to config before processing
        self._save_output_settings()
        
        # Create output path
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        video_path_obj = Path(video_path)
        
        # Get selected output format from MainWindow's dropdown
        output_format = self.format_combo.currentText()
        output_path = Path(OUTPUT_DIR) / f"{video_path_obj.stem}.CENSORED.{output_format}"
        
        # Create queue item
        item = QueueItem(
            input_path=video_path_obj,
            output_path=output_path,
            filters=settings,
            profile_name=profile_name
        )
        
        # Add to queue
        self.processing_queue.add(item)
        self.queue_panel.refresh()
        
        # Save queue state for crash recovery
        self.processing_queue.save_state()
        
        # Start processing if not already
        if not self.processing:
            self._process_next()
    
    def _process_next(self):
        item = self.processing_queue.get_next_pending()
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
    
    @Slot(str, float, str)
    def on_progress_update(self, item_id: str, progress: float, status: str):
        """Handle progress updates from background thread."""
        item = self.processing_queue.get(item_id)
        if item:
            item.update_progress(progress, status)
            self.queue_panel.update_item(item_id)

    @Slot(str)
    def on_item_complete(self, item_id: str):
        """Handle item completion."""
        item = self.processing_queue.get(item_id)
        if item:
            item.complete()
            self.queue_panel.update_item(item_id)
            
            # Log completion for audit trail
            self._log_batch_result(item, "complete")
            
            # Save queue state (remove completed from persistence)
            self.processing_queue.save_state()
            
            # Auto-clear this item after 30 seconds to free memory
            QTimer.singleShot(30000, lambda: self._auto_clear_item(item_id))
            
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

    @Slot(str, str)
    def on_item_failed(self, item_id: str, error: str):
        """Handle item failure."""
        item = self.processing_queue.get(item_id)
        if item:
            item.fail(error)
            self.queue_panel.update_item(item_id)
            
            # Log failure for audit trail
            self._log_batch_result(item, f"failed: {error[:50]}")
            
            # Save queue state
            self.processing_queue.save_state()
            
            # Trigger next item
            QTimer.singleShot(100, self._process_next)

    def _run_censor(self, item: QueueItem):
        try:
            import subprocess
            
            VENV_PYTHON = str(Path(__file__).parent.parent / "venv" / "bin" / "python")
            CENSOR_SCRIPT = str(Path(__file__).parent.parent / "censor_video.py")
            
            env = os.environ.copy()
            env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            
            cmd = [
                "arch", "-arm64", VENV_PYTHON, "-u",  # Force arm64 unbuffered
                CENSOR_SCRIPT,
                str(item.input_path), str(item.output_path),
                "--save-summary", str(item.output_path.with_suffix('.json')),
                "-y"
            ]
            
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
                if "STEP 1" in line:
                    self.progress_update.emit(item.id, 0.05, "Detecting profanity...")
                elif "PROGRESS:" in line and "Step 1" in line:
                    # Parse percentage: PROGRESS: 45% (Step 1)
                    try:
                        percent = int(line.split(":")[1].split("%")[0].strip())
                        # Step 1 is 5% -> 35% of total
                        total_progress = 0.05 + (percent / 100.0 * 0.30)
                        self.progress_update.emit(item.id, total_progress, f"Scanning audio... {percent}%")
                    except Exception as e:
                        with open(debug_log, "a") as f:
                            f.write(f"[ERROR] Parse failed: {e}\n")
                elif "STEP 2:" in line and "Nudity" in line:
                    self.progress_update.emit(item.id, 0.35, "Detecting nudity...")
                elif "Extracting frames" in line:
                    self.progress_update.emit(item.id, 0.38, "Extracting frames...")
                elif "Analyzing frames" in line:
                    # [PIPE] Analyzing frames:  70%|...
                    try:
                        # Extract percentage from tqdm output
                        parts = line.split("|")
                        if len(parts) > 1 and "%" in parts[0]:
                            pct_str = parts[0].split("frames:")[-1].replace("%", "").strip()
                            if pct_str:
                                percent = int(pct_str)
                                # Step 2b (Detection) is 40% -> 70%
                                total_progress = 0.40 + (percent / 100.0 * 0.30)
                                self.progress_update.emit(item.id, total_progress, f"Scanning video... {percent}%")
                    except:
                        pass
                elif "STEP 2.5" in line:
                    self.progress_update.emit(item.id, 0.70, "Detecting sexual content...")
                elif "STEP 2.7" in line:
                    self.progress_update.emit(item.id, 0.75, "Detecting violence...")
                elif "STEP 3" in line:
                    self.progress_update.emit(item.id, 0.80, "Planning edits...")
                elif "STEP 4" in line:
                    self.progress_update.emit(item.id, 0.85, "Rendering video...")
                elif "Applying" in line and "edit" in line.lower():
                    self.progress_update.emit(item.id, 0.95, "Applying edits...")
                elif "Complete" in line or "SUCCESS" in line:
                    self.progress_update.emit(item.id, 1.0, "Complete")
            
            process.wait()
            
            if process.returncode == 0:
                self.item_complete.emit(item.id)
            else:
                self.item_failed.emit(item.id, f"Processing failed (exit code {process.returncode})")
        
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
