"""
Hover Preview Component.
Displays a small video preview window when hovering over detection cards.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt, QUrl, QTimer, QPoint

class HoverPreview(QWidget):
    """
    A persistent popup window for previewing video segments.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use Popup flag with parent - will close when parent closes
        # Remove WindowStaysOnTopHint to avoid orphan windows
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)  # Ensure cleanup
        self.setFixedSize(320, 200) # 16:9 approx
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)
        
        self.container = QFrame()
        self.container.setStyleSheet("background: black; border: 1px solid #3b82f6; border-radius: 4px;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(1,1,1,1)
        
        self.video_widget = QVideoWidget()
        self.container_layout.addWidget(self.video_widget)
        
        self.layout.addWidget(self.container)
        
        # Media setup
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0) # Mute hover preview? Or low volume. Request didn't specify, mute is safer.
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        self.current_video_path = None
        
        # Loop timer
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self._check_loop)
        self.start_ms = 0
        self.duration_ms = 2000 # 2 seconds
        
    def start_preview(self, video_path: str, start_time: float, global_pos: QPoint):
        """
        Start previewing the detection.
        video_path: Path to video file
        start_time: Start time in seconds
        global_pos: QPoint for where to show the tooltip
        """
        if not video_path:
            return
            
        # Move to position (offset by cursor size usually, but passed pos is card pos)
        # Position to the right of the cursor if possible, or left
        screen_geo = self.screen().availableGeometry()
        
        x = global_pos.x() + 20
        y = global_pos.y()
        
        if x + self.width() > screen_geo.right():
            x = global_pos.x() - self.width() - 20
            
        self.move(x, y)
        
        # Load media if changed
        if video_path != self.current_video_path:
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.current_video_path = video_path
            
        # Seek and play
        self.start_ms = int(start_time * 1000)
        self.media_player.setPosition(self.start_ms)
        self.media_player.play()
        
        self.loop_timer.start(100) # Check every 100ms
        self.show()
        
    def stop_preview(self):
        """Stop playback and hide the preview."""
        self.loop_timer.stop()
        self.media_player.stop()
        self.media_player.setPosition(0)
        self.hide()
    
    def hideEvent(self, event):
        """Ensure media stops when widget is hidden."""
        self.loop_timer.stop()
        self.media_player.stop()
        super().hideEvent(event)
    
    def leaveEvent(self, event):
        """Stop preview when mouse leaves the widget."""
        self.stop_preview()
        super().leaveEvent(event)
        
    def _check_loop(self):
        if self.media_player.position() > self.start_ms + self.duration_ms:
            self.media_player.setPosition(self.start_ms)
