#!/usr/bin/env python3
"""
Video Censor GUI Application
A macOS desktop app with drag-and-drop, preference manager, and queue for video censoring.
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional
import time

# Force dark appearance on macOS
if sys.platform == 'darwin':
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    # Try to set dark mode via defaults
    try:
        subprocess.run(['defaults', 'write', '-g', 'NSRequiresAquaSystemAppearance', '-bool', 'No'], 
                       capture_output=True, timeout=2)
    except:
        pass

# Add package to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from video_censor.preferences import ContentFilterSettings, Profile
from video_censor.profile_manager import ProfileManager
from video_censor.queue import QueueItem, ProcessingQueue
from video_censor.profile_dialog import ProfileDialog
from video_censor.widgets import ModernToggle, GradientProgressBar, ModernFilterRow, StatusDot
from video_censor.config import Config
from video_censor.content_lookup import IMDbClient, DoesTheDogDieClient, MovieContentInfo, Severity, ContentCategory

# Paths
VENV_PYTHON = str(Path(__file__).parent / "venv" / "bin" / "python")
CENSOR_SCRIPT = str(Path(__file__).parent / "censor_video.py")
OUTPUT_DIR = "/Volumes/20tb/cleanmovies"

# Supported video formats
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm')


class PreferencePanel(tk.Frame):
    """
    Preference Manager panel for configuring filters before processing.
    
    Shows video summary, profile selection, and per-video filter overrides.
    """
    
    def __init__(self, parent, profile_manager: ProfileManager, on_start_callback):
        super().__init__(parent, bg="#141419", highlightbackground="#2a2a35", highlightthickness=1)
        
        self.profile_manager = profile_manager
        self.on_start_callback = on_start_callback
        
        # Premium color palette
        self.bg_color = "#141419"
        self.fg_color = "#f0f0f5"
        self.accent_color = "#3b82f6"
        self.accent_secondary = "#8b5cf6"
        self.muted_color = "#71717a"
        self.dark_bg = "#0a0a0f"
        self.border_color = "#2a2a35"
        self.success_color = "#22c55e"
        
        # State
        self.current_video_path: Optional[Path] = None
        self.current_video_size: int = 0
        self.current_video_duration: float = 0.0
        self.content_info: Optional[MovieContentInfo] = None
        self._lookup_thread: Optional[threading.Thread] = None
        
        # Load config for API keys
        config_path = Path(__file__).parent / "config.yaml"
        self.config = Config.load(config_path)
        
        self._create_ui()
        self._set_empty_state()
    
    def _create_ui(self) -> None:
        """Build the preference panel UI."""
        # Title
        title = tk.Label(
            self,
            text="Preference Manager",
            font=("SF Pro Display", 14, "bold"),
            bg=self.bg_color,
            fg=self.fg_color,
            padx=15,
            pady=10
        )
        title.pack(anchor="w")
        
        # Video info section
        self.video_frame = tk.Frame(self, bg=self.bg_color, padx=15)
        self.video_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Video icon and name
        self.video_icon = tk.Label(
            self.video_frame,
            text="📹",
            font=("SF Pro Display", 32),
            bg=self.bg_color,
            fg=self.fg_color
        )
        self.video_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        video_info = tk.Frame(self.video_frame, bg=self.bg_color)
        video_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.video_name = tk.Label(
            video_info,
            text="No video selected",
            font=("SF Pro Display", 13, "bold"),
            bg=self.bg_color,
            fg=self.fg_color,
            anchor="w"
        )
        self.video_name.pack(fill=tk.X)
        
        self.video_details = tk.Label(
            video_info,
            text="Drop or browse to add a video",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color,
            anchor="w"
        )
        self.video_details.pack(fill=tk.X)
        
        # Content Warnings section (collapsible)
        self._create_content_warnings_section(self)
        
        # Separator
        tk.Frame(self, bg=self.border_color, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        # Profile selection section
        profile_section = tk.Frame(self, bg=self.bg_color, padx=15)
        profile_section.pack(fill=tk.X)
        
        tk.Label(
            profile_section,
            text="Profile",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w")
        
        profile_row = tk.Frame(profile_section, bg=self.bg_color)
        profile_row.pack(fill=tk.X, pady=(5, 0))
        
        self.profile_var = tk.StringVar(value="Default")
        self.profile_dropdown = ttk.Combobox(
            profile_row,
            textvariable=self.profile_var,
            values=self.profile_manager.list_names(),
            state="readonly",
            font=("SF Pro Display", 12),
            width=20
        )
        self.profile_dropdown.pack(side=tk.LEFT)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self._on_profile_change)
        
        self.manage_btn = tk.Button(
            profile_row,
            text="⚙",
            font=("SF Pro Display", 14),
            bg=self.bg_color,
            fg=self.muted_color,
            activebackground=self.bg_color,
            activeforeground=self.accent_color,
            relief=tk.FLAT,
            command=self._on_manage_profiles
        )
        self.manage_btn.pack(side=tk.LEFT, padx=5)
        
        # Hint text
        self.hint_label = tk.Label(
            profile_section,
            text="Choose a profile or customize filters below",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        )
        self.hint_label.pack(anchor="w", pady=(5, 0))
        
        # Filter controls section
        tk.Frame(self, bg=self.border_color, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        filters_frame = tk.Frame(self, bg=self.bg_color, padx=15)
        filters_frame.pack(fill=tk.X)
        
        tk.Label(
            filters_frame,
            text="Content Filters",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", pady=(0, 4))
        
        # Helper text
        tk.Label(
            filters_frame,
            text="Filters apply equally to all characters and relationships",
            font=("SF Pro Display", 9),
            bg=self.bg_color,
            fg="#52525b"
        ).pack(anchor="w", pady=(0, 12))
        
        # Filter toggle variables
        self.var_language = tk.BooleanVar(value=True)
        self.var_sexual = tk.BooleanVar(value=True)
        self.var_nudity = tk.BooleanVar(value=True)
        self.var_mature = tk.BooleanVar(value=False)
        self.var_romance = tk.IntVar(value=0)
        self.var_violence = tk.IntVar(value=0)
        self.var_safe_cover = tk.BooleanVar(value=False)
        self.var_force_subtitles = tk.BooleanVar(value=False)
        self.var_censor_subtitles = tk.BooleanVar(value=True)
        self.var_video_format = tk.StringVar(value="mp4")
        
        # Modern filter rows with toggle switches
        ModernFilterRow(
            filters_frame,
            text="Language (profanity & slurs)",
            variable=self.var_language,
            emoji="🔇",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color
        ).pack(fill=tk.X)
        
        ModernFilterRow(
            filters_frame,
            text="Sexual Content (dialogue)",
            variable=self.var_sexual,
            emoji="💬",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color
        ).pack(fill=tk.X)
        
        ModernFilterRow(
            filters_frame,
            text="Nudity (visual)",
            variable=self.var_nudity,
            emoji="👁",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color
        ).pack(fill=tk.X)
        
        # Romance level segmented control
        romance_frame = tk.Frame(filters_frame, bg=self.bg_color)
        romance_frame.pack(fill=tk.X, pady=(12, 4))
        
        tk.Label(
            romance_frame,
            text="💕  Romance Intensity",
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        romance_controls = tk.Frame(romance_frame, bg=self.dark_bg, padx=2, pady=2)
        romance_controls.pack(side=tk.RIGHT)
        
        romance_labels = [("Keep", 0), ("Heavy", 1), ("Strict", 2)]
        for label, value in romance_labels:
            rb = tk.Radiobutton(
                romance_controls,
                text=label,
                variable=self.var_romance,
                value=value,
                font=("SF Pro Display", 10),
                bg=self.dark_bg,
                fg=self.fg_color,
                selectcolor=self.accent_color,
                activebackground=self.dark_bg,
                activeforeground=self.fg_color,
                indicatoron=0,
                padx=8,
                pady=3,
                relief=tk.FLAT,
                highlightthickness=0
            )
            rb.pack(side=tk.LEFT)
        
        # Violence level segmented control
        violence_frame = tk.Frame(filters_frame, bg=self.bg_color)
        violence_frame.pack(fill=tk.X, pady=(8, 4))
        
        tk.Label(
            violence_frame,
            text="🗡  Violence Intensity",
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        violence_controls = tk.Frame(violence_frame, bg=self.dark_bg, padx=2, pady=2)
        violence_controls.pack(side=tk.RIGHT)
        
        violence_labels = [("Keep", 0), ("Gore", 1), ("Death", 2), ("Fight", 3)]
        for label, value in violence_labels:
            rb = tk.Radiobutton(
                violence_controls,
                text=label,
                variable=self.var_violence,
                value=value,
                font=("SF Pro Display", 10),
                bg=self.dark_bg,
                fg=self.fg_color,
                selectcolor=self.accent_color,
                activebackground=self.dark_bg,
                activeforeground=self.fg_color,
                indicatoron=0,
                padx=8,
                pady=3,
                relief=tk.FLAT,
                highlightthickness=0
            )
            rb.pack(side=tk.LEFT)
        
        # Mature themes (disabled)
        ModernFilterRow(
            filters_frame,
            text="Mature Themes",
            variable=self.var_mature,
            emoji="🚫",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color,
            disabled=True
        ).pack(fill=tk.X, pady=(8, 0))
        
        # Save as defaults link
        self.save_defaults_btn = tk.Button(
            filters_frame,
            text="💾 Save as profile defaults",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.accent_color,
            activebackground=self.bg_color,
            activeforeground="#3a8adf",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_save_defaults
        )
        self.save_defaults_btn.pack(anchor="w", pady=(10, 0))
        
        # Custom phrases collapsible section
        self._create_custom_phrases_section(filters_frame)
        
        # Subtitles section
        self._create_subtitles_section(filters_frame)
        
        # Safe Cover section
        self._create_safe_cover_section(filters_frame)

        # Output Quality section
        tk.Frame(self, bg=self.border_color, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        self.quality_frame = tk.Frame(self, bg=self.bg_color, padx=15)
        self.quality_frame.pack(fill=tk.X)
        
        tk.Label(
            self.quality_frame,
            text="Output Quality",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w")
        
        # Quality Mode (CRF vs Target Size)
        mode_row = tk.Frame(self.quality_frame, bg=self.bg_color)
        mode_row.pack(fill=tk.X, pady=(8, 0))
        
        self.var_quality_mode = tk.StringVar(value="crf")
        
        # Radio buttons for mode
        tk.Radiobutton(
            mode_row,
            text="Quality Priority (CRF)",
            variable=self.var_quality_mode,
            value="crf",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color,
            selectcolor=self.accent_color,
            activebackground=self.bg_color,
            activeforeground=self.fg_color,
            command=self._update_quality_ui
        ).pack(side=tk.LEFT)
        
        tk.Radiobutton(
            mode_row,
            text="Target File Size",
            variable=self.var_quality_mode,
            value="target_size",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color,
            selectcolor=self.accent_color,
            activebackground=self.bg_color,
            activeforeground=self.fg_color,
            command=self._update_quality_ui
        ).pack(side=tk.LEFT, padx=(15, 0))
        
        # Controls Row (Dynamic)
        controls_row = tk.Frame(self.quality_frame, bg=self.bg_color)
        controls_row.pack(fill=tk.X, pady=(8, 0))
        
        # CRF Control Frame
        self.crf_frame = tk.Frame(controls_row, bg=self.bg_color)
        
        tk.Label(
            self.crf_frame,
            text="CRF Value:",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.var_crf = tk.IntVar(value=23)
        self.crf_scale = tk.Scale(
            self.crf_frame,
            from_=18,
            to=35,
            orient=tk.HORIZONTAL,
            variable=self.var_crf,
            bg=self.bg_color,
            fg=self.fg_color,
            highlightthickness=0,
            length=150,
            command=lambda v: self.crf_value_label.config(text=str(int(float(v))))
        )
        self.crf_scale.pack(side=tk.LEFT, padx=(5, 5))
        
        self.crf_value_label = tk.Label(
            self.crf_frame,
            text="23",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.accent_color,
            width=3
        )
        self.crf_value_label.pack(side=tk.LEFT)
        
        tk.Label(
            self.crf_frame,
            text="(Lower is better)",
            font=("SF Pro Display", 9),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # Target Size Control Frame
        self.size_frame = tk.Frame(controls_row, bg=self.bg_color)
        
        tk.Label(
            self.size_frame,
            text="Target Size:",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.var_target_size = tk.StringVar(value="100")
        
        self.size_entry = tk.Entry(
            self.size_frame,
            textvariable=self.var_target_size,
            font=("SF Pro Display", 11),
            bg=self.dark_bg,
            fg=self.fg_color,
            width=6,
            relief=tk.FLAT,
            justify="center"
        )
        self.size_entry.pack(side=tk.LEFT, padx=(5, 5))
        
        tk.Label(
            self.size_frame,
            text="MB",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        # Encoding Speed Row
        speed_row = tk.Frame(self.quality_frame, bg=self.bg_color)
        speed_row.pack(fill=tk.X, pady=(8, 0))
        
        tk.Label(
            speed_row,
            text="Encoding Speed:",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.var_speed = tk.StringVar(value="medium")
        speed_options = ["veryslow", "slower", "slow", "medium", "fast", "faster", "veryfast", "superfast", "ultrafast"]
        
        self.speed_combo = ttk.Combobox(
            speed_row,
            textvariable=self.var_speed,
            values=speed_options,
            state="readonly",
            font=("SF Pro Display", 11),
            width=10
        )
        self.speed_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        tk.Label(
            speed_row,
            text="(Slower = better compression)",
            font=("SF Pro Display", 9, "italic"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        
        # Initialize values from config
        self.var_quality_mode.set(self.config.output.quality_mode)
        self.var_crf.set(self.config.output.video_crf)
        self.crf_value_label.config(text=str(self.config.output.video_crf))
        self.var_target_size.set(str(self.config.output.target_size_mb))
        self.var_speed.set(self.config.output.encoding_speed)
        
        # Trigger UI update
        self._update_quality_ui()

        # Output Folder section
        tk.Frame(self, bg=self.border_color, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        self.output_frame = tk.Frame(self, bg=self.bg_color, padx=15)
        self.output_frame.pack(fill=tk.X)
        
        tk.Label(
            self.output_frame,
            text="Output Folder",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w")
        
        output_row = tk.Frame(self.output_frame, bg=self.bg_color)
        output_row.pack(fill=tk.X, pady=(5, 0))
        
        # Format selection (Video Type Converter)
        format_frame = tk.Frame(output_row, bg=self.bg_color)
        format_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        tk.Label(
            format_frame,
            text="Format:",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.format_dropdown = ttk.Combobox(
            format_frame,
            textvariable=self.var_video_format,
            values=["mp4", "mkv", "avi", "mov"],
            state="readonly",
            font=("SF Pro Display", 11),
            width=5
        )
        self.format_dropdown.pack(side=tk.LEFT)
        
        # Initialize output_dir from config
        self.output_dir = self.config.output.custom_output_dir
        
        self.output_path_var = tk.StringVar(value=self.output_dir if self.output_dir else "Default (Same as input or configured)")
        
        self.output_entry = tk.Entry(
            output_row,
            textvariable=self.output_path_var,
            font=("SF Pro Display", 11),
            bg=self.dark_bg,
            fg=self.fg_color if self.output_dir else self.muted_color,
            relief=tk.FLAT,
            readonlybackground=self.dark_bg,
            state="readonly"
        )
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        
        self.change_output_btn = tk.Button(
            output_row,
            text="Change…",
            font=("SF Pro Display", 11),
            bg=self.dark_bg,
            fg=self.accent_color,
            activebackground=self.dark_bg,
            activeforeground="#3a8adf",
            relief=tk.FLAT,
            command=self._choose_output_folder
        )
        self.change_output_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Start button
        tk.Frame(self, bg=self.border_color, height=1).pack(fill=tk.X, padx=15, pady=15)
        
        self.start_btn = tk.Button(
            self,
            text="▶ Start Filtering",
            font=("SF Pro Display", 14, "bold"),
            bg=self.accent_color,
            fg=self.fg_color,
            activebackground="#3a8adf",
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            padx=30,
            pady=12,
            command=self._on_start
        )
        self.start_btn.pack(pady=(0, 15))
    
    def _create_filter_checkbox(
        self, 
        parent: tk.Frame, 
        text: str, 
        variable: tk.BooleanVar,
        disabled: bool = False
    ) -> tk.Checkbutton:
        """Create a styled filter checkbox."""
        cb = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.muted_color if disabled else self.fg_color,
            selectcolor=self.dark_bg,
            activebackground=self.bg_color,
            activeforeground=self.fg_color,
            state=tk.DISABLED if disabled else tk.NORMAL
        )
        cb.pack(anchor="w", pady=4)
        return cb
    
    def _create_content_warnings_section(self, parent: tk.Frame) -> None:
        """Create the collapsible content warnings section."""
        # Container for the collapsible section
        self.warnings_container = tk.Frame(parent, bg=self.bg_color, padx=15)
        self.warnings_container.pack(fill=tk.X, pady=(10, 0))
        
        # Header with chevron toggle and lookup button
        header_frame = tk.Frame(self.warnings_container, bg=self.bg_color)
        header_frame.pack(fill=tk.X)
        
        self.warnings_expanded = False
        self.warnings_chevron = tk.Label(
            header_frame,
            text="▶",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color,
            cursor="hand2"
        )
        self.warnings_chevron.pack(side=tk.LEFT)
        
        header_label = tk.Label(
            header_frame,
            text="🎬 Content Warnings (IMDb & DTDD)",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color,
            cursor="hand2"
        )
        header_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Lookup button
        self.lookup_btn = tk.Button(
            header_frame,
            text="🔍 Lookup",
            font=("SF Pro Display", 10),
            bg=self.dark_bg,
            fg=self.accent_color,
            activebackground=self.dark_bg,
            activeforeground="#3a8adf",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._lookup_content_warnings
        )
        self.lookup_btn.pack(side=tk.RIGHT)
        
        # Status indicator
        self.lookup_status = tk.Label(
            header_frame,
            text="",
            font=("SF Pro Display", 9),
            bg=self.bg_color,
            fg=self.muted_color
        )
        self.lookup_status.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Bind click to toggle
        self.warnings_chevron.bind("<Button-1>", lambda e: self._toggle_content_warnings())
        header_label.bind("<Button-1>", lambda e: self._toggle_content_warnings())
        
        # Expandable content frame (initially hidden)
        self.warnings_content = tk.Frame(self.warnings_container, bg=self.bg_color)
        
        # Empty state message
        self.warnings_empty = tk.Label(
            self.warnings_content,
            text="Click 'Lookup' to fetch content warnings for this video",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        )
        self.warnings_empty.pack(anchor="w", pady=(8, 0))
        
        # IMDb section frame
        self.imdb_frame = tk.Frame(self.warnings_content, bg=self.bg_color)
        
        tk.Label(
            self.imdb_frame,
            text="IMDb Parents Guide",
            font=("SF Pro Display", 10, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(anchor="w", pady=(8, 4))
        
        self.imdb_badges_frame = tk.Frame(self.imdb_frame, bg=self.bg_color)
        self.imdb_badges_frame.pack(fill=tk.X)
        
        # DoesTheDogDie section frame
        self.dtdd_frame = tk.Frame(self.warnings_content, bg=self.bg_color)
        
        tk.Label(
            self.dtdd_frame,
            text="DoesTheDogDie Triggers",
            font=("SF Pro Display", 10, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(anchor="w", pady=(12, 4))
        
        self.dtdd_list_frame = tk.Frame(self.dtdd_frame, bg=self.bg_color)
        self.dtdd_list_frame.pack(fill=tk.X)
    
    def _toggle_content_warnings(self) -> None:
        """Toggle the content warnings section visibility."""
        if self.warnings_expanded:
            self.warnings_content.pack_forget()
            self.warnings_chevron.config(text="▶")
        else:
            self.warnings_content.pack(fill=tk.X)
            self.warnings_chevron.config(text="▼")
        self.warnings_expanded = not self.warnings_expanded
    
    def _lookup_content_warnings(self) -> None:
        """Fetch content warnings from external databases."""
        if not self.current_video_path:
            return
        
        # Extract movie title from filename
        movie_title = self._extract_movie_title(self.current_video_path.stem)
        if not movie_title:
            self.lookup_status.config(text="❌ Couldn't parse title", fg="#ef4444")
            return
        
        # Show loading state
        self.lookup_btn.config(state=tk.DISABLED, text="⏳ Looking up...")
        self.lookup_status.config(text="", fg=self.muted_color)
        
        # Run lookup in background thread
        def do_lookup():
            try:
                # Try IMDb first
                imdb_client = IMDbClient()
                imdb_info = imdb_client.lookup_movie(movie_title)
                
                # Try DoesTheDogDie if API key configured
                dtdd_info = None
                dtdd_api_key = self.config.content_lookup.dtdd_api_key
                if dtdd_api_key:
                    dtdd_client = DoesTheDogDieClient(dtdd_api_key)
                    # Use IMDb ID if we have it
                    imdb_id = imdb_info.imdb_id if imdb_info else None
                    dtdd_info = dtdd_client.lookup_movie(movie_title, imdb_id)
                
                # Merge results
                if imdb_info:
                    self.content_info = imdb_info
                    if dtdd_info:
                        self.content_info.dtdd_id = dtdd_info.dtdd_id
                        self.content_info.triggers = dtdd_info.triggers
                elif dtdd_info:
                    self.content_info = dtdd_info
                else:
                    self.content_info = None
                
                # Update UI on main thread
                self.after(0, lambda: self._on_lookup_complete(True))
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Content lookup failed: {e}")
                self.after(0, lambda: self._on_lookup_complete(False, str(e)))
        
        self._lookup_thread = threading.Thread(target=do_lookup, daemon=True)
        self._lookup_thread.start()
    
    def _on_lookup_complete(self, success: bool, error: str = "") -> None:
        """Handle lookup completion on main thread."""
        self.lookup_btn.config(state=tk.NORMAL, text="🔍 Lookup")
        
        if success and self.content_info:
            self.lookup_status.config(
                text=f"✓ Found: {self.content_info.title}",
                fg=self.success_color
            )
            self._update_warnings_display()
            # Expand section to show results
            if not self.warnings_expanded:
                self._toggle_content_warnings()
        elif success:
            self.lookup_status.config(text="⚠ Not found", fg="#facc15")
        else:
            self.lookup_status.config(text=f"❌ Error", fg="#ef4444")
    
    def _update_quality_ui(self) -> None:
        """Update visibility of quality controls based on mode."""
        mode = self.var_quality_mode.get()
        if mode == "crf":
            self.crf_frame.pack(side=tk.LEFT)
            self.size_frame.pack_forget()
        else:
            self.crf_frame.pack_forget()
            self.size_frame.pack(side=tk.LEFT)

        """Update the warnings display with fetched content."""
        # Hide empty state
        self.warnings_empty.pack_forget()
        
        # Clear previous badges
        for widget in self.imdb_badges_frame.winfo_children():
            widget.destroy()
        for widget in self.dtdd_list_frame.winfo_children():
            widget.destroy()
        
        if not self.content_info:
            self.warnings_empty.pack(anchor="w", pady=(8, 0))
            self.imdb_frame.pack_forget()
            self.dtdd_frame.pack_forget()
            return
        
        # Show IMDb section if we have warnings
        if self.content_info.warnings:
            self.imdb_frame.pack(fill=tk.X)
            
            for warning in self.content_info.warnings:
                badge_frame = tk.Frame(self.imdb_badges_frame, bg=self.bg_color)
                badge_frame.pack(side=tk.LEFT, padx=(0, 8), pady=2)
                
                # Category name
                cat_name = warning.category.value.replace("_", " ").title()
                if len(cat_name) > 12:
                    cat_name = cat_name[:10] + "..."
                
                # Severity badge with color
                sev_color = warning.severity.color
                badge = tk.Label(
                    badge_frame,
                    text=f"{cat_name}: {warning.severity.value.title()}",
                    font=("SF Pro Display", 9),
                    bg=sev_color,
                    fg="#000000" if warning.severity in [Severity.MILD, Severity.NONE] else "#ffffff",
                    padx=6,
                    pady=2
                )
                badge.pack()
        else:
            self.imdb_frame.pack_forget()
        
        # Show DoesTheDogDie section if we have triggers
        if self.content_info.triggers:
            self.dtdd_frame.pack(fill=tk.X)
            
            # Show top 5 relevant triggers
            for trigger in self.content_info.triggers[:5]:
                if not trigger.is_present:
                    continue
                    
                trigger_frame = tk.Frame(self.dtdd_list_frame, bg=self.bg_color)
                trigger_frame.pack(fill=tk.X, pady=1)
                
                # Indicator
                indicator = "⚠️" if trigger.confidence > 0.7 else "❓"
                
                tk.Label(
                    trigger_frame,
                    text=f"{indicator} {trigger.topic}",
                    font=("SF Pro Display", 10),
                    bg=self.bg_color,
                    fg=self.fg_color,
                    anchor="w"
                ).pack(side=tk.LEFT)
                
                # Vote count
                tk.Label(
                    trigger_frame,
                    text=f"({trigger.yes_votes}↑)",
                    font=("SF Pro Display", 9),
                    bg=self.bg_color,
                    fg=self.muted_color
                ).pack(side=tk.LEFT, padx=(5, 0))
        else:
            self.dtdd_frame.pack_forget()
    
    def _extract_movie_title(self, filename: str) -> str:
        """Extract movie title from filename, removing year and quality tags."""
        import re
        
        # Remove common video quality indicators
        cleaned = re.sub(r'[\[\(]?(1080p|720p|480p|2160p|4K|HDR|BluRay|BRRip|WEBRip|HDTV|DVDRip|x264|x265|HEVC|AAC|DTS|REMUX)[\]\)]?', '', filename, flags=re.IGNORECASE)
        
        # Remove year in parentheses or brackets
        cleaned = re.sub(r'[\[\(]?(19|20)\d{2}[\]\)]?', '', cleaned)
        
        # Remove trailing dots, dashes, underscores
        cleaned = re.sub(r'[._-]+$', '', cleaned)
        
        # Replace dots and underscores with spaces
        cleaned = re.sub(r'[._]', ' ', cleaned)
        
        # Remove multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    
    def _create_custom_phrases_section(self, parent: tk.Frame) -> None:
        """Create the collapsible custom phrases section."""
        # Container for the collapsible section
        self.phrases_container = tk.Frame(parent, bg=self.bg_color)
        self.phrases_container.pack(fill=tk.X, pady=(15, 0))
        
        # Header with chevron toggle
        header_frame = tk.Frame(self.phrases_container, bg=self.bg_color)
        header_frame.pack(fill=tk.X)
        
        self.phrases_expanded = False
        self.phrases_chevron = tk.Label(
            header_frame,
            text="▶",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color,
            cursor="hand2"
        )
        self.phrases_chevron.pack(side=tk.LEFT)
        
        header_label = tk.Label(
            header_frame,
            text="Custom phrases to mute or cut",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color,
            cursor="hand2"
        )
        header_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Bind click to toggle
        self.phrases_chevron.bind("<Button-1>", lambda e: self._toggle_custom_phrases())
        header_label.bind("<Button-1>", lambda e: self._toggle_custom_phrases())
        
        # Expandable content frame (initially hidden)
        self.phrases_content = tk.Frame(self.phrases_container, bg=self.bg_color)
        
        # Multi-line text box (4-6 lines)
        self.phrases_text = tk.Text(
            self.phrases_content,
            height=5,
            font=("SF Pro Display", 11),
            bg=self.dark_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#3a3a3a",
            highlightcolor=self.accent_color,
            wrap=tk.WORD,
            padx=8,
            pady=8
        )
        self.phrases_text.pack(fill=tk.X, pady=(8, 0))
        
        # Placeholder text
        self.phrases_placeholder = "Type or paste any words or sentences here\nOne per line\nExample: stupid, oh my gosh, shut up"
        self._set_phrases_placeholder()
        
        # Bind focus events for placeholder behavior
        self.phrases_text.bind("<FocusIn>", self._on_phrases_focus_in)
        self.phrases_text.bind("<FocusOut>", self._on_phrases_focus_out)
        
        # Links/buttons row
        links_frame = tk.Frame(self.phrases_content, bg=self.bg_color)
        links_frame.pack(fill=tk.X, pady=(8, 0))
        
        # "Open as text file…" link
        self.open_file_link = tk.Label(
            links_frame,
            text="Open as text file…",
            font=("SF Pro Display", 10, "underline"),
            bg=self.bg_color,
            fg=self.accent_color,
            cursor="hand2"
        )
        self.open_file_link.pack(side=tk.LEFT)
        self.open_file_link.bind("<Button-1>", lambda e: self._open_custom_phrases_file())
        
        # "Paste full movie transcript" button (disabled for now)
        self.transcript_btn = tk.Button(
            links_frame,
            text="Paste full movie transcript → auto fill matches",
            font=("SF Pro Display", 9),
            bg=self.bg_color,
            fg="#555555",
            activebackground=self.bg_color,
            activeforeground="#555555",
            relief=tk.FLAT,
            state=tk.DISABLED,
            cursor="arrow"
        )
        self.transcript_btn.pack(side=tk.RIGHT)
    
    def _toggle_custom_phrases(self) -> None:
        """Toggle the custom phrases section visibility."""
        if self.phrases_expanded:
            self.phrases_content.pack_forget()
            self.phrases_chevron.config(text="▶")
        else:
            self.phrases_content.pack(fill=tk.X)
            self.phrases_chevron.config(text="▼")
        self.phrases_expanded = not self.phrases_expanded
    
    def _set_phrases_placeholder(self) -> None:
        """Set the placeholder text in phrases text box."""
        self.phrases_text.insert("1.0", self.phrases_placeholder)
        self.phrases_text.config(fg=self.muted_color)
        self._phrases_has_placeholder = True

    def _choose_output_folder(self) -> None:
        """Open directory chooser for output folder."""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_dir if self.output_dir else os.path.expanduser("~")
        )
        
        # Save quality preferences
        self.config.output.quality_mode = self.var_quality_mode.get()
        self.config.output.video_crf = self.var_crf.get()
        try:
            self.config.output.target_size_mb = int(self.var_target_size.get())
        except ValueError:
            self.config.output.target_size_mb = 100  # Fallback
        self.config.output.encoding_speed = self.var_speed.get()
        
        if folder:
            self.output_dir = folder
            # Save output folder preferences
            self.config.output.custom_output_dir = self.output_dir
            
            # Update UI
            self.output_path_var.set(folder)
            self.output_entry.config(fg=self.fg_color)
            
            # Save to config file
            # Ideally we should use a proper config saver, but for now we'll load raw yaml, update, and save
            try:
                import yaml
                config_path = Path(__file__).parent / "config.yaml"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        data = yaml.safe_load(f) or {}
                    
                    if 'output' not in data:
                        data['output'] = {}
                    
                    data['output']['custom_output_dir'] = folder
                    
                    with open(config_path, 'w') as f:
                        yaml.dump(data, f, default_flow_style=False)
                        
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to save config: {e}")
    
    def _on_phrases_focus_in(self, event) -> None:
        """Clear placeholder when text box gets focus."""
        if self._phrases_has_placeholder:
            self.phrases_text.delete("1.0", tk.END)
            self.phrases_text.config(fg=self.fg_color)
            self._phrases_has_placeholder = False
    
    def _on_phrases_focus_out(self, event) -> None:
        """Restore placeholder if text box is empty."""
        content = self.phrases_text.get("1.0", tk.END).strip()
        if not content:
            self._set_phrases_placeholder()
    
    def _get_custom_phrases(self) -> list:
        """Get list of custom phrases from text box."""
        if self._phrases_has_placeholder:
            return []
        content = self.phrases_text.get("1.0", tk.END).strip()
        if not content:
            return []
        # Split by newlines and filter empty lines
        return [line.strip() for line in content.split("\n") if line.strip()]
    
    def _set_custom_phrases(self, phrases: list) -> None:
        """Set custom phrases in text box."""
        self.phrases_text.delete("1.0", tk.END)
        if phrases:
            self.phrases_text.insert("1.0", "\n".join(phrases))
            self.phrases_text.config(fg=self.fg_color)
            self._phrases_has_placeholder = False
        else:
            self._set_phrases_placeholder()
    
    def _open_custom_phrases_file(self) -> None:
        """Open the custom phrases file in the default editor."""
        import os
        import subprocess
        
        # Ensure directory exists
        phrases_dir = Path.home() / ".video_censor"
        phrases_dir.mkdir(exist_ok=True)
        
        phrases_file = phrases_dir / "custom_phrases.txt"
        
        # Create file if it doesn't exist
        if not phrases_file.exists():
            phrases_file.write_text("# Custom phrases to mute or cut\n# One phrase per line\n\n")
        
        # Open in default editor
        try:
            subprocess.run(["open", str(phrases_file)], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def _create_safe_cover_section(self, parent: tk.Frame) -> None:
        """Create the Safe Cover section."""
        # Container
        safe_cover_container = tk.Frame(parent, bg=self.bg_color)
        safe_cover_container.pack(fill=tk.X, pady=(20, 0))
        
        # Section header
        tk.Label(
            safe_cover_container,
            text="Safe Cover Image for Media Players",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", pady=(0, 8))
        
        # Checkbox with icon
        cover_frame = tk.Frame(safe_cover_container, bg=self.bg_color)
        cover_frame.pack(fill=tk.X)
        
        self.safe_cover_cb = tk.Checkbutton(
            cover_frame,
            text="\U0001F3A8  Generate a kid-friendly cover image",
            variable=self.var_safe_cover,
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.fg_color,
            selectcolor=self.dark_bg,
            activebackground=self.bg_color,
            activeforeground=self.fg_color
        )
        self.safe_cover_cb.pack(anchor="w")
        
        # Helper text
        tk.Label(
            safe_cover_container,
            text="Creates a new poster from calmer scenes for Plex or other players",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", padx=(24, 0), pady=(2, 0))
    
    def _create_subtitles_section(self, parent: tk.Frame) -> None:
        """Create the Subtitles section."""
        # Container
        subtitles_container = tk.Frame(parent, bg=self.bg_color)
        subtitles_container.pack(fill=tk.X, pady=(20, 0))
        
        # Section header
        tk.Label(
            subtitles_container,
            text="Subtitles",
            font=("SF Pro Display", 11, "bold"),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", pady=(0, 8))
        
        # Force English subtitles checkbox
        ModernFilterRow(
            subtitles_container,
            text="Force English subtitles",
            variable=self.var_force_subtitles,
            emoji="📝",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color
        ).pack(fill=tk.X)
        
        # Helper text for force subtitles
        tk.Label(
            subtitles_container,
            text="Burns embedded English subtitles into video (re-encodes video)",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", padx=(36, 0), pady=(2, 8))
        
        # Censor profanity in subtitles checkbox
        ModernFilterRow(
            subtitles_container,
            text="Censor profanity in subtitles",
            variable=self.var_censor_subtitles,
            emoji="🔇",
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            accent_color=self.accent_color
        ).pack(fill=tk.X)
        
        # Helper text for censor subtitles
        tk.Label(
            subtitles_container,
            text="Replaces profanity words in subtitles with [...]",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(anchor="w", padx=(36, 0), pady=(2, 0))
    
    def _set_empty_state(self) -> None:
        """Set the panel to empty/waiting state."""
        self.current_video_path = None
        self.video_icon.config(text="📁")
        self.video_name.config(text="No video selected")
        self.video_details.config(text="Drop or browse to add a video")
        self.start_btn.config(state=tk.DISABLED)
    
    def set_video(self, video_path: Path) -> None:
        """Set the currently selected video."""
        self.current_video_path = video_path
        
        # Get file info
        try:
            stat = video_path.stat()
            self.current_video_size = stat.st_size
        except:
            self.current_video_size = 0
        
        # Update display
        self.video_icon.config(text="📹")
        self.video_name.config(text=video_path.name)
        
        # Format size
        size_str = self._format_size(self.current_video_size)
        self.video_details.config(text=f"Size: {size_str}")
        
        # Enable start button
        self.start_btn.config(state=tk.NORMAL)
        
        # Apply current profile settings
        self._apply_profile_settings()
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def _on_profile_change(self, event=None) -> None:
        """Handle profile selection change."""
        self._apply_profile_settings()
    
    def _apply_profile_settings(self) -> None:
        """Apply the selected profile's settings to controls."""
        profile_name = self.profile_var.get()
        profile = self.profile_manager.get_or_default(profile_name)
        
        self.var_language.set(profile.settings.filter_language)
        self.var_sexual.set(profile.settings.filter_sexual_content)
        self.var_nudity.set(profile.settings.filter_nudity)
        self.var_romance.set(profile.settings.filter_romance_level)
        self.var_violence.set(profile.settings.filter_violence_level)
        self.var_mature.set(profile.settings.filter_mature_themes)
        self.var_safe_cover.set(profile.settings.safe_cover_enabled)
        self.var_force_subtitles.set(profile.settings.force_english_subtitles)
        self.var_censor_subtitles.set(profile.settings.censor_subtitle_profanity)
        self._set_custom_phrases(profile.settings.custom_block_phrases)
    
    def _on_manage_profiles(self) -> None:
        """Open the Profile Manager dialog."""
        dialog = ProfileDialog(
            self.winfo_toplevel(),
            self.profile_manager,
            on_profiles_changed=self._refresh_profile_list
        )
        self.wait_window(dialog)
    
    def _refresh_profile_list(self) -> None:
        """Refresh the profile dropdown after changes."""
        current = self.profile_var.get()
        names = self.profile_manager.list_names()
        self.profile_dropdown['values'] = names
        
        # Keep selection if still valid
        if current in names:
            self.profile_var.set(current)
        else:
            self.profile_var.set("Default")
            self._apply_profile_settings()
    
    def _on_save_defaults(self) -> None:
        """Save current settings as profile defaults."""
        profile_name = self.profile_var.get()
        profile = self.profile_manager.get(profile_name)
        
        if not profile:
            return
        
        new_settings = self.get_current_settings()
        
        try:
            profile.settings = new_settings
            self.profile_manager.update(profile_name, profile)
            messagebox.showinfo(
                "Saved",
                f"Settings saved to profile '{profile_name}'"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def get_current_settings(self) -> ContentFilterSettings:
        """Get the current filter settings from controls."""
        return ContentFilterSettings(
            filter_language=self.var_language.get(),
            filter_sexual_content=self.var_sexual.get(),
            filter_nudity=self.var_nudity.get(),
            filter_romance_level=self.var_romance.get(),
            filter_violence_level=self.var_violence.get(),
            filter_mature_themes=self.var_mature.get(),
            custom_block_phrases=self._get_custom_phrases(),
            safe_cover_enabled=self.var_safe_cover.get(),
            force_english_subtitles=self.var_force_subtitles.get(),
            censor_subtitle_profanity=self.var_censor_subtitles.get()
        )
    
    def get_current_profile_name(self) -> str:
        """Get the selected profile name."""
        return self.profile_var.get()
    
    def _on_start(self) -> None:
        """Collect settings and start processing."""
        if not self.current_video_path:
            messagebox.showwarning("No Video", "Please select a video file first.")
            return
            
        # Update config with current settings
        self.config.nudity.body_parts = [] # Defaults to all for now
        
        # Update output config from quality preset
        preset_display = self.quality_preset_var.get()
        preset_key = self.preset_map.get(preset_display, "original")
        self.config.output.quality_preset = preset_key
        
        # Reset internal defaults (optional, but good for consistency)
        if preset_key == "original":
            self.config.output.video_crf = 23
        else:
            self.config.output.video_crf = 23  # or whatever default used by renderer for presets

        # Save config to ensure subprocess picks it up
        try:
            config_path = Path(__file__).parent / "config.yaml"
            self.config.save(config_path)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

        # Build filter settings
        settings = self.get_current_settings()
        
        if self.current_video_path and self.on_start_callback:
            settings = self.get_current_settings()
            profile_name = self.get_current_profile_name()
            output_format = self.var_video_format.get()
            self.on_start_callback(self.current_video_path, settings, profile_name, output_format=output_format)
            
        # Reset to empty state
        self._set_empty_state()


class QueuePanel(tk.Frame):
    """
    Queue panel showing processing jobs and their status.
    """
    
    def __init__(self, parent, queue: ProcessingQueue):
        super().__init__(parent, bg="#141419", highlightbackground="#2a2a35", highlightthickness=1)
        
        self.queue = queue
        
        # Premium color palette
        self.bg_color = "#141419"
        self.fg_color = "#f0f0f5"
        self.muted_color = "#71717a"
        self.dark_bg = "#0a0a0f"
        self.accent_color = "#3b82f6"
        self.accent_secondary = "#8b5cf6"
        self.success_color = "#22c55e"
        self.border_color = "#2a2a35"
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Build the queue panel UI."""
        # Title
        header = tk.Frame(self, bg=self.bg_color)
        header.pack(fill=tk.X, padx=15, pady=12)
        
        tk.Label(
            header,
            text="Processing Queue",
            font=("SF Pro Display", 14, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        self.count_label = tk.Label(
            header,
            text="No videos in queue",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        )
        self.count_label.pack(side=tk.RIGHT)
        
        # Scrollable list container
        list_container = tk.Frame(self, bg=self.bg_color)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Canvas for scrolling
        self.canvas = tk.Canvas(
            list_container, 
            bg=self.bg_color, 
            highlightthickness=0
        )
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.items_frame = tk.Frame(self.canvas, bg=self.bg_color)
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        
        self.items_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Empty state - centered icon and message
        self.empty_frame = tk.Frame(self.items_frame, bg=self.bg_color)
        
        self._item_widgets = {}
        
        # Show initial empty state
        self._show_empty_state()
    
    def _show_empty_state(self) -> None:
        """Show empty state with icon."""
        self.empty_frame = tk.Frame(self.items_frame, bg=self.bg_color, pady=40)
        self.empty_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon
        tk.Label(
            self.empty_frame,
            text="🎬",
            font=("SF Pro Display", 36),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack()
        
        tk.Label(
            self.empty_frame,
            text="Your processing queue is empty",
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.muted_color
        ).pack(pady=(10, 2))
        
        tk.Label(
            self.empty_frame,
            text="Add videos to get started",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg="#52525b"
        ).pack()
    
    def _on_frame_configure(self, event) -> None:
        """Reset the scroll region when items change."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event) -> None:
        """Adjust item width when canvas is resized."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def refresh(self) -> None:
        """Refresh the queue display."""
        # Clear existing widgets
        for widget in self.items_frame.winfo_children():
            widget.destroy()
        self._item_widgets.clear()
        
        items = self.queue.items
        
        if not items:
            self._show_empty_state()
            self.count_label.config(text="No videos in queue")
            return
        
        # Update count
        pending = self.queue.pending_count
        processing = self.queue.processing_count
        complete = self.queue.complete_count
        total = len(items)
        self.count_label.config(text=f"{complete}/{total} complete")
        
        # Create item widgets
        for item in items:
            self._create_item_widget(item)
    
    def _create_item_widget(self, item: QueueItem) -> None:
        """Create a widget for a queue item."""
        item_frame = tk.Frame(
            self.items_frame,
            bg=self.dark_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        item_frame.pack(fill=tk.X, pady=4, padx=5)
        
        # Content
        content = tk.Frame(item_frame, bg=self.dark_bg, padx=12, pady=10)
        content.pack(fill=tk.X)
        
        # Top row: filename and status dot
        top_row = tk.Frame(content, bg=self.dark_bg)
        top_row.pack(fill=tk.X)
        
        # Status dot
        status_dot = StatusDot(
            top_row,
            status=item.status,
            bg=self.dark_bg
        )
        status_dot.pack(side=tk.LEFT, padx=(0, 8))
        
        # Filename
        name_label = tk.Label(
            top_row,
            text=item.filename,
            font=("SF Pro Display", 11, "bold"),
            bg=self.dark_bg,
            fg=self.fg_color,
            anchor="w"
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Profile badge
        profile_badge = tk.Label(
            content,
            text=item.profile_name,
            font=("SF Pro Display", 9),
            bg="#1e1e28",
            fg=self.muted_color,
            padx=6,
            pady=1
        )
        profile_badge.pack(anchor="w", pady=(6, 0))
        
        # Filter summary tags row
        tags_frame = tk.Frame(content, bg=self.dark_bg)
        tags_frame.pack(anchor="w", pady=(4, 0))
        
        # Show short filter summary
        filter_summary = item.filters.short_summary()
        if filter_summary and filter_summary != "None":
            for tag in filter_summary.split():
                tag_bg = "#2a3a4a" if tag in ("Custom", "Cover") else "#252530"
                tag_fg = "#4ade80" if tag in ("Custom", "Cover") else self.muted_color
                tag_label = tk.Label(
                    tags_frame,
                    text=tag,
                    font=("SF Pro Display", 8),
                    bg=tag_bg,
                    fg=tag_fg,
                    padx=4,
                    pady=1
                )
                tag_label.pack(side=tk.LEFT, padx=(0, 4))
        
        # Status text
        status_label = tk.Label(
            content,
            text=item.status_display(),
            font=("SF Pro Display", 10),
            bg=self.dark_bg,
            fg=self._get_status_color(item.status)
        )
        status_label.pack(anchor="w", pady=(4, 0))
        
        # Progress bar for processing items
        if item.is_processing:
            progress_bar = GradientProgressBar(
                content,
                width=200,
                height=6,
                gradient_start=self.accent_color,
                gradient_end=self.accent_secondary,
                bg_color=self.border_color,
                value=item.progress,
                bg=self.dark_bg
            )
            progress_bar.pack(fill=tk.X, pady=(8, 0))
            
            self._item_widgets[item.id] = {
                'frame': item_frame,
                'status': status_label,
                'progress': progress_bar,
                'status_dot': status_dot
            }
        else:
            self._item_widgets[item.id] = {
                'frame': item_frame,
                'status': status_label,
                'progress': None,
                'status_dot': status_dot
            }
    
    def _get_status_color(self, status: str) -> str:
        """Get color for status display."""
        colors = {
            'pending': "#71717a",
            'processing': "#3b82f6",
            'complete': "#22c55e",
            'error': "#ef4444",
            'cancelled': "#71717a"
        }
        return colors.get(status, self.muted_color)
    
    def update_item(self, item: QueueItem) -> None:
        """Update display for a specific item."""
        if item.id in self._item_widgets:
            widgets = self._item_widgets[item.id]
            widgets['status'].config(
                text=item.status_display(),
                fg=self._get_status_color(item.status)
            )


class VideoCensorApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Video Censor")
        self.root.geometry("1100x750")
        self.root.minsize(950, 650)
        
        # Force dark appearance on macOS
        if sys.platform == 'darwin':
            try:
                # Use NSAppearance to force dark mode (requires Tk 8.6.9+)
                self.root.tk.call('tk::unsupported::MacWindowStyle', 'appearance', 
                                  self.root._w, 'darkAqua')
            except tk.TclError:
                pass
            
            # Alternative: set background early to prevent white flash
            self.root.update_idletasks()
        
        # Premium color palette
        self.bg_color = "#0a0a0f"
        self.fg_color = "#f0f0f5"
        self.accent_color = "#3b82f6"
        self.accent_secondary = "#8b5cf6"
        self.panel_bg = "#141419"
        self.border_color = "#2a2a35"
        self.muted_color = "#71717a"
        
        self.root.configure(bg=self.bg_color)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TButton", background=self.accent_color, foreground=self.fg_color)
        self.style.configure("TProgressbar", background=self.accent_color, troughcolor=self.border_color)
        self.style.configure("TCombobox", fieldbackground=self.panel_bg, background=self.panel_bg)
        
        # Initialize managers
        self.profile_manager = ProfileManager()
        self.processing_queue = ProcessingQueue()
        
        # Processing state
        self.processing = False
        self.current_item: Optional[QueueItem] = None
        
        self._create_ui()
        self._setup_drag_drop()
    
    def _create_ui(self) -> None:
        """Build the main application UI."""
        # Header with gradient accent
        header = tk.Frame(self.root, bg=self.bg_color)
        header.pack(fill=tk.X, padx=24, pady=(20, 12))
        
        # Title section
        title_frame = tk.Frame(header, bg=self.bg_color)
        title_frame.pack(side=tk.LEFT)
        
        title = tk.Label(
            title_frame,
            text="Video Censor",
            font=("SF Pro Display", 28, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        title.pack(anchor="w")
        
        subtitle = tk.Label(
            title_frame,
            text="Family-safe video filtering • Fully local • Private",
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.muted_color
        )
        subtitle.pack(anchor="w", pady=(2, 0))
        
        # Status badge in header (right side)
        status_frame = tk.Frame(header, bg=self.bg_color)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = tk.Label(
            status_frame,
            text="Idle",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color,
            padx=12,
            pady=4
        )
        self.status_label.pack()
        
        # Separator
        tk.Frame(self.root, bg=self.border_color, height=1).pack(fill=tk.X, padx=24)
        
        # Main content area with three zones
        content = tk.Frame(self.root, bg=self.bg_color)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)
        content.columnconfigure(0, weight=1, minsize=260)  # Drop zone
        content.columnconfigure(1, weight=2, minsize=380)  # Preference Manager
        content.columnconfigure(2, weight=1, minsize=280)  # Queue
        content.rowconfigure(0, weight=1)
        
        # Left: Drop zone
        self._create_drop_zone(content)
        
        # Center: Preference Manager
        self.preference_panel = PreferencePanel(
            content,
            self.profile_manager,
            on_start_callback=self._on_start_filtering
        )
        self.preference_panel.grid(row=0, column=1, sticky="nsew", padx=12)
        
        # Right: Queue
        self.queue_panel = QueuePanel(content, self.processing_queue)
        self.queue_panel.grid(row=0, column=2, sticky="nsew")
        
        # Footer
        self._create_footer()
    
    def _create_drop_zone(self, parent: tk.Frame) -> None:
        """Create the video drop zone with modern styling."""
        drop_frame = tk.Frame(
            parent,
            bg=self.panel_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        drop_frame.grid(row=0, column=0, sticky="nsew")
        
        # Inner frame with dashed border effect
        inner_frame = tk.Frame(drop_frame, bg=self.panel_bg, padx=20, pady=20)
        inner_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header for drop zone
        tk.Label(
            inner_frame,
            text="Add Video",
            font=("SF Pro Display", 14, "bold"),
            bg=self.panel_bg,
            fg=self.fg_color,
            anchor="w"
        ).pack(anchor="w", pady=(0, 15))
        
        # Drop area with dashed visual
        drop_area = tk.Frame(
            inner_frame,
            bg="#0f0f14",
            highlightbackground=self.accent_color,
            highlightthickness=1
        )
        drop_area.pack(fill=tk.BOTH, expand=True)
        
        # Center content in drop area
        center = tk.Frame(drop_area, bg="#0f0f14")
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Upload icon with accent color
        self.drop_icon = tk.Label(
            center,
            text="⬆",
            font=("SF Pro Display", 36),
            bg="#0f0f14",
            fg=self.accent_color
        )
        self.drop_icon.pack()
        
        self.drop_label = tk.Label(
            center,
            text="Drop a video here or click to choose",
            font=("SF Pro Display", 12),
            bg="#0f0f14",
            fg=self.fg_color
        )
        self.drop_label.pack(pady=(12, 4))
        
        self.format_label = tk.Label(
            center,
            text="Supports MP4, MOV, AVI, and other common formats",
            font=("SF Pro Display", 10),
            bg="#0f0f14",
            fg=self.muted_color
        )
        self.format_label.pack()
        
        # Browse button with hover effect
        self.browse_btn = tk.Button(
            center,
            text="Choose File",
            font=("SF Pro Display", 12, "bold"),
            bg=self.accent_color,
            fg=self.fg_color,
            activebackground=self.accent_secondary,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            padx=24,
            pady=10,
            cursor="hand2",
            command=self._browse_files
        )
        self.browse_btn.pack(pady=(20, 0))
        
        # Make drop area clickable
        for widget in [drop_area, center, self.drop_icon, self.drop_label, self.format_label]:
            widget.bind("<Button-1>", lambda e: self._browse_files())
            widget.configure(cursor="hand2")
        
        self.drop_frame = drop_frame
        self.drop_area = drop_area
    
    def _create_footer(self) -> None:
        """Create the footer with output path and controls."""
        footer = tk.Frame(self.root, bg=self.bg_color)
        footer.pack(fill=tk.X, padx=24, pady=(0, 16))
        
        # Left side: status
        left = tk.Frame(footer, bg=self.bg_color)
        left.pack(side=tk.LEFT)
        
        output_label = tk.Label(
            left,
            text=f"Output folder: {OUTPUT_DIR}",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color
        )
        output_label.pack(side=tk.LEFT)
        
        # Right side: links
        right = tk.Frame(footer, bg=self.bg_color)
        right.pack(side=tk.RIGHT)
        
        manage_btn = tk.Button(
            right,
            text="Manage Profiles",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.accent_color,
            activebackground=self.bg_color,
            activeforeground=self.accent_secondary,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._open_profile_manager
        )
        manage_btn.pack(side=tk.LEFT, padx=(0, 16))
        
        logs_btn = tk.Button(
            right,
            text="View Logs",
            font=("SF Pro Display", 10),
            bg=self.bg_color,
            fg=self.muted_color,
            activebackground=self.bg_color,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            cursor="hand2"
        )
        logs_btn.pack(side=tk.LEFT)
    
    def _open_profile_manager(self) -> None:
        """Open the profile manager dialog."""
        from video_censor.profile_dialog import ProfileDialog
        dialog = ProfileDialog(
            self.root,
            self.profile_manager,
            on_profiles_changed=self.preference_panel._refresh_profile_list
        )
        self.root.wait_window(dialog)
    
    def _setup_drag_drop(self) -> None:
        """Setup drag and drop handlers."""
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
        except ImportError:
            # Fallback: clicking opens file browser
            self.drop_label.config(text="Click to browse files")
    
    def _on_drop(self, event) -> None:
        """Handle dropped files."""
        files = self.root.tk.splitlist(event.data)
        for file_path in files:
            # Clean up macOS drag-and-drop paths (may have curly braces or extra chars)
            file_path = file_path.strip()
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            
            if file_path.lower().endswith(VIDEO_EXTENSIONS):
                self._select_video(Path(file_path))
                break
            else:
                messagebox.showwarning("Invalid File", f"Not a supported video format:\n{file_path}")
    
    def _browse_files(self) -> None:
        """Open file browser dialog."""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.avi *.mov *.m4v *.wmv"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            self._select_video(Path(file_path))
    
    def _select_video(self, video_path: Path) -> None:
        """Handle video selection - show in preference panel."""
        self.preference_panel.set_video(video_path)
    
    def _on_start_filtering(
        self, 
        video_path: Path, 
        settings: ContentFilterSettings, 
        profile_name: str,
        output_dir: Optional[str] = None,
        output_format: str = "mp4"
    ) -> None:
        """Handle start filtering request from preference panel."""
        # Determine output folder
        if output_dir:
            target_dir = Path(output_dir)
        elif self.config and self.config.output.custom_output_dir:
            target_dir = Path(self.config.output.custom_output_dir)
        else:
            # Fallback to default logic (hardcoded global or input dir)
            target_dir = Path(OUTPUT_DIR) if OUTPUT_DIR else video_path.parent
            
        # Create output path
        os.makedirs(target_dir, exist_ok=True)
        # Use selected format extension
        output_path = target_dir / f"{video_path.stem}.CENSORED.{output_format}"
        
        # Create queue item
        item = QueueItem(
            input_path=video_path,
            output_path=output_path,
            filters=settings,
            profile_name=profile_name
        )
        
        # Add to queue
        self.processing_queue.add(item)
        self.queue_panel.refresh()
        
        # Start processing if not already
        if not self.processing:
            self._process_next()
    
    def _process_next(self) -> None:
        """Process the next item in the queue."""
        item = self.processing_queue.get_next_pending()
        if not item:
            self.processing = False
            return
        
        self.processing = True
        self.current_item = item
        item.start_processing()
        self.queue_panel.refresh()
        
        # Run in background thread
        thread = threading.Thread(target=self._run_censor, args=(item,))
        thread.daemon = True
        thread.start()
    
    def _run_censor(self, item: QueueItem) -> None:
        """Run the censor pipeline for a queue item."""
        try:
            # Set up environment with Homebrew in PATH
            env = os.environ.copy()
            env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
            
            # Build command with filter flags
            cmd = [
                VENV_PYTHON, CENSOR_SCRIPT,
                str(item.input_path), str(item.output_path),
                "--save-summary", str(item.output_path.with_suffix('.json')),
                "-y"
            ]
            
            # Add filter flags based on settings
            if not item.filters.filter_language:
                cmd.append("--no-profanity")
            if not item.filters.filter_nudity:
                cmd.append("--no-nudity")
            
            # TODO: Pass sexual content and romance level settings when pipeline supports it
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )
            
            # Monitor output
            for line in process.stdout:
                if "STEP 1" in line:
                    item.update_progress(0.1, "Detecting profanity...")
                elif "STEP 2" in line:
                    item.update_progress(0.3, "Detecting nudity...")
                elif "STEP 2.5" in line:
                    item.update_progress(0.5, "Detecting sexual content...")
                elif "STEP 3" in line:
                    item.update_progress(0.7, "Planning edits...")
                elif "STEP 4" in line:
                    item.update_progress(0.85, "Rendering video...")
                
                self.root.after(0, self.queue_panel.refresh)
            
            process.wait()
            
            if process.returncode == 0:
                item.complete()
                self.root.after(0, lambda: self._on_item_complete(item))
            else:
                item.fail("Processing failed")
                self.root.after(0, self.queue_panel.refresh)
        
        except Exception as e:
            item.fail(str(e))
            self.root.after(0, self.queue_panel.refresh)
        
        finally:
            # Process next item
            self.root.after(100, self._process_next)
    
    def _on_item_complete(self, item: QueueItem) -> None:
        """Handle completed item."""
        self.queue_panel.refresh()
        
        # Show notification
        try:
            subprocess.run([
                "osascript", "-e",
                f'display notification "Censored video saved!" with title "Video Censor" sound name "Glass"'
            ])
        except:
            pass


def main():
    """Main entry point."""
    root = tk.Tk()
    
    # CRITICAL: Force clam theme immediately before any widgets are created
    style = ttk.Style(root)
    style.theme_use('clam')
    
    # Define dark color palette
    bg_dark = "#0a0a0f"
    fg_light = "#f0f0f5"
    panel_bg = "#141419"
    accent = "#3b82f6"
    border = "#2a2a35"
    
    # Use Tk Option database to set default colors for ALL widgets
    root.option_add('*Background', bg_dark)
    root.option_add('*Foreground', fg_light)
    root.option_add('*activeBackground', panel_bg)
    root.option_add('*activeForeground', fg_light)
    root.option_add('*selectBackground', accent)
    root.option_add('*selectForeground', fg_light)
    root.option_add('*highlightBackground', border)
    root.option_add('*highlightColor', accent)
    root.option_add('*troughColor', border)
    root.option_add('*insertBackground', fg_light)
    
    # Force the root window background
    root.configure(bg=bg_dark)
    
    # Configure ttk styles with dark colors
    style.configure('.', background=bg_dark, foreground=fg_light)
    style.configure('TFrame', background=bg_dark)
    style.configure('TLabel', background=bg_dark, foreground=fg_light)
    style.configure('TButton', background=accent, foreground=fg_light)
    style.configure('TEntry', fieldbackground=panel_bg, foreground=fg_light)
    style.configure('TCombobox', fieldbackground=panel_bg, foreground=fg_light, 
                    background=panel_bg, arrowcolor=fg_light)
    style.configure('TProgressbar', background=accent, troughcolor=border)
    style.configure('TRadiobutton', background=bg_dark, foreground=fg_light)
    style.configure('TCheckbutton', background=bg_dark, foreground=fg_light)
    style.configure('TScrollbar', background=panel_bg, troughcolor=bg_dark)
    
    # Map states for interactive widgets
    style.map('TCombobox', 
              fieldbackground=[('readonly', panel_bg)],
              selectbackground=[('readonly', accent)])
    style.map('TButton',
              background=[('active', accent), ('pressed', border)])
    
    app = VideoCensorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
