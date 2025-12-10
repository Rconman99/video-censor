"""
Profile Manager dialog for creating and editing filter profiles.

Provides a Toplevel window for managing named filter profiles
with full CRUD operations.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from .preferences import ContentFilterSettings, Profile
from .profile_manager import ProfileManager


class ProfileDialog(tk.Toplevel):
    """
    Profile Manager dialog window.
    
    Allows users to view, create, edit, and delete filter profiles.
    """
    
    def __init__(
        self, 
        parent: tk.Tk, 
        profile_manager: ProfileManager,
        on_profiles_changed: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        
        self.profile_manager = profile_manager
        self.on_profiles_changed = on_profiles_changed
        self.current_profile: Optional[Profile] = None
        self._unsaved_changes = False
        
        # Window setup
        self.title("Profile Manager")
        self.geometry("700x500")
        self.minsize(600, 400)
        self.transient(parent)
        self.grab_set()
        
        # Dark theme colors (matching main app)
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#4a9eff"
        self.panel_bg = "#2d2d2d"
        self.border_color = "#4a4a4a"
        self.muted_color = "#888888"
        
        self.configure(bg=self.bg_color)
        
        self._create_ui()
        self._load_profiles()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self) -> None:
        """Build the dialog UI."""
        # Configure styles
        style = ttk.Style()
        style.configure("Dark.TFrame", background=self.bg_color)
        style.configure("Panel.TFrame", background=self.panel_bg)
        style.configure("Dark.TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("Panel.TLabel", background=self.panel_bg, foreground=self.fg_color)
        style.configure("Muted.TLabel", background=self.panel_bg, foreground=self.muted_color)
        
        # Main container
        main_frame = tk.Frame(self, bg=self.bg_color, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Label(
            main_frame,
            text="⚙ Profile Manager",
            font=("SF Pro Display", 18, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        header.pack(anchor="w", pady=(0, 15))
        
        # Content area with two panels
        content = tk.Frame(main_frame, bg=self.bg_color)
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=1, minsize=220)
        content.columnconfigure(1, weight=2, minsize=350)
        content.rowconfigure(0, weight=1)
        
        # Left panel: Profile list
        self._create_profile_list(content)
        
        # Right panel: Edit form
        self._create_edit_panel(content)
    
    def _create_profile_list(self, parent: tk.Frame) -> None:
        """Create the left panel with profile list."""
        left_panel = tk.Frame(
            parent,
            bg=self.panel_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # List header
        tk.Label(
            left_panel,
            text="Profiles",
            font=("SF Pro Display", 14, "bold"),
            bg=self.panel_bg,
            fg=self.fg_color,
            padx=15,
            pady=10
        ).pack(anchor="w")
        
        # Listbox with scrollbar
        list_frame = tk.Frame(left_panel, bg=self.panel_bg)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.profile_listbox = tk.Listbox(
            list_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            selectbackground=self.accent_color,
            selectforeground=self.fg_color,
            font=("SF Pro Display", 12),
            relief=tk.FLAT,
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self.profile_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.profile_listbox.yview)
        
        self.profile_listbox.bind("<<ListboxSelect>>", self._on_profile_select)
        
        # Buttons
        btn_frame = tk.Frame(left_panel, bg=self.panel_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self._create_button(btn_frame, "New", self._on_new).pack(side=tk.LEFT, padx=(0, 5))
        self._create_button(btn_frame, "Duplicate", self._on_duplicate).pack(side=tk.LEFT, padx=5)
        self._create_button(btn_frame, "Delete", self._on_delete, danger=True).pack(side=tk.LEFT, padx=5)
    
    def _create_edit_panel(self, parent: tk.Frame) -> None:
        """Create the right panel with edit form."""
        right_panel = tk.Frame(
            parent,
            bg=self.panel_bg,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        right_panel.grid(row=0, column=1, sticky="nsew")
        
        # Edit panel header
        tk.Label(
            right_panel,
            text="Edit Profile",
            font=("SF Pro Display", 14, "bold"),
            bg=self.panel_bg,
            fg=self.fg_color,
            padx=15,
            pady=10
        ).pack(anchor="w")
        
        # Form container
        form = tk.Frame(right_panel, bg=self.panel_bg, padx=15, pady=10)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Profile name
        tk.Label(
            form,
            text="Profile Name",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color
        ).pack(anchor="w")
        
        self.name_entry = tk.Entry(
            form,
            font=("SF Pro Display", 13),
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.border_color
        )
        self.name_entry.pack(fill=tk.X, pady=(5, 15))
        self.name_entry.bind("<KeyRelease>", lambda e: self._mark_unsaved())
        
        # Description
        tk.Label(
            form,
            text="Description",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color
        ).pack(anchor="w")
        
        self.desc_entry = tk.Entry(
            form,
            font=("SF Pro Display", 12),
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.border_color
        )
        self.desc_entry.pack(fill=tk.X, pady=(5, 20))
        self.desc_entry.bind("<KeyRelease>", lambda e: self._mark_unsaved())
        
        # Filter settings section
        tk.Label(
            form,
            text="Content Filters",
            font=("SF Pro Display", 12, "bold"),
            bg=self.panel_bg,
            fg=self.fg_color
        ).pack(anchor="w", pady=(10, 10))
        
        # Checkboxes for filters
        self.var_language = tk.BooleanVar(value=True)
        self.var_sexual = tk.BooleanVar(value=True)
        self.var_nudity = tk.BooleanVar(value=True)
        self.var_mature = tk.BooleanVar(value=False)
        self.var_romance = tk.IntVar(value=0)
        self.var_violence = tk.IntVar(value=0)
        self.var_safe_cover = tk.BooleanVar(value=False)
        self.var_force_subtitles = tk.BooleanVar(value=False)
        self.var_censor_subtitles = tk.BooleanVar(value=True)
        
        self._create_checkbox(form, "Language (profanity and slurs)", self.var_language)
        self._create_checkbox(form, "Sexual Content (in dialogue)", self.var_sexual)
        self._create_checkbox(form, "Nudity (visual detection)", self.var_nudity)
        
        # Romance level
        romance_frame = tk.Frame(form, bg=self.panel_bg)
        romance_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(
            romance_frame,
            text="Romance Intensity",
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        romance_options = tk.Frame(romance_frame, bg=self.panel_bg)
        romance_options.pack(side=tk.RIGHT)
        
        levels = [("Keep All", 0), ("Heavy Only", 1), ("Strict", 2)]
        for text, value in levels:
            rb = tk.Radiobutton(
                romance_options,
                text=text,
                variable=self.var_romance,
                value=value,
                font=("SF Pro Display", 11),
                bg=self.panel_bg,
                fg=self.fg_color,
                selectcolor=self.bg_color,
                activebackground=self.panel_bg,
                activeforeground=self.fg_color,
                command=self._mark_unsaved
            )
            rb.pack(side=tk.LEFT, padx=5)
        
        # Violence level
        violence_frame = tk.Frame(form, bg=self.panel_bg)
        violence_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(
            violence_frame,
            text="Violence Intensity",
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.fg_color
        ).pack(side=tk.LEFT)
        
        violence_options = tk.Frame(violence_frame, bg=self.panel_bg)
        violence_options.pack(side=tk.RIGHT)
        
        v_levels = [("Keep All", 0), ("Gore", 1), ("Death", 2), ("Fighting", 3)]
        for text, value in v_levels:
            rb = tk.Radiobutton(
                violence_options,
                text=text,
                variable=self.var_violence,
                value=value,
                font=("SF Pro Display", 11),
                bg=self.panel_bg,
                fg=self.fg_color,
                selectcolor=self.bg_color,
                activebackground=self.panel_bg,
                activeforeground=self.fg_color,
                command=self._mark_unsaved
            )
            rb.pack(side=tk.LEFT, padx=5)
        
        # Mature themes (greyed out for now)
        mature_cb = self._create_checkbox(
            form, 
            "Mature Themes (drugs, self-harm) - Coming Soon", 
            self.var_mature,
            disabled=True
        )
        
        # Custom phrases collapsible section
        self._create_custom_phrases_section(form)
        
        # Safe Cover section
        safe_cover_frame = tk.Frame(form, bg=self.panel_bg)
        safe_cover_frame.pack(fill=tk.X, pady=(15, 0))
        
        tk.Label(
            safe_cover_frame,
            text="Safe Cover Image",
            font=("SF Pro Display", 11, "bold"),
            bg=self.panel_bg,
            fg=self.muted_color
        ).pack(anchor="w", pady=(0, 5))
        
        self.safe_cover_cb = tk.Checkbutton(
            safe_cover_frame,
            text="🎨  Always generate kid-friendly cover image",
            variable=self.var_safe_cover,
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.fg_color,
            selectcolor=self.bg_color,
            activebackground=self.panel_bg,
            activeforeground=self.fg_color,
            command=self._mark_unsaved
        )
        self.safe_cover_cb.pack(anchor="w")
        
        # Subtitles section
        subtitles_frame = tk.Frame(form, bg=self.panel_bg)
        subtitles_frame.pack(fill=tk.X, pady=(15, 0))
        
        tk.Label(
            subtitles_frame,
            text="Subtitles",
            font=("SF Pro Display", 11, "bold"),
            bg=self.panel_bg,
            fg=self.muted_color
        ).pack(anchor="w", pady=(0, 5))
        
        self.force_subtitles_cb = tk.Checkbutton(
            subtitles_frame,
            text="📝  Force English subtitles (burns into video)",
            variable=self.var_force_subtitles,
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.fg_color,
            selectcolor=self.bg_color,
            activebackground=self.panel_bg,
            activeforeground=self.fg_color,
            command=self._mark_unsaved
        )
        self.force_subtitles_cb.pack(anchor="w")
        
        self.censor_subtitles_cb = tk.Checkbutton(
            subtitles_frame,
            text="🔇  Censor profanity in subtitles",
            variable=self.var_censor_subtitles,
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.fg_color,
            selectcolor=self.bg_color,
            activebackground=self.panel_bg,
            activeforeground=self.fg_color,
            command=self._mark_unsaved
        )
        self.censor_subtitles_cb.pack(anchor="w")
        
        # Spacer
        tk.Frame(form, bg=self.panel_bg, height=20).pack(fill=tk.X)
        
        # Save button
        save_frame = tk.Frame(form, bg=self.panel_bg)
        save_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.save_btn = tk.Button(
            save_frame,
            text="💾 Save Changes",
            font=("SF Pro Display", 13),
            bg=self.accent_color,
            fg=self.fg_color,
            activebackground="#3a8adf",
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self._on_save
        )
        self.save_btn.pack(side=tk.RIGHT)
        
        # Cancel button
        self.cancel_btn = tk.Button(
            save_frame,
            text="Cancel",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color,
            activebackground=self.panel_bg,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=self._on_close
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        self.status_label = tk.Label(
            save_frame,
            text="",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color
        )
        self.status_label.pack(side=tk.LEFT)
    
    def _create_button(
        self, 
        parent: tk.Frame, 
        text: str, 
        command: Callable,
        danger: bool = False
    ) -> tk.Button:
        """Create a styled button."""
        bg = "#d9534f" if danger else self.panel_bg
        return tk.Button(
            parent,
            text=text,
            font=("SF Pro Display", 11),
            bg=bg,
            fg=self.fg_color,
            activebackground=self.accent_color,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=command
        )
    
    def _create_checkbox(
        self, 
        parent: tk.Frame, 
        text: str, 
        variable: tk.BooleanVar,
        disabled: bool = False
    ) -> tk.Checkbutton:
        """Create a styled checkbox."""
        cb = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            font=("SF Pro Display", 12),
            bg=self.panel_bg,
            fg=self.muted_color if disabled else self.fg_color,
            selectcolor=self.bg_color,
            activebackground=self.panel_bg,
            activeforeground=self.fg_color,
            command=self._mark_unsaved,
            state=tk.DISABLED if disabled else tk.NORMAL
        )
        cb.pack(anchor="w", pady=5)
        return cb
    
    def _create_custom_phrases_section(self, parent: tk.Frame) -> None:
        """Create the collapsible custom phrases section."""
        import subprocess
        from pathlib import Path
        
        # Container for the collapsible section
        self.phrases_container = tk.Frame(parent, bg=self.panel_bg)
        self.phrases_container.pack(fill=tk.X, pady=(15, 0))
        
        # Header with chevron toggle
        header_frame = tk.Frame(self.phrases_container, bg=self.panel_bg)
        header_frame.pack(fill=tk.X)
        
        self.phrases_expanded = False
        self.phrases_chevron = tk.Label(
            header_frame,
            text="▶",
            font=("SF Pro Display", 10),
            bg=self.panel_bg,
            fg=self.muted_color,
            cursor="hand2"
        )
        self.phrases_chevron.pack(side=tk.LEFT)
        
        header_label = tk.Label(
            header_frame,
            text="Custom phrases to mute or cut",
            font=("SF Pro Display", 11),
            bg=self.panel_bg,
            fg=self.muted_color,
            cursor="hand2"
        )
        header_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Bind click to toggle
        self.phrases_chevron.bind("<Button-1>", lambda e: self._toggle_custom_phrases())
        header_label.bind("<Button-1>", lambda e: self._toggle_custom_phrases())
        
        # Expandable content frame (initially hidden)
        self.phrases_content = tk.Frame(self.phrases_container, bg=self.panel_bg)
        
        # Multi-line text box (4-6 lines)
        self.phrases_text = tk.Text(
            self.phrases_content,
            height=5,
            font=("SF Pro Display", 11),
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.border_color,
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
        self.phrases_text.bind("<Key>", lambda e: self._mark_unsaved())
        
        # Links/buttons row
        links_frame = tk.Frame(self.phrases_content, bg=self.panel_bg)
        links_frame.pack(fill=tk.X, pady=(8, 0))
        
        # "Open as text file…" link
        self.open_file_link = tk.Label(
            links_frame,
            text="Open as text file…",
            font=("SF Pro Display", 10, "underline"),
            bg=self.panel_bg,
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
            bg=self.panel_bg,
            fg="#555555",
            activebackground=self.panel_bg,
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
        import subprocess
        from pathlib import Path
        
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
    
    def _load_profiles(self) -> None:
        """Load profiles into the listbox."""
        self.profile_listbox.delete(0, tk.END)
        for profile in self.profile_manager.list_profiles():
            # Show name with short summary
            summary = profile.settings.short_summary()
            display_text = f"{profile.name}  •  {summary}" if summary != "None" else profile.name
            self.profile_listbox.insert(tk.END, display_text)
        
        # Select first profile
        if self.profile_listbox.size() > 0:
            self.profile_listbox.selection_set(0)
            self._on_profile_select(None)
    
    def _on_profile_select(self, event) -> None:
        """Handle profile selection."""
        if self._unsaved_changes:
            if not self._confirm_discard():
                # Re-select previous profile
                if self.current_profile:
                    names = self.profile_manager.list_names()
                    if self.current_profile.name in names:
                        idx = names.index(self.current_profile.name)
                        self.profile_listbox.selection_clear(0, tk.END)
                        self.profile_listbox.selection_set(idx)
                return
        
        selection = self.profile_listbox.curselection()
        if not selection:
            return
        
        # Extract profile name from display text (format: "Name  •  Summary")
        display_text = self.profile_listbox.get(selection[0])
        name = display_text.split("  •  ")[0] if "  •  " in display_text else display_text
        
        profile = self.profile_manager.get(name)
        if profile:
            self.current_profile = profile
            self._populate_form(profile)
            self._unsaved_changes = False
            self._update_status("")
    
    def _populate_form(self, profile: Profile) -> None:
        """Fill the form with profile data."""
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, profile.name)
        
        self.desc_entry.delete(0, tk.END)
        self.desc_entry.insert(0, profile.description)
        
        settings = profile.settings
        self.var_language.set(settings.filter_language)
        self.var_sexual.set(settings.filter_sexual_content)
        self.var_nudity.set(settings.filter_nudity)
        self.var_romance.set(settings.filter_romance_level)
        self.var_violence.set(settings.filter_violence_level)
        self.var_mature.set(settings.filter_mature_themes)
        self.var_safe_cover.set(settings.safe_cover_enabled)
        self.var_force_subtitles.set(settings.force_english_subtitles)
        self.var_censor_subtitles.set(settings.censor_subtitle_profanity)
        self._set_custom_phrases(settings.custom_block_phrases)
    
    def _get_form_settings(self) -> ContentFilterSettings:
        """Get settings from the form."""
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
    
    def _mark_unsaved(self) -> None:
        """Mark that there are unsaved changes."""
        self._unsaved_changes = True
        self._update_status("Unsaved changes")
    
    def _update_status(self, text: str) -> None:
        """Update the status label."""
        self.status_label.config(text=text)
    
    def _on_save(self) -> None:
        """Save the current profile."""
        if not self.current_profile:
            return
        
        new_name = self.name_entry.get().strip()
        if not new_name:
            messagebox.showerror("Error", "Profile name cannot be empty")
            return
        
        # Prevent renaming Default
        if self.current_profile.name == "Default" and new_name != "Default":
            messagebox.showerror("Error", "Cannot rename the Default profile")
            return
        
        # Check for duplicate name
        if new_name != self.current_profile.name:
            if new_name in self.profile_manager.list_names():
                messagebox.showerror("Error", f"A profile named '{new_name}' already exists")
                return
        
        # Update profile
        updated_profile = Profile(
            name=new_name,
            description=self.desc_entry.get().strip(),
            settings=self._get_form_settings()
        )
        
        try:
            self.profile_manager.update(self.current_profile.name, updated_profile)
            self.current_profile = updated_profile
            self._unsaved_changes = False
            self._update_status("✓ Saved")
            
            # Refresh list if name changed
            self._load_profiles()
            
            # Notify parent
            if self.on_profiles_changed:
                self.on_profiles_changed()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile: {e}")
    
    def _on_new(self) -> None:
        """Create a new profile."""
        if self._unsaved_changes:
            if not self._confirm_discard():
                return
        
        # Find a unique name
        base_name = "New Profile"
        name = base_name
        counter = 1
        existing = self.profile_manager.list_names()
        while name in existing:
            counter += 1
            name = f"{base_name} {counter}"
        
        new_profile = Profile(
            name=name,
            description="",
            settings=ContentFilterSettings()
        )
        
        try:
            self.profile_manager.add(new_profile)
            self._load_profiles()
            
            # Select the new profile
            names = self.profile_manager.list_names()
            idx = names.index(name)
            self.profile_listbox.selection_clear(0, tk.END)
            self.profile_listbox.selection_set(idx)
            self._on_profile_select(None)
            
            # Focus name entry for immediate editing
            self.name_entry.focus_set()
            self.name_entry.select_range(0, tk.END)
            
            if self.on_profiles_changed:
                self.on_profiles_changed()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create profile: {e}")
    
    def _on_duplicate(self) -> None:
        """Duplicate the selected profile."""
        if not self.current_profile:
            return
        
        if self._unsaved_changes:
            if not self._confirm_discard():
                return
        
        # Find a unique name
        base_name = f"{self.current_profile.name} Copy"
        name = base_name
        counter = 1
        existing = self.profile_manager.list_names()
        while name in existing:
            counter += 1
            name = f"{base_name} {counter}"
        
        try:
            new_profile = self.profile_manager.duplicate(self.current_profile.name, name)
            self._load_profiles()
            
            # Select the new profile
            names = self.profile_manager.list_names()
            idx = names.index(name)
            self.profile_listbox.selection_clear(0, tk.END)
            self.profile_listbox.selection_set(idx)
            self._on_profile_select(None)
            
            if self.on_profiles_changed:
                self.on_profiles_changed()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate profile: {e}")
    
    def _on_delete(self) -> None:
        """Delete the selected profile."""
        if not self.current_profile:
            return
        
        if self.current_profile.name == "Default":
            messagebox.showinfo("Info", "Cannot delete the Default profile")
            return
        
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete profile '{self.current_profile.name}'?\n\nThis cannot be undone."
        ):
            return
        
        try:
            self.profile_manager.delete(self.current_profile.name)
            self.current_profile = None
            self._unsaved_changes = False
            self._load_profiles()
            
            if self.on_profiles_changed:
                self.on_profiles_changed()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete profile: {e}")
    
    def _confirm_discard(self) -> bool:
        """Ask user to confirm discarding unsaved changes."""
        return messagebox.askyesno(
            "Unsaved Changes",
            "You have unsaved changes. Discard them?"
        )
    
    def _on_close(self) -> None:
        """Handle window close."""
        if self._unsaved_changes:
            if not self._confirm_discard():
                return
        self.destroy()
