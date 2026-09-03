"""Unit tests for the drawing model and geometry helpers."""

import math
import unittest

from screendraw.model import (ARROW, ELLIPSE, FREEHAND, RECTANGLE, DrawingModel,
                              Shape, constrain_angle, constrain_square)


def make_shape(kind=FREEHAND, color="#FF0000", width=6):
    return Shape(kind=kind, points=((0, 0), (10, 10)), color=color, width=width)


class ShapeTests(unittest.TestCase):
    def test_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            Shape(kind="triangle", points=((0, 0), (1, 1)), color="#FFF", width=1)

    def test_rejects_single_point(self):
        with self.assertRaises(ValueError):
            Shape(kind=FREEHAND, points=((0, 0),), color="#FFF", width=1)

    def test_bbox_covers_all_points(self):
        shape = Shape(kind=FREEHAND, points=((5, 9), (-3, 40), (12, 1)),
                      color="#FFF", width=1)
        self.assertEqual(shape.bbox, (-3, 1, 12, 40))

    def test_all_tool_kinds_are_constructible(self):
        for kind in (FREEHAND, ARROW, RECTANGLE, ELLIPSE):
            self.assertEqual(make_shape(kind).kind, kind)


class UndoRedoTests(unittest.TestCase):
    def setUp(self):
        self.model = DrawingModel()

    def test_starts_empty(self):
        self.assertTrue(self.model.is_empty)
        self.assertFalse(self.model.can_undo)
        self.assertFalse(self.model.can_redo)

    def test_add_then_undo_then_redo(self):
        shape = make_shape()
        self.model.add(shape)
        self.assertEqual(self.model.shapes, [shape])

        self.assertTrue(self.model.undo())
        self.assertEqual(self.model.shapes, [])
        self.assertTrue(self.model.can_redo)

        self.assertTrue(self.model.redo())
        self.assertEqual(self.model.shapes, [shape])

    def test_undo_on_empty_history_is_a_no_op(self):
        self.assertFalse(self.model.undo())
        self.assertFalse(self.model.redo())

    def test_adding_after_undo_discards_the_redo_branch(self):
        first, second = make_shape(), make_shape(ARROW)
        self.model.add(first)
        self.model.undo()
        self.model.add(second)
        self.assertEqual(self.model.shapes, [second])
        self.assertFalse(self.model.can_redo)

    def test_clear_is_undoable(self):
        shapes = [make_shape(), make_shape(RECTANGLE)]
        for shape in shapes:
            self.model.add(shape)

        self.assertTrue(self.model.clear())
        self.assertTrue(self.model.is_empty)

        self.assertTrue(self.model.undo())
        self.assertEqual(self.model.shapes, shapes)

    def test_clear_on_empty_canvas_reports_no_change(self):
        self.assertFalse(self.model.clear())
        self.assertFalse(self.model.can_undo)

    def test_undo_stack_is_bounded(self):
        from screendraw.model import MAX_UNDO_DEPTH

        for _ in range(MAX_UNDO_DEPTH + 50):
            self.model.add(make_shape())
        self.assertLessEqual(len(self.model._undo), MAX_UNDO_DEPTH)

    def test_history_snapshots_are_independent(self):
        self.model.add(make_shape())
        snapshot = self.model.shapes
        self.model.add(make_shape(ARROW))
        self.assertEqual(len(snapshot), 1, "earlier state must not be mutated")


class ConstraintTests(unittest.TestCase):
    def test_square_uses_the_longer_axis(self):
        self.assertEqual(constrain_square((0, 0), (100, 30)), (100, 100))

    def test_square_preserves_direction(self):
        self.assertEqual(constrain_square((50, 50), (10, 40)), (10, 10))

    def test_angle_snaps_to_45_degrees(self):
        x, y = constrain_angle((0, 0), (100, 10))
        self.assertAlmostEqual(x, 100.498, places=2)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_angle_snaps_diagonally(self):
        x, y = constrain_angle((0, 0), (100, 90))
        self.assertAlmostEqual(x, y, places=6)

    def test_angle_preserves_length(self):
        start, end = (10, 10), (60, 33)
        snapped = constrain_angle(start, end)
        self.assertAlmostEqual(
            math.dist(start, snapped), math.dist(start, end), places=6)

    def test_zero_length_vector_is_unchanged(self):
        self.assertEqual(constrain_angle((7, 7), (7, 7)), (7, 7))


if __name__ == "__main__":
    unittest.main()
