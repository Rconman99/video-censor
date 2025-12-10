"""
Profile Manager Dialog for Video Censor.

Allows creating, editing, and deleting filter profiles.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox, QRadioButton, QButtonGroup, QPlainTextEdit,
    QScrollArea, QListWidget, QListWidgetItem, QLineEdit, QSplitter,
    QMessageBox, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from video_censor.preferences import ContentFilterSettings, Profile
from video_censor.profile_manager import ProfileManager


class ProfileDialog(QDialog):
    """Profile Manager dialog for creating and editing profiles."""
    
    profiles_changed = Signal()
    
    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.current_profile: Optional[Profile] = None
        
        self.setWindowTitle("Profile Manager")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)
        
        self._create_ui()
        self._load_profiles()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        header = QHBoxLayout()
        title = QLabel("Profile Manager")
        title.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("background: transparent; border: none; font-size: 18px; color: #71717a;")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        
        layout.addLayout(header)
        
        # Splitter for list and editor
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Profile list
        left_panel = QFrame()
        left_panel.setStyleSheet("background: #141419; border-radius: 8px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        
        list_header = QHBoxLayout()
        list_title = QLabel("Profiles")
        list_title.setStyleSheet("font-weight: bold; background: transparent;")
        list_header.addWidget(list_title)
        list_header.addStretch()
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.clicked.connect(self._add_profile)
        list_header.addWidget(add_btn)
        
        left_layout.addLayout(list_header)
        
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self.profile_list)
        
        splitter.addWidget(left_panel)
        
        # Right: Profile editor
        right_panel = QFrame()
        right_panel.setStyleSheet("background: #141419; border-radius: 8px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)
        
        # Profile name
        name_layout = QHBoxLayout()
        name_label = QLabel("Profile Name:")
        name_label.setStyleSheet("background: transparent;")
        name_layout.addWidget(name_label)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter profile name")
        name_layout.addWidget(self.name_edit, 1)
        
        right_layout.addLayout(name_layout)
        
        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(12)
        
        # Content filters
        filters_label = QLabel("Content Filters")
        filters_label.setStyleSheet("font-weight: bold; background: transparent;")
        settings_layout.addWidget(filters_label)
        
        self.cb_language = QCheckBox("🗣  Language (profanity, slurs)")
        settings_layout.addWidget(self.cb_language)
        
        self.cb_sexual = QCheckBox("💬  Sexual Content (dialogue)")
        settings_layout.addWidget(self.cb_sexual)
        
        self.cb_nudity = QCheckBox("👁  Nudity (visual)")
        settings_layout.addWidget(self.cb_nudity)
        
        self.cb_mature = QCheckBox("🚫  Mature Themes")
        self.cb_mature.setEnabled(False)
        self.cb_mature.setStyleSheet("color: #71717a;")
        settings_layout.addWidget(self.cb_mature)
        
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
        
        romance_layout.addWidget(self.rb_romance_keep)
        romance_layout.addWidget(self.rb_romance_heavy)
        romance_layout.addWidget(self.rb_romance_strict)
        
        settings_layout.addWidget(romance_group)
        
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
        
        violence_layout.addWidget(self.rb_violence_keep)
        violence_layout.addWidget(self.rb_violence_gore)
        violence_layout.addWidget(self.rb_violence_death)
        violence_layout.addWidget(self.rb_violence_fight)
        
        settings_layout.addWidget(violence_group)
        
        # Custom phrases
        phrases_label = QLabel("📝  Custom Phrases")
        phrases_label.setStyleSheet("font-weight: bold; background: transparent;")
        settings_layout.addWidget(phrases_label)
        
        phrases_hint = QLabel("Words or sentences to mute/cut (one per line)")
        phrases_hint.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        settings_layout.addWidget(phrases_hint)
        
        self.phrases_edit = QPlainTextEdit()
        self.phrases_edit.setPlaceholderText("Type or paste any words or sentences here\nOne per line")
        self.phrases_edit.setMaximumHeight(120)
        settings_layout.addWidget(self.phrases_edit)
        
        # Safe cover
        safe_cover_layout = QHBoxLayout()
        safe_cover_label = QLabel("🖼  Generate kid-friendly cover image")
        safe_cover_label.setStyleSheet("background: transparent;")
        safe_cover_layout.addWidget(safe_cover_label)
        safe_cover_layout.addStretch()
        
        self.cb_safe_cover = QCheckBox()
        safe_cover_layout.addWidget(self.cb_safe_cover)
        
        settings_layout.addLayout(safe_cover_layout)
        settings_layout.addStretch()
        
        scroll.setWidget(settings_widget)
        right_layout.addWidget(scroll, 1)
        
        # Action buttons
        actions = QHBoxLayout()
        
        self.delete_btn = QPushButton("Delete Profile")
        self.delete_btn.setProperty("class", "secondary")
        self.delete_btn.clicked.connect(self._delete_profile)
        actions.addWidget(self.delete_btn)
        
        actions.addStretch()
        
        self.save_btn = QPushButton("Save Profile")
        self.save_btn.clicked.connect(self._save_profile)
        actions.addWidget(self.save_btn)
        
        right_layout.addLayout(actions)
        
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([300, 600])
        
        layout.addWidget(splitter, 1)
    
    def _load_profiles(self):
        """Load profiles into the list."""
        self.profile_list.clear()
        
        for profile in self.profile_manager.list_all():
            item = QListWidgetItem()
            
            # Create widget for profile item
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(2)
            
            name_label = QLabel(profile.name)
            name_label.setStyleSheet("font-weight: bold; background: transparent;")
            layout.addWidget(name_label)
            
            summary = profile.settings.short_summary() or "No filters"
            summary_label = QLabel(summary)
            summary_label.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
            layout.addWidget(summary_label)
            
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, profile.name)
            
            self.profile_list.addItem(item)
            self.profile_list.setItemWidget(item, widget)
        
        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)
    
    def _on_profile_selected(self, row: int):
        """Handle profile selection."""
        if row < 0:
            self.current_profile = None
            return
        
        item = self.profile_list.item(row)
        profile_name = item.data(Qt.UserRole)
        profile = self.profile_manager.get(profile_name)
        
        if profile:
            self.current_profile = profile
            self._display_profile(profile)
    
    def _display_profile(self, profile: Profile):
        """Display profile settings in the editor."""
        self.name_edit.setText(profile.name)
        
        settings = profile.settings
        self.cb_language.setChecked(settings.filter_language)
        self.cb_sexual.setChecked(settings.filter_sexual_content)
        self.cb_nudity.setChecked(settings.filter_nudity)
        self.cb_mature.setChecked(settings.filter_mature_themes)
        
        self.romance_group.button(settings.filter_romance_level).setChecked(True)
        self.violence_group.button(settings.filter_violence_level).setChecked(True)
        
        self.phrases_edit.setPlainText("\n".join(settings.custom_block_phrases))
        self.cb_safe_cover.setChecked(settings.safe_cover_enabled)
    
    def _get_current_settings(self) -> ContentFilterSettings:
        """Get settings from the editor controls."""
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
    
    def _add_profile(self):
        """Add a new profile."""
        new_profile = Profile(
            name="New Profile",
            settings=ContentFilterSettings()
        )
        
        # Find unique name
        base_name = "New Profile"
        counter = 1
        while self.profile_manager.get(new_profile.name):
            new_profile.name = f"{base_name} {counter}"
            counter += 1
        
        self.profile_manager.add(new_profile)
        self._load_profiles()
        
        # Select the new profile
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.data(Qt.UserRole) == new_profile.name:
                self.profile_list.setCurrentRow(i)
                break
        
        self.profiles_changed.emit()
    
    def _save_profile(self):
        """Save the current profile."""
        if not self.current_profile:
            return
        
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Profile name cannot be empty")
            return
        
        old_name = self.current_profile.name
        
        # Update profile
        self.current_profile.name = new_name
        self.current_profile.settings = self._get_current_settings()
        
        # If name changed, need to delete old and add new
        if old_name != new_name:
            self.profile_manager.delete(old_name)
            self.profile_manager.add(self.current_profile)
        else:
            self.profile_manager.update(old_name, self.current_profile)
        
        self._load_profiles()
        
        # Select the saved profile
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.data(Qt.UserRole) == new_name:
                self.profile_list.setCurrentRow(i)
                break
        
        self.profiles_changed.emit()
    
    def _delete_profile(self):
        """Delete the current profile."""
        if not self.current_profile:
            return
        
        if self.current_profile.name == "Default":
            QMessageBox.warning(self, "Error", "Cannot delete the Default profile")
            return
        
        reply = QMessageBox.question(
            self, 
            "Delete Profile",
            f'Are you sure you want to delete "{self.current_profile.name}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.profile_manager.delete(self.current_profile.name)
            self.current_profile = None
            self._load_profiles()
            self.profiles_changed.emit()
