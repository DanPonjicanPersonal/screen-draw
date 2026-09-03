"""Entry point: ``python -m screendraw``."""

from __future__ import annotations

import sys

from .config import HOTKEYS


def main() -> int:
    if not sys.platform.startswith("win"):
        print("screen-draw requires Windows.", file=sys.stderr)
        return 1

    from .app import ScreenDrawApp

    app = ScreenDrawApp()
    if app.hotkeys.failed:
        _warn_about_hotkeys(app)
    app.run()
    return 0


def _warn_about_hotkeys(app) -> None:
    """Tell the user which shortcuts are unavailable.

    The global hotkeys are the way out of draw mode when the toolbar is
    hidden, so a silent failure could leave the mouse captured.
    """
    from tkinter import messagebox

    labels = {action: label for action, _m, _v, label in HOTKEYS}
    lost = ", ".join(f"{labels[a]} ({a})" for a in app.hotkeys.failed if a in labels)
    message = (
        "Another program has already claimed these screen-draw shortcuts:\n\n"
        f"{lost}\n\n"
        "They will not work. Use the toolbar buttons instead."
    )
    print(message, file=sys.stderr)
    messagebox.showwarning("screen-draw", message, parent=app.root)


if __name__ == "__main__":
    raise SystemExit(main())
