from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt, Signal

class DetectionGroupHeader(QWidget):
    """
    Collapsible header for grouped detections.
    Provides batch keep/skip actions (Keep All / Skip All).
    """
    
    # Signals for batch actions
    keep_all_requested = Signal(str) # Emits the word/group name
    skip_all_requested = Signal(str) # Emits the word/group name
    
    def __init__(self, word: str, count: int, color: str = "#ccc", parent=None):
        super().__init__(parent)
        self.word = word
        self.count = count
        self.expanded = False # Start collapsed by default for better overview
        self.children_cards = []
        
        # Style
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            DetectionGroupHeader {
                background-color: transparent;
                border: none;
                margin-top: 2px;
            }
            QPushButton#toggleBtn {
                border: none;
                background: transparent;
                font-weight: bold;
                color: #555;
            }
            QPushButton#toggleBtn:hover {
                color: #000;
            }
            QLabel {
                font-size: 13px;
                color: #333;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 2, 8, 2) # Indent left
        
        # Apply color border
        self.setStyleSheet(self.styleSheet() + f"DetectionGroupHeader {{ border-left: 2px solid {color}; }}")
        
        # Expand/collapse toggle
        self.toggle_btn = QPushButton("▶") # Default collapsed
        self.toggle_btn.setObjectName("toggleBtn")
        self.toggle_btn.setFixedWidth(24)
        self.toggle_btn.clicked.connect(self._toggle_expand)
        layout.addWidget(self.toggle_btn)
        
        # Word label
        word_label = QLabel(f"<b>{word}</b>")
        layout.addWidget(word_label)
        
        # Count badge
        count_label = QLabel(f"({count} items)")
        count_label.setStyleSheet("color: #666;")
        layout.addWidget(count_label)
        
        layout.addStretch()
        
        # Batch action buttons
        # Keep All
        keep_btn = QPushButton("✓ Keep All")
        keep_btn.setCursor(Qt.PointingHandCursor)
        keep_btn.setStyleSheet("""
            QPushButton {
                background-color: #e6f4ea;
                color: #1e8e3e;
                border: 1px solid #1e8e3e;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #dcece0;
            }
        """)
        keep_btn.clicked.connect(lambda: self.keep_all_requested.emit(self.word))
        layout.addWidget(keep_btn)
        
        # Skip All
        skip_btn = QPushButton("✗ Delete All")
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #fce8e6;
                color: #d93025;
                border: 1px solid #d93025;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f6dada;
            }
        """)
        skip_btn.clicked.connect(lambda: self.skip_all_requested.emit(self.word))
        layout.addWidget(skip_btn)
        
    def add_child_card(self, card):
        """Register a child card to be toggled."""
        self.children_cards.append(card)
        # Assuming card is already added to the parent layout elsewhere
        
    def set_expanded(self, expanded: bool):
        """Set expansion state."""
        self.expanded = expanded
        self.toggle_btn.setText("▼" if self.expanded else "▶")
        for card in self.children_cards:
            card.setVisible(self.expanded)
            
    def _toggle_expand(self):
        """Toggle expansion state."""
        self.set_expanded(not self.expanded)
