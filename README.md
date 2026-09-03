# screen-draw

Draw on top of your Windows screen. The annotations float above every other
application, so you can circle a cell in Excel, arrow at a button in a browser,
or scribble over a video call without the other program knowing anything about it.

Pure Python standard library — no packages to install.

## Quick start

```powershell
git clone https://github.com/DanPonjicanPersonal/screen-draw.git
cd screen-draw
python -m screendraw
```

Or double-click **`run.bat`**, which starts it without a console window.

Requires Windows and Python 3.10+ (Tkinter ships with the standard Windows
Python installer).

## Using it

screen-draw opens a small toolbar near the top of the screen and starts in
**pass-through mode**, so it does not touch your mouse until you ask it to.
Click a tool (or press **Ctrl+Alt+D**) to start annotating.

| Tool | What it does |
| --- | --- |
| **Pen** | Freehand drawing that follows the cursor |
| **Arrow** | Drag from the tail to the head to point at something |
| **Rect** | Outline rectangle, no fill |
| **Circle** | Outline ellipse, no fill |

Pick any of eight colours and three line widths from the toolbar. Hold
**Shift** while dragging to constrain a rectangle to a square, an ellipse to a
circle, or an arrow to the nearest 45°.

**Right-click anywhere to undo the last annotation.**

### Draw mode vs. pass-through mode

This is the important one. `Draw: ON` means the overlay is capturing the mouse,
so clicks annotate instead of reaching the app underneath. Press
**Ctrl+Alt+D** (or click the mode button) to go back to `Draw: OFF`: your
annotations stay on screen, but the mouse goes straight back to whatever is
below, so you can keep scrolling, typing and clicking normally.

If the mouse ever seems stuck, you are in draw mode — press **Esc** or
**Ctrl+Alt+D**.

### Shortcuts

These work system-wide, from any application:

| Shortcut | Action |
| --- | --- |
| `Ctrl+Alt+D` | Toggle draw mode on/off |
| `Ctrl+Alt+Z` | Undo |
| `Ctrl+Alt+Y` | Redo |
| `Ctrl+Alt+C` | Clear everything |
| `Ctrl+Alt+H` | Hide/show the toolbar |
| `Ctrl+Alt+Q` | Quit |

While in draw mode these also work: `1`–`4` select the pen, arrow, rectangle
and ellipse; `Ctrl+Z` / `Ctrl+Y` undo and redo; `Delete` clears; `Esc` leaves
draw mode.

Clearing is undoable, so `Ctrl+Alt+C` followed by `Ctrl+Alt+Z` brings your
annotations back.

## How it works

Windows will not deliver mouse input to a fully transparent pixel, which is the
central obstacle for any see-through annotation overlay: make the window
transparent enough to see through and it stops receiving the strokes you draw
on it. screen-draw solves this with two stacked full-screen windows:

1. **The ink layer** is chroma-key transparent and carries the
   `WS_EX_TRANSPARENT` style, so it is purely visual and never intercepts the
   mouse. This is what actually shows your annotations.
2. **The input catcher** sits directly beneath it, painted black at 1% opacity.
   That is invisible in practice but *not* fully transparent, so Windows still
   hit-tests it and it receives every click and drag.

Toggling pass-through mode simply hides the input catcher, which hands the
mouse straight back to the application underneath while the ink layer keeps
displaying your annotations.

Some launchers start a program with `SW_HIDE` so no console flashes up, and
Windows applies that to the process's *first* top-level window — which would
silently hide the input catcher while Tk still believed it was mapped. The
overlay therefore re-asserts the visibility and z-order of its windows
periodically rather than trusting the initial mapping.

The overlay spans the full virtual desktop, so it covers every monitor, and the
process opts into per-monitor DPI awareness so strokes land exactly under the
cursor on scaled displays.

## Project layout

| Path | Purpose |
| --- | --- |
| `screendraw/app.py` | Overlay windows, tools and stroke handling |
| `screendraw/model.py` | Shape records and snapshot-based undo/redo |
| `screendraw/toolbar.py` | The floating control bar |
| `screendraw/win32.py` | ctypes wrappers for the Win32 calls used |
| `screendraw/hotkeys.py` | System-wide hotkeys on a dedicated thread |
| `screendraw/config.py` | Palette, widths and shortcut definitions |
| `tests/` | Unit and live-window integration tests |

## Tests

```powershell
python -m unittest discover -s tests -t .
```

The integration tests build the real overlay windows and assert against the
live desktop — including that the ink layer is click-through while the catcher
underneath still receives the mouse — so windows will flicker briefly while
they run.

## Notes and limits

- Annotations are vector items held in memory; there is no save/export yet.
- If another program already owns one of the `Ctrl+Alt` shortcuts, screen-draw
  warns you at startup and that shortcut is unavailable.
- The overlay cannot draw over content that bypasses the normal desktop
  compositor, such as the secure desktop (Ctrl+Alt+Del), UAC consent prompts,
  or some exclusive-fullscreen games.
