"""
Generate an Altium PcbLib footprint for the Seeed Wio-SX1262 module.

Geometry is taken from the authoritative Seeed KiCad footprint
``Module:MODULE12P-1.27-11X11.6MM`` (extracted from the OPL KiCad library
``.kicad_pcb``) and re-authored into Altium following an in-house layer style:

    1) Copper            : the 12 SMD pads (Top copper).
    2) Top Overlay       : component outline with gaps over the pads.
    3) Mechanical 5      : component extent outline + ``.Designator`` (1 mm Arial,
                           centered).
    4) Mechanical 13     : component body outline + an outline around every pad +
                           a pin-1 indicator.
    5) Mechanical 15     : courtyard + a 1 mm "+" cross marking the body center.
    6) (Top Overlay)     : see (2) -- the gapped silkscreen outline.

Line-width house rules: every line is 0.15 mm, except the pad outlines on
Mechanical 13, which are 0.10 mm.

This is a first pass intended for visual review and refinement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from altium_monkey import (
    AltiumPcbFootprint,
    AltiumPcbLib,
    PadShape,
    PcbLayer,
    PcbTextJustification,
)

SAMPLE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SAMPLE_DIR / "output" / "Wio-SX1262.PcbLib"

MM_TO_MILS = 1000.0 / 25.4

# --- House-style constants (millimetres) ------------------------------------
LINE_MM = 0.15            # every line except the M13 pad outlines
PAD_OUTLINE_MM = 0.10     # pad outlines on Mechanical 13
DESIGNATOR_HEIGHT_MM = 1.0
SILK_PAD_CLEARANCE_MM = 0.25  # silk cutout clearance around pad/soldermask
MIN_SILK_SEGMENT_MM = 0.30    # drop/merge silk runs shorter than this
COURTYARD_CLEARANCE_MM = 0.25
CENTER_CROSS_MM = 1.0     # total length of each arm of the "+" cross
PAD1_MARKER_RADIUS_MM = 0.15
PAD1_MARKER_GAP_MM = 0.25  # gap from pad edge to the pin-1 dot

# Layer roles.
#
# Mechanical layers are used as Top/Bottom pairs (M5<->M6, M13<->M14,
# M15<->M16, ...): when a component is flipped to the bottom of a board the
# top-side mechanical data lands on its paired bottom layer. The Wio-SX1262 is
# a top-only SMD part, so only the top members of each pair are populated here.
COPPER_LAYER = PcbLayer.TOP
SILK_LAYER = PcbLayer.TOP_OVERLAY
EXTENT_LAYER = PcbLayer.MECHANICAL_5     # component location (body bounding box)
BODY_LAYER = PcbLayer.MECHANICAL_13      # pin locations (body + pad outlines)
COURTYARD_LAYER = PcbLayer.MECHANICAL_15


@dataclass(frozen=True)
class PadSpec:
    """A single SMD pad in body-centered millimetre coordinates (y up)."""

    designator: str
    name: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    roundrect_ratio: float  # KiCad rratio: corner_radius / min(w, h)


@dataclass(frozen=True)
class FootprintSpec:
    """A footprint expressed in body-centered millimetre coordinates."""

    name: str
    description: str
    body_w_mm: float
    body_h_mm: float
    pads: tuple[PadSpec, ...]


def _wio_sx1262_spec() -> FootprintSpec:
    """Build the Wio-SX1262 spec from the Seeed KiCad footprint geometry.

    Source: ``MODULE12P-1.27-11X11.6MM.kicad_mod`` -- body 11.6 x 11 mm, twelve
    roundrect pads on a 1.27 mm pitch. In KiCad each pad is ``size 1.6 0.6``
    rotated 90 deg with ``rratio 0.5``, i.e. effectively 0.6 mm wide x 1.6 mm
    tall fully-rounded (stadium) pads. At 1.6 mm tall the pads protrude ~0.5 mm
    past the body's top/bottom edges. KiCad coordinates (origin at body corner,
    y down) are converted to a body-centered, y-up frame here.
    """
    body_w, body_h = 11.6, 11.0
    # KiCad pad size is (1.6, 0.6) rotated 90 deg -> effective (x, y) = (0.6, 1.6).
    pad_w, pad_h, rratio = 0.6, 1.6, 0.5

    # (designator, name, kicad_x, kicad_y) straight from the .kicad_mod.
    kicad_pads = [
        ("1", "RF_SW", 1.33, -0.3),
        ("2", "MISO", 2.6, -0.3),
        ("3", "MOSI", 3.87, -0.3),
        ("4", "SCK", 5.14, -0.3),
        ("5", "RST", 6.41, -0.3),
        ("6", "NSS", 7.68, -0.3),
        ("7", "GND1", 8.95, -0.3),
        ("8", "VCC", 10.22, -0.3),
        ("9", "ANT", 6.41, -10.7),
        ("10", "GND2", 5.14, -10.7),
        ("11", "BUSY", 3.87, -10.7),
        ("12", "DIO1", 2.6, -10.7),
    ]
    cx, cy = body_w / 2.0, body_h / 2.0  # KiCad body center
    pads = tuple(
        PadSpec(
            designator=des,
            name=name,
            x_mm=kx - cx,        # center x
            y_mm=-(ky + cy),     # flip y (KiCad y-down) and center
            w_mm=pad_w,
            h_mm=pad_h,
            roundrect_ratio=rratio,
        )
        for des, name, kx, ky in kicad_pads
    )
    return FootprintSpec(
        name="MODULE12P-1.27-11X11.6MM",
        description="Seeed Wio-SX1262 LoRa module, 12-pin SMT",
        body_w_mm=body_w,
        body_h_mm=body_h,
        pads=pads,
    )


# --- Geometry helpers (operate in mm, convert at the API boundary) ----------
def _mil(value_mm: float) -> float:
    return value_mm * MM_TO_MILS


def _pt(x_mm: float, y_mm: float) -> tuple[float, float]:
    return (_mil(x_mm), _mil(y_mm))


def _add_segment(
    fp: AltiumPcbFootprint,
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    width_mm: float,
    layer: PcbLayer,
) -> None:
    fp.add_track(_pt(*p0), _pt(*p1), width_mils=_mil(width_mm), layer=layer)


def _add_rect(
    fp: AltiumPcbFootprint,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    *,
    width_mm: float,
    layer: PcbLayer,
) -> None:
    corners = [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    ]
    for i in range(4):
        _add_segment(fp, corners[i], corners[(i + 1) % 4], width_mm=width_mm, layer=layer)


def _subtract_intervals(
    span: tuple[float, float],
    blocks: list[tuple[float, float]],
    *,
    merge_gap: float = 0.0,
    min_segment: float = 0.0,
) -> list[tuple[float, float]]:
    """Return the parts of ``span`` not covered by any block.

    ``merge_gap`` fuses blocks separated by less than that distance, so the
    tiny inter-pad slivers on a fine-pitch edge collapse into one cutout
    instead of producing a row of dashes. ``min_segment`` drops any surviving
    run shorter than that length.
    """
    lo, hi = span
    merged: list[tuple[float, float]] = []
    for b0, b1 in sorted(blocks):
        b0, b1 = max(b0, lo), min(b1, hi)
        if b1 <= b0:
            continue
        if merged and b0 <= merged[-1][1] + merge_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b1))
        else:
            merged.append((b0, b1))
    segments: list[tuple[float, float]] = []
    cursor = lo
    for b0, b1 in merged:
        if b0 > cursor:
            segments.append((cursor, b0))
        cursor = b1
    if cursor < hi:
        segments.append((cursor, hi))
    return [(a, b) for a, b in segments if b - a >= min_segment]


# --- Builders for each layer role -------------------------------------------
def _add_copper(fp: AltiumPcbFootprint, spec: FootprintSpec) -> None:
    for pad in spec.pads:
        fp.add_pad(
            designator=pad.designator,
            position_mils=_pt(pad.x_mm, pad.y_mm),
            width_mils=_mil(pad.w_mm),
            height_mils=_mil(pad.h_mm),
            layer=COPPER_LAYER,
            shape=PadShape.ROUNDED_RECTANGLE,
            # KiCad rratio (radius/min-side) maps to Altium percent where 100%
            # is a fully rounded end: percent = 200 * rratio.
            corner_radius_percent=int(round(pad.roundrect_ratio * 200)),
        )


def _add_extent_and_designator(fp: AltiumPcbFootprint, spec: FootprintSpec) -> None:
    hw, hh = spec.body_w_mm / 2.0, spec.body_h_mm / 2.0
    _add_rect(fp, -hw, -hh, hw, hh, width_mm=LINE_MM, layer=EXTENT_LAYER)
    # ``.Designator`` special string, 1 mm Arial, centered on the body.
    fp.add_text(
        text=".Designator",
        position_mils=_pt(0.0, 0.0),
        height_mils=_mil(DESIGNATOR_HEIGHT_MM),
        layer=EXTENT_LAYER,
        font_kind="truetype",
        font_name="Arial",
        stroke_width_mils=_mil(LINE_MM),
        is_designator=True,
        text_justification=PcbTextJustification.CENTER_CENTER,
    )


def _add_body_and_pad_outlines(fp: AltiumPcbFootprint, spec: FootprintSpec) -> None:
    hw, hh = spec.body_w_mm / 2.0, spec.body_h_mm / 2.0
    _add_rect(fp, -hw, -hh, hw, hh, width_mm=LINE_MM, layer=BODY_LAYER)
    for pad in spec.pads:
        _add_rect(
            fp,
            pad.x_mm - pad.w_mm / 2.0,
            pad.y_mm - pad.h_mm / 2.0,
            pad.x_mm + pad.w_mm / 2.0,
            pad.y_mm + pad.h_mm / 2.0,
            width_mm=PAD_OUTLINE_MM,
            layer=BODY_LAYER,
        )
    # Pin-1 indicator: a small dot just outside pad 1, on its far (body-edge)
    # side, drawn as a near-solid arc.
    pad1 = next(p for p in spec.pads if p.designator == "1")
    marker_x = pad1.x_mm - pad1.w_mm / 2.0 - PAD1_MARKER_GAP_MM - PAD1_MARKER_RADIUS_MM
    fp.add_arc(
        center_mils=_pt(marker_x, pad1.y_mm),
        radius_mils=_mil(PAD1_MARKER_RADIUS_MM),
        start_angle_degrees=0.0,
        end_angle_degrees=360.0,
        width_mils=_mil(LINE_MM),
        layer=BODY_LAYER,
    )


def _body_and_pad_bounds(spec: FootprintSpec) -> tuple[float, float, float, float]:
    """Bounding box (x_min, y_min, x_max, y_max) of the body and all pads."""
    hw, hh = spec.body_w_mm / 2.0, spec.body_h_mm / 2.0
    x_min, y_min, x_max, y_max = -hw, -hh, hw, hh
    for p in spec.pads:
        x_min = min(x_min, p.x_mm - p.w_mm / 2.0)
        x_max = max(x_max, p.x_mm + p.w_mm / 2.0)
        y_min = min(y_min, p.y_mm - p.h_mm / 2.0)
        y_max = max(y_max, p.y_mm + p.h_mm / 2.0)
    return x_min, y_min, x_max, y_max


def _add_courtyard_and_center(fp: AltiumPcbFootprint, spec: FootprintSpec) -> None:
    # Courtyard is the body-and-pad bounding box plus clearance, so the
    # protruding pad tips are enclosed.
    x_min, y_min, x_max, y_max = _body_and_pad_bounds(spec)
    c = COURTYARD_CLEARANCE_MM
    _add_rect(
        fp, x_min - c, y_min - c, x_max + c, y_max + c,
        width_mm=LINE_MM, layer=COURTYARD_LAYER,
    )
    arm = CENTER_CROSS_MM / 2.0
    _add_segment(fp, (-arm, 0.0), (arm, 0.0), width_mm=LINE_MM, layer=COURTYARD_LAYER)
    _add_segment(fp, (0.0, -arm), (0.0, arm), width_mm=LINE_MM, layer=COURTYARD_LAYER)


def _add_silk_outline_with_gaps(fp: AltiumPcbFootprint, spec: FootprintSpec) -> None:
    """Module outline on the silkscreen with cutouts over the pads/soldermask.

    The body rectangle is drawn, but any run of the outline that would cross a
    pad (plus clearance) is cut out. Fine-pitch slivers between adjacent pads
    are merged into a single cutout so the result reads as a clean outline
    rather than a row of dashes.
    """
    hw, hh = spec.body_w_mm / 2.0, spec.body_h_mm / 2.0
    clr = SILK_PAD_CLEARANCE_MM

    def pads_crossing_y(edge_y: float) -> list[tuple[float, float]]:
        blocks = []
        for p in spec.pads:
            if p.y_mm - p.h_mm / 2.0 - clr <= edge_y <= p.y_mm + p.h_mm / 2.0 + clr:
                blocks.append((p.x_mm - p.w_mm / 2.0 - clr, p.x_mm + p.w_mm / 2.0 + clr))
        return blocks

    def pads_crossing_x(edge_x: float) -> list[tuple[float, float]]:
        blocks = []
        for p in spec.pads:
            if p.x_mm - p.w_mm / 2.0 - clr <= edge_x <= p.x_mm + p.w_mm / 2.0 + clr:
                blocks.append((p.y_mm - p.h_mm / 2.0 - clr, p.y_mm + p.h_mm / 2.0 + clr))
        return blocks

    # Horizontal edges (top and bottom): cut out over pads along x.
    for edge_y in (-hh, hh):
        for x0, x1 in _subtract_intervals(
            (-hw, hw), pads_crossing_y(edge_y),
            merge_gap=MIN_SILK_SEGMENT_MM, min_segment=MIN_SILK_SEGMENT_MM,
        ):
            _add_segment(fp, (x0, edge_y), (x1, edge_y), width_mm=LINE_MM, layer=SILK_LAYER)
    # Vertical edges (left and right): cut out over pads along y.
    for edge_x in (-hw, hw):
        for y0, y1 in _subtract_intervals(
            (-hh, hh), pads_crossing_x(edge_x),
            merge_gap=MIN_SILK_SEGMENT_MM, min_segment=MIN_SILK_SEGMENT_MM,
        ):
            _add_segment(fp, (edge_x, y0), (edge_x, y1), width_mm=LINE_MM, layer=SILK_LAYER)


def build_footprint(spec: FootprintSpec, pcblib: AltiumPcbLib) -> AltiumPcbFootprint:
    fp = pcblib.add_footprint(
        spec.name,
        height=f"{_mil(2.95):.4f}mil",
        description=spec.description,
    )
    _add_copper(fp, spec)                 # 1) copper
    _add_silk_outline_with_gaps(fp, spec)  # 2/6) silkscreen with gaps over pads
    _add_extent_and_designator(fp, spec)  # 3) M5 extent + designator
    _add_body_and_pad_outlines(fp, spec)  # 4) M13 body + pad outlines + pin-1
    _add_courtyard_and_center(fp, spec)   # 5) M15 courtyard + center cross
    return fp


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    spec = _wio_sx1262_spec()
    pcblib = AltiumPcbLib()
    build_footprint(spec, pcblib)
    pcblib.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
