from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from pathlib import Path


class ErrorDialog(QDialog):
    def __init__(self, title: str, message: str, details: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.details = details
        
        self._setup_ui(title, message)
    
    def _setup_ui(self, title: str, message: str):
        layout = QVBoxLayout(self)
        
        # Header with icon
        header = QHBoxLayout()
        
        icon_label = QLabel("⚠️")
        icon_label.setFont(QFont("Arial", 32))
        header.addWidget(icon_label)
        
        header.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f5f5f8;")
        header.addWidget(title_label)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Message
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("padding: 12px; background: #12121a; border-radius: 6px; color: #f5f5f8; border: 1px solid #282838;")
        layout.addWidget(message_label)
        
        # Expandable details
        if self.details:
            self.details_toggle = QCheckBox("Show technical details")
            self.details_toggle.toggled.connect(self._toggle_details)
            layout.addWidget(self.details_toggle)
            
            self.details_text = QTextEdit()
            self.details_text.setPlainText(self.details)
            self.details_text.setReadOnly(True)
            self.details_text.setMaximumHeight(150)
            self.details_text.setVisible(False)
            self.details_text.setStyleSheet("background: #0f0f14; color: #b0b0c0; border: 1px solid #282838; font-family: monospace; font-size: 11px;")
            layout.addWidget(self.details_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        if self.details:
            copy_btn = QPushButton("Copy Error")
            copy_btn.clicked.connect(self._copy_error)
            btn_layout.addWidget(copy_btn)
        
        log_btn = QPushButton("Open Log Folder")
        log_btn.clicked.connect(self._open_logs)
        btn_layout.addWidget(log_btn)
        
        btn_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def _toggle_details(self, checked):
        self.details_text.setVisible(checked)
        self.adjustSize()
    
    def _copy_error(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(f"{self.windowTitle()}\n\n{self.details}")
    
    def _open_logs(self):
        import subprocess
        import sys
        
        log_dir = Path.home() / ".videocensor" / "logs"
        
        if sys.platform == "darwin":
            subprocess.run(["open", str(log_dir)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(log_dir)])
        else:
            subprocess.run(["xdg-open", str(log_dir)])


def show_error(title: str, message: str, details: str = None, parent=None):
    """Convenience function to show error dialog"""
    dialog = ErrorDialog(title, message, details, parent)
    dialog.exec()
