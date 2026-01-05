"""
Editor Panel for Video Censor.

Main drag-to-cut editor view combining video player, enhanced timeline,
and project management for non-destructive editing.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSplitter, QMessageBox, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

from .player import VideoPlayerWidget
from .editor_timeline import EditorTimelineWidget
from video_censor.editing.project import ProjectFile
from video_censor.editing.intervals import EditDecision, Action


class EditorPanel(QFrame):
    """
    Main editor panel for drag-to-cut editing.
    
    Features:
    - Video player with frame step controls
    - Enhanced timeline with drag selection
    - Detection marker lanes
    - Edits lane showing cuts/mutes/blurs
    - Project save/load
    - Undo/redo support
    """
    
    export_requested = Signal(object)  # Emits ProjectFile
    close_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "editor-panel")
        
        self._video_path: Path = None
        self._project: ProjectFile = None
        self._detection_data: dict = {}
        
        self._create_ui()
        self._connect_signals()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header = self._create_header()
        layout.addLayout(header)
        
        # Main splitter: Player (top) | Timeline (bottom)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet("QSplitter::handle { background: #2a2a35; }")
        
        # Video player
        self.player = VideoPlayerWidget()
        self.player.setMinimumHeight(300)
        self.splitter.addWidget(self.player)
        
        # Timeline area (including controls)
        timeline_widget = QWidget()
        timeline_layout = QVBoxLayout(timeline_widget)
        timeline_layout.setContentsMargins(0, 8, 0, 0)
        timeline_layout.setSpacing(8)
        
        # Timeline toolbar
        toolbar = self._create_toolbar()
        timeline_layout.addLayout(toolbar)
        
        # Enhanced timeline
        self.timeline = EditorTimelineWidget()
        timeline_layout.addWidget(self.timeline)
        
        self.splitter.addWidget(timeline_widget)
        self.splitter.setSizes([400, 250])
        
        layout.addWidget(self.splitter, 1)
        
        # Footer with actions
        footer = self._create_footer()
        layout.addLayout(footer)
    
    def _create_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        
        # Title
        title = QLabel("✂️ Timeline Editor")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f5f5f8;")
        header.addWidget(title)
        
        # Project status
        self.project_label = QLabel("No project loaded")
        self.project_label.setStyleSheet("color: #71717a; font-size: 11px;")
        header.addWidget(self.project_label)
        
        header.addStretch()
        
        # Keyboard hints
        hints = QLabel("Space: Play • ←→: Frame • Cmd+Z: Undo • Drag to select")
        hints.setStyleSheet("""
            color: #52525b; 
            font-size: 10px; 
            background: #1a1a24; 
            padding: 6px 12px; 
            border-radius: 4px;
        """)
        header.addWidget(hints)
        
        return header
    
    def _create_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        
        # Snap toggle
        self.snap_check = QCheckBox("🔗 Snap to Markers")
        self.snap_check.setChecked(True)
        self.snap_check.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        self.snap_check.stateChanged.connect(self._on_snap_changed)
        toolbar.addWidget(self.snap_check)
        
        # Ripple toggle
        self.ripple_check = QCheckBox("📍 Ripple Edit")
        self.ripple_check.setChecked(True)
        self.ripple_check.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        self.ripple_check.setToolTip("When on, cuts shift later content earlier")
        self.ripple_check.stateChanged.connect(self._on_ripple_changed)
        toolbar.addWidget(self.ripple_check)
        
        toolbar.addStretch()
        
        # Undo/Redo buttons
        self.btn_undo = QPushButton("↩ Undo")
        self.btn_undo.setEnabled(False)
        self.btn_undo.setStyleSheet(self._tool_btn_style())
        self.btn_undo.clicked.connect(self._undo)
        toolbar.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton("↪ Redo")
        self.btn_redo.setEnabled(False)
        self.btn_redo.setStyleSheet(self._tool_btn_style())
        self.btn_redo.clicked.connect(self._redo)
        toolbar.addWidget(self.btn_redo)
        
        # Navigation buttons
        self.btn_prev_marker = QPushButton("⏮ Prev Marker")
        self.btn_prev_marker.setStyleSheet(self._tool_btn_style())
        self.btn_prev_marker.clicked.connect(self._jump_prev_marker)
        toolbar.addWidget(self.btn_prev_marker)
        
        self.btn_next_marker = QPushButton("Next Marker ⏭")
        self.btn_next_marker.setStyleSheet(self._tool_btn_style())
        self.btn_next_marker.clicked.connect(self._jump_next_marker)
        toolbar.addWidget(self.btn_next_marker)
        
        return toolbar
    
    def _create_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setSpacing(12)
        
        # Save project button
        self.btn_save = QPushButton("💾 Save Project")
        self.btn_save.setStyleSheet(self._tool_btn_style())
        self.btn_save.clicked.connect(self._save_project)
        footer.addWidget(self.btn_save)
        
        footer.addStretch()
        
        # Discard button
        self.btn_discard = QPushButton("Cancel")
        self.btn_discard.setStyleSheet("""
            QPushButton {
                background: #2a2a38;
                color: #a0a0b0;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3a3a48; }
        """)
        self.btn_discard.clicked.connect(self._on_close)
        footer.addWidget(self.btn_discard)
        
        # Export button
        self.btn_export = QPushButton("▶ Export Edited Video")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #16a34a);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ade80, stop:1 #22c55e);
            }
        """)
        self.btn_export.clicked.connect(self._on_export)
        footer.addWidget(self.btn_export)
        
        return footer
    
    def _tool_btn_style(self) -> str:
        return """
            QPushButton {
                background: #2a2a38;
                color: #d0d0d8;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: #3a3a48; }
            QPushButton:disabled { color: #4a4a58; }
        """
    
    def _connect_signals(self):
        # Player <-> Timeline sync
        self.player.position_changed.connect(self.timeline.set_position)
        self.timeline.seek_requested.connect(self.player.set_position)
        
        # Edit actions from timeline
        self.timeline.edit_action_requested.connect(self._on_edit_action)
    
    # === Public API ===
    
    def load_video(self, video_path: Path, detection_data: dict, duration: float):
        """
        Load a video into the editor.
        
        Args:
            video_path: Path to the video file
            detection_data: Detection results {type: [segments]}
            duration: Video duration in seconds
        """
        self._video_path = video_path
        self._detection_data = detection_data
        
        # Load or create project
        existing = ProjectFile.load_for_video(video_path)
        if existing:
            self._project = existing
            self.project_label.setText(f"📁 Project loaded ({len(self._project.edits)} edits)")
        else:
            self._project = ProjectFile.create_for_video(
                video_path,
                fps=24.0,  # TODO: detect actual FPS
                duration=duration
            )
            # Store detection metadata
            self._project.detection_metadata = {
                'profanity_count': len(detection_data.get('profanity', [])),
                'nudity_count': len(detection_data.get('nudity', [])),
                'sexual_content_count': len(detection_data.get('sexual_content', [])),
            }
            self.project_label.setText("📁 New project")
        
        # Load into player
        self.player.load_video(str(video_path))
        
        # Load into timeline
        self.timeline.set_data(duration, detection_data)
        self.timeline.set_edits(self._project.edits)
        
        # Update toggle states
        self.snap_check.setChecked(self._project.snap_enabled)
        self.ripple_check.setChecked(self._project.ripple_mode)
        
        self._update_undo_buttons()
    
    def get_project(self) -> ProjectFile:
        """Get the current project file."""
        return self._project
    
    # === Event Handlers ===
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()
        
        if key == Qt.Key_Z and modifiers == Qt.ControlModifier:
            self._undo()
        elif key == Qt.Key_Z and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self._redo()
        elif key == Qt.Key_J:
            self._jump_prev_marker()
        elif key == Qt.Key_K:
            self._jump_next_marker()
        elif key == Qt.Key_S and modifiers == Qt.ControlModifier:
            self._save_project()
        else:
            super().keyPressEvent(event)
    
    def _on_edit_action(self, action_str: str, start: float, end: float):
        """Handle edit action from timeline."""
        if not self._project:
            return
        
        edit = EditDecision(
            source_start=start,
            source_end=end,
            action=Action(action_str),
            reason="Manual edit",
            source_start_frame=self._project.time_to_frame(start),
            source_end_frame=self._project.time_to_frame(end),
        )
        
        self._project.add_edit(edit)
        self.timeline.set_edits(self._project.edits)
        self._update_undo_buttons()
        self._update_project_label()
    
    def _on_snap_changed(self, state):
        self.timeline.set_snap_enabled(state == Qt.Checked)
        if self._project:
            self._project.snap_enabled = (state == Qt.Checked)
    
    def _on_ripple_changed(self, state):
        if self._project:
            self._project.ripple_mode = (state == Qt.Checked)
            self._project._recalculate_output_times()
            self.timeline.set_edits(self._project.edits)
    
    def _undo(self):
        if self._project and self._project.undo():
            self.timeline.set_edits(self._project.edits)
            self._update_undo_buttons()
            self._update_project_label()
    
    def _redo(self):
        if self._project and self._project.redo():
            self.timeline.set_edits(self._project.edits)
            self._update_undo_buttons()
            self._update_project_label()
    
    def _update_undo_buttons(self):
        if self._project:
            self.btn_undo.setEnabled(self._project.can_undo)
            self.btn_redo.setEnabled(self._project.can_redo)
    
    def _update_project_label(self):
        if self._project:
            dirty = "*" if self._project.is_dirty else ""
            self.project_label.setText(f"📁 {len(self._project.edits)} edits{dirty}")
    
    def _jump_prev_marker(self):
        """Jump to previous detection marker."""
        current = self.player.media_player.position() / 1000  # ms to sec
        markers = self.timeline.selection_overlay.snap_markers
        
        # Find previous marker
        prev_marker = 0
        for m in reversed(markers):
            if m < current - 0.1:  # Small buffer to avoid stuck
                prev_marker = m
                break
        
        self.player.set_position(int(prev_marker * 1000))
    
    def _jump_next_marker(self):
        """Jump to next detection marker."""
        current = self.player.media_player.position() / 1000
        markers = self.timeline.selection_overlay.snap_markers
        
        # Find next marker
        next_marker = self.timeline.duration
        for m in markers:
            if m > current + 0.1:
                next_marker = m
                break
        
        self.player.set_position(int(next_marker * 1000))
    
    def _save_project(self):
        """Save the project file."""
        if self._project:
            path = self._project.save()
            self._update_project_label()
            QMessageBox.information(self, "Saved", f"Project saved to:\n{path}")
    
    def _on_export(self):
        """Handle export request."""
        if self._project and self._project.is_dirty:
            reply = QMessageBox.question(
                self, "Save First?",
                "Save project before exporting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._project.save()
            elif reply == QMessageBox.Cancel:
                return
        
        self.player.media_player.stop()
        self.export_requested.emit(self._project)
    
    def _on_close(self):
        """Handle close/cancel."""
        if self._project and self._project.is_dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved edits. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self._project.save()
            elif reply == QMessageBox.Cancel:
                return
        
        self.player.media_player.stop()
        self.close_requested.emit()
