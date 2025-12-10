"""
Cinema-Themed Dark Stylesheet for Video Censor.

Movie theater inspired design with censor rating aesthetics,
film reel accents, and family-safe visual metaphors.
"""

# Cinema Color Palette
COLORS = {
    # Backgrounds - Deep theater blacks
    "bg_darkest": "#050507",
    "bg_dark": "#0a0a0e",
    "bg_panel": "#111116",
    "bg_card": "#161620",
    "bg_input": "#1a1a25",
    "bg_hover": "#1f1f2b",
    
    # Borders
    "border_dark": "#1c1c28",
    "border_medium": "#282838",
    "border_light": "#383850",
    
    # Text
    "fg_primary": "#f5f5f8",
    "fg_secondary": "#a8a8b8",
    "fg_muted": "#5a5a6a",
    
    # Cinema Accents
    "cinema_gold": "#d4af37",
    "cinema_red": "#c41e3a",
    "cinema_burgundy": "#722f37",
    
    # Rating Colors
    "rating_safe": "#2dd4bf",      # Teal - G/Family
    "rating_caution": "#fbbf24",   # Amber - PG
    "rating_warning": "#f97316",   # Orange - PG-13
    "rating_danger": "#ef4444",    # Red - R/Mature
    
    # Action Colors
    "accent_primary": "#6366f1",   # Indigo
    "accent_secondary": "#8b5cf6", # Purple
    "success": "#22c55e",
    "info": "#0ea5e9",
}

# Premium Cinema QSS Stylesheet
DARK_STYLESHEET = """
/* ============================================
   GLOBAL STYLES - Cinema Theme
   ============================================ */

* {
    font-family: "SF Pro Display", "Inter", "Segoe UI", sans-serif;
}

QMainWindow, QDialog {
    background: #050507;
    color: #f5f5f8;
}

QWidget {
    background-color: transparent;
    color: #f5f5f8;
    font-size: 13px;
}

/* ============================================
   TYPOGRAPHY - Movie Poster Style
   ============================================ */

QLabel {
    background: transparent;
    color: #f5f5f8;
}

QLabel[class="app-title"] {
    font-size: 36px;
    font-weight: 800;
    letter-spacing: -1px;
    color: #ffffff;
}

QLabel[class="app-subtitle"] {
    font-size: 13px;
    font-weight: 400;
    color: #5a5a6a;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QLabel[class="section-title"] {
    font-size: 16px;
    font-weight: 700;
    color: #f5f5f8;
    padding-bottom: 8px;
}

QLabel[class="helper"] {
    font-size: 11px;
    color: #5a5a6a;
}

/* ============================================
   CINEMA PANELS - Theater Card Style
   ============================================ */

QFrame {
    background-color: #111116;
    border: 1px solid #1c1c28;
    border-radius: 16px;
}

QFrame[class="panel"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #151520, stop:1 #111116);
    border: 1px solid #282838;
    border-radius: 20px;
    padding: 24px;
}

QFrame[class="panel"]:hover {
    border-color: #383850;
}

/* Drop Zone - Film Reel Style */
QFrame[class="drop-zone"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d0d12, stop:0.5 #0a0a0e, stop:1 #0d0d12);
    border: 2px dashed #383850;
    border-radius: 20px;
}

QFrame[class="drop-zone"]:hover {
    border-color: #6366f1;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #101018, stop:0.5 #0c0c14, stop:1 #101018);
}

/* Rating Badge Styles */
QLabel[class="badge-safe"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0d9488, stop:1 #14b8a6);
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
    text-transform: uppercase;
}

QLabel[class="badge-caution"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #d97706, stop:1 #f59e0b);
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
}

QLabel[class="badge-warning"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ea580c, stop:1 #f97316);
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
}

/* ============================================
   BUTTONS - Cinema Style
   ============================================ */

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6366f1, stop:1 #4f46e5);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #818cf8, stop:1 #6366f1);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4f46e5, stop:1 #4338ca);
}

QPushButton:disabled {
    background: #1c1c28;
    color: #4a4a5a;
}

/* Primary Action - Spotlight Gradient */
QPushButton[class="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:0.4 #8b5cf6, stop:1 #a855f7);
    font-size: 15px;
    font-weight: 700;
    padding: 16px 32px;
    border-radius: 12px;
    letter-spacing: 0.5px;
}

QPushButton[class="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #818cf8, stop:0.4 #a78bfa, stop:1 #c084fc);
}

/* Secondary Button - Theater Outline */
QPushButton[class="secondary"] {
    background: transparent;
    border: 1px solid #383850;
    color: #a8a8b8;
}

QPushButton[class="secondary"]:hover {
    background-color: #1a1a25;
    border-color: #4a4a60;
    color: #f5f5f8;
}

/* Link Button */
QPushButton[class="link"] {
    background: transparent;
    border: none;
    color: #6366f1;
    padding: 4px 8px;
    font-weight: 500;
}

QPushButton[class="link"]:hover {
    color: #818cf8;
}

/* ============================================
   INPUTS - Cinematic Style
   ============================================ */

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #1a1a25;
    border: 1px solid #282838;
    border-radius: 10px;
    padding: 12px 16px;
    color: #f5f5f8;
    selection-background-color: #6366f1;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #6366f1;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {
    border-color: #383850;
}

QPlainTextEdit {
    font-family: "SF Mono", "JetBrains Mono", monospace;
    font-size: 12px;
}

/* ============================================
   COMBO BOX - Film Selector Style
   ============================================ */

QComboBox {
    background-color: #1a1a25;
    border: 1px solid #282838;
    border-radius: 10px;
    padding: 10px 16px;
    padding-right: 36px;
    color: #f5f5f8;
    min-width: 160px;
}

QComboBox:hover {
    border-color: #383850;
}

QComboBox:focus {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #5a5a6a;
}

QComboBox QAbstractItemView {
    background-color: #161620;
    border: 1px solid #282838;
    border-radius: 10px;
    padding: 6px;
    selection-background-color: #6366f1;
}

/* ============================================
   CHECKBOXES & RADIOS - Rating Toggle Style
   ============================================ */

QCheckBox, QRadioButton {
    spacing: 12px;
    color: #f5f5f8;
    padding: 6px 0;
}

QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 2px solid #383850;
    border-radius: 6px;
    background-color: #1a1a25;
}

QCheckBox::indicator:hover {
    border-color: #4a4a60;
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6366f1, stop:1 #8b5cf6);
    border-color: #6366f1;
}

QRadioButton::indicator {
    width: 22px;
    height: 22px;
    border: 2px solid #383850;
    border-radius: 11px;
    background-color: #1a1a25;
}

QRadioButton::indicator:hover {
    border-color: #4a4a60;
}

QRadioButton::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6366f1, stop:1 #8b5cf6);
    border-color: #6366f1;
}

/* Disabled state */
QCheckBox:disabled, QRadioButton:disabled {
    color: #4a4a5a;
}

/* ============================================
   GROUP BOXES - Content Rating Sections
   ============================================ */

QGroupBox {
    background-color: #161620;
    border: 1px solid #282838;
    border-radius: 14px;
    margin-top: 24px;
    padding: 24px 18px 18px 18px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 18px;
    top: 10px;
    padding: 0 10px;
    color: #f5f5f8;
    background-color: #161620;
}

/* ============================================
   SCROLL AREAS - Smooth Cinema Scroll
   ============================================ */

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background-color: #0a0a0e;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #282838;
    border-radius: 4px;
    min-height: 50px;
}

QScrollBar::handle:vertical:hover {
    background-color: #383850;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ============================================
   PROGRESS BAR - Film Strip Style
   ============================================ */

QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #1c1c28;
    height: 12px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #a855f7);
    border-radius: 6px;
}

/* ============================================
   LIST WIDGET - Movie Queue Style
   ============================================ */

QListWidget {
    background-color: #111116;
    border: 1px solid #282838;
    border-radius: 14px;
    outline: none;
    padding: 6px;
}

QListWidget::item {
    background-color: transparent;
    padding: 10px 14px;
    border-radius: 10px;
    margin: 3px 0;
}

QListWidget::item:selected {
    background-color: #1a1a25;
    border-left: 4px solid #6366f1;
}

QListWidget::item:hover:!selected {
    background-color: #161620;
}

/* ============================================
   TOOL TIP - Cinema Info Card
   ============================================ */

QToolTip {
    background-color: #1f1f2b;
    color: #f5f5f8;
    border: 1px solid #383850;
    padding: 10px 14px;
    border-radius: 10px;
}

/* ============================================
   STATUS INDICATORS
   ============================================ */

QLabel[class="status-idle"] {
    background: #1c1c28;
    color: #5a5a6a;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid #282838;
}

QLabel[class="status-processing"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #8b5cf6);
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
}

QLabel[class="status-complete"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #059669, stop:1 #10b981);
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
}
"""
