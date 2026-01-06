from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QCheckBox, QComboBox, QGroupBox,
    QRadioButton, QButtonGroup, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont

class SetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VideoCensor Setup")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(600, 500)
        
        # Add pages
        self.addPage(WelcomePage())
        self.addPage(PrivacyInfoPage())
        self.addPage(ModelDownloadPage())
        self.addPage(BasicSettingsPage())
        self.addPage(CompletePage())
        
        # Custom button text
        self.setButtonText(QWizard.FinishButton, "Start Using Video Censor")


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to Video Censor")
        self.setSubTitle("Let's get you set up in just a few steps")
        
        layout = QVBoxLayout(self)
        
        # Logo/icon placeholder
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setText("🎬")  # Replace with actual icon
        logo_label.setStyleSheet("font-size: 72px;")
        layout.addWidget(logo_label)
        
        # Welcome text
        welcome_text = QLabel(
            "<h2>Automatically censor profanity and nudity in your videos</h2>"
            "<p>Video Censor uses AI to detect and blur/bleep inappropriate content, "
            "making your videos family-friendly.</p>"
            "<br>"
            "<p><b>This wizard will help you:</b></p>"
            "<ul>"
            "<li>Download required AI models (~2GB)</li>"
            "<li>Configure your preferences</li>"
            "<li>Get ready to process your first video</li>"
            "</ul>"
        )
        welcome_text.setWordWrap(True)
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setStyleSheet("font-size: 14px;")
        layout.addWidget(welcome_text)
        
        layout.addStretch()


class PrivacyInfoPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Privacy & How It Works")
        self.setSubTitle("Understanding what Video Censor does")
        
        layout = QVBoxLayout(self)
        
        # Privacy assurance
        privacy_group = QGroupBox("🔒 Your Privacy")
        privacy_layout = QVBoxLayout(privacy_group)
        privacy_text = QLabel(
            "<p><b>Everything runs locally on your computer.</b></p>"
            "<ul>"
            "<li>Your videos are never uploaded anywhere</li>"
            "<li>No internet required after setup</li>"
            "<li>No data is collected or shared</li>"
            "</ul>"
        )
        privacy_text.setWordWrap(True)
        privacy_text.setStyleSheet("font-size: 13px;")
        privacy_layout.addWidget(privacy_text)
        layout.addWidget(privacy_group)
        
        # How it works
        how_group = QGroupBox("🧠 How It Works")
        how_layout = QVBoxLayout(how_group)
        how_text = QLabel(
            "<p><b>Two AI models analyze your video:</b></p>"
            "<ul>"
            "<li><b>Whisper</b> - Transcribes speech and detects profanity</li>"
            "<li><b>NudeNet</b> - Analyzes video frames for nudity</li>"
            "</ul>"
            "<p>You review all detections before rendering. You're always in control.</p>"
        )
        how_text.setWordWrap(True)
        how_text.setStyleSheet("font-size: 13px;")
        how_layout.addWidget(how_text)
        layout.addWidget(how_group)
        
        layout.addStretch()


class ModelDownloadPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Download AI Models")
        self.setSubTitle("Required for video analysis (one-time download)")
        
        self.download_complete = False
        self._layout_setup()
    
    def _layout_setup(self):
        layout = QVBoxLayout(self)
        
        # Size warning
        size_label = QLabel(
            "⚠️ This will download approximately <b>2GB</b> of AI models.\n"
            "Make sure you have a stable internet connection."
        )
        size_label.setWordWrap(True)
        size_label.setStyleSheet("color: #fbbf24; font-weight: bold;")
        layout.addWidget(size_label)
        
        layout.addSpacing(20)
        
        # Whisper model
        whisper_group = QGroupBox("Whisper (Speech Recognition)")
        whisper_layout = QVBoxLayout(whisper_group)
        self.whisper_status = QLabel("⏳ Waiting...")
        self.whisper_progress = QProgressBar()
        self.whisper_progress.setRange(0, 100)
        whisper_layout.addWidget(self.whisper_status)
        whisper_layout.addWidget(self.whisper_progress)
        layout.addWidget(whisper_group)
        
        # NudeNet model
        nudenet_group = QGroupBox("NudeNet (Visual Detection)")
        nudenet_layout = QVBoxLayout(nudenet_group)
        self.nudenet_status = QLabel("⏳ Waiting...")
        self.nudenet_progress = QProgressBar()
        self.nudenet_progress.setRange(0, 100)
        nudenet_layout.addWidget(self.nudenet_status)
        nudenet_layout.addWidget(self.nudenet_progress)
        layout.addWidget(nudenet_group)
        
        layout.addSpacing(20)
        
        # Download button
        self.download_btn = QPushButton("Download Models")
        self.download_btn.setMinimumHeight(40)
        self.download_btn.clicked.connect(self._start_download)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:disabled { background: #4b5563; color: #9ca3af; }
        """)
        layout.addWidget(self.download_btn)
        
        # Overall status
        self.overall_status = QLabel("")
        self.overall_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.overall_status)
        
        layout.addStretch()
    
    def _start_download(self):
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading...")
        
        # Start download thread
        self.download_thread = ModelDownloadThread()
        self.download_thread.whisper_progress.connect(self._update_whisper)
        self.download_thread.nudenet_progress.connect(self._update_nudenet)
        self.download_thread.whisper_status.connect(self.whisper_status.setText)
        self.download_thread.nudenet_status.connect(self.nudenet_status.setText)
        self.download_thread.finished.connect(self._download_finished)
        self.download_thread.error.connect(self._download_error)
        self.download_thread.start()
    
    def _update_whisper(self, value):
        self.whisper_progress.setValue(value)
    
    def _update_nudenet(self, value):
        self.nudenet_progress.setValue(value)
    
    def _download_finished(self):
        self.download_complete = True
        self.download_btn.setText("✓ Download Complete")
        self.overall_status.setText("✅ All models ready!")
        self.overall_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        self.completeChanged.emit()
    
    def _download_error(self, error_msg):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Retry Download")
        self.overall_status.setText(f"❌ Error: {error_msg}")
        self.overall_status.setStyleSheet("color: #f87171;")
    
    def isComplete(self):
        return self.download_complete


class ModelDownloadThread(QThread):
    whisper_progress = Signal(int)
    nudenet_progress = Signal(int)
    whisper_status = Signal(str)
    nudenet_status = Signal(str)
    finished = Signal()
    error = Signal(str)
    
    def run(self):
        try:
            # Download Whisper
            self.whisper_status.emit("📥 Downloading Whisper model...")
            self._download_whisper()
            self.whisper_status.emit("✅ Whisper ready")
            self.whisper_progress.emit(100)
            
            # Download NudeNet
            self.nudenet_status.emit("📥 Downloading NudeNet model...")
            self._download_nudenet()
            self.nudenet_status.emit("✅ NudeNet ready")
            self.nudenet_progress.emit(100)
            
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _download_whisper(self):
        """Initialize Whisper model (triggers download)"""
        from faster_whisper import WhisperModel
        
        # This downloads the model on first run
        # Use small model for faster setup, user can change later
        self.whisper_progress.emit(10)
        # Attempt to init model - faster_whisper auto-downloads
        model = WhisperModel("base", device="cpu", compute_type="int8")
        self.whisper_progress.emit(100)
        del model  # Free memory
    
    def _download_nudenet(self):
        """Initialize NudeNet model (triggers download)"""
        try:
           from nudenet import NudeDetector
           
           self.nudenet_progress.emit(10)
           # Trigger download by initializing
           detector = NudeDetector() 
           self.nudenet_progress.emit(100)
           del detector  # Free memory
        except ImportError:
            # Fallback for dev environment without nudenet
            self.nudenet_status.emit("⚠️ NudeNet not found (skipped)")
            self.nudenet_progress.emit(100)


class BasicSettingsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Basic Settings")
        self.setSubTitle("Configure how Video Censor works for you")
        
        layout = QVBoxLayout(self)
        
        # Use case selection
        use_case_group = QGroupBox("What will you mainly use this for?")
        use_case_layout = QVBoxLayout(use_case_group)
        
        self.use_case_group = QButtonGroup(self)
        
        family = QRadioButton("👨‍👩‍👧‍👦 Family movie nights - Maximum filtering")
        youtube = QRadioButton("📺 YouTube/streaming - Monetization-safe")
        personal = QRadioButton("🎬 Personal preference - Balanced")
        minimal = QRadioButton("🔇 Light touch - Only severe content")
        
        family.setChecked(True)
        
        self.use_case_group.addButton(family, 0)
        self.use_case_group.addButton(youtube, 1)
        self.use_case_group.addButton(personal, 2)
        self.use_case_group.addButton(minimal, 3)
        
        use_case_layout.addWidget(family)
        use_case_layout.addWidget(youtube)
        use_case_layout.addWidget(personal)
        use_case_layout.addWidget(minimal)
        
        layout.addWidget(use_case_group)
        
        # Performance setting
        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)
        
        perf_text = QLabel("Choose based on your computer:")
        perf_layout.addWidget(perf_text)
        
        self.perf_combo = QComboBox()
        self.perf_combo.addItems([
            "🐢 Low Power - Slower but stable (recommended for laptops)",
            "⚖️ Balanced - Good mix of speed and stability",
            "🚀 High Performance - Fastest (requires 16GB+ RAM)"
        ])
        self.perf_combo.setCurrentIndex(0)  # Default to low power for safety
        perf_layout.addWidget(self.perf_combo)
        
        layout.addWidget(perf_group)
        
        # Register fields for access later
        self.registerField("use_case", self, "use_case_value")
        self.registerField("performance", self.perf_combo, "currentIndex")
        
        layout.addStretch()
    
    @property
    def use_case_value(self):
        return self.use_case_group.checkedId()


class CompletePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("You're All Set!")
        self.setSubTitle("Video Censor is ready to use")
        
        layout = QVBoxLayout(self)
        
        # Success message
        success_label = QLabel("🎉")
        success_label.setStyleSheet("font-size: 64px;")
        success_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(success_label)
        
        ready_text = QLabel(
            "<h2>Setup Complete!</h2>"
            "<p>You're ready to start censoring videos.</p>"
            "<br>"
            "<p><b>Quick tips:</b></p>"
            "<ul>"
            "<li>Drag and drop a video file to get started</li>"
            "<li>Press <b>G</b> to group detections by word</li>"
            "<li>Press <b>1-4</b> to batch keep/skip by severity</li>"
            "<li>Press <b>Ctrl+R</b> for quick re-render</li>"
            "</ul>"
            "<br>"
            "<p>You can change settings anytime in <b>Preferences</b>.</p>"
        )
        ready_text.setWordWrap(True)
        ready_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(ready_text)
        
        layout.addStretch()
