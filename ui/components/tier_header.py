from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class TierHeader(QWidget):
    """
    Header for a severity tier group (e.g. SEVERE, MILD).
    Shows tier name, color, total count, and tier-wide actions.
    """
    
    keep_all_tier_requested = Signal()
    skip_all_tier_requested = Signal()
    
    def __init__(self, name: str, color: str, total_count: int, parent=None):
        super().__init__(parent)
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        
        # Color indicator
        indicator = QLabel("●")
        indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
        layout.addWidget(indicator)
        
        # Name
        name_label = QLabel(f"<b>{name.upper()}</b>")
        name_label.setStyleSheet("font-size: 13px; color: #333;")
        layout.addWidget(name_label)
        
        # Count
        count_label = QLabel(f"({total_count} detections)")
        count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(count_label)
        
        layout.addStretch()
        
        # Tier-level batch buttons
        # Keep All (Keep high severity or low severity)
        keep_btn = QPushButton(f"✓ Keep All")
        keep_btn.setCursor(Qt.PointingHandCursor)
        # Dynamic style based on tier color? Maybe too much rainbow.
        # Use standard green/red but maybe with colored border?
        keep_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #e6f4ea;
                color: #1e8e3e;
                border: 1px solid #1e8e3e;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #dcece0;
            }}
        """)
        keep_btn.clicked.connect(self.keep_all_tier_requested.emit)
        layout.addWidget(keep_btn)
        
        # Skip All
        skip_btn = QPushButton(f"✗ Delete All")
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #fce8e6;
                color: #d93025;
                border: 1px solid #d93025;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #f6dada;
            }}
        """)
        skip_btn.clicked.connect(self.skip_all_tier_requested.emit)
        layout.addWidget(skip_btn)
        
        # Styling for the container row
        # Add a subtle left border or background tint matching severity
        self.setStyleSheet(f"""
            TierHeader {{
                background-color: {color}15; /* 15 = ~8% opacity hex approx */
                border-left: 4px solid {color};
                margin-top: 12px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)
