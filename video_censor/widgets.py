"""
Custom Modern Widgets for Video Censor GUI

Premium UI components including toggle switches and gradient progress bars.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Tuple


class ModernToggle(tk.Canvas):
    """
    iOS-style toggle switch widget.
    
    A sleek, animated toggle switch with smooth rounded track and sliding knob.
    """
    
    def __init__(
        self,
        parent,
        variable: Optional[tk.BooleanVar] = None,
        on_color: str = "#3b82f6",
        off_color: str = "#3a3a45",
        knob_color: str = "#ffffff",
        width: int = 44,
        height: int = 24,
        command: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg=kwargs.get('bg', parent.cget('bg')),
            **{k: v for k, v in kwargs.items() if k != 'bg'}
        )
        
        self.on_color = on_color
        self.off_color = off_color
        self.knob_color = knob_color
        self.toggle_width = width
        self.toggle_height = height
        self.command = command
        
        # State
        self.variable = variable or tk.BooleanVar(value=False)
        self._value = self.variable.get()
        
        # Animation state
        self._animating = False
        self._target_x = 0
        self._current_x = 0
        
        # Draw initial state
        self._draw()
        
        # Bindings
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        # Watch for variable changes
        self.variable.trace_add("write", self._on_variable_change)
    
    def _draw(self) -> None:
        """Draw the toggle switch."""
        self.delete("all")
        
        w = self.toggle_width
        h = self.toggle_height
        r = h // 2  # Radius for rounded ends
        padding = 2
        knob_r = r - padding
        
        # Determine colors based on state
        bg_color = self.on_color if self._value else self.off_color
        
        # Draw rounded track
        self.create_oval(0, 0, h, h, fill=bg_color, outline="", tags="track")
        self.create_oval(w - h, 0, w, h, fill=bg_color, outline="", tags="track")
        self.create_rectangle(r, 0, w - r, h, fill=bg_color, outline="", tags="track")
        
        # Calculate knob position
        if self._value:
            knob_x = w - r
        else:
            knob_x = r
        
        # Use animation position if animating
        if self._animating:
            knob_x = self._current_x
        
        # Draw knob with subtle shadow (use solid color for Tk compatibility)
        shadow_offset = 1
        self.create_oval(
            knob_x - knob_r + shadow_offset,
            padding + shadow_offset,
            knob_x + knob_r + shadow_offset,
            h - padding + shadow_offset,
            fill="#1a1a1f",
            outline="",
            tags="shadow"
        )
        
        # Draw knob
        self.create_oval(
            knob_x - knob_r,
            padding,
            knob_x + knob_r,
            h - padding,
            fill=self.knob_color,
            outline="",
            tags="knob"
        )
    
    def _on_click(self, event) -> None:
        """Handle click to toggle."""
        self._value = not self._value
        self.variable.set(self._value)
        self._animate_toggle()
        
        if self.command:
            self.command()
    
    def _on_variable_change(self, *args) -> None:
        """Handle external variable changes."""
        new_value = self.variable.get()
        if new_value != self._value:
            self._value = new_value
            self._animate_toggle()
    
    def _animate_toggle(self) -> None:
        """Animate the toggle transition."""
        w = self.toggle_width
        h = self.toggle_height
        r = h // 2
        
        start_x = r if self._value else w - r
        end_x = w - r if self._value else r
        
        self._current_x = start_x
        self._target_x = end_x
        self._animating = True
        self._animate_step()
    
    def _animate_step(self) -> None:
        """Single animation frame."""
        if not self._animating:
            return
        
        # Ease towards target
        diff = self._target_x - self._current_x
        if abs(diff) < 1:
            self._current_x = self._target_x
            self._animating = False
        else:
            self._current_x += diff * 0.3
        
        self._draw()
        
        if self._animating:
            self.after(10, self._animate_step)
    
    def _on_enter(self, event) -> None:
        """Hover effect."""
        self.configure(cursor="hand2")
    
    def _on_leave(self, event) -> None:
        """Remove hover effect."""
        self.configure(cursor="")
    
    def get(self) -> bool:
        """Get current value."""
        return self._value
    
    def set(self, value: bool) -> None:
        """Set value externally."""
        self.variable.set(value)


class GradientProgressBar(tk.Canvas):
    """
    Modern gradient progress bar.
    
    Features rounded ends and a smooth gradient fill.
    """
    
    def __init__(
        self,
        parent,
        width: int = 200,
        height: int = 8,
        gradient_start: str = "#3b82f6",
        gradient_end: str = "#8b5cf6",
        bg_color: str = "#2a2a35",
        value: float = 0.0,
        **kwargs
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg=kwargs.get('bg', parent.cget('bg')),
            **{k: v for k, v in kwargs.items() if k != 'bg'}
        )
        
        self.bar_width = width
        self.bar_height = height
        self.gradient_start = gradient_start
        self.gradient_end = gradient_end
        self.track_color = bg_color
        self._value = min(max(value, 0.0), 1.0)
        
        self._draw()
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """Convert RGB tuple to hex color."""
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    def _interpolate_color(self, color1: str, color2: str, t: float) -> str:
        """Interpolate between two colors."""
        rgb1 = self._hex_to_rgb(color1)
        rgb2 = self._hex_to_rgb(color2)
        
        rgb = tuple(int(rgb1[i] + (rgb2[i] - rgb1[i]) * t) for i in range(3))
        return self._rgb_to_hex(rgb)
    
    def _draw(self) -> None:
        """Draw the progress bar."""
        self.delete("all")
        
        w = self.bar_width
        h = self.bar_height
        r = h // 2
        
        # Draw track (rounded rectangle)
        self._draw_rounded_rect(0, 0, w, h, r, self.track_color, "track")
        
        # Calculate fill width
        fill_width = max(h, int(w * self._value))  # Minimum width = height for rounded look
        
        if self._value > 0:
            # Draw gradient fill using multiple thin rectangles
            steps = max(1, fill_width - h)  # Subtract diameter for proper sizing
            
            for i in range(steps):
                x = r + i
                t = i / max(1, steps - 1) if steps > 1 else 0
                color = self._interpolate_color(self.gradient_start, self.gradient_end, t)
                self.create_line(x, 1, x, h - 1, fill=color, tags="fill")
            
            # Draw rounded caps
            self.create_oval(0, 0, h, h, fill=self.gradient_start, outline="", tags="fill_cap")
            
            if fill_width >= h:
                end_color = self._interpolate_color(
                    self.gradient_start, 
                    self.gradient_end, 
                    min(1.0, self._value)
                )
                cap_x = min(fill_width - h, w - h)
                self.create_oval(cap_x, 0, cap_x + h, h, fill=end_color, outline="", tags="fill_cap")
    
    def _draw_rounded_rect(
        self, 
        x1: int, 
        y1: int, 
        x2: int, 
        y2: int, 
        r: int, 
        fill: str, 
        tags: str
    ) -> None:
        """Draw a rounded rectangle."""
        self.create_oval(x1, y1, x1 + 2*r, y2, fill=fill, outline="", tags=tags)
        self.create_oval(x2 - 2*r, y1, x2, y2, fill=fill, outline="", tags=tags)
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
    
    def set_value(self, value: float) -> None:
        """Set progress value (0.0 to 1.0)."""
        self._value = min(max(value, 0.0), 1.0)
        self._draw()
    
    def get_value(self) -> float:
        """Get current value."""
        return self._value


class ModernFilterRow(tk.Frame):
    """
    A styled filter row with label and toggle switch.
    """
    
    def __init__(
        self,
        parent,
        text: str,
        variable: tk.BooleanVar,
        emoji: str = "",
        bg_color: str = "#141419",
        fg_color: str = "#ffffff",
        accent_color: str = "#3b82f6",
        command: Optional[Callable] = None,
        disabled: bool = False,
        **kwargs
    ):
        super().__init__(parent, bg=bg_color, **kwargs)
        
        self.variable = variable
        self.disabled = disabled
        
        # Container with hover effect
        self.configure(padx=0, pady=6)
        
        # Label with emoji
        display_text = f"{emoji}  {text}" if emoji else text
        self.label = tk.Label(
            self,
            text=display_text,
            font=("SF Pro Display", 12),
            bg=bg_color,
            fg="#666666" if disabled else fg_color,
            anchor="w"
        )
        self.label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Toggle switch
        if not disabled:
            self.toggle = ModernToggle(
                self,
                variable=variable,
                on_color=accent_color,
                bg=bg_color,
                command=command
            )
            self.toggle.pack(side=tk.RIGHT, padx=(10, 0))
        else:
            # Disabled state - show "Coming Soon" badge
            badge = tk.Label(
                self,
                text="Soon",
                font=("SF Pro Display", 9),
                bg="#2a2a35",
                fg="#666666",
                padx=6,
                pady=2
            )
            badge.pack(side=tk.RIGHT, padx=(10, 0))


class StatusDot(tk.Canvas):
    """
    A small colored status indicator dot.
    """
    
    STATUS_COLORS = {
        'pending': "#666666",
        'processing': "#3b82f6",
        'complete': "#22c55e",
        'error': "#ef4444",
        'cancelled': "#666666"
    }
    
    def __init__(
        self,
        parent,
        status: str = "pending",
        size: int = 8,
        **kwargs
    ):
        super().__init__(
            parent,
            width=size,
            height=size,
            highlightthickness=0,
            bg=kwargs.get('bg', parent.cget('bg')),
            **{k: v for k, v in kwargs.items() if k != 'bg'}
        )
        
        self.size = size
        self._status = status
        self._draw()
    
    def _draw(self) -> None:
        """Draw the status dot."""
        self.delete("all")
        color = self.STATUS_COLORS.get(self._status, "#666666")
        self.create_oval(0, 0, self.size, self.size, fill=color, outline="")
    
    def set_status(self, status: str) -> None:
        """Update status."""
        self._status = status
        self._draw()
