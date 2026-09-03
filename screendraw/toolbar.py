"""The floating control bar."""

from __future__ import annotations

import tkinter as tk

from . import config
from .model import ARROW, ELLIPSE, FREEHAND, RECTANGLE

TOOL_BUTTONS = (
    (FREEHAND, "Pen", "1"),
    (ARROW, "Arrow", "2"),
    (RECTANGLE, "Rect", "3"),
    (ELLIPSE, "Circle", "4"),
)

# Keeps the bar clear of the title bar of a maximised window underneath.
TOOLBAR_TOP_MARGIN = 60


class Toolbar:
    """A small always-on-top window holding the tool, colour and width pickers.

    The bar talks to the application through the ``controller`` object rather
    than reaching into it, so the widget layout stays independent of the
    drawing logic.
    """

    def __init__(self, master: tk.Misc, controller) -> None:
        self.controller = controller
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=config.TOOLBAR_BG)

        self._tool_buttons: dict[str, tk.Button] = {}
        self._color_buttons: dict[str, tk.Label] = {}
        self._width_buttons: dict[int, tk.Button] = {}
        self._visible = True

        outer = tk.Frame(self.window, bg=config.TOOLBAR_BG, padx=6, pady=5)
        outer.pack(fill="both", expand=True)

        self._build_grip(outer)
        self._build_tools(outer)
        self._build_colors(outer)
        self._build_widths(outer)
        self._build_actions(outer)

        self.window.update()

    # --- construction --------------------------------------------------
    def _separator(self, parent: tk.Misc) -> None:
        tk.Frame(parent, bg=config.TOOLBAR_MUTED, width=1).pack(
            side="left", fill="y", padx=6, pady=2)

    def _build_grip(self, parent: tk.Misc) -> None:
        grip = tk.Label(parent, text="\u2630", bg=config.TOOLBAR_BG,
                        fg=config.TOOLBAR_FG, cursor="fleur",
                        font=("Segoe UI", 11))
        grip.pack(side="left", padx=(2, 6))
        grip.bind("<Button-1>", self._start_drag)
        grip.bind("<B1-Motion>", self._on_drag)

    def _build_tools(self, parent: tk.Misc) -> None:
        for kind, label, key in TOOL_BUTTONS:
            button = tk.Button(
                parent, text=f"{label}\n{key}", width=6,
                font=("Segoe UI", 8), bd=0, relief="flat",
                bg=config.TOOLBAR_MUTED, fg=config.TOOLBAR_FG,
                activebackground=config.TOOLBAR_ACCENT,
                activeforeground="#FFFFFF", cursor="hand2",
                command=lambda k=kind: self.controller.set_tool(k))
            button.pack(side="left", padx=2)
            self._tool_buttons[kind] = button
        self._separator(parent)

    def _build_colors(self, parent: tk.Misc) -> None:
        for name, value in config.PALETTE:
            swatch = tk.Label(parent, bg=value, width=2, height=1,
                              bd=2, relief="flat", cursor="hand2")
            swatch.pack(side="left", padx=2)
            swatch.bind("<Button-1>", lambda _e, v=value: self.controller.set_color(v))
            self._color_buttons[value] = swatch
        self._separator(parent)

    def _build_widths(self, parent: tk.Misc) -> None:
        for label, value in config.WIDTHS:
            button = tk.Button(
                parent, text=label, width=6, font=("Segoe UI", 8),
                bd=0, relief="flat", bg=config.TOOLBAR_MUTED,
                fg=config.TOOLBAR_FG, activebackground=config.TOOLBAR_ACCENT,
                activeforeground="#FFFFFF", cursor="hand2",
                command=lambda v=value: self.controller.set_width(v))
            button.pack(side="left", padx=2)
            self._width_buttons[value] = button
        self._separator(parent)

    def _action_button(self, parent: tk.Misc, text: str, command,
                       bg: str | None = None, width: int = 6) -> tk.Button:
        button = tk.Button(
            parent, text=text, width=width, font=("Segoe UI", 8),
            bd=0, relief="flat", bg=bg or config.TOOLBAR_MUTED,
            fg=config.TOOLBAR_FG, activebackground=config.TOOLBAR_ACCENT,
            activeforeground="#FFFFFF", cursor="hand2", command=command)
        button.pack(side="left", padx=2)
        return button

    def _build_actions(self, parent: tk.Misc) -> None:
        self.undo_button = self._action_button(parent, "Undo", self.controller.undo)
        self.redo_button = self._action_button(parent, "Redo", self.controller.redo)
        self._action_button(parent, "Clear", self.controller.clear)
        self._separator(parent)
        self.mode_button = self._action_button(
            parent, "Draw: ON", self.controller.toggle_draw_mode, width=9)
        self._action_button(parent, "\u2715", self.controller.quit,
                            bg="#7F1D1D", width=3)

    # --- dragging ------------------------------------------------------
    def _start_drag(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root - self.window.winfo_x(),
                             event.y_root - self.window.winfo_y())

    def _on_drag(self, event: tk.Event) -> None:
        offset_x, offset_y = self._drag_origin
        self.window.geometry(
            f"+{event.x_root - offset_x}+{event.y_root - offset_y}")
        self.window.update_idletasks()

    # --- state ---------------------------------------------------------
    def place_top_center(self, screen_x: int, screen_y: int, screen_width: int) -> None:
        """Centre the bar near the top of the primary desktop area."""
        self.window.update()
        width = self.window.winfo_width()
        if width <= 1:  # not mapped yet, fall back to the requested size
            width = self.window.winfo_reqwidth()
        x = screen_x + max(0, (screen_width - width) // 2)
        self.window.geometry(f"+{x}+{screen_y + TOOLBAR_TOP_MARGIN}")
        # Flush the move to the real window. A pending geometry request would
        # otherwise be discarded by the next SetWindowPos call.
        self.window.update_idletasks()

    def sync(self, *, tool: str, color: str, width: int, drawing: bool,
             can_undo: bool, can_redo: bool) -> None:
        """Repaint the bar so it matches the current application state."""
        for kind, button in self._tool_buttons.items():
            selected = kind == tool
            button.configure(
                bg=config.TOOLBAR_ACCENT if selected else config.TOOLBAR_MUTED)

        for value, swatch in self._color_buttons.items():
            swatch.configure(relief="solid" if value == color else "flat",
                             bd=2, highlightthickness=0)

        for value, button in self._width_buttons.items():
            selected = value == width
            button.configure(
                bg=config.TOOLBAR_ACCENT if selected else config.TOOLBAR_MUTED)

        self.mode_button.configure(
            text="Draw: ON" if drawing else "Draw: OFF",
            bg="#166534" if drawing else "#7C2D12")
        self.undo_button.configure(state="normal" if can_undo else "disabled")
        self.redo_button.configure(state="normal" if can_redo else "disabled")

    def toggle_visibility(self) -> None:
        self._visible = not self._visible
        if self._visible:
            self.window.deiconify()
        else:
            self.window.withdraw()

    @property
    def visible(self) -> bool:
        return self._visible
