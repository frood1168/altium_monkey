from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from altium_monkey import AltiumPcbDoc, AltiumPcbLib, PcbDocBuilder, PcbLayer
from altium_monkey.altium_layer_stack_document import AltiumLayerStackDocument

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
sys.path.insert(0, str(EXAMPLES_ROOT))

from _pcbdoc_rigid_flex_authoring import (  # noqa: E402
    build_recreation_document,
    recreation_board_outline_mils,
    recreation_reference_stackup_path,
    recreation_reference_stackupx_path,
)

SPEC_NAME = "cavity_placements"
SOURCE_PCBLIB = EXAMPLES_ROOT / "assets" / "pcblib" / "R0402_0.40MM_HD.PcbLib"
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_SOURCE_PCBLIB = OUTPUT_DIR / "R0402_0.40MM_HD.PcbLib"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_cavity_placements.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_cavity_placements.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_cavity_placements.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "cavity_placements_manifest.json"

COMPONENT_PLACEMENT_NAMES = {
    0: "None",
    1: "BodyUp",
    2: "BodyDown",
}
# Preserve the source top-overlay text metadata used by the sample designator.
TOP_OVERLAY_V7_SAVE_ID = 16973830
TEXT_LAYOUT = {
    "R6": {
        "designator": {
            "x_mils": 943.342,
            "y_mils": 469.0052,
            "height_mils": 32.0,
            "textbox_width_mils": 73.3161,
            "textbox_height_mils": 51.9897,
            "snap_x_mils": 970.0,
            "snap_y_mils": 485.0,
        }
    },
    "R5": {
        "designator": {
            "x_mils": 858.342,
            "y_mils": 469.0052,
            "height_mils": 32.0,
            "textbox_width_mils": 73.3161,
            "textbox_height_mils": 51.9897,
            "snap_x_mils": 885.0,
            "snap_y_mils": 485.0,
        }
    },
    "R4": {
        "designator": {
            "x_mils": 773.342,
            "y_mils": 469.0052,
            "height_mils": 32.0,
            "textbox_width_mils": 73.3161,
            "textbox_height_mils": 51.9897,
            "snap_x_mils": 800.0,
            "snap_y_mils": 485.0,
        }
    },
    "R2": {
        "designator": {
            "x_mils": 597.0178,
            "y_mils": 469.8851,
            "height_mils": 32.0,
            "textbox_width_mils": 73.3161,
            "textbox_height_mils": 51.9897,
            "snap_x_mils": 623.6758,
            "snap_y_mils": 485.8799,
        }
    },
    "R1": {
        "designator": {
            "x_mils": 523.6736,
            "y_mils": 469.0052,
            "height_mils": 32.0,
            "textbox_width_mils": 62.6529,
            "textbox_height_mils": 51.9897,
            "snap_x_mils": 545.0,
            "snap_y_mils": 485.0,
        }
    },
}


def _component_placement_name(value: int | None) -> str | int | None:
    if value is None:
        return None
    return COMPONENT_PLACEMENT_NAMES.get(value, value)


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _placements() -> tuple[tuple[str, PcbLayer, tuple[float, float]], ...]:
    return (
        ("R6", PcbLayer.BOTTOM, (965.0, 420.0)),
        ("R5", PcbLayer.MID2, (880.0, 420.0)),
        ("R4", PcbLayer.MID4, (795.0, 420.0)),
        ("R2", PcbLayer.MID1, (618.6758, 420.8799)),
        ("R1", PcbLayer.TOP, (540.0, 420.0)),
    )


def _copy_source_pcblib() -> AltiumPcbLib:
    OUTPUT_SOURCE_PCBLIB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PCBLIB, OUTPUT_SOURCE_PCBLIB)
    return AltiumPcbLib.from_file(OUTPUT_SOURCE_PCBLIB)


def _mils_to_internal(value: float) -> int:
    return int(round(float(value) * 10000.0))


def _apply_reference_text_layout(builder: PcbDocBuilder) -> None:
    component_by_index = {
        index: component.designator
        for index, component in enumerate(builder.components)
    }
    for text in builder.texts:
        if text.component_index is None:
            continue
        designator = component_by_index.get(text.component_index)
        if designator not in TEXT_LAYOUT:
            continue
        layout_key = "designator" if text.is_designator else "comment"
        if layout_key not in TEXT_LAYOUT[designator]:
            continue
        layout = TEXT_LAYOUT[designator][layout_key]
        text.layer = int(PcbLayer.TOP_OVERLAY)
        text.x = _mils_to_internal(layout["x_mils"])
        text.y = _mils_to_internal(layout["y_mils"])
        text.height = _mils_to_internal(layout["height_mils"])
        text.rotation = 0.0
        text.stroke_width = _mils_to_internal(10.0)
        text.is_mirrored = False
        text.font_type = 0
        text._font_type_offset43 = 0
        text.stroke_font_type = 1
        text.font_name = "Arial"
        text.barcode_font_name = "Arial"
        text.text_content = designator if layout_key == "designator" else "Comment"
        text.textbox_rect_width = _mils_to_internal(layout["textbox_width_mils"])
        text.textbox_rect_height = _mils_to_internal(layout["textbox_height_mils"])
        text.textbox_rect_justification = 5
        text.is_justification_valid = True
        text.snap_point_x = _mils_to_internal(layout["snap_x_mils"])
        text.snap_point_y = _mils_to_internal(layout["snap_y_mils"])
        text.advance_snapping = False
        text.barcode_layer_v7 = TOP_OVERLAY_V7_SAVE_ID
    builder._texts_dirty = True


def _build_pcbdoc(path: Path) -> None:
    stack = build_recreation_document(SPEC_NAME)
    source_pcblib = _copy_source_pcblib()
    footprint = source_pcblib.footprints[0]

    builder = PcbDocBuilder()
    builder.set_layer_stack_document(stack)
    builder.set_outline_vertices_mils(recreation_board_outline_mils(SPEC_NAME))
    builder.set_origin_to_outline_lower_left()
    for designator, layer, position in _placements():
        builder.place_footprint(
            footprint,
            designator=designator,
            position_mils=position,
            layer=layer,
            rotation_degrees=90.0,
            source_pcblib=source_pcblib,
            source_footprint_library=OUTPUT_SOURCE_PCBLIB.name,
        )
    _apply_reference_text_layout(builder)
    builder.save(path)

    OUTPUT_STACKUP.write_bytes(
        recreation_reference_stackup_path(SPEC_NAME).read_bytes()
    )
    OUTPUT_STACKUPX.write_bytes(
        recreation_reference_stackupx_path(SPEC_NAME).read_bytes()
    )


def _copper_layer_policy(
    stack: AltiumLayerStackDocument,
) -> dict[str, dict[str, object]]:
    return {
        layer.display_name: {
            "legacy_layer_id": layer.legacy_layer_id,
            "component_placement": _component_placement_name(layer.component_placement),
            "copper_orientation": _stackupx_property(layer, "CopperOrientation"),
            "thickness_mils": layer.copper_thickness_mils,
        }
        for layer in stack.physical_stacks[0].layers
        if layer.family == "copper"
    }


def _stackupx_property(layer: object, name: str) -> str:
    lower_name = name.lower()
    for prop_name, _prop_type, value in getattr(layer, "stackupx_properties", ()):
        if str(prop_name).lower() == lower_name:
            return str(value)
    return ""


def _dielectric_layers(
    stack: AltiumLayerStackDocument,
) -> list[dict[str, object]]:
    return [
        {
            "name": layer.display_name,
            "family": layer.family,
            "material": layer.dielectric_material,
            "thickness_mils": layer.dielectric_height_mils,
            "dielectric_constant": layer.dielectric_constant,
            "dielectric_type": layer.dielectric_type,
        }
        for layer in stack.physical_stacks[0].layers
        if layer.family in {"dielectric", "solder_mask"}
    ]


def _internal_to_mils(value: int) -> float:
    return round(float(value) / 10000.0, 4)


def _expected_component_text_layout() -> dict[str, dict[str, dict[str, object]]]:
    expected: dict[str, dict[str, dict[str, object]]] = {}
    for designator, per_kind in TEXT_LAYOUT.items():
        expected[designator] = {}
        for kind, layout in per_kind.items():
            expected[designator][kind] = {
                "text": designator if kind == "designator" else "Comment",
                "layer": int(PcbLayer.TOP_OVERLAY),
                "x_mils": round(float(layout["x_mils"]), 4),
                "y_mils": round(float(layout["y_mils"]), 4),
                "height_mils": round(float(layout["height_mils"]), 4),
                "rotation_degrees": 0.0,
                "stroke_width_mils": 10.0,
                "font_type": 0,
                "font_name": "Arial",
                "stroke_font_type": 1,
                "textbox_width_mils": round(float(layout["textbox_width_mils"]), 4),
                "textbox_height_mils": round(float(layout["textbox_height_mils"]), 4),
                "textbox_justification": 5,
                "is_justification_valid": True,
                "snap_x_mils": round(float(layout["snap_x_mils"]), 4),
                "snap_y_mils": round(float(layout["snap_y_mils"]), 4),
                "is_mirrored": False,
            }
    return expected


def _component_text_layout(
    pcbdoc: AltiumPcbDoc,
) -> dict[str, dict[str, dict[str, object]]]:
    component_by_index = {
        index: component.designator for index, component in enumerate(pcbdoc.components)
    }
    layout: dict[str, dict[str, dict[str, object]]] = {}
    for text in pcbdoc.texts:
        if text.component_index is None:
            continue
        designator = component_by_index.get(text.component_index)
        if designator is None:
            continue
        kind = (
            "designator" if text.is_designator else "comment" if text.is_comment else ""
        )
        if not kind:
            continue
        layout.setdefault(designator, {})[kind] = {
            "text": text.text_content,
            "layer": int(text.layer),
            "x_mils": _internal_to_mils(text.x),
            "y_mils": _internal_to_mils(text.y),
            "height_mils": _internal_to_mils(text.height),
            "rotation_degrees": round(float(text.rotation), 4),
            "stroke_width_mils": _internal_to_mils(text.stroke_width),
            "font_type": int(text.font_type),
            "font_name": text.font_name,
            "stroke_font_type": int(text.stroke_font_type),
            "textbox_width_mils": _internal_to_mils(text.textbox_rect_width),
            "textbox_height_mils": _internal_to_mils(text.textbox_rect_height),
            "textbox_justification": int(text.textbox_rect_justification),
            "is_justification_valid": bool(text.is_justification_valid),
            "snap_x_mils": _internal_to_mils(text.snap_point_x),
            "snap_y_mils": _internal_to_mils(text.snap_point_y),
            "is_mirrored": bool(text.is_mirrored),
        }
    return {
        designator: layout[designator]
        for designator, _layer, _position in _placements()
        if designator in layout
    }


def _manifest(path: Path) -> dict[str, object]:
    pcbdoc = AltiumPcbDoc.from_file(path)
    stack = AltiumLayerStackDocument.from_pcbdoc(pcbdoc)
    model_entries = pcbdoc.get_embedded_model_entries()
    components = [
        {
            "designator": component.designator,
            "layer": component.layer,
            "footprint": component.footprint,
            "source_footprint_library": component.source_footprint_library_name,
        }
        for component in pcbdoc.components
    ]
    component_index_by_designator = {
        component.designator: index for index, component in enumerate(pcbdoc.components)
    }
    pad_layers = {
        designator: sorted(
            {
                PcbLayer(pad.layer).to_json_name()
                for pad in pcbdoc.pads
                if pad.component_index == component_index
            }
        )
        for designator, component_index in component_index_by_designator.items()
    }
    cavity_regions = [
        region
        for region in pcbdoc.regions
        if region.region_kind is not None
        and region.region_kind.name == "CAVITY_DEFINITION"
    ]
    shapebased_cavities = [
        region
        for region in pcbdoc.shapebased_regions
        if region.region_kind is not None
        and region.region_kind.name == "CAVITY_DEFINITION"
    ]
    component_body_indices = sorted(
        int(body.component_index)
        for body in pcbdoc.component_bodies
        if body.component_index is not None
    )
    expected_layers = {
        designator: layer.to_json_name()
        for designator, layer, _position in _placements()
    }
    expected_copper_policy = {
        "Top Layer": {
            "legacy_layer_id": 1,
            "component_placement": "BodyUp",
            "copper_orientation": "0",
            "thickness_mils": 1.378,
        },
        "IN1": {
            "legacy_layer_id": 2,
            "component_placement": "BodyUp",
            "copper_orientation": "0",
            "thickness_mils": 1.378,
        },
        "IN2": {
            "legacy_layer_id": 4,
            "component_placement": "None",
            "copper_orientation": "0",
            "thickness_mils": 1.378,
        },
        "IN3": {
            "legacy_layer_id": 5,
            "component_placement": "BodyDown",
            "copper_orientation": "1",
            "thickness_mils": 1.378,
        },
        "IN4": {
            "legacy_layer_id": 3,
            "component_placement": "BodyDown",
            "copper_orientation": "1",
            "thickness_mils": 1.378,
        },
        "Bottom Layer": {
            "legacy_layer_id": 32,
            "component_placement": "BodyDown",
            "copper_orientation": "1",
            "thickness_mils": 1.378,
        },
    }
    copper_policy = _copper_layer_policy(stack)
    component_text_layout = _component_text_layout(pcbdoc)
    semantic_match = (
        {item["designator"]: item["layer"] for item in components} == expected_layers
        and {item["footprint"] for item in components} == {"R0402_0.40MM_HD"}
        and pad_layers == {key: [value] for key, value in expected_layers.items()}
        and copper_policy == expected_copper_policy
        and component_text_layout == _expected_component_text_layout()
        and len(cavity_regions) == len(_placements())
        and len(shapebased_cavities) == len(_placements())
        and len(pcbdoc.component_bodies) == len(_placements())
        and component_body_indices == list(range(len(_placements())))
        and len(model_entries) == 1
    )
    return {
        "schema": "altium_monkey.examples.pcbdoc_create_cavity_placements.a0",
        "source_pcblib": _relative_to_examples(OUTPUT_SOURCE_PCBLIB),
        "output_pcbdoc": _relative_to_examples(path),
        "output_stackup": _relative_to_examples(OUTPUT_STACKUP),
        "output_stackupx": _relative_to_examples(OUTPUT_STACKUPX),
        "stackup_reference": _relative_to_examples(
            recreation_reference_stackup_path(SPEC_NAME)
        ),
        "stackupx_reference": _relative_to_examples(
            recreation_reference_stackupx_path(SPEC_NAME)
        ),
        "stackup_exact_reference_match": OUTPUT_STACKUP.read_bytes()
        == recreation_reference_stackup_path(SPEC_NAME).read_bytes(),
        "stackupx_exact_reference_match": OUTPUT_STACKUPX.read_bytes()
        == recreation_reference_stackupx_path(SPEC_NAME).read_bytes(),
        "semantic_match": semantic_match,
        "copper_layers": list(copper_policy),
        "copper_layer_policy": copper_policy,
        "dielectric_layers": _dielectric_layers(stack),
        "components": components,
        "component_text_layout": component_text_layout,
        "pad_layers": pad_layers,
        "cavity_region_count": len(cavity_regions),
        "shapebased_cavity_region_count": len(shapebased_cavities),
        "component_body_count": len(pcbdoc.component_bodies),
        "shapebased_component_body_count": len(pcbdoc.shapebased_component_bodies),
        "embedded_model_count": len(model_entries),
        "embedded_model_names": [model.name for model, _payload in model_entries],
        "cavity_height_mils": sorted(
            {round(region.cavity_height_mils, 6) for region in cavity_regions}
        ),
    }


def build_outputs(
    pcbdoc_path: Path = OUTPUT_PCBDOC,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path]:
    pcbdoc_path.parent.mkdir(parents=True, exist_ok=True)
    _build_pcbdoc(pcbdoc_path)
    manifest = _manifest(pcbdoc_path)
    if not manifest["semantic_match"]:
        raise RuntimeError("Generated cavity placement board did not match")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pcbdoc_path, manifest_path


def main() -> None:
    pcbdoc_path, manifest_path = build_outputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"Wrote {pcbdoc_path}")
    print(f"Wrote {OUTPUT_SOURCE_PCBLIB}")
    print(f"Wrote {OUTPUT_STACKUP}")
    print(f"Wrote {OUTPUT_STACKUPX}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(f"Components: {len(manifest['components'])}")
    print(f"Cavity regions: {manifest['cavity_region_count']}")
    print(f"Copper placement: {manifest['copper_layer_policy']}")


if __name__ == "__main__":
    main()
