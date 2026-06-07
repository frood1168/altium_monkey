from __future__ import annotations

import json
from pathlib import Path

from altium_monkey import (
    AltiumPcbFootprint,
    AltiumPcbLib,
    PadShape,
    PcbBodyProjection,
    PcbLayer,
    PcbRegionKind,
)

SAMPLE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PATH = OUTPUT_DIR / "pcblib_create_cavity_region.PcbLib"
MANIFEST_PATH = OUTPUT_DIR / "pcblib_create_cavity_region.json"
STEP_MODEL_PATH = SAMPLE_DIR / "assets" / "RESC1005X04L.step"

FOOTPRINT_NAME = "R0402_0.40MM_HD_CAVITY_DEMO"
CAVITY_WIDTH_MILS = 47.244
CAVITY_HEIGHT_MILS = 23.622
CAVITY_DEPTH_MILS = 19.685


def _rectangle_outline(
    width_mils: float, height_mils: float
) -> list[tuple[float, float]]:
    half_width = width_mils / 2.0
    half_height = height_mils / 2.0
    return [
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    ]


def _add_box_tracks(
    footprint: AltiumPcbFootprint,
    *,
    left_mils: float,
    bottom_mils: float,
    right_mils: float,
    top_mils: float,
    width_mils: float,
    layer: PcbLayer,
) -> None:
    footprint.add_track(
        (left_mils, bottom_mils),
        (right_mils, bottom_mils),
        width_mils=width_mils,
        layer=layer,
    )
    footprint.add_track(
        (left_mils, top_mils),
        (right_mils, top_mils),
        width_mils=width_mils,
        layer=layer,
    )
    footprint.add_track(
        (left_mils, bottom_mils),
        (left_mils, top_mils),
        width_mils=width_mils,
        layer=layer,
    )
    footprint.add_track(
        (right_mils, bottom_mils),
        (right_mils, top_mils),
        width_mils=width_mils,
        layer=layer,
    )


def _cavity_summary(pcblib_path: Path) -> dict[str, object]:
    parsed = AltiumPcbLib.from_file(pcblib_path)
    footprint = parsed.footprints[0]
    model_entries = parsed.get_embedded_model_entries()
    cavity_regions = [
        region
        for region in footprint.regions
        if region.region_kind == PcbRegionKind.CAVITY_DEFINITION
    ]
    if len(cavity_regions) != 1:
        raise RuntimeError(f"Expected one cavity region, found {len(cavity_regions)}")

    region = cavity_regions[0]
    xs = [vertex.x_mils for vertex in region.outline_vertices]
    ys = [vertex.y_mils for vertex in region.outline_vertices]
    return {
        "pcblib": str(pcblib_path.relative_to(SAMPLE_DIR)),
        "footprint": footprint.name,
        "region_native_kind": int(region.kind),
        "region_kind": region.region_kind.name,
        "layer": PcbLayer(region.layer).to_json_name(),
        "cavity_height_mils": round(region.cavity_height_mils, 6),
        "cavity_height_mm": round(region.cavity_height_mils * 0.0254, 6),
        "bounds_mils": {
            "width": round(max(xs) - min(xs), 6),
            "height": round(max(ys) - min(ys), 6),
        },
        "pad_count": len(footprint.pads),
        "track_count": len(footprint.tracks),
        "region_count": len(footprint.regions),
        "component_body_count": len(footprint.component_bodies),
        "embedded_model_count": len(model_entries),
        "embedded_model_names": [model.name for model, _payload in model_entries],
    }


def build_pcblib(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pcblib = AltiumPcbLib()
    step_model = pcblib.add_embedded_model(
        name=STEP_MODEL_PATH.name,
        model_data=STEP_MODEL_PATH.read_bytes(),
    )
    footprint = pcblib.add_footprint(
        FOOTPRINT_NAME,
        height="20mil",
        description="0402 footprint with a Mechanical 1 cavity definition region",
    )

    for designator, x_mils in (("1", -18.0), ("2", 18.0)):
        footprint.add_pad(
            designator=designator,
            position_mils=(x_mils, 0.0),
            width_mils=18.0,
            height_mils=22.0,
            layer=PcbLayer.TOP,
            shape=PadShape.ROUNDED_RECTANGLE,
        )

    _add_box_tracks(
        footprint,
        left_mils=-32.0,
        bottom_mils=-18.0,
        right_mils=32.0,
        top_mils=18.0,
        width_mils=2.0,
        layer=PcbLayer.MECHANICAL_13,
    )

    footprint.add_region(
        outline_points_mils=_rectangle_outline(CAVITY_WIDTH_MILS, CAVITY_HEIGHT_MILS),
        layer=PcbLayer.MECHANICAL_1,
        kind=PcbRegionKind.CAVITY_DEFINITION,
        cavity_height_mils=CAVITY_DEPTH_MILS,
        subpoly_index=-1,
    )
    footprint.add_embedded_3d_model(
        step_model,
        layer=PcbLayer.MECHANICAL_13,
        side=PcbBodyProjection.TOP,
    )

    pcblib.save(output_path)
    return output_path


def main() -> None:
    output_path = build_pcblib()
    summary = _cavity_summary(output_path)
    MANIFEST_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
