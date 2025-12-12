"""
Search Tab for querying the Cloud Database.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QColor

from video_censor.cloud_db import get_cloud_client

class SearchWorker(QThread):
    """Background thread for executing searches."""
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

class SearchResultWidget(QFrame):
    """Widget displaying a single search result."""
    
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #181820; border-radius: 8px;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header: Title + Date
        header = QHBoxLayout()
        title = QLabel(data.get('title', 'Unknown'))
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: white; background: transparent;")
        header.addWidget(title)
        
        date_str = data.get('created_at', '')[:10]
        date_lbl = QLabel(date_str)
        date_lbl.setStyleSheet("color: #71717a; font-size: 11px; background: transparent;")
        header.addWidget(date_lbl)
        
        layout.addLayout(header)
        
        # Stats Row
        stats = QHBoxLayout()
        stats.setSpacing(16)
        
        nudity_count = len(data.get('nudity_segments', []) or [])
        profanity_count = len(data.get('profanity_segments', []) or [])
        sexual_count = len(data.get('sexual_content_segments', []) or [])
        violence_count = len(data.get('violence_segments', []) or [])
        
        self._add_stat(stats, "Nudity", nudity_count, "#f43f5e" if nudity_count > 0 else "#22c55e")
        self._add_stat(stats, "Profanity", profanity_count, "#fbbf24" if profanity_count > 0 else "#22c55e")
        self._add_stat(stats, "Sexual", sexual_count, "#d946ef" if sexual_count > 0 else "#22c55e")
        # Violence is optional/beta, usually huge numbers
        if violence_count > 0:
            self._add_stat(stats, "Violence", violence_count, "#ef4444")
            
        stats.addStretch()
        layout.addLayout(stats)
        
        # Timeline (Lazy loaded)
        self.timeline_container = QWidget()
        self.timeline_container.hide()
        layout.addWidget(self.timeline_container)
        
        self.data = data
        self.is_expanded = False
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_expand()
            
    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            if not self.timeline_container.layout():
                # Lazy load timeline
                from .timeline import TimelineWidget
                tl_layout = QVBoxLayout(self.timeline_container)
                tl_layout.setContentsMargins(0, 10, 0, 0)
                
                timeline = TimelineWidget()
                
                # Format data
                duration = self.data.get('duration_seconds', 0)
                formatted_data = {
                    'nudity': self.data.get('nudity_segments'),
                    'profanity': self.data.get('profanity_segments'),
                    'sexual_content': self.data.get('sexual_content_segments'),
                    'violence': self.data.get('violence_segments'),
                }
                
                timeline.set_data(duration, formatted_data)
                tl_layout.addWidget(timeline)
                
            self.timeline_container.show()
            self.setStyleSheet("background: #20202a; border-radius: 8px; border: 1px solid #3b82f6;")
        else:
            self.timeline_container.hide()
            self.setStyleSheet("background: #181820; border-radius: 8px;")
    def _add_stat(self, layout, label, count, color):
        lbl = QLabel(f"{label}: {count}")
        lbl.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 12px; background: transparent;")
        layout.addWidget(lbl)


class SearchTab(QWidget):
    """Tab for searching the cloud database."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.current_worker = None
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 20)
        
        # Header
        header_lbl = QLabel("☁️  Cloud Search")
        header_lbl.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        layout.addWidget(header_lbl)
        
        desc = QLabel("Check if a movie is safe before you download. Search our crowdsourced database.")
        desc.setStyleSheet("font-size: 13px; color: #a1a1aa;")
        layout.addWidget(desc)
        
        # Search Bar
        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter movie title...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #181820;
                color: white;
                border: 1px solid #272730;
                border-radius: 6px;
                padding: 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self.search_input)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(100)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
        """)
        self.search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_btn)
        
        layout.addLayout(search_row)
        
        # Results Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(12)
        self.results_layout.addStretch()
        
        self.scroll.setWidget(self.results_container)
        layout.addWidget(self.scroll)
        
        # Loading indicator
        self.loader = QLabel("Searching...")
        self.loader.setAlignment(Qt.AlignCenter)
        self.loader.setStyleSheet("color: #71717a; font-size: 14px;")
        self.loader.hide()
        # Insert loader above scroll view or overlay it? 
        # For simplicity, we'll swap visibility or just add to layout temporarily.
        # Actually, let's just use empty state text in the container
        
        # Initial empty state
        self._show_message("Search for a movie to see detection results.")
        
    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        self.search_input.setEnabled(False)
        self.search_btn.setEnabled(False)
        self._clear_results()
        self._show_message("Searching cloud database...")
        
        self.current_worker = SearchWorker(query)
        self.current_worker.finished.connect(self._on_search_finished)
        self.current_worker.error.connect(self._on_search_error)
        self.current_worker.start()
        
    def _on_search_finished(self, results):
        self.search_input.setEnabled(True)
        self.search_btn.setEnabled(True)
        self._clear_results()
        
        if not results:
            self._show_message(f"No results found for '{self.search_input.text()}'.")
            return
            
        # Add results
        # Remove the stretch item at the end first
        self._remove_stretch()
            
        for data in results:
            widget = SearchResultWidget(data)
            self.results_layout.addWidget(widget)
            
        self.results_layout.addStretch()
        
    def _on_search_error(self, error):
        self.search_input.setEnabled(True)
        self.search_btn.setEnabled(True)
        self._clear_results()
        self._show_message(f"Error: {error}")
        
    def _clear_results(self):
        # Remove all widgets from layout
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # self._clear_layout(item.layout())
                pass
                
    def _show_message(self, text):
        self._clear_results()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #71717a; font-size: 14px; padding: 40px;")
        self.results_layout.addWidget(lbl)
        self.results_layout.addStretch()
        
    def _remove_stretch(self):
        # A simple hack to remove the last stretch item if present is tricky without logic
        # But _clear_results removes everything anyway, so we are fine.
        pass
