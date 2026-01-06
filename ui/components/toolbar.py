"""
Processing Toolbar component.
Clean status bar for queue management.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


class ProcessingToolbar(QWidget):
    """Toolbar showing queue status and global controls."""
    
    pause_all_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Processing")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f5f5f8;")
        layout.addWidget(title)
        
        # Queue count - clear labeling
        self.queue_label = QLabel("0 of 0 complete")
        self.queue_label.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(self.queue_label)
        
        layout.addStretch()
        
        # Power mode indicator
        self.power_label = QLabel("⚡ Balanced")
        self.power_label.setToolTip("Processing mode (change in Edit > Preferences)")
        self.power_label.setStyleSheet("""
            background-color: #1f1f2e;
            padding: 6px 14px;
            border-radius: 14px;
            color: #a0a0b0;
            font-size: 11px;
            font-weight: 600;
        """)
        layout.addWidget(self.power_label)
        
        # Pause all button
        self.pause_all_btn = QPushButton("⏸ Pause")
        self.pause_all_btn.setFixedHeight(32)
        self.pause_all_btn.setFixedWidth(90)
        self.pause_all_btn.clicked.connect(self.pause_all_clicked.emit)
        self.pause_all_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #b0b0c0;
                border: 1px solid #303040;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #282840;
                border-color: #404060;
            }
        """)
        layout.addWidget(self.pause_all_btn)
        
        # Auto-sleep toggle
        self.sleep_btn = QPushButton("💤 Auto-Sleep")
        self.sleep_btn.setCheckable(True)
        self.sleep_btn.setToolTip("Put computer to sleep when queue completes")
        self.sleep_btn.setFixedHeight(32)
        self.sleep_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f2e;
                color: #71717a;
                border: 1px solid #303040;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:checked {
                background: #4c1d95;
                color: #ffffff;
                border: 1px solid #6d28d9;
            }
            QPushButton:hover {
                border-color: #404060;
            }
        """)
        layout.addWidget(self.sleep_btn)
    
    def set_queue_count(self, total: int, complete: int):
        """Update queue count display"""
        if total == 0:
            self.queue_label.setText("Queue empty")
        else:
            self.queue_label.setText(f"{complete} of {total} complete")
    
    def set_paused(self, paused: bool):
        """Update pause button state"""
        if paused:
            self.pause_all_btn.setText("▶ Resume")
            self.pause_all_btn.setStyleSheet("""
                QPushButton {
                    background: #1f2e1f;
                    color: #90d090;
                    border: 1px solid #304030;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #284028;
                }
            """)
        else:
            self.pause_all_btn.setText("⏸ Pause")
            self.pause_all_btn.setStyleSheet("""
                QPushButton {
                    background: #1f1f2e;
                    color: #b0b0c0;
                    border: 1px solid #303040;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #282840;
                    border-color: #404060;
                }
            """)
    
    def set_power_mode(self, mode: str):
        """Update power mode display"""
        icons = {
            "low_power": "🐢 Low Power",
            "balanced": "⚡ Balanced", 
            "high_performance": "🚀 Performance"
        }
        self.power_label.setText(icons.get(mode, mode))
