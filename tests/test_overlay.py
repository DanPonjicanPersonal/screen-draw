"""Integration tests that build the real overlay windows.

These exercise the part that unit tests cannot reach: that the ink layer is
genuinely click-through while the input catcher underneath it still receives
the mouse, and that strokes, undo and mode switching behave on a live canvas.
"""

import ctypes
import sys
import unittest
from ctypes import wintypes

if sys.platform.startswith("win"):
    from screendraw import win32
    from screendraw.app import ScreenDrawApp
    from screendraw.model import ARROW, ELLIPSE, FREEHAND, RECTANGLE

user32 = ctypes.WinDLL("user32", use_last_error=True) if sys.platform.startswith("win") else None


class FakeEvent:
    """Stands in for a Tk mouse event."""

    def __init__(self, x, y, shift=False):
        self.x_root = x
        self.y_root = y
        self.state = 0x0001 if shift else 0


def window_at(x, y):
    point = wintypes.POINT(x, y)
    hwnd = user32.WindowFromPoint(point)
    return user32.GetAncestor(hwnd, win32.GA_ROOT) if hwnd else 0


@unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.app = ScreenDrawApp()
        self.app.root.update()

    def tearDown(self):
        try:
            self.app.quit()
        except Exception:
            pass

    def pump(self):
        self.app.root.update()

    def stroke(self, tool, start, end, shift=False):
        """Drive a full press/drag/release cycle through the app handlers."""
        self.app.set_tool(tool)
        self.app._on_press(FakeEvent(*start))
        mid = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
        self.app._on_motion(FakeEvent(*mid, shift=shift))
        self.app._on_motion(FakeEvent(*end, shift=shift))
        self.app._on_release(FakeEvent(*end, shift=shift))
        self.pump()

    # --- window plumbing -------------------------------------------------
    def test_overlay_covers_the_whole_virtual_desktop(self):
        expected = win32.virtual_screen()
        self.assertEqual(
            (self.app.origin_x, self.app.origin_y,
             self.app.screen_w, self.app.screen_h), expected)

    def test_starts_in_pass_through_mode(self):
        # Grabbing the mouse before the user asks would look like a broken
        # mouse, so nothing is captured until a tool is chosen.
        self.assertFalse(self.app.drawing_mode)
        self.assertNotEqual(window_at(700, 700), win32.hwnd_of(self.app.catcher))
        self.assertEqual(self.app.toolbar.mode_button["text"], "Draw: OFF")

    def test_choosing_a_tool_enables_draw_mode(self):
        self.app.set_tool(ARROW)
        self.pump()
        self.assertTrue(self.app.drawing_mode)
        self.assertEqual(window_at(700, 700), win32.hwnd_of(self.app.catcher))

    def test_ink_layer_is_click_through_and_catcher_receives_the_mouse(self):
        style = win32.user32.GetWindowLongW(
            win32.hwnd_of(self.app.ink), win32.GWL_EXSTYLE)
        self.assertTrue(style & win32.WS_EX_TRANSPARENT,
                        "ink layer must not intercept the mouse")

        self.stroke(FREEHAND, (400, 500), (520, 560))
        self.app._restack()
        self.pump()

        catcher_hwnd = win32.hwnd_of(self.app.catcher)
        # A blank point and a point on top of fresh ink must both land on the
        # catcher, otherwise strokes would be lost to the app underneath.
        self.assertEqual(window_at(460, 530), catcher_hwnd, "over ink")
        self.assertEqual(window_at(700, 700), catcher_hwnd, "over blank area")

    def test_leaving_draw_mode_returns_the_mouse_to_other_apps(self):
        catcher_hwnd = win32.hwnd_of(self.app.catcher)
        self.app.set_draw_mode(True)
        self.pump()
        self.assertEqual(window_at(700, 700), catcher_hwnd)

        self.app.set_draw_mode(False)
        self.pump()
        self.assertNotEqual(window_at(700, 700), catcher_hwnd)

        self.app.set_draw_mode(True)
        self.pump()
        self.assertEqual(window_at(700, 700), catcher_hwnd)

    def test_annotations_survive_switching_out_of_draw_mode(self):
        self.stroke(ARROW, (300, 400), (500, 600))
        self.app.set_draw_mode(False)
        self.pump()
        self.assertEqual(len(self.app.model.shapes), 1)
        self.assertTrue(self.app.canvas.find_all())

    # --- tools -----------------------------------------------------------
    def test_every_tool_records_a_shape_and_paints_it(self):
        for tool in (FREEHAND, ARROW, RECTANGLE, ELLIPSE):
            with self.subTest(tool=tool):
                self.app.clear()
                self.app.model = type(self.app.model)()
                self.stroke(tool, (200, 300), (420, 480))
                self.assertEqual(len(self.app.model.shapes), 1)
                self.assertEqual(self.app.model.shapes[0].kind, tool)
                self.assertTrue(self.app.canvas.find_all(),
                                "tool drew nothing on the canvas")

    def test_freehand_keeps_every_sampled_point(self):
        self.stroke(FREEHAND, (100, 100), (300, 260))
        self.assertGreaterEqual(len(self.app.model.shapes[0].points), 3)

    def test_preview_items_are_removed_after_the_stroke(self):
        self.stroke(RECTANGLE, (150, 150), (350, 300))
        self.assertEqual(self.app.canvas.find_withtag("preview"), ())

    def test_tiny_drag_does_not_create_a_shape(self):
        self.stroke(RECTANGLE, (600, 600), (601, 601))
        self.assertEqual(self.app.model.shapes, [])

    def test_single_click_with_pen_leaves_a_dot(self):
        self.app.set_tool(FREEHAND)
        self.app._on_press(FakeEvent(500, 500))
        self.app._on_release(FakeEvent(500, 500))
        self.pump()
        self.assertEqual(len(self.app.model.shapes), 1)
        self.assertTrue(self.app.canvas.find_all())

    def test_shift_constrains_a_rectangle_to_a_square(self):
        self.stroke(RECTANGLE, (200, 200), (400, 260), shift=True)
        (x1, y1), (x2, y2) = self.app.model.shapes[0].points
        self.assertAlmostEqual(abs(x2 - x1), abs(y2 - y1))

    def test_color_and_width_selections_are_applied(self):
        self.app.set_color("#22C55E")
        self.app.set_width(11)
        self.stroke(ARROW, (100, 400), (300, 400))
        shape = self.app.model.shapes[0]
        self.assertEqual(shape.color, "#22C55E")
        self.assertEqual(shape.width, 11)

    # --- history ---------------------------------------------------------
    def test_undo_and_redo_repaint_the_canvas(self):
        self.stroke(FREEHAND, (100, 100), (200, 200))
        self.stroke(RECTANGLE, (300, 300), (400, 400))
        self.assertEqual(len(self.app.model.shapes), 2)

        self.app.undo()
        self.pump()
        self.assertEqual(len(self.app.model.shapes), 1)

        self.app.redo()
        self.pump()
        self.assertEqual(len(self.app.model.shapes), 2)
        self.assertTrue(self.app.canvas.find_all())

    def test_clear_empties_the_canvas_and_is_undoable(self):
        self.stroke(ELLIPSE, (100, 100), (300, 300))
        self.app.clear()
        self.pump()
        self.assertEqual(self.app.canvas.find_all(), ())

        self.app.undo()
        self.pump()
        self.assertEqual(len(self.app.model.shapes), 1)
        self.assertTrue(self.app.canvas.find_all())

    # --- toolbar ---------------------------------------------------------
    def test_toolbar_reflects_state_and_can_be_hidden(self):
        self.app.set_tool(ARROW)
        self.pump()
        self.assertEqual(self.app.toolbar.mode_button["text"], "Draw: ON")

        self.app.toggle_toolbar()
        self.pump()
        self.assertFalse(self.app.toolbar.visible)

        self.app.toggle_toolbar()
        self.pump()
        self.assertTrue(self.app.toolbar.visible)

    def test_toolbar_is_centred_near_the_top_of_the_screen(self):
        window = self.app.toolbar.window
        window.update()
        expected_x = self.app.origin_x + (self.app.screen_w - window.winfo_width()) // 2
        self.assertAlmostEqual(window.winfo_x(), expected_x, delta=4)
        self.assertGreater(window.winfo_y(), self.app.origin_y)

    def test_restacking_does_not_move_the_toolbar(self):
        window = self.app.toolbar.window
        window.update()
        before = (window.winfo_x(), window.winfo_y())
        for _ in range(3):
            self.app._restack()
        self.pump()
        self.assertEqual((window.winfo_x(), window.winfo_y()), before)

    def test_toolbar_can_be_dragged_to_a_new_position(self):
        window = self.app.toolbar.window
        window.update()
        self.app.toolbar._start_drag(FakeEvent(window.winfo_x() + 10,
                                               window.winfo_y() + 10))
        self.app.toolbar._on_drag(FakeEvent(600, 400))
        self.app._restack()
        self.pump()
        self.assertEqual((window.winfo_x(), window.winfo_y()), (590, 390))

    def test_restack_recovers_a_window_hidden_by_windows(self):
        # A launcher that starts us with SW_HIDE hides the first top-level
        # window while Tk still believes it is mapped, which used to leave
        # draw mode silently unable to receive the mouse.
        SW_HIDE = 0
        self.app.set_draw_mode(True)
        self.pump()
        catcher_hwnd = win32.hwnd_of(self.app.catcher)
        win32.user32.ShowWindow(catcher_hwnd, SW_HIDE)
        self.pump()
        self.assertFalse(win32.user32.IsWindowVisible(catcher_hwnd))

        self.app._restack()
        self.pump()
        self.assertTrue(win32.user32.IsWindowVisible(catcher_hwnd),
                        "restack must re-show the input catcher")
        self.assertEqual(window_at(700, 700), catcher_hwnd)

    def test_global_hotkeys_registered(self):
        self.assertEqual(self.app.hotkeys.failed, [],
                         "some global hotkeys could not be registered")


if __name__ == "__main__":
    unittest.main()
