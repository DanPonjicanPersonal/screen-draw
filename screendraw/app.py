"""The screen annotation overlay.

Windows cannot deliver mouse input to fully transparent pixels, so the overlay
is split across two stacked full-screen windows:

* the **ink layer** is chroma-key transparent and flagged ``WS_EX_TRANSPARENT``
  so it is purely visual and never intercepts the mouse, and
* the **input catcher** sits directly underneath it at 1% opacity, which is
  invisible in practice but still hit-testable, so it receives every stroke.

Hiding the input catcher therefore hands the mouse straight back to whatever
application is underneath while the annotations stay on screen.
"""

from __future__ import annotations

import tkinter as tk

from . import config, win32
from .hotkeys import HotkeyManager
from .model import (ARROW, ELLIPSE, FREEHAND, RECTANGLE, DrawingModel, Shape,
                    constrain_angle, constrain_square)
from .toolbar import Toolbar

PREVIEW_TAG = "preview"
RESTACK_INTERVAL_MS = 2000
HOTKEY_POLL_MS = 40


class ScreenDrawApp:
    def __init__(self) -> None:
        win32.enable_dpi_awareness()

        self.model = DrawingModel()
        self.tool = FREEHAND
        self.color = config.DEFAULT_COLOR
        self.width = config.DEFAULT_WIDTH
        # Start in pass-through mode. Capturing the mouse behind an invisible
        # full-screen window before the user has asked for it feels like a
        # broken mouse, so drawing begins only once a tool is chosen.
        self.drawing_mode = False
        self._stroke: dict | None = None
        self._closing = False
        self._scheduled: list[str] = []

        self.root = tk.Tk()
        self.root.withdraw()

        self.origin_x, self.origin_y, self.screen_w, self.screen_h = win32.virtual_screen()
        geometry = (f"{self.screen_w}x{self.screen_h}"
                    f"+{self.origin_x}+{self.origin_y}")

        self._build_input_catcher(geometry)
        self._build_ink_layer(geometry)
        self.toolbar = Toolbar(self.root, self)
        win32.hide_from_taskbar(self.toolbar.window)
        self.toolbar.place_top_center(self.origin_x, self.origin_y, self.screen_w)

        self._bind_mouse()
        self._bind_keys()
        self._start_hotkeys()

        self.set_draw_mode(False)
        self._restack_loop()
        self._poll_hotkeys()

    # --- window construction -------------------------------------------
    def _build_input_catcher(self, geometry: str) -> None:
        self.catcher = tk.Toplevel(self.root)
        self.catcher.overrideredirect(True)
        self.catcher.geometry(geometry)
        self.catcher.configure(bg=config.CATCHER_COLOR, cursor="crosshair")
        self.catcher.attributes("-topmost", True)
        self.catcher.attributes("-alpha", config.CATCHER_ALPHA)
        self.catcher.update_idletasks()
        win32.hide_from_taskbar(self.catcher)

    def _build_ink_layer(self, geometry: str) -> None:
        self.ink = tk.Toplevel(self.root)
        self.ink.overrideredirect(True)
        self.ink.geometry(geometry)
        self.ink.configure(bg=config.CHROMA_KEY)
        self.ink.attributes("-topmost", True)
        self.ink.attributes("-transparentcolor", config.CHROMA_KEY)
        self.canvas = tk.Canvas(self.ink, bg=config.CHROMA_KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.ink.update_idletasks()
        win32.hide_from_taskbar(self.ink)
        win32.set_click_through(self.ink, True)

    # --- event wiring ---------------------------------------------------
    def _bind_mouse(self) -> None:
        self.catcher.bind("<Button-1>", self._on_press)
        self.catcher.bind("<B1-Motion>", self._on_motion)
        self.catcher.bind("<ButtonRelease-1>", self._on_release)
        self.catcher.bind("<Button-3>", lambda _e: self.undo())

    def _bind_keys(self) -> None:
        keys = {
            "1": FREEHAND, "2": ARROW, "3": RECTANGLE, "4": ELLIPSE,
        }
        for key, tool in keys.items():
            self.catcher.bind(key, lambda _e, t=tool: self.set_tool(t))
        self.catcher.bind("<Control-z>", lambda _e: self.undo())
        self.catcher.bind("<Control-y>", lambda _e: self.redo())
        self.catcher.bind("<Delete>", lambda _e: self.clear())
        self.catcher.bind("<Escape>", lambda _e: self.set_draw_mode(False))

    def _start_hotkeys(self) -> None:
        self.hotkeys = HotkeyManager()
        self._actions = {
            "toggle_draw": self.toggle_draw_mode,
            "undo": self.undo,
            "redo": self.redo,
            "clear": self.clear,
            "toggle_toolbar": self.toggle_toolbar,
            "quit": self.quit,
        }
        for action, mods, vk, _label in config.HOTKEYS:
            self.hotkeys.bind(action, mods, vk)
        self.hotkeys.start()

    def _poll_hotkeys(self) -> None:
        if self._closing:
            return
        for action in self.hotkeys.poll():
            handler = self._actions.get(action)
            if handler:
                handler()
        self._schedule(HOTKEY_POLL_MS, self._poll_hotkeys)

    # --- coordinates ----------------------------------------------------
    def _canvas_point(self, event: tk.Event) -> tuple[float, float]:
        """Convert a screen-space event into ink-canvas coordinates."""
        return (event.x_root - self.origin_x, event.y_root - self.origin_y)

    # --- drawing --------------------------------------------------------
    def _on_press(self, event: tk.Event) -> None:
        point = self._canvas_point(event)
        self._stroke = {"start": point, "points": [point]}

    def _on_motion(self, event: tk.Event) -> None:
        if self._stroke is None:
            return
        point = self._canvas_point(event)
        shift_held = bool(event.state & 0x0001)

        if self.tool == FREEHAND:
            previous = self._stroke["points"][-1]
            if previous != point:
                self._stroke["points"].append(point)
                self.canvas.create_line(
                    *previous, *point, fill=self.color, width=self.width,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND, tags=PREVIEW_TAG)
            return

        end = self._constrain(self._stroke["start"], point, shift_held)
        self._stroke["points"] = [self._stroke["start"], end]
        self.canvas.delete(PREVIEW_TAG)
        self._draw(self.tool, self._stroke["points"], self.color, self.width,
                   tags=PREVIEW_TAG)

    def _on_release(self, event: tk.Event) -> None:
        if self._stroke is None:
            return
        stroke, self._stroke = self._stroke, None
        self.canvas.delete(PREVIEW_TAG)

        points = stroke["points"]
        if self.tool != FREEHAND:
            end = self._constrain(stroke["start"],
                                  self._canvas_point(event),
                                  bool(event.state & 0x0001))
            points = [stroke["start"], end]
            if (abs(end[0] - stroke["start"][0]) < config.MIN_DRAG_PIXELS
                    and abs(end[1] - stroke["start"][1]) < config.MIN_DRAG_PIXELS):
                return  # an accidental click rather than a deliberate shape
        elif len(points) < 2:
            points = points * 2  # a single tap becomes a dot

        shape = Shape(kind=self.tool, points=tuple(points),
                      color=self.color, width=self.width)
        self.model.add(shape)
        self._draw(shape.kind, shape.points, shape.color, shape.width)
        self._sync_toolbar()

    def _constrain(self, start, end, shift_held: bool):
        if not shift_held:
            return end
        if self.tool == ARROW:
            return constrain_angle(start, end)
        return constrain_square(start, end)

    def _draw(self, kind: str, points, color: str, width: int,
              tags: str | None = None) -> None:
        options = {"tags": tags} if tags else {}

        if kind == FREEHAND:
            if len(set(points)) == 1:
                x, y = points[0]
                radius = max(1.0, width / 2)
                self.canvas.create_oval(x - radius, y - radius, x + radius,
                                        y + radius, fill=color, outline=color,
                                        **options)
                return
            flat = [coordinate for point in points for coordinate in point]
            self.canvas.create_line(*flat, fill=color, width=width,
                                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                    smooth=True, **options)
            return

        (x1, y1), (x2, y2) = points[0], points[-1]
        if kind == ARROW:
            head = (max(10.0, width * 3.5), max(13.0, width * 4.5),
                    max(5.0, width * 2.0))
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width,
                                    arrow=tk.LAST, arrowshape=head,
                                    capstyle=tk.ROUND, **options)
        elif kind == RECTANGLE:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color,
                                         width=width, **options)
        elif kind == ELLIPSE:
            self.canvas.create_oval(x1, y1, x2, y2, outline=color,
                                    width=width, **options)

    def _redraw_all(self) -> None:
        self.canvas.delete("all")
        for shape in self.model.shapes:
            self._draw(shape.kind, shape.points, shape.color, shape.width)

    # --- controller API used by the toolbar -----------------------------
    def set_tool(self, tool: str) -> None:
        """Select a tool, switching into draw mode if it is not already on."""
        self.tool = tool
        if not self.drawing_mode:
            self.set_draw_mode(True)
        self._sync_toolbar()

    def set_color(self, color: str) -> None:
        self.color = color
        self._sync_toolbar()

    def set_width(self, width: int) -> None:
        self.width = width
        self._sync_toolbar()

    def undo(self) -> None:
        if self.model.undo():
            self._redraw_all()
            self._sync_toolbar()

    def redo(self) -> None:
        if self.model.redo():
            self._redraw_all()
            self._sync_toolbar()

    def clear(self) -> None:
        if self.model.clear():
            self._redraw_all()
            self._sync_toolbar()

    def toggle_draw_mode(self) -> None:
        self.set_draw_mode(not self.drawing_mode)

    def set_draw_mode(self, enabled: bool) -> None:
        """Enable annotating, or release the mouse back to other applications."""
        self.drawing_mode = enabled
        if enabled:
            self.catcher.deiconify()
            self._restack()
            self.catcher.focus_force()
        else:
            self._stroke = None
            self.canvas.delete(PREVIEW_TAG)
            self.catcher.withdraw()
        self._sync_toolbar()

    def toggle_toolbar(self) -> None:
        self.toolbar.toggle_visibility()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        for job in self._scheduled:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._scheduled.clear()
        try:
            self.hotkeys.stop()
        finally:
            self.root.destroy()

    # --- housekeeping ---------------------------------------------------
    def _schedule(self, delay_ms: int, callback) -> None:
        """Run ``callback`` later, remembering the job so quit can cancel it."""
        self._scheduled.append(self.root.after(delay_ms, callback))
        del self._scheduled[:-8]

    def _sync_toolbar(self) -> None:
        self.toolbar.sync(tool=self.tool, color=self.color, width=self.width,
                          drawing=self.drawing_mode,
                          can_undo=self.model.can_undo,
                          can_redo=self.model.can_redo)

    def _restack(self) -> None:
        """Keep the catcher below the ink, and the toolbar above both."""
        # Flush pending window moves first, otherwise SetWindowPos below
        # cancels them and windows snap back to their previous position.
        self.root.update_idletasks()
        if self.drawing_mode:
            win32.ensure_visible(self.catcher)
            win32.raise_topmost(self.catcher)
        win32.ensure_visible(self.ink)
        win32.raise_topmost(self.ink)
        if self.toolbar.visible:
            win32.ensure_visible(self.toolbar.window)
            win32.raise_topmost(self.toolbar.window)

    def _restack_loop(self) -> None:
        if self._closing:
            return
        self._restack()
        self._schedule(RESTACK_INTERVAL_MS, self._restack_loop)

    def run(self) -> None:
        self.root.mainloop()
