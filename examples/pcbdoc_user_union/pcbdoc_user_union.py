import json
from pathlib import Path

from altium_monkey import (
    AltiumPcbDoc,
    AltiumPcbLib,
    PadShape,
    PcbBodyProjection,
    PcbLayer,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
INPUT_PCBDOC = EXAMPLES_ROOT / "assets" / "pcbdoc" / "blank.PcbDoc"
TP_PCBLIB = SAMPLE_DIR / "assets" / "footprints" / "9774080360R-YIYUAN.PcbLib"
MH_PCBLIB = SAMPLE_DIR / "assets" / "footprints" / "YZ209315103P-01.PcbLib"
STEP_MODEL = (
    SAMPLE_DIR / "assets" / "models" / "cricket-node-hw__B__fixture_alignment.step"
)
OUTPUT_PATH = SAMPLE_DIR / "output" / "pcbdoc_user_union.PcbDoc"
SUMMARY_PATH = SAMPLE_DIR / "output" / "pcbdoc_user_union.json"
UNION_NAME = "DEMO_USER_UNION"
BOARD_WIDTH_MILS = 8000.0
BOARD_HEIGHT_MILS = 6000.0
MM_TO_MILS = 1000.0 / 25.4


def _new_demo_board() -> AltiumPcbDoc:
    pcbdoc = AltiumPcbDoc.from_file(INPUT_PCBDOC)
    pcbdoc.set_outline_rectangle_mils(0.0, 0.0, BOARD_WIDTH_MILS, BOARD_HEIGHT_MILS)
    pcbdoc.set_origin_to_outline_lower_left()
    return pcbdoc


def _load_single_footprint(path: Path) -> tuple[AltiumPcbLib, object]:
    pcblib = AltiumPcbLib.from_file(path)
    if len(pcblib.footprints) != 1:
        raise RuntimeError(f"Expected one footprint in {path.name}")
    return pcblib, pcblib.footprints[0]


def _members_by_collection(user_union: object) -> dict[str, int]:
    return {
        collection: len(members)
        for collection, members in user_union.members_by_collection.items()
    }


def _find_demo_union(pcbdoc: AltiumPcbDoc) -> object:
    for user_union in pcbdoc.user_unions:
        if user_union.name == UNION_NAME:
            return user_union
    raise RuntimeError(f"Missing user union {UNION_NAME!r}")


def build_pcbdoc(
    output_path: Path = OUTPUT_PATH,
    summary_path: Path = SUMMARY_PATH,
) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tp_lib, tp_footprint = _load_single_footprint(TP_PCBLIB)
    mh_lib, mh_footprint = _load_single_footprint(MH_PCBLIB)

    pcbdoc = _new_demo_board()
    tp_component = pcbdoc.add_component_from_pcblib(
        tp_footprint,
        designator="TP1",
        position_mils=(1800.0, 3200.0),
        layer=PcbLayer.TOP,
        rotation_degrees=0.0,
        source_pcblib=tp_lib,
        comment_text="TEST POINT",
        component_parameters={"Source": tp_footprint.name},
    )
    mh_component = pcbdoc.add_component_from_pcblib(
        mh_footprint,
        designator="MH1",
        position_mils=(5700.0, 3200.0),
        layer=PcbLayer.TOP,
        rotation_degrees=0.0,
        source_pcblib=mh_lib,
        comment_text="MOUNTING HOLE",
        component_parameters={"Source": mh_footprint.name},
    )

    npth_pad = pcbdoc.add_pad(
        designator="NPTH1",
        position_mils=(3900.0, 2050.0),
        width_mils=125.0,
        height_mils=125.0,
        shape=PadShape.CIRCLE,
        layer=PcbLayer.MULTI_LAYER,
        hole_size_mils=2.0 * MM_TO_MILS,
        plated=False,
        solder_mask_expansion_mils=0.0,
        paste_mask_expansion_mils=0.0,
    )
    npth_pad.is_tenting_top = True
    npth_pad.is_tenting_bottom = True
    npth_pad.pastemask_expansion_mode = 0
    npth_pad.soldermask_expansion_mode = 0

    via = pcbdoc.add_via(
        position_mils=(3900.0, 3950.0),
        diameter_mils=28.0,
        hole_size_mils=12.0,
        net="DEMO_UNION_NET",
    )

    trace_a = pcbdoc.add_track(
        (1450.0, 3950.0),
        (3900.0, 3950.0),
        width_mils=10.0,
        layer=PcbLayer.TOP,
        net="DEMO_UNION_NET",
    )
    trace_b = pcbdoc.add_track(
        (3900.0, 3950.0),
        (6100.0, 3950.0),
        width_mils=10.0,
        layer=PcbLayer.TOP,
        net="DEMO_UNION_NET",
    )
    trace_c = pcbdoc.add_track(
        (2700.0, 2050.0),
        (5100.0, 2050.0),
        width_mils=8.0,
        layer=PcbLayer.TOP_OVERLAY,
    )
    arc = pcbdoc.add_arc(
        center_mils=(3900.0, 3050.0),
        radius_mils=700.0,
        start_angle_degrees=20.0,
        end_angle_degrees=160.0,
        width_mils=8.0,
        layer=PcbLayer.TOP_OVERLAY,
    )
    circle = pcbdoc.add_arc(
        center_mils=(3900.0, 3050.0),
        radius_mils=350.0,
        start_angle_degrees=0.0,
        end_angle_degrees=360.0,
        width_mils=6.0,
        layer=PcbLayer.TOP_OVERLAY,
    )
    fill = pcbdoc.add_fill(
        (3350.0, 2600.0),
        (4450.0, 2780.0),
        layer=PcbLayer.TOP,
        net="DEMO_UNION_NET",
    )
    pcbdoc.add_region(
        outline_points_mils=[
            (3250.0, 3300.0),
            (4550.0, 3300.0),
            (4300.0, 3600.0),
            (3500.0, 3600.0),
        ],
        layer=PcbLayer.TOP,
        net="DEMO_UNION_NET",
    )
    region_shape = pcbdoc.shapebased_regions[-1]
    label = pcbdoc.add_text(
        text="USER UNION FEATURE SMOKE",
        position_mils=(2700.0, 4750.0),
        height_mils=90.0,
        stroke_width_mils=8.0,
        layer=PcbLayer.TOP_OVERLAY,
    )

    step_model = pcbdoc.add_embedded_model(
        name=STEP_MODEL.name,
        model_data=STEP_MODEL.read_bytes(),
    )
    model_body = pcbdoc.add_embedded_3d_model(
        step_model,
        layer=PcbLayer.MECHANICAL_13,
        side=PcbBodyProjection.TOP,
        location_mils=(3900.0, 3050.0),
        bounds_mils=(2900.0, 2400.0, 4900.0, 3700.0),
        overall_height_mils=220.0,
        rotation_z_degrees=0.0,
        name="FREE_STEP_BODY",
    )
    model_shape_body = pcbdoc.shapebased_component_bodies[-1]

    created_union = pcbdoc.create_user_union(
        UNION_NAME,
        [
            tp_component,
            mh_component,
            npth_pad,
            via,
            trace_a,
            trace_b,
            trace_c,
            arc,
            circle,
            fill,
            region_shape,
            label,
            model_body,
            model_shape_body,
        ],
    )
    expected_collections = {
        "arcs",
        "components",
        "component_bodies",
        "fills",
        "pads",
        "regions",
        "shapebased_regions",
        "shapebased_component_bodies",
        "texts",
        "tracks",
        "vias",
    }
    created_collections = set(created_union.members_by_collection)
    if not expected_collections.issubset(created_collections):
        missing = ", ".join(sorted(expected_collections - created_collections))
        raise RuntimeError(f"Created union is missing member collections: {missing}")

    pcbdoc.save(output_path)

    reparsed = AltiumPcbDoc.from_file(output_path)
    reparsed_union = _find_demo_union(reparsed)
    members_by_collection = _members_by_collection(reparsed_union)
    if not expected_collections.issubset(set(members_by_collection)):
        raise RuntimeError(
            "Saved PcbDoc did not reparse with the expected user-union members"
        )

    summary = {
        "input_pcbdoc": "assets/pcbdoc/blank.PcbDoc",
        "footprints": [TP_PCBLIB.name, MH_PCBLIB.name],
        "step_model": STEP_MODEL.name,
        "output_pcbdoc": "pcbdoc_user_union/output/pcbdoc_user_union.PcbDoc",
        "union_name": reparsed_union.name,
        "union_index": reparsed_union.union_index,
        "member_count": reparsed_union.member_count,
        "members_by_collection": members_by_collection,
        "component_designators": [
            component.designator for component in reparsed.components
        ],
        "pad_count": len(reparsed.pads),
        "via_count": len(reparsed.vias),
        "track_count": len(reparsed.tracks),
        "arc_count": len(reparsed.arcs),
        "fill_count": len(reparsed.fills),
        "region_count": len(reparsed.regions),
        "component_body_count": len(reparsed.component_bodies),
        "typed_smart_union_count": len(reparsed.smart_unions),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return output_path, summary_path


def main() -> None:
    output_path, summary_path = build_pcbdoc()
    print(f"Wrote {output_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
