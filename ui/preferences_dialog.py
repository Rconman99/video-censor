from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QGroupBox, QFormLayout, QSlider,
    QMessageBox, QFileDialog, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from video_censor.config import Config


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(550, 500)
        
        self.config = Config.load()
        # self.original_config = Config.load()  # For cancel/reset logic if needed complex rollback
        
        self._setup_ui()
        self._load_values()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs for categories
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_detection_tab(), "Detection")
        self.tabs.addTab(self._create_profanity_tab(), "Profanity")
        self.tabs.addTab(self._create_output_tab(), "Output")
        self.tabs.addTab(self._create_performance_tab(), "Performance")
        self.tabs.addTab(self._create_sync_tab(), "Sync")
        layout.addWidget(self.tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        btn_layout.addWidget(apply_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._ok)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    # === GENERAL TAB ===
    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Preset selection (Visual only for now, logic handled in main window or presets manager)
        # preset_group = QGroupBox("Default Preset")
        # preset_layout = QFormLayout(preset_group)
        # self.preset_combo = QComboBox()
        # self.preset_combo.addItems(["Default (Balanced)", "Family Friendly", "YouTube Safe", "Minimal"])
        # preset_layout.addRow("Start with:", self.preset_combo)
        # layout.addWidget(preset_group)
        
        # Output location
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)
        
        output_row = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Leave empty for same folder as input")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_path)
        output_row.addWidget(browse_btn)
        output_layout.addRow("Custom Output Folder:", output_row)
        
        # self.add_suffix = QCheckBox("Add '_censored' suffix to filename")
        # self.add_suffix.setChecked(True)
        # output_layout.addRow("", self.add_suffix)
        
        layout.addWidget(output_group)
        
        # Behavior
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)
        
        self.auto_save_detections = QCheckBox("Auto-save detections after analysis")
        self.auto_load_detections = QCheckBox("Prompt to load existing detections")
        # self.remember_window = QCheckBox("Remember window size and position")
        
        behavior_layout.addWidget(self.auto_save_detections)
        behavior_layout.addWidget(self.auto_load_detections)
        # behavior_layout.addWidget(self.remember_window)
        
        layout.addWidget(behavior_group)
        
        layout.addStretch()
        return widget
    
    # === DETECTION TAB ===
    def _create_detection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Detection types
        types_group = QGroupBox("Detection Types")
        types_layout = QVBoxLayout(types_group)
        
        # Note: These map to what runs in pipeline, usually controlled by components
        # But here we can verify if we want to skip entire stages
        # For now, simplistic mapping
        # self.detect_profanity = QCheckBox("Detect profanity (audio)")
        # self.detect_nudity = QCheckBox("Detect nudity (visual)")
        # self.detect_profanity.setChecked(True)
        # self.detect_nudity.setChecked(True)
        # types_layout.addWidget(self.detect_profanity)
        # types_layout.addWidget(self.detect_nudity)
        
        # Nudity specific
        self.nudity_engine = QComboBox()
        self.nudity_engine.addItem("🧠 Precision (Dual-Stage, Best Accuracy)", "precision")
        self.nudity_engine.addItem("🚀 YOLO (Fast, Reliable)", "yolo")
        self.nudity_engine.addItem("🕰️ NudeNet (Legacy)", "nudenet")
        
        self.nudity_threshold_spin = QDoubleSpinBox()
        self.nudity_threshold_spin.setRange(0.1, 0.99)
        self.nudity_threshold_spin.setSingleStep(0.05)
        
        types_layout.addWidget(QLabel("Nudity Detection Engine:"))
        types_layout.addWidget(self.nudity_engine)
        
        engine_desc = QLabel(
            "Precision mode uses a multi-stage AI filter to virtually eliminate false positives (like hands or clothing)."
        )
        engine_desc.setStyleSheet("color: #a0a0b0; font-size: 10px; font-style: italic; margin-bottom: 10px;")
        engine_desc.setWordWrap(True)
        types_layout.addWidget(engine_desc)
        
        types_layout.addWidget(QLabel("Nudity Confidence Threshold:"))
        types_layout.addWidget(self.nudity_threshold_spin)
        
        layout.addWidget(types_group)
        
        # Context-aware
        context_group = QGroupBox("Smart Detection (LLM)")
        context_layout = QVBoxLayout(context_group)
        
        self.context_aware = QCheckBox("Enable Context-Aware Analysis")
        context_desc = QLabel(
            "Uses AI to understand context (e.g. quoted profanity, medical nudity).\n"
            "Requires an LLM provider (Ollama, Anthropic, or OpenAI)."
        )
        context_desc.setStyleSheet("color: gray; font-size: 11px;")
        
        form_layout = QFormLayout()
        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["ollama", "anthropic", "openai"])
        self.llm_model = QLineEdit()
        self.llm_model.setPlaceholderText("e.g. llama3, gpt-4")
        self.llm_key = QLineEdit()
        self.llm_key.setEchoMode(QLineEdit.Password)
        
        form_layout.addRow("Provider:", self.llm_provider)
        form_layout.addRow("Model Name:", self.llm_model)
        form_layout.addRow("API Key:", self.llm_key)
        
        context_layout.addWidget(self.context_aware)
        context_layout.addWidget(context_desc)
        context_layout.addLayout(form_layout)
        
        layout.addWidget(context_group)
        
        layout.addStretch()
        return widget
    
    # === PROFANITY TAB ===
    def _create_profanity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Severity tiers
        tiers_group = QGroupBox("Word Severity")
        tiers_layout = QVBoxLayout(tiers_group)
        
        tiers_desc = QLabel(
            "Words are grouped by severity for easier review.\n"
            "Detection Browser uses these tiers."
        )
        tiers_layout.addWidget(tiers_desc)
        
        # Tier preview
        tier_preview = QLabel(
            "🔴 <b>Severe:</b> f*ck, sh*t, c*nt, b*tch...\n"
            "🟠 <b>Moderate:</b> bastard, piss, crap...\n"
            "🟡 <b>Mild:</b> damn, hell...\n"
            "🟣 <b>Religious:</b> god, jesus, christ..."
        )
        tier_preview.setStyleSheet("background: #2a2a35; padding: 10px; border-radius: 4px; color: #e0e0e0;")
        tiers_layout.addWidget(tier_preview)
        
        layout.addWidget(tiers_group)
        
        # Custom words
        custom_group = QGroupBox("Custom Words")
        custom_layout = QVBoxLayout(custom_group)
        
        # Whitelist (Safe words)
        custom_layout.addWidget(QLabel("Whitelist (Never flag):"))
        self.custom_whitelist = QLineEdit()
        self.custom_whitelist.setPlaceholderText("word1, word2, word3")
        custom_layout.addWidget(self.custom_whitelist)

        # Blacklist (Always flag)
        custom_layout.addWidget(QLabel("Blacklist (Always flag):"))
        self.custom_blacklist = QLineEdit()
        self.custom_blacklist.setPlaceholderText("word1, word2, word3")
        custom_layout.addWidget(self.custom_blacklist)
        
        layout.addWidget(custom_group)
        
        layout.addStretch()
        return widget
    
    # === OUTPUT TAB ===
    def _create_output_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Audio censoring
        audio_group = QGroupBox("Audio Censoring")
        audio_layout = QFormLayout(audio_group)
        
        self.bleep_mode = QComboBox()
        self.bleep_mode.addItem("🔇 Silence (mute)", "mute")
        self.bleep_mode.addItem("📢 Tone (bleep)", "beep")
        
        audio_layout.addRow("Censor Mode:", self.bleep_mode)
        
        self.bleep_volume = QSlider(Qt.Horizontal)
        self.bleep_volume.setRange(0, 100)
        audio_layout.addRow("Beep Volume:", self.bleep_volume)
        
        self.beep_freq = QSpinBox()
        self.beep_freq.setRange(200, 2000)
        self.beep_freq.setSingleStep(100)
        audio_layout.addRow("Beep Freq (Hz):", self.beep_freq)
        
        layout.addWidget(audio_group)
        
        # Output format
        format_group = QGroupBox("Output Format")
        format_layout = QFormLayout(format_group)
        
        self.output_format = QComboBox()
        self.output_format.addItems(["mp4", "mkv", "avi", "mov"])
        format_layout.addRow("Container:", self.output_format)
        
        self.quality_preset = QComboBox()
        self.quality_preset.addItems(["original", "auto", "1080p_high", "720p_high", "480p"])
        format_layout.addRow("Quality Preset:", self.quality_preset)
        
        layout.addWidget(format_group)
        
        layout.addStretch()
        return widget
    
    # === PERFORMANCE TAB ===
    def _create_performance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Performance mode
        perf_group = QGroupBox("Processing Mode")
        perf_layout = QVBoxLayout(perf_group)
        
        self.perf_mode = QComboBox()
        self.perf_mode.addItem("🐢 Low Power - Slower but stable (recommended)", "low_power")
        self.perf_mode.addItem("⚖️ Balanced - Good mix of speed and stability", "balanced")
        self.perf_mode.addItem("🚀 High Performance - Fastest (16GB+ RAM)", "high_performance")
        
        perf_layout.addWidget(self.perf_mode)
        
        perf_desc = QLabel(
            "Low Power: Sequential processing, minimal RAM\n"
            "Balanced: Some parallelism, moderate RAM\n"
            "High Performance: Full parallel, high RAM usage"
        )
        perf_desc.setStyleSheet("color: gray; font-size: 11px;")
        perf_layout.addWidget(perf_desc)
        
        layout.addWidget(perf_group)
        
        # Whisper model
        whisper_group = QGroupBox("Speech Recognition (Whisper)")
        whisper_layout = QFormLayout(whisper_group)
        
        self.whisper_model = QComboBox()
        self.whisper_model.addItem("tiny - Fastest", "tiny")
        self.whisper_model.addItem("base - Fast, Good (Default)", "base")
        self.whisper_model.addItem("small - Better", "small")
        self.whisper_model.addItem("medium - High Quality", "medium")
        self.whisper_model.addItem("large - Best Quality (Slow)", "large")
        
        whisper_layout.addRow("Model Size:", self.whisper_model)
        
        layout.addWidget(whisper_group)
        
        layout.addStretch()
        return widget
    
    # === SYNC TAB ===
    def _create_sync_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Enable sync
        self.sync_enabled = QCheckBox("Enable cloud sync")
        layout.addWidget(self.sync_enabled)
        
        sync_desc = QLabel(
            "Sync settings across devices via Supabase."
        )
        sync_desc.setStyleSheet("color: gray;")
        layout.addWidget(sync_desc)
        
        # Supabase credentials
        creds_group = QGroupBox("Connection")
        creds_layout = QFormLayout(creds_group)
        
        self.supabase_url = QLineEdit()
        self.supabase_url.setPlaceholderText("https://xxxxx.supabase.co")
        creds_layout.addRow("URL:", self.supabase_url)
        
        self.supabase_key = QLineEdit()
        self.supabase_key.setEchoMode(QLineEdit.Password)
        creds_layout.addRow("API Key:", self.supabase_key)
        
        self.user_id = QLineEdit()
        creds_layout.addRow("User UUID:", self.user_id)
        
        layout.addWidget(creds_group)
        
        # Sync options
        options_group = QGroupBox("Sync Options")
        options_layout = QVBoxLayout(options_group)
        
        self.auto_sync = QCheckBox("Auto-sync on startup/exit")
        options_layout.addWidget(self.auto_sync)
        
        sync_now_btn = QPushButton("Sync Now")
        sync_now_btn.clicked.connect(self._sync_now)
        options_layout.addWidget(sync_now_btn)
        
        layout.addWidget(options_group)
        
        layout.addStretch()
        return widget
    
    # === HELPER METHODS ===
    
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_path.setText(path)
    
    def _sync_now(self):
        # Trigger basic save first to ensure credentials are used
        self._save_values()
        
        # Try to invoke sync manager
        try:
           from video_censor.sync import SyncManager
           import threading
           
           def run_sync():
               success = SyncManager(self.config).sync_now()
               # UI update logic for success...
               
           threading.Thread(target=run_sync, daemon=True).start()
           QMessageBox.information(self, "Sync", "Sync started in background...")
           
        except Exception as e:
            QMessageBox.warning(self, "Sync Error", str(e))
    
    def _load_values(self):
        """Load current config values into UI."""
        # General
        self.output_path.setText(self.config.output.custom_output_dir or "")
        
        # Detection Cache
        self.auto_save_detections.setChecked(self.config.detection_cache.auto_save)
        self.auto_load_detections.setChecked(self.config.detection_cache.auto_load)
        
        # Detection
        idx = self.nudity_engine.findData(self.config.nudity.engine)
        if idx >= 0: self.nudity_engine.setCurrentIndex(idx)
        self.nudity_threshold_spin.setValue(self.config.nudity.threshold)
        
        # LLM
        self.context_aware.setChecked(self.config.llm.enabled)
        idx = self.llm_provider.findText(self.config.llm.provider)
        if idx >= 0: self.llm_provider.setCurrentIndex(idx)
        self.llm_model.setText(self.config.llm.model)
        self.llm_key.setText(self.config.llm.api_key)
        
        # Profanity
        self.custom_whitelist.setText(", ".join(self.config.profanity.custom_whitelist))
        self.custom_blacklist.setText(", ".join(self.config.profanity.custom_blacklist))
        
        # Output
        idx = self.bleep_mode.findData(self.config.profanity.censor_mode)
        if idx >= 0: self.bleep_mode.setCurrentIndex(idx)
        
        self.bleep_volume.setValue(int(self.config.profanity.beep_volume * 100))
        self.beep_freq.setValue(self.config.profanity.beep_frequency_hz)
        
        idx = self.output_format.findText(self.config.output.video_format)
        if idx >= 0: self.output_format.setCurrentIndex(idx)
        
        idx = self.quality_preset.findText(self.config.output.quality_preset)
        if idx >= 0: self.quality_preset.setCurrentIndex(idx)
        
        # Performance
        idx = self.perf_mode.findData(self.config.system.performance_mode)
        if idx >= 0: self.perf_mode.setCurrentIndex(idx)
        
        idx = self.whisper_model.findData(self.config.whisper.model_size)
        if idx >= 0: self.whisper_model.setCurrentIndex(idx)
        
        # Sync
        self.sync_enabled.setChecked(self.config.sync.enabled)
        self.auto_sync.setChecked(self.config.sync.auto_sync)
        self.supabase_url.setText(self.config.sync.supabase_url)
        self.supabase_key.setText(self.config.sync.supabase_key)
        self.user_id.setText(self.config.sync.user_id)
        
    
    def _save_values(self):
        """Save UI values to config object."""
        # General
        self.config.output.custom_output_dir = self.output_path.text().strip()
        self.config.detection_cache.auto_save = self.auto_save_detections.isChecked()
        self.config.detection_cache.auto_load = self.auto_load_detections.isChecked()
        
        # Detection
        self.config.nudity.engine = self.nudity_engine.currentData()
        self.config.nudity.threshold = self.nudity_threshold_spin.value()
        
        # LLM
        self.config.llm.enabled = self.context_aware.isChecked()
        self.config.llm.provider = self.llm_provider.currentText()
        self.config.llm.model = self.llm_model.text().strip()
        self.config.llm.api_key = self.llm_key.text().strip()
        
        # Profanity
        w_text = self.custom_whitelist.text()
        self.config.profanity.custom_whitelist = [x.strip() for x in w_text.split(",") if x.strip()]
        
        b_text = self.custom_blacklist.text()
        self.config.profanity.custom_blacklist = [x.strip() for x in b_text.split(",") if x.strip()]
        
        # Output
        self.config.profanity.censor_mode = self.bleep_mode.currentData()
        self.config.profanity.beep_volume = self.bleep_volume.value() / 100.0
        self.config.profanity.beep_frequency_hz = self.beep_freq.value()
        
        self.config.output.video_format = self.output_format.currentText()
        self.config.output.quality_preset = self.quality_preset.currentText()
        
        # Performance
        self.config.system.performance_mode = self.perf_mode.currentData()
        self.config.whisper.model_size = self.whisper_model.currentData()
        
        # Sync
        self.config.sync.enabled = self.sync_enabled.isChecked()
        self.config.sync.auto_sync = self.auto_sync.isChecked()
        self.config.sync.supabase_url = self.supabase_url.text().strip()
        self.config.sync.supabase_key = self.supabase_key.text().strip()
        self.config.sync.user_id = self.user_id.text().strip()
        
        # Flush to disk
        try:
             self.config.save()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save config: {e}")
    
    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Reset all settings to defaults?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config = Config.default()
            self._load_values()
    
    def _apply(self):
        self._save_values()
        # Optional: Emit signal for main window update
        pass
    
    def _ok(self):
        self._save_values()
        self.accept()
