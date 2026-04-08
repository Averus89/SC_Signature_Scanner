#!/usr/bin/env python3
"""
Overlay popup for SC Signature Scanner.
Shows signature identification results on top of the game.
"""

import tkinter as tk
from typing import List, Dict, Any, Optional, Tuple, Callable

from theme import RegolithTheme


class OverlayPopup:
    """Always-on-top overlay popup for showing signature results."""

    # Colors — sourced from RegolithTheme so palette changes propagate here automatically
    _C = RegolithTheme.COLORS
    BG_COLOR = _C['bg_dark']
    BG_LIGHT = _C['bg_main']
    BORDER_COLOR = _C['border']
    FG_COLOR = _C['text_primary']
    ACCENT_COLOR = _C['accent_primary']
    HEADER_COLOR = _C['accent_secondary']
    SHIP_COLOR = _C['cyan']
    MINING_COLOR = _C['accent_primary']
    SALVAGE_COLOR = "#a371f7"  # salvage purple — not in RegolithTheme palette
    MUTED_COLOR = _C['text_secondary']
    
    def __init__(
        self,
        root: tk.Tk,
        position: Tuple[int, int] = None,
        duration: int = 10,
        scale: float = 1.0,
    ):
        """
        Initialize overlay.

        Args:
            root: The application's Tk root window. Overlay windows are
                Toplevel children of this root so there is only one Tk instance.
            position: (x, y) tuple for top-left corner, or None for center
            duration: seconds to display
            scale: font/size scale factor (0.5 to 2.0)
        """
        self._root = root
        self.position = position  # (x, y) tuple
        self.duration = duration
        self.scale = max(0.5, min(2.0, scale))  # Clamp to valid range
        self.window: Optional[tk.Toplevel] = None
        self._after_id = None
    
    def set_position(self, x: int, y: int):
        """Set the overlay position."""
        self.position = (x, y)
    
    def show(self, signature: int, matches: List[Dict[str, Any]]):
        """Show the overlay with signature results."""
        # Cancel any pending hide
        if self._after_id and self.window:
            try:
                self.window.after_cancel(self._after_id)
            except tk.TclError:
                pass
        
        # Destroy existing window
        if self.window:
            self.window.destroy()
        
        # Create new overlay window
        self.window = tk.Toplevel(self._root)
        self.window.overrideredirect(True)  # No window decorations
        self.window.attributes('-topmost', True)  # Always on top
        self.window.attributes('-alpha', 0.95)  # Slight transparency
        self.window.configure(bg=self.BG_COLOR)
        
        # Build content
        self._build_content(signature, matches)
        
        # Position window
        self.window.update_idletasks()
        self._position_window()
        
        # Schedule hide using Tkinter's after() - thread safe
        self._after_id = self.window.after(self.duration * 1000, self._hide)
    
    def _scaled_font(self, family: str, base_size: int, weight: str = "") -> tuple:
        """Return a font tuple scaled by the scale factor."""
        scaled_size = int(base_size * self.scale)
        if weight:
            return (family, scaled_size, weight)
        return (family, scaled_size)
    
    def _build_content(self, signature: int, matches: List[Dict[str, Any]]):
        """Build the popup content."""
        # Scaled padding (increased horizontal for wider popup)
        pad_x = int(20 * self.scale)  # 10% wider
        pad_y = int(12 * self.scale)
        pad_small = int(8 * self.scale)
        
        # Outer border frame
        border = tk.Frame(self.window, bg=self.BORDER_COLOR, padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        
        frame = tk.Frame(border, bg=self.BG_COLOR, padx=pad_x, pady=pad_y)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with signature value
        header = tk.Label(
            frame,
            text=f"SIGNATURE: {signature:,}",
            font=self._scaled_font("Consolas", 14, "bold"),
            fg=self.HEADER_COLOR,
            bg=self.BG_COLOR
        )
        header.pack(anchor=tk.W, pady=(0, pad_small))
        
        # Separator
        sep = tk.Frame(frame, height=int(2 * self.scale), bg=self.ACCENT_COLOR)
        sep.pack(fill=tk.X, pady=(0, int(10 * self.scale)))
        
        # Results
        if not matches:
            no_match = tk.Label(
                frame,
                text="No matches found",
                font=self._scaled_font("Segoe UI", 10),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            )
            no_match.pack(anchor=tk.W)
        else:
            # Show first match with composition
            match = matches[0]
            self._add_match_with_composition(frame, match)
        
        # Close hint
        hint = tk.Label(
            frame,
            text=f"Auto-hide in {self.duration}s",
            font=self._scaled_font("Segoe UI", 8),
            fg=self.MUTED_COLOR,
            bg=self.BG_COLOR
        )
        hint.pack(anchor=tk.E, pady=(int(10 * self.scale), 0))
    
    def _add_match_with_composition(self, parent: tk.Frame, match: Dict[str, Any]):
        """Add a match row with mineral composition breakdown."""
        # Main container
        container = tk.Frame(parent, bg=self.BG_COLOR)
        container.pack(fill=tk.X, pady=int(3 * self.scale))
        
        # Rock type name and icon
        match_type = match.get('type', 'unknown')
        category = match.get('category', '')
        
        # Match categories from scanner.py
        if category == 'ship_mining' or match_type == 'ship_mining':
            tier = match.get('tier', '').lower()
            if tier in ('legendary', 'epic'):
                color = "#f85149"   # Red — extreme value
            elif tier == 'rare':
                color = "#a371f7"   # Purple — high value
            elif tier == 'uncommon':
                color = self.MINING_COLOR  # Orange — medium value
            else:
                color = self.MUTED_COLOR   # Grey — common
            icon = "🪨"
        elif category == 'space_deposit' or match_type == 'space_deposits':
            color = self.MINING_COLOR
            icon = "🪨"
        elif category == 'surface_deposit' or match_type == 'surface_deposits':
            color = self.MINING_COLOR
            icon = "⛏️"
        elif match_type == 'ground_deposit' or category == 'ground_deposits':
            variant = match.get('variant', '')
            if variant == 'small':
                color = "#a371f7"  # Purple for hand mining
                icon = "💎"
            else:
                color = "#a371f7"  # Purple for vehicle mining  
                icon = "🚗"
        elif match_type == 'salvage':
            color = self.SALVAGE_COLOR
            icon = "🔧"
        elif match_type == 'salvage_debris':
            color = self.SALVAGE_COLOR
            icon = "🪛"
        elif match_type == 'known':
            color = self.MINING_COLOR
            icon = "📡"
        else:
            color = self.FG_COLOR
            icon = "❓"
        
        # Header row: Icon + Name + Value
        header_row = tk.Frame(container, bg=self.BG_COLOR)
        header_row.pack(fill=tk.X, pady=(0, int(3 * self.scale)))
        
        name = match.get('name', 'Unknown')
        name_label = tk.Label(
            header_row,
            text=f"{icon} {name}",
            font=self._scaled_font("Segoe UI", 12, "bold"),
            fg="#3fb950",
            bg=self.BG_COLOR,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT)
        
        # Mining method indicator
        if category == 'ship_mining' or match_type == 'ship_mining':
            tier = match.get('tier', '').capitalize()
            mining_method = f"🚀 Ship Mining — {tier} tier"
            method_color = self.SHIP_COLOR
        elif category == 'space_deposit' or match_type == 'space_deposits':
            mining_method = "🚀 Ship Mining"
            method_color = self.SHIP_COLOR
        elif category == 'surface_deposit' or match_type == 'surface_deposits':
            mining_method = "🚀 Ship Mining"
            method_color = self.SHIP_COLOR
        elif match_type == 'ground_deposit' or category == 'ground_deposits':
            variant = match.get('variant', '')
            if variant == 'small':
                mining_method = "💎 Hand Mining"
                method_color = "#a371f7"  # Purple
            else:
                mining_method = "🚗 ROC Mining"
                method_color = "#a371f7"  # Purple
        elif match_type == 'salvage':
            mining_method = "🔧 Hull Scraping"
            method_color = self.SALVAGE_COLOR
        elif match_type == 'salvage_debris':
            mining_method = "🪛 Wreck Debris — Tractor Beam / Collect"
            method_color = self.SALVAGE_COLOR
        elif match_type == 'known':
            mining_method = None
            method_color = self.MUTED_COLOR
        else:
            mining_method = None
            method_color = self.MUTED_COLOR
        
        if mining_method:
            method_row = tk.Frame(container, bg=self.BG_COLOR)
            method_row.pack(fill=tk.X, pady=(0, int(5 * self.scale)))
            
            method_label = tk.Label(
                method_row,
                text=mining_method,
                font=self._scaled_font("Segoe UI", 9),
                fg=method_color,
                bg=self.BG_COLOR,
                anchor=tk.W
            )
            method_label.pack(side=tk.LEFT)
        
        single_mineral = match.get('single_mineral', False)
        
        if single_mineral:
            # Single mineral deposit — two sub-cases:
            # 1. ship_mining: mineral is KNOWN from the signature (show it definitively)
            # 2. ground deposit: mineral is unknown (show possible list)
            mineral_known = match.get('mineral') and category == 'ship_mining'
            possible_minerals = match.get('possible_minerals', [])
            info_row = tk.Frame(container, bg=self.BG_LIGHT)
            info_row.pack(fill=tk.X, pady=(int(5 * self.scale), 0))

            if mineral_known:
                pass
            elif possible_minerals:
                minerals_text = ", ".join(possible_minerals[:5])  # Show first 5
                if len(possible_minerals) > 5:
                    minerals_text += f" (+{len(possible_minerals) - 5} more)"
                tk.Label(
                    info_row,
                    text="Possible mineral:",
                    font=self._scaled_font("Consolas", 9),
                    fg=self.MUTED_COLOR,
                    bg=self.BG_LIGHT,
                    padx=10
                ).pack(anchor=tk.W, pady=(5, 0))
                tk.Label(
                    info_row,
                    text=minerals_text,
                    font=self._scaled_font("Consolas", 10),
                    fg="#3fb950",
                    bg=self.BG_LIGHT,
                    padx=10
                ).pack(anchor=tk.W, pady=(0, 5))
            else:
                tk.Label(
                    info_row,
                    text="100% single mineral purity",
                    font=self._scaled_font("Consolas", 10),
                    fg="#3fb950",
                    bg=self.BG_LIGHT,
                    padx=10,
                    pady=5
                ).pack(anchor=tk.W)
            
    
    def _position_window(self):
        """Position the window based on settings."""
        if self.position:
            # Use saved position
            x, y = self.position
            self.window.geometry(f"+{x}+{y}")
        else:
            # Default to center
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.window.geometry(f"+{x}+{y}")
    
    def _hide(self):
        """Hide the overlay."""
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
    
    def destroy(self):
        """Cleanup resources."""
        if self._after_id and self.window:
            try:
                self.window.after_cancel(self._after_id)
            except tk.TclError:
                pass
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class PositionAdjuster:
    """Draggable window for setting overlay position."""

    # Colors — sourced from RegolithTheme so palette changes propagate here automatically
    _C = RegolithTheme.COLORS
    BG_COLOR = _C['bg_dark']
    BG_LIGHT = _C['bg_main']
    BORDER_COLOR = _C['border']
    ACCENT_COLOR = _C['accent_primary']
    CYAN = _C['cyan']
    TEXT_PRIMARY = _C['text_primary']
    TEXT_MUTED = _C['text_secondary']
    SUCCESS = _C['success']
    ERROR = _C['error']
    
    def __init__(self, parent: tk.Tk, current_position: Tuple[int, int] = None, 
                 on_save: Callable[[int, int], None] = None):
        """
        Create position adjuster window.
        
        Args:
            parent: Parent Tk window
            current_position: Starting (x, y) position
            on_save: Callback with (x, y) when saved
        """
        self.parent = parent
        self.on_save = on_save
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Create window as Toplevel (not new Tk root)
        self.window = tk.Toplevel(parent)
        self.window.title("Adjust Overlay Position")
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.95)
        self.window.configure(bg=self.BG_COLOR)
        
        # Build content
        self._build_content()
        
        # Position window
        self.window.update_idletasks()
        if current_position:
            x, y = current_position
        else:
            # Center by default
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
        
        self.window.geometry(f"+{x}+{y}")
        
        # Bind drag events
        self.window.bind('<Button-1>', self._start_drag)
        self.window.bind('<B1-Motion>', self._on_drag)
        
        # Handle window close (X button or escape)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
    
    def _build_content(self):
        """Build the adjuster UI."""
        # Outer border
        border = tk.Frame(self.window, bg=self.BORDER_COLOR, padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        
        frame = tk.Frame(border, bg=self.BG_COLOR, padx=20, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(
            frame,
            text="📍 OVERLAY POSITION",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_COLOR,
            bg=self.BG_COLOR
        )
        title.pack(pady=(0, 8))
        
        # Instructions
        instructions = tk.Label(
            frame,
            text="Drag this window to desired position",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_COLOR
        )
        instructions.pack(pady=(0, 15))
        
        # Separator
        sep = tk.Frame(frame, height=2, bg=self.ACCENT_COLOR)
        sep.pack(fill=tk.X, pady=(0, 15))
        
        # Sample content (to show approximate size)
        sample_border = tk.Frame(frame, bg=self.BORDER_COLOR)
        sample_border.pack(fill=tk.X, pady=(0, 15))
        
        sample_inner = tk.Frame(sample_border, bg=self.BG_LIGHT, padx=10, pady=8)
        sample_inner.pack(fill=tk.X, padx=1, pady=1)
        
        sample = tk.Label(
            sample_inner,
            text="SIGNATURE: 8,500\n──────────────\n1. 🚀 Gladius (front)\n2. ⛏️ C-type Asteroid ×5\n3. 🔧 Salvage Panels (4)",
            font=("Consolas", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_LIGHT,
            justify=tk.LEFT
        )
        sample.pack(anchor=tk.W)
        
        # Position display
        self.pos_label = tk.Label(
            frame,
            text="Position: (0, 0)",
            font=("Consolas", 10),
            fg=self.CYAN,
            bg=self.BG_COLOR
        )
        self.pos_label.pack(pady=(0, 15))
        
        # Buttons
        btn_frame = tk.Frame(frame, bg=self.BG_COLOR)
        btn_frame.pack(fill=tk.X)
        
        save_btn = tk.Button(
            btn_frame,
            text="✓ Save Position",
            font=("Segoe UI", 10, "bold"),
            bg=self.SUCCESS,
            fg=self.BG_COLOR,
            activebackground="#4cc764",
            activeforeground=self.BG_COLOR,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._save
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_btn = tk.Button(
            btn_frame,
            text="✗ Cancel",
            font=("Segoe UI", 10),
            bg=self.ERROR,
            fg=self.TEXT_PRIMARY,
            activebackground="#f97583",
            activeforeground=self.TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._cancel
        )
        cancel_btn.pack(side=tk.LEFT)
    
    def _start_drag(self, event):
        """Start dragging."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        """Handle drag motion."""
        x = self.window.winfo_x() + event.x - self._drag_start_x
        y = self.window.winfo_y() + event.y - self._drag_start_y
        self.window.geometry(f"+{x}+{y}")
        self.pos_label.config(text=f"Position: ({x}, {y})")
    
    def _save(self):
        """Save position and close."""
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.destroy()
        if self.on_save:
            self.on_save(x, y)
    
    def _cancel(self):
        """Cancel and close."""
        self.window.destroy()
    
    def run(self):
        """Run the adjuster (blocking until closed)."""
        # Make modal - wait for this window to close
        self.window.grab_set()
        self.parent.wait_window(self.window)

