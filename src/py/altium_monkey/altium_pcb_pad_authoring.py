"""Shared PCB pad authoring helpers."""

from __future__ import annotations

from .altium_pcb_enums import PadHoleShape, PadShape
from .altium_record_pcb__pad import AltiumPcbPad

ROUNDED_RECTANGLE_ALT_SHAPE = 9
ROUNDED_RECTANGLE_FULL_STACK_LAYER_CODE = 4
ROUNDED_RECTANGLE_FULL_STACK_MODE_FLAGS = 0x0180
ROUNDED_RECTANGLE_FULL_STACK_ENABLED = 9
DEFAULT_ROUNDED_RECTANGLE_CORNER_RADIUS_PERCENT = 50
ROUND_HOLE_SHAPE = int(PadHoleShape.ROUND)
SQUARE_HOLE_SHAPE = int(PadHoleShape.SQUARE)
SLOT_HOLE_SHAPE = 2
PadHoleShapeInput = PadHoleShape | int | str
PadShapeInput = PadShape | int | str


def validate_non_negative(value: float, name: str) -> None:
    if float(value) < 0.0:
        raise ValueError(f"{name} must be non-negative")


def normalize_pad_hole_shape(value: PadHoleShapeInput) -> PadHoleShape:
    """
    Normalize public pad hole-shape input.
    """
    if isinstance(value, PadHoleShape):
        return value
    if isinstance(value, int):
        try:
            return PadHoleShape(value)
        except ValueError as exc:
            raise ValueError("hole_shape must be round, square, or slot") from exc

    normalized = str(value).strip().lower().replace("_", "-")
    aliases = {
        "0": PadHoleShape.ROUND,
        "round": PadHoleShape.ROUND,
        "circular": PadHoleShape.ROUND,
        "circle": PadHoleShape.ROUND,
        "1": PadHoleShape.SQUARE,
        "square": PadHoleShape.SQUARE,
        "2": PadHoleShape.SLOT,
        "slot": PadHoleShape.SLOT,
        "slotted": PadHoleShape.SLOT,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError("hole_shape must be round, square, or slot") from exc


def normalize_pad_shape(value: PadShapeInput) -> PadShape:
    """
    Normalize public pad shape input.
    """
    if isinstance(value, PadShape):
        return value
    if isinstance(value, int):
        try:
            return PadShape(value)
        except ValueError as exc:
            raise ValueError(
                "shape must be circle, rectangle, octagonal, rounded_rectangle, or custom"
            ) from exc

    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "1": PadShape.CIRCLE,
        "circle": PadShape.CIRCLE,
        "round": PadShape.CIRCLE,
        "circular": PadShape.CIRCLE,
        "2": PadShape.RECTANGLE,
        "rect": PadShape.RECTANGLE,
        "rectangle": PadShape.RECTANGLE,
        "3": PadShape.OCTAGONAL,
        "octagon": PadShape.OCTAGONAL,
        "octagonal": PadShape.OCTAGONAL,
        "4": PadShape.ROUNDED_RECTANGLE,
        "rounded-rect": PadShape.ROUNDED_RECTANGLE,
        "rounded-rectangle": PadShape.ROUNDED_RECTANGLE,
        "10": PadShape.CUSTOM,
        "custom": PadShape.CUSTOM,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(
            "shape must be circle, rectangle, octagonal, rounded_rectangle, or custom"
        ) from exc


def apply_authored_pad_shape(
    pad: AltiumPcbPad,
    *,
    shape: PadShapeInput,
    width_iu: int,
    height_iu: int,
    corner_radius_percent: int | None,
) -> None:
    """
    Apply public semantic pad shape to native fields.

    Altium does not persist authored rounded rectangles as base shape `4`.
    It uses a round base shape plus SubRecord 6 alternate-shape and radius
    data. Keeping that encoding here prevents public API callers from writing
    files that reopen with invalid pad-shape state.
    """
    shape_id = int(normalize_pad_shape(shape))
    if shape_id != int(PadShape.ROUNDED_RECTANGLE):
        pad.shape = shape_id
        pad.top_shape = shape_id
        pad.mid_shape = shape_id
        pad.bot_shape = shape_id
        return

    corner_pct = _normalize_corner_radius_percent(corner_radius_percent)
    base_shape = int(PadShape.CIRCLE)
    pad.shape = base_shape
    pad.top_shape = base_shape
    pad.mid_shape = base_shape
    pad.bot_shape = base_shape
    pad.inner_size_x = [width_iu] * 29
    pad.inner_size_y = [height_iu] * 29
    pad.inner_shape = [base_shape] * 29
    pad.alt_shape = [ROUNDED_RECTANGLE_ALT_SHAPE] * 32
    pad.corner_radius = [corner_pct] * 32
    pad.full_stack_layer_entries = [
        (
            ROUNDED_RECTANGLE_FULL_STACK_LAYER_CODE,
            ROUNDED_RECTANGLE_FULL_STACK_MODE_FLAGS,
            ROUNDED_RECTANGLE_FULL_STACK_ENABLED,
            width_iu,
            height_iu,
            corner_pct,
        )
    ]


def _normalize_corner_radius_percent(value: int | None) -> int:
    percent = (
        DEFAULT_ROUNDED_RECTANGLE_CORNER_RADIUS_PERCENT if value is None else int(value)
    )
    if not 0 <= percent <= 100:
        raise ValueError("corner_radius_percent must be between 0 and 100")
    return percent
