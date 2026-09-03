"""Drawing data model: shape records plus snapshot-based undo/redo."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

Point = tuple[float, float]

FREEHAND = "free"
ARROW = "arrow"
RECTANGLE = "rect"
ELLIPSE = "oval"

TOOLS = (FREEHAND, ARROW, RECTANGLE, ELLIPSE)

MAX_UNDO_DEPTH = 200


@dataclass(frozen=True)
class Shape:
    """One completed annotation.

    ``points`` holds every sampled point for freehand strokes, and exactly two
    points (start, end) for arrows, rectangles and ellipses.
    """

    kind: str
    points: tuple[Point, ...]
    color: str
    width: int

    def __post_init__(self) -> None:
        if self.kind not in TOOLS:
            raise ValueError(f"unknown shape kind: {self.kind!r}")
        if len(self.points) < 2:
            raise ValueError("a shape needs at least two points")

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass
class DrawingModel:
    """Holds the annotations and the undo/redo history.

    History is stored as snapshots of the shape list. Snapshots are shallow
    copies of a list of immutable ``Shape`` objects, so they are cheap, and
    they make destructive operations such as clear-all undoable for free.
    """

    shapes: list[Shape] = field(default_factory=list)
    _undo: list[list[Shape]] = field(default_factory=list, repr=False)
    _redo: list[list[Shape]] = field(default_factory=list, repr=False)

    def _commit(self, new_shapes: list[Shape]) -> None:
        self._undo.append(list(self.shapes))
        if len(self._undo) > MAX_UNDO_DEPTH:
            del self._undo[0]
        self._redo.clear()
        self.shapes = new_shapes

    def add(self, shape: Shape) -> None:
        self._commit(self.shapes + [shape])

    def clear(self) -> bool:
        """Erase every annotation. Returns False when there was nothing to erase."""
        if not self.shapes:
            return False
        self._commit([])
        return True

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(list(self.shapes))
        self.shapes = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(list(self.shapes))
        self.shapes = self._redo.pop()
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def is_empty(self) -> bool:
        return not self.shapes


def constrain_square(start: Point, end: Point) -> Point:
    """Snap ``end`` so the box from ``start`` is a perfect square/circle."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    size = max(abs(dx), abs(dy))
    return (
        start[0] + (size if dx >= 0 else -size),
        start[1] + (size if dy >= 0 else -size),
    )


def constrain_angle(start: Point, end: Point) -> Point:
    """Snap the start->end vector to the nearest 45 degree step."""
    import math

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return end
    step = math.pi / 4
    angle = round(math.atan2(dy, dx) / step) * step
    return (start[0] + length * math.cos(angle), start[1] + length * math.sin(angle))


def rebuild(shape: Shape, **changes) -> Shape:
    """Return a copy of ``shape`` with the given fields replaced."""
    return replace(shape, **changes)
