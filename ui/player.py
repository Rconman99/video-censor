"""
Video Player Widget for Video Censor.
Wraps QMediaPlayer and QVideoWidget with custom controls.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, 
    QStyle, QFrame
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt, Signal, QUrl, QTime

class VideoPlayerWidget(QWidget):
    """
    A custom video player widget with playback controls.
    """
    
    position_changed = Signal(int)  # Emitted when playback position changes (ms)
    duration_changed = Signal(int)  # Emitted when media duration changes (ms)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Media Player components
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.video_widget = QVideoWidget()
        
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Connect signals
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.errorOccurred.connect(self._handle_error)
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video Area
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background: black; border-radius: 6px;")
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_widget)
        
        layout.addWidget(self.video_container, 1)
        
        # Controls Area
        controls = QFrame()
        controls.setStyleSheet("background: #181820; padding: 4px;")
        controls_layout = QHBoxLayout(controls)
        
        # Play/Pause Button
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.clicked.connect(self.toggle_playback)
        self.play_btn.setStyleSheet("border: none; border-radius: 4px; background: #2a2a35;")
        controls_layout.addWidget(self.play_btn)
        
        # Time Label (Current)
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: #a1a1aa; font-family: monospace; font-size: 11px;")
        controls_layout.addWidget(self.time_label)
        
        # Seek Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderPressed.connect(self.media_player.pause)
        self.slider.sliderReleased.connect(self.media_player.play)
        controls_layout.addWidget(self.slider)
        
        # Time Label (Total)
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: #71717a; font-family: monospace; font-size: 11px;")
        controls_layout.addWidget(self.duration_label)
        
        # Volume
        vol_btn = QPushButton("🔊")
        vol_btn.setFixedSize(24, 24)
        vol_btn.setStyleSheet("border: none; color: #a1a1aa;")
        controls_layout.addWidget(vol_btn)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100))
        controls_layout.addWidget(self.volume_slider)
        
        layout.addWidget(controls)
        
    def load_video(self, path: str):
        """Load a video file."""
        self.media_player.setSource(QUrl.fromLocalFile(path))
        self.play_btn.setEnabled(True)
        
    def toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
            
    def play(self):
        self.media_player.play()
        
    def pause(self):
        self.media_player.pause()
        
    def set_position(self, position: int):
        """Seek to position in ms."""
        self.media_player.setPosition(position)
        
    def _on_position_changed(self, position: int):
        self.slider.setValue(position)
        self.time_label.setText(self._format_time(position))
        self.position_changed.emit(position)
        
    def _on_duration_changed(self, duration: int):
        self.slider.setRange(0, duration)
        self.duration_label.setText(self._format_time(duration))
        self.duration_changed.emit(duration)
        
    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            
    def _handle_error(self):
        self.play_btn.setEnabled(False)
        self.time_label.setText("Error")
        print(f"Video Player Error: {self.media_player.errorString()}")
        
    def _format_time(self, ms: int) -> str:
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000) % 60
        hours = (ms // 3600000)
        
        if hours > 0:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes:02}:{seconds:02}"
