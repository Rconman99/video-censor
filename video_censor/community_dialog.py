"""
Community Timestamps Dialog - Browse and use crowd-sourced censor timestamps.

Part of the Video Censor V2 Community Features.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QFrame, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from video_censor.cloud_db import get_cloud_client, DetectionResult
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CINEMA THEME CONSTANTS
# =============================================================================
COLORS = {
    'bg_dark': '#0a0a0f',
    'bg_card': '#12121a',
    'bg_hover': '#1a1a25',
    'accent': '#6366f1',
    'accent_hover': '#818cf8',
    'success': '#22c55e',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'text_primary': '#f8fafc',
    'text_secondary': '#94a3b8',
    'border': '#1e293b',
}


class SearchWorker(QThread):
    """Background worker for searching community timestamps."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query
    
    def run(self):
        try:
            client = get_cloud_client()
            results = client.search_videos(self.query)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class CommunityDialog(QDialog):
    """
    Browse and search community-contributed timestamps.
    
    Users can:
    - Search for movies by title
    - View contributor trust scores and vote counts
    - One-click apply timestamps to skip local processing
    """
    
    timestamps_selected = Signal(dict)  # Emits selected detection data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Community Timestamps")
        self.setMinimumSize(700, 500)
        self._search_worker = None
        self._selected_result = None
        
        self._setup_ui()
        self._apply_styles()
        self._load_stats()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("Community Timestamps Library")
        header.setFont(QFont("Inter", 18, QFont.Bold))
        header.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(header)
        
        subtitle = QLabel("Browse crowd-sourced censor timestamps from other users")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(subtitle)
        
        # Stats bar
        self.stats_label = QLabel("Loading community stats...")
        self.stats_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 12px;
            padding: 8px 12px;
            background: {COLORS['bg_card']};
            border-radius: 6px;
        """)
        layout.addWidget(self.stats_label)
        
        # Search bar
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by movie title...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 12px 16px;
                font-size: 14px;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        search_layout.addWidget(self.search_input)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                background: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_hover']};
            }}
            QPushButton:disabled {{
                background: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
        """)
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Title", "Duration", "Segments", "Score", "Date"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.results_table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text_primary']};
                gridline-color: {COLORS['border']};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background: {COLORS['accent']};
            }}
            QHeaderView::section {{
                background: {COLORS['bg_dark']};
                color: {COLORS['text_secondary']};
                padding: 10px;
                border: none;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.results_table)
        
        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.contributor_btn = QPushButton("📊 My Contributions")
        self.contributor_btn.clicked.connect(self._show_contributor_stats)
        self.contributor_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 16px;
                font-size: 13px;
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_hover']};
                color: {COLORS['text_primary']};
            }}
        """)
        btn_layout.addWidget(self.contributor_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 24px;
                font-size: 13px;
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_hover']};
            }}
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        self.use_btn = QPushButton("Use These Timestamps")
        self.use_btn.setEnabled(False)
        self.use_btn.clicked.connect(self._on_use_selected)
        self.use_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 600;
                background: {COLORS['success']};
                color: white;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: #16a34a;
            }}
            QPushButton:disabled {{
                background: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
        """)
        btn_layout.addWidget(self.use_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        """Apply overall dialog styling."""
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['bg_dark']};
            }}
        """)
    
    def _load_stats(self):
        """Load and display community statistics."""
        try:
            client = get_cloud_client()
            stats = client.get_stats()
            if stats.get('available'):
                total = stats.get('total_videos', 0)
                self.stats_label.setText(
                    f"📚 {total:,} videos in library  •  "
                    f"💡 Timestamps are crowd-sourced by the community"
                )
            else:
                self.stats_label.setText("⚠️ Community database unavailable")
        except Exception as e:
            self.stats_label.setText(f"⚠️ Could not load stats: {e}")
    
    def _on_search(self):
        """Handle search button click."""
        query = self.search_input.text().strip()
        if not query:
            return
        
        self.search_btn.setEnabled(False)
        self.progress.show()
        self.results_table.setRowCount(0)
        
        self._search_worker = SearchWorker(query)
        self._search_worker.finished.connect(self._on_search_complete)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()
    
    def _on_search_complete(self, results: List[Dict[str, Any]]):
        """Handle search results."""
        self.search_btn.setEnabled(True)
        self.progress.hide()
        
        self.results_table.setRowCount(len(results))
        self._search_results = results
        
        for row, result in enumerate(results):
            # Title
            title = result.get('title', 'Unknown')
            self.results_table.setItem(row, 0, QTableWidgetItem(title))
            
            # Duration
            duration = result.get('duration_seconds', 0)
            mins = int(duration // 60)
            secs = int(duration % 60)
            self.results_table.setItem(row, 1, QTableWidgetItem(f"{mins}:{secs:02d}"))
            
            # Segment count
            nudity = len(result.get('nudity_segments', []))
            profanity = len(result.get('profanity_segments', []))
            sexual = len(result.get('sexual_content_segments', []))
            total_segments = nudity + profanity + sexual
            self.results_table.setItem(row, 2, QTableWidgetItem(str(total_segments)))
            
            # Quality score
            upvotes = result.get('upvotes', 0)
            downvotes = result.get('downvotes', 0)
            score = upvotes - downvotes
            score_text = f"+{score}" if score > 0 else str(score)
            score_item = QTableWidgetItem(score_text)
            if score > 0:
                score_item.setForeground(Qt.green)
            elif score < 0:
                score_item.setForeground(Qt.red)
            self.results_table.setItem(row, 3, score_item)
            
            # Date
            created = result.get('created_at', '')
            if created:
                date_str = created[:10]  # YYYY-MM-DD
            else:
                date_str = "—"
            self.results_table.setItem(row, 4, QTableWidgetItem(date_str))
        
        if not results:
            self.stats_label.setText("No results found. Try a different search term.")
    
    def _on_search_error(self, error: str):
        """Handle search error."""
        self.search_btn.setEnabled(True)
        self.progress.hide()
        self.stats_label.setText(f"⚠️ Search error: {error}")
    
    def _on_selection_changed(self):
        """Handle table selection change."""
        selected = self.results_table.selectedItems()
        self.use_btn.setEnabled(len(selected) > 0)
        
        if selected:
            row = selected[0].row()
            self._selected_result = self._search_results[row]
    
    def _on_use_selected(self):
        """Use the selected timestamps."""
        if self._selected_result:
            self.timestamps_selected.emit(self._selected_result)
            self.accept()
    
    def _show_contributor_stats(self):
        """Show the current user's contribution statistics."""
        try:
            client = get_cloud_client()
            stats = client.get_contributor_stats()
            
            if stats:
                msg = (
                    f"<h3>Your Contributions</h3>"
                    f"<p><b>Contributor ID:</b> {stats['contributor_id']}</p>"
                    f"<p><b>Trust Score:</b> {stats['trust_score']:.1f}</p>"
                    f"<p><b>Videos Contributed:</b> {stats['contribution_count']}</p>"
                    f"<p><b>Helpful Votes:</b> {stats['helpful_votes']}</p>"
                    f"<p><b>Member Since:</b> {stats.get('member_since', 'Unknown')[:10]}</p>"
                )
                QMessageBox.information(self, "Your Contributions", msg)
            else:
                QMessageBox.information(
                    self, 
                    "Your Contributions", 
                    "You haven't contributed any timestamps yet.\n\n"
                    "Process a video and enable 'Contribute to Community' to share your timestamps!"
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load stats: {e}")


class CommunityStatusBanner(QFrame):
    """
    Small banner showing community timestamp availability.
    Displayed in the queue item when community data is available.
    """
    
    use_community = Signal()
    
    def __init__(self, detection: DetectionResult, parent=None):
        super().__init__(parent)
        self.detection = detection
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Icon and text
        icon = QLabel("✓")
        icon.setStyleSheet(f"color: {COLORS['success']}; font-size: 14px;")
        layout.addWidget(icon)
        
        text = QLabel(f"Community timestamps available (score: {self.detection.quality_score:.1f})")
        text.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        layout.addWidget(text)
        
        layout.addStretch()
        
        # Use button
        use_btn = QPushButton("Use")
        use_btn.clicked.connect(self.use_community.emit)
        use_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 4px 12px;
                font-size: 11px;
                background: {COLORS['success']};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: #16a34a;
            }}
        """)
        layout.addWidget(use_btn)
        
        # Style the frame
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['success']};
                border-radius: 6px;
            }}
        """)
