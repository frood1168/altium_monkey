from __future__ import annotations

import json
import re
from pathlib import Path

from altium_monkey import (
    AltiumPcbLib,
    MechanicalLayerKind,
    PcbLayer,
)
from altium_monkey.altium_pcb_enums import (
    pcb_mechanical_layer_number_to_v7_saved_layer_id,
)
from altium_monkey.altium_pcblib_builder import PcbLibBuildProfile
from altium_monkey.altium_pcblib_builder import mechanical_layer_kind_to_pcblib_token

SAMPLE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PATH = OUTPUT_DIR / "pcblib_create_mechanical_layer_kinds.PcbLib"
MANIFEST_PATH = OUTPUT_DIR / "pcblib_create_mechanical_layer_kinds.json"

FOOTPRINT_NAME = "MECH_LAYER_KIND_SAMPLE"

SAMPLE_LAYER_NAMES = [
    ("MECHANICAL1", "Mechanical 1", True),
    ("MECHANICAL2", "Board Shape", True),
    ("MECHANICAL3", "Route Tool Path", True),
    ("MECHANICAL4", "V Cut", True),
    ("MECHANICAL5", "Fab Notes", True),
    ("MECHANICAL6", "Sheet", True),
    ("MECHANICAL7", "Board", True),
    ("MECHANICAL8", "Dimensions", True),
    ("MECHANICAL9", "Assembly Notes", True),
    ("MECHANICAL10", "Top 3D Body", True),
    ("MECHANICAL11", "Bottom 3D Body", True),
    ("MECHANICAL12", "Top Assembly", True),
    ("MECHANICAL13", "Bottom Assembly", True),
    ("MECHANICAL14", "Top Coating", True),
    ("MECHANICAL15", "Bottom Coating", True),
    ("MECHANICAL16", "Top Component Center", True),
    ("MECHANICAL17", "Bottom Component Center", True),
    ("MECHANICAL18", "Top Glue Points", True),
    ("MECHANICAL19", "Bottom Glue Points", True),
    ("MECHANICAL20", "Top Courtyard", True),
    ("MECHANICAL21", "Bottom Courtyard", True),
    ("MECHANICAL22", "Top Component Outline", True),
    ("MECHANICAL23", "Bottom Component Outline", True),
    ("MECHANICAL24", "Top Designator", True),
    ("MECHANICAL25", "Bottom Designator", True),
    ("MECHANICAL26", "Top Dimensions", True),
    ("MECHANICAL27", "Bottom Dimensions", True),
    ("MECHANICAL28", "Top Gold Plating", True),
    ("MECHANICAL29", "Bottom Gold Plating", True),
    ("MECHANICAL30", "Top Value", True),
    ("MECHANICAL31", "Bottom Value", True),
    ("MECHANICAL32", "Mechanical 32", False),
]

SAMPLE_ASSIGNMENTS = [
    ("MECHANICAL2", MechanicalLayerKind.BOARD_SHAPE),
    ("MECHANICAL3", MechanicalLayerKind.ROUTE_TOOL_PATH),
    ("MECHANICAL4", MechanicalLayerKind.VCUT),
    ("MECHANICAL5", MechanicalLayerKind.FAB_NOTES),
    ("MECHANICAL6", MechanicalLayerKind.SHEET),
    ("MECHANICAL7", MechanicalLayerKind.BOARD),
    ("MECHANICAL8", MechanicalLayerKind.DIMENSIONS),
    ("MECHANICAL9", MechanicalLayerKind.ASSEMBLY_NOTES),
    ("MECHANICAL10", MechanicalLayerKind.BODY_3D_TOP),
    ("MECHANICAL11", MechanicalLayerKind.BODY_3D_BOTTOM),
    ("MECHANICAL12", MechanicalLayerKind.ASSEMBLY_TOP),
    ("MECHANICAL13", MechanicalLayerKind.ASSEMBLY_BOTTOM),
    ("MECHANICAL14", MechanicalLayerKind.COATING_TOP),
    ("MECHANICAL15", MechanicalLayerKind.COATING_BOTTOM),
    ("MECHANICAL16", MechanicalLayerKind.COMPONENT_CENTER_TOP),
    ("MECHANICAL17", MechanicalLayerKind.COMPONENT_CENTER_BOTTOM),
    ("MECHANICAL18", MechanicalLayerKind.GLUE_POINTS_TOP),
    ("MECHANICAL19", MechanicalLayerKind.GLUE_POINTS_BOTTOM),
    ("MECHANICAL20", MechanicalLayerKind.COURTYARD_TOP),
    ("MECHANICAL21", MechanicalLayerKind.COURTYARD_BOTTOM),
    ("MECHANICAL22", MechanicalLayerKind.COMPONENT_OUTLINE_TOP),
    ("MECHANICAL23", MechanicalLayerKind.COMPONENT_OUTLINE_BOTTOM),
    ("MECHANICAL24", MechanicalLayerKind.DESIGNATOR_TOP),
    ("MECHANICAL25", MechanicalLayerKind.DESIGNATOR_BOTTOM),
    ("MECHANICAL26", MechanicalLayerKind.DIMENSIONS_TOP),
    ("MECHANICAL27", MechanicalLayerKind.DIMENSIONS_BOTTOM),
    ("MECHANICAL28", MechanicalLayerKind.GOLD_PLATING_TOP),
    ("MECHANICAL29", MechanicalLayerKind.GOLD_PLATING_BOTTOM),
    ("MECHANICAL30", MechanicalLayerKind.VALUE_TOP),
    ("MECHANICAL31", MechanicalLayerKind.VALUE_BOTTOM),
]

SAMPLE_COMPONENT_LAYER_PAIRS = [
    ("MECHANICAL10", "MECHANICAL11"),
    ("MECHANICAL12", "MECHANICAL13"),
    ("MECHANICAL14", "MECHANICAL15"),
    ("MECHANICAL16", "MECHANICAL17"),
    ("MECHANICAL18", "MECHANICAL19"),
    ("MECHANICAL20", "MECHANICAL21"),
    ("MECHANICAL22", "MECHANICAL23"),
    ("MECHANICAL24", "MECHANICAL25"),
    ("MECHANICAL26", "MECHANICAL27"),
    ("MECHANICAL28", "MECHANICAL29"),
    ("MECHANICAL30", "MECHANICAL31"),
]

ROUTE_TOOL_PATH_LAYER = "MECHANICAL3"

LAYER_SET_1_PREFIX = (
    "MultiLayer",
    "TopPaste",
    "TopOverlay",
    "TopSolder",
    "TopLayer",
    "BottomLayer",
    "BottomSolder",
    "BottomOverlay",
    "BottomPaste",
    "DrillGuide",
    "KeepOutLayer",
)


def _mechanical_layer_number(layer: str) -> int:
    return int(layer.removeprefix("MECHANICAL"))


def _expected_layer_set_1_layers() -> tuple[str, ...]:
    enabled_numbers = tuple(
        _mechanical_layer_number(layer)
        for layer, _name, enabled in SAMPLE_LAYER_NAMES
        if enabled
    )
    return (
        LAYER_SET_1_PREFIX
        + tuple(f"Mechanical{number}" for number in enabled_numbers if number <= 16)
        + ("DrillDrawing",)
        + tuple(f"Mechanical{number}" for number in enabled_numbers if number > 16)
    )


def _expected_layer_set_5_layers() -> tuple[str, ...]:
    return tuple(
        f"Mechanical{_mechanical_layer_number(layer)}"
        for layer, _name, enabled in SAMPLE_LAYER_NAMES
        if enabled
    )


def _expected_mechanical_kind_fields(layer: str, token: str) -> dict[str, str]:
    fields = {
        "layer_v8": token,
        "v9_cache": token,
    }
    if _mechanical_layer_number(layer) <= 16:
        fields["legacy"] = token
    else:
        fields["v7"] = token
    return fields


def _primitive_counts(parsed: AltiumPcbLib) -> dict[str, int]:
    footprints = parsed.footprints
    if len(footprints) != 1:
        raise RuntimeError(
            f"Generated sample should contain one footprint, found {len(footprints)}"
        )
    footprint = footprints[0]
    return {
        "pads": len(getattr(footprint, "pads", ())),
        "vias": len(getattr(footprint, "vias", ())),
        "tracks": len(getattr(footprint, "tracks", ())),
        "arcs": len(getattr(footprint, "arcs", ())),
        "fills": len(getattr(footprint, "fills", ())),
        "regions": len(getattr(footprint, "regions", ())),
        "texts": len(getattr(footprint, "texts", ())),
        "component_bodies": len(getattr(footprint, "component_bodies", ())),
    }


def _readback_manifest(pcblib_path: Path) -> dict[str, object]:
    parsed = AltiumPcbLib.from_file(pcblib_path)
    library_data = PcbLibBuildProfile.from_pcblib(pcblib_path).library_data
    layer_table = library_data.layer_table

    registry = []
    for layer, expected_name, expected_enabled in SAMPLE_LAYER_NAMES:
        mechanical_number = _mechanical_layer_number(layer)
        if mechanical_number <= 16:
            entry = layer_table.legacy_layer(
                PcbLayer.MECHANICAL_1.value + mechanical_number - 1
            )
        else:
            v7_layer_id = pcb_mechanical_layer_number_to_v7_saved_layer_id(
                mechanical_number
            )
            if v7_layer_id is None:
                raise RuntimeError(f"{layer} did not map to a V7 layer id")
            entry = layer_table.v7_layer_by_layer_id(v7_layer_id)
        if entry is None:
            raise RuntimeError(f"{layer} was not present in Library/Data")
        if entry.name != expected_name:
            raise RuntimeError(
                f"{layer} expected name {expected_name!r}, read {entry.name!r}"
            )
        if entry.mechanical_enabled != expected_enabled:
            raise RuntimeError(
                f"{layer} expected enabled={expected_enabled}, "
                f"read enabled={entry.mechanical_enabled}"
            )
        registry.append(
            {
                "layer": layer,
                "name": expected_name,
                "enabled": expected_enabled,
            }
        )

    assignments = []
    mechanical_kind_fields = []
    for layer, expected_kind in SAMPLE_ASSIGNMENTS:
        actual_kind = parsed.get_mechanical_layer_kind(layer)
        if actual_kind != expected_kind:
            raise RuntimeError(
                f"{layer} expected {expected_kind.name}, "
                f"read {actual_kind.name if actual_kind is not None else None}"
            )
        expected_token = mechanical_layer_kind_to_pcblib_token(expected_kind)
        actual_fields = library_data.mechanical_layer_kind_field_values(layer)
        expected_fields = _expected_mechanical_kind_fields(layer, expected_token)
        if actual_fields != expected_fields:
            raise RuntimeError(
                f"{layer} expected MECHKIND fields {expected_fields!r}, "
                f"read {actual_fields!r}"
            )
        assignments.append(
            {
                "layer": layer,
                "kind": expected_kind.name,
                "value": int(expected_kind),
            }
        )
        mechanical_kind_fields.append(
            {
                "layer": layer,
                "fields": actual_fields,
            }
        )

    pair_values: dict[int, dict[int, str]] = {}
    for segment in library_data.segments:
        key = segment.key or ""
        match = re.fullmatch(r"MECHPAIR(\d+)L([12])", key, re.IGNORECASE)
        if match is None or segment.value is None:
            continue
        pair_values.setdefault(int(match.group(1)), {})[int(match.group(2))] = (
            segment.value
        )

    pairs = []
    for pair_index, (layer_1, layer_2) in enumerate(SAMPLE_COMPONENT_LAYER_PAIRS):
        actual_pair = pair_values.get(pair_index, {})
        actual_layer_1 = actual_pair.get(1, "")
        actual_layer_2 = actual_pair.get(2, "")
        if actual_layer_1 != layer_1 or actual_layer_2 != layer_2:
            raise RuntimeError(
                f"MECHPAIR{pair_index} expected {layer_1}/{layer_2}, "
                f"read {actual_layer_1}/{actual_layer_2}"
            )
        pairs.append(
            {
                "pair_index": pair_index,
                "layer_1": layer_1,
                "layer_2": layer_2,
            }
        )

    route_record = library_data.get_board_record("ROUTETOOLPATHLAYER")
    route_tool_path_layer = (
        str(route_record.get_value("ROUTETOOLPATHLAYER", "")).strip()
        if route_record is not None
        else ""
    )
    if route_tool_path_layer != ROUTE_TOOL_PATH_LAYER:
        raise RuntimeError(
            f"ROUTETOOLPATHLAYER expected {ROUTE_TOOL_PATH_LAYER}, "
            f"read {route_tool_path_layer!r}"
        )

    layer_set_1 = library_data.layer_sets.layer_set(1)
    layer_set_5 = library_data.layer_sets.layer_set(5)
    if layer_set_1 is None or layer_set_5 is None:
        raise RuntimeError("Generated PcbLib did not contain layer sets 1 and 5")
    expected_layer_set_1 = _expected_layer_set_1_layers()
    expected_layer_set_5 = _expected_layer_set_5_layers()
    if layer_set_1.layers != expected_layer_set_1:
        raise RuntimeError(
            "LAYERSET1LAYERS did not match enabled mechanical layers: "
            f"expected {expected_layer_set_1!r}, read {layer_set_1.layers!r}"
        )
    if layer_set_5.layers != expected_layer_set_5:
        raise RuntimeError(
            "LAYERSET5LAYERS did not match enabled mechanical layers: "
            f"expected {expected_layer_set_5!r}, read {layer_set_5.layers!r}"
        )

    primitive_counts = _primitive_counts(parsed)
    if any(primitive_counts.values()):
        raise RuntimeError(
            f"Generated metadata-only PcbLib unexpectedly has primitives: "
            f"{primitive_counts!r}"
        )

    return {
        "pcblib": str(pcblib_path.relative_to(SAMPLE_DIR)),
        "footprints": parsed.footprint_names(),
        "registry_layer_count": len(registry),
        "registry": registry,
        "assignment_count": len(assignments),
        "assignments": assignments,
        "mechanical_kind_fields": mechanical_kind_fields,
        "pair_count": len(pairs),
        "component_layer_pairs": pairs,
        "route_tool_path_layer": route_tool_path_layer,
        "layer_set_1_layers": list(layer_set_1.layers),
        "layer_set_5_layers": list(layer_set_5.layers),
        "primitive_counts": primitive_counts,
        "unassigned_layers": ["MECHANICAL1", "MECHANICAL32"],
        "parsed_mapping_entry_count": len(parsed.mechanical_layer_kinds),
    }


def build_pcblib(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pcblib = AltiumPcbLib()
    pcblib.add_footprint(
        FOOTPRINT_NAME,
        height="18mil",
        description="PcbLib mechanical layer kind sample",
    )

    for layer, name, enabled in SAMPLE_LAYER_NAMES:
        pcblib.set_mechanical_layer(layer, name=name, enabled=enabled)
    for pair_index, (layer_1, layer_2) in enumerate(SAMPLE_COMPONENT_LAYER_PAIRS):
        pcblib.set_mechanical_layer_pair(layer_1, layer_2, pair_index=pair_index)
    for layer, kind in SAMPLE_ASSIGNMENTS:
        pcblib.set_mechanical_layer_kind(layer, kind)

    pcblib.save(output_path)
    return output_path


def main() -> None:
    output_path = build_pcblib()
    manifest = _readback_manifest(output_path)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
