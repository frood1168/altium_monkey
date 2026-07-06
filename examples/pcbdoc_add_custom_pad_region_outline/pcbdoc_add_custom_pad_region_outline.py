from __future__ import annotations

import json
import math
from pathlib import Path

from altium_monkey import (
    AltiumPcbDoc,
    PadHoleShape,
    PadShape,
    PcbCustomPadLayerShapeSpec,
    PcbExtendedVertex,
    PcbLayer,
    PcbRegionKind,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
INPUT_PCBDOC = EXAMPLES_ROOT / "assets" / "pcbdoc" / "blank.PcbDoc"
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_add_custom_pad_region_outline.PcbDoc"
OUTPUT_MANIFEST = OUTPUT_DIR / "pcbdoc_add_custom_pad_region_outline.json"


def _iu(mils: float) -> int:
    return int(round(float(mils) * 10000.0))


def _extended_vertex(
    x_mils: float,
    y_mils: float,
    *,
    center_mils: tuple[float, float] | None = None,
    radius_mils: float = 0.0,
    start_angle: float = 0.0,
    end_angle: float = 0.0,
) -> PcbExtendedVertex:
    vertex = PcbExtendedVertex()
    vertex.x = _iu(x_mils)
    vertex.y = _iu(y_mils)
    if center_mils is None:
        vertex.is_round = False
        return vertex

    vertex.is_round = True
    vertex.center_x = _iu(center_mils[0])
    vertex.center_y = _iu(center_mils[1])
    vertex.radius = _iu(radius_mils)
    vertex.start_angle = float(start_angle)
    vertex.end_angle = float(end_angle)
    return vertex


def _capsule_outline(
    *,
    center_mils: tuple[float, float] = (0.0, 0.0),
    half_width_mils: float,
    half_height_mils: float,
) -> list[PcbExtendedVertex]:
    cx, cy = center_mils
    radius_mils = math.hypot(half_width_mils, half_height_mils)
    right_start_angle = math.atan2(-half_height_mils, half_width_mils)
    right_end_angle = math.atan2(half_height_mils, half_width_mils)
    left_start_angle = math.atan2(half_height_mils, -half_width_mils)
    left_end_angle = math.atan2(-half_height_mils, -half_width_mils)

    return [
        _extended_vertex(cx - half_width_mils, cy - half_height_mils),
        _extended_vertex(
            cx + half_width_mils,
            cy - half_height_mils,
            center_mils=(cx, cy),
            radius_mils=radius_mils,
            start_angle=right_start_angle,
            end_angle=right_end_angle,
        ),
        _extended_vertex(cx + half_width_mils, cy + half_height_mils),
        _extended_vertex(
            cx - half_width_mils,
            cy + half_height_mils,
            center_mils=(cx, cy),
            radius_mils=radius_mils,
            start_angle=left_start_angle,
            end_angle=left_end_angle,
        ),
    ]


def _outline_summary(shape_region: object) -> dict[str, object]:
    outline = list(getattr(shape_region, "outline", []) or [])
    if len(outline) > 1 and outline[0].x == outline[-1].x and outline[0].y == outline[-1].y:
        outline = outline[:-1]
    return {
        "layer": int(getattr(shape_region, "layer", 0)),
        "vertex_count": len(outline),
        "arc_vertex_count": sum(1 for vertex in outline if bool(vertex.is_round)),
        "hole_count": int(getattr(shape_region, "hole_count", 0)),
    }


def _custom_pad_manifest(pcbdoc: AltiumPcbDoc) -> dict[str, object]:
    pad = next(pad for pad in pcbdoc.pads if pad.designator == "CP1")
    custom_shape = pad.custom_shape
    layer_shapes = [] if custom_shape is None else custom_shape.iter_layer_shapes()
    return {
        "designator": pad.designator,
        "has_custom_shape": custom_shape is not None,
        "anchor_pad_index": None if custom_shape is None else custom_shape.anchor_pad_index,
        "hole_shape": int(pad.hole_shape),
        "hole_size_mils": round(float(pad.hole_size) / 10000.0, 6),
        "plated": bool(pad.is_plated),
        "layer_shapes": [
            {
                "layer": int(layer_shape.layer or 0),
                "has_shape_region": layer_shape.shape_region is not None,
                "outline": _outline_summary(layer_shape.shape_region),
            }
            for layer_shape in layer_shapes
        ],
    }


def build_pcbdoc(output_path: Path = OUTPUT_PCBDOC) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pcbdoc = AltiumPcbDoc.from_file(INPUT_PCBDOC)
    pcbdoc.set_outline_rectangle_mils(0.0, 0.0, 5600.0, 3600.0)
    pcbdoc.set_origin_to_outline_lower_left()

    pcbdoc.add_text(
        text="arc outline region",
        position_mils=(760.0, 3090.0),
        height_mils=70.0,
        stroke_width_mils=8.0,
        layer=PcbLayer.TOP_OVERLAY,
    )
    pcbdoc.add_region(
        outline_points_mils=[],
        outline_vertices=_capsule_outline(
            center_mils=(1450.0, 2350.0),
            half_width_mils=430.0,
            half_height_mils=210.0,
        ),
        hole_points_mils=[[(1340.0, 2290.0), (1560.0, 2290.0), (1450.0, 2460.0)]],
        layer=PcbLayer.TOP,
        kind=PcbRegionKind.COPPER,
        is_shapebased=True,
        net="ARC_REGION",
    )

    pcbdoc.add_text(
        text="custom pad with per-layer body",
        position_mils=(2750.0, 3090.0),
        height_mils=70.0,
        stroke_width_mils=8.0,
        layer=PcbLayer.TOP_OVERLAY,
    )
    pcbdoc.add_custom_pad(
        designator="CP1",
        position_mils=(3750.0, 2350.0),
        outline_points_mils=[],
        outline_vertices=_capsule_outline(
            half_width_mils=290.0,
            half_height_mils=130.0,
        ),
        layer=PcbLayer.TOP,
        layer_shapes=[
            PcbCustomPadLayerShapeSpec(
                layer=PcbLayer.BOTTOM,
                outline_points_mils=(),
                outline_vertices=_capsule_outline(
                    half_width_mils=250.0,
                    half_height_mils=170.0,
                ),
            )
        ],
        anchor_diameter_mils=95.0,
        anchor_shape=PadShape.CIRCLE,
        hole_size_mils=36.0,
        plated=True,
        hole_shape=PadHoleShape.ROUND,
        net="ARC_CUSTOM_PAD",
    )

    pcbdoc.save(output_path)

    parsed = AltiumPcbDoc.from_file(output_path)
    custom_pad = _custom_pad_manifest(parsed)
    normal_region = _outline_summary(parsed.shapebased_regions[0])
    checks = {
        "shape_based_region_has_arc_vertices": normal_region["arc_vertex_count"] > 0,
        "custom_pad_has_two_layer_shapes": len(custom_pad["layer_shapes"]) == 2,
        "custom_pad_layer_shapes_have_arc_vertices": all(
            layer_shape["outline"]["arc_vertex_count"] > 0
            for layer_shape in custom_pad["layer_shapes"]
        ),
        "custom_shapes_data_present": len(parsed.custom_shapes) == 1,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Custom pad region outline sample failed checks: {checks}")

    manifest = {
        "output_pcbdoc": output_path.name,
        "normal_region": normal_region,
        "custom_pad": custom_pad,
        "custom_shape_record_count": len(parsed.custom_shapes),
        "checks": checks,
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    output_path = build_pcbdoc()
    print(f"Wrote {output_path}")
    print(f"Wrote {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()
