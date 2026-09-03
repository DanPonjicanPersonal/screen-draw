"""Shared appearance and input configuration."""

from __future__ import annotations

from .hotkeys import MOD_ALT, MOD_CONTROL

# Colour used as the chroma key for the ink layer. Any pixel painted in this
# exact colour becomes fully transparent, so it must never appear in the
# palette or in the toolbar.
CHROMA_KEY = "#010203"

# The input catcher is painted this colour at 1% opacity. It has to be very
# slightly opaque, because fully transparent pixels do not receive mouse input.
CATCHER_COLOR = "#000000"
CATCHER_ALPHA = 0.01

PALETTE: tuple[tuple[str, str], ...] = (
    ("Red", "#FF2D2D"),
    ("Orange", "#FF8C1A"),
    ("Yellow", "#FFE01B"),
    ("Green", "#22C55E"),
    ("Blue", "#3B82F6"),
    ("Purple", "#A855F7"),
    ("White", "#FFFFFF"),
    ("Black", "#111111"),
)

WIDTHS: tuple[tuple[str, int], ...] = (
    ("Thin", 3),
    ("Medium", 6),
    ("Thick", 11),
)

DEFAULT_COLOR = PALETTE[0][1]
DEFAULT_WIDTH = WIDTHS[1][1]

# Shapes smaller than this (in pixels) are treated as an accidental click.
MIN_DRAG_PIXELS = 4

# Global hotkeys: (action, modifiers, virtual key code, human readable label).
HOTKEYS: tuple[tuple[str, int, int, str], ...] = (
    ("toggle_draw", MOD_CONTROL | MOD_ALT, 0x44, "Ctrl+Alt+D"),   # D
    ("undo", MOD_CONTROL | MOD_ALT, 0x5A, "Ctrl+Alt+Z"),          # Z
    ("redo", MOD_CONTROL | MOD_ALT, 0x59, "Ctrl+Alt+Y"),          # Y
    ("clear", MOD_CONTROL | MOD_ALT, 0x43, "Ctrl+Alt+C"),         # C
    ("toggle_toolbar", MOD_CONTROL | MOD_ALT, 0x48, "Ctrl+Alt+H"),  # H
    ("quit", MOD_CONTROL | MOD_ALT, 0x51, "Ctrl+Alt+Q"),          # Q
)

TOOLBAR_BG = "#1F2430"
TOOLBAR_FG = "#E6E9EF"
TOOLBAR_ACCENT = "#3B82F6"
TOOLBAR_MUTED = "#39404F"
