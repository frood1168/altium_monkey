from __future__ import annotations

import json
import re
from pathlib import Path

from altium_monkey import (
    AltiumPcbDoc,
    MechanicalLayerKind,
)
from altium_monkey.altium_pcb_layer_kind_mapping import (
    mechanical_layer_kind_to_data_token,
)

SAMPLE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PATH = OUTPUT_DIR / "pcbdoc_create_mechanical_layer_kinds.PcbDoc"
MANIFEST_PATH = OUTPUT_DIR / "pcbdoc_create_mechanical_layer_kinds.json"

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


def _mechanical_layer_v7_id(layer: str) -> int:
    return 0x01020000 + _mechanical_layer_number(layer)


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


def _split_layer_set(value: object) -> tuple[str, ...]:
    return tuple(
        part.strip() for part in str(value or "").strip().split(",") if part.strip()
    )


def _primitive_counts(parsed: AltiumPcbDoc) -> dict[str, int]:
    return {
        "components": len(getattr(parsed, "components", ())),
        "pads": len(getattr(parsed, "pads", ())),
        "vias": len(getattr(parsed, "vias", ())),
        "tracks": len(getattr(parsed, "tracks", ())),
        "arcs": len(getattr(parsed, "arcs", ())),
        "fills": len(getattr(parsed, "fills", ())),
        "regions": len(getattr(parsed, "regions", ())),
        "shapebased_regions": len(getattr(parsed, "shapebased_regions", ())),
        "texts": len(getattr(parsed, "texts", ())),
        "component_bodies": len(getattr(parsed, "component_bodies", ())),
    }


def _indexed_raw_layer_field(
    raw_board: dict[str, object],
    prefix_pattern: str,
    layer_id: int,
    field_name: str,
) -> str | None:
    groups: dict[int, dict[str, str]] = {}
    pattern = re.compile(prefix_pattern, re.IGNORECASE)
    for key, value in raw_board.items():
        match = pattern.match(str(key))
        if match is None:
            continue
        groups.setdefault(int(match.group(1)), {})[match.group(2).upper()] = str(value)
    for values in groups.values():
        if values.get("LAYERID") == str(int(layer_id)):
            return values.get(field_name.upper())
    return None


def _v7_raw_layer_index(
    raw_board: dict[str, object],
    layer_id: int,
) -> int | None:
    for key, value in raw_board.items():
        match = re.fullmatch(r"LAYERV7_(\d+)LAYERID", str(key), re.IGNORECASE)
        if match is None or str(value) != str(int(layer_id)):
            continue
        return int(match.group(1))
    return None


def _mechanical_kind_fields(
    raw_board: dict[str, object],
    layer: str,
) -> dict[str, str | None]:
    mechanical_number = _mechanical_layer_number(layer)
    v7_layer_id = _mechanical_layer_v7_id(layer)
    fields: dict[str, str | None] = {}
    if mechanical_number <= 16:
        legacy_value = raw_board.get(f"LAYER{56 + mechanical_number}MECHKIND")
        fields["legacy"] = str(legacy_value) if legacy_value else None
    else:
        v7_index = _v7_raw_layer_index(raw_board, v7_layer_id)
        v7_value = (
            None if v7_index is None else raw_board.get(f"LAYERV7_{v7_index}MECHKIND")
        )
        fields["v7"] = str(v7_value) if v7_value else None
    fields["layer_v8"] = _indexed_raw_layer_field(
        raw_board,
        r"^LAYER_V8_(\d+)(.+)$",
        v7_layer_id,
        "MECHKIND",
    )
    fields["v9_cache"] = _indexed_raw_layer_field(
        raw_board,
        r"^V9_CACHE_LAYER(\d+)_(.+)$",
        v7_layer_id,
        "MECHKIND",
    )
    return fields


def _readback_manifest(pcbdoc_path: Path) -> dict[str, object]:
    parsed = AltiumPcbDoc.from_file(pcbdoc_path)
    if parsed.board is None:
        raise RuntimeError("Generated PcbDoc did not contain Board6/Data")

    enabled_v7_ids = set(parsed.board.enabled_mechanical_v7_save_ids)
    registry = []
    for layer, expected_name, expected_enabled in SAMPLE_LAYER_NAMES:
        v7_id = _mechanical_layer_v7_id(layer)
        actual_name = parsed.board.v9_layer_cache.get(v7_id)
        actual_enabled = v7_id in enabled_v7_ids
        if actual_name != expected_name:
            raise RuntimeError(
                f"{layer} expected name {expected_name!r}, read {actual_name!r}"
            )
        if actual_enabled != expected_enabled:
            raise RuntimeError(
                f"{layer} expected enabled={expected_enabled}, "
                f"read enabled={actual_enabled}"
            )
        registry.append(
            {
                "layer": layer,
                "name": expected_name,
                "enabled": expected_enabled,
            }
        )

    raw_board = parsed.board.raw_record or {}
    assignments = []
    mechanical_kind_fields = []
    for layer, expected_kind in SAMPLE_ASSIGNMENTS:
        actual_kind = parsed.get_mechanical_layer_kind(layer)
        if actual_kind != expected_kind:
            raise RuntimeError(
                f"{layer} expected {expected_kind.name}, "
                f"read {actual_kind.name if actual_kind is not None else None}"
            )
        expected_token = mechanical_layer_kind_to_data_token(expected_kind)
        actual_fields = _mechanical_kind_fields(raw_board, layer)
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

    pairs = []
    for pair_index, (layer_1, layer_2) in enumerate(SAMPLE_COMPONENT_LAYER_PAIRS):
        actual_layer_1 = str(raw_board.get(f"MECHPAIR{pair_index}L1", "")).strip()
        actual_layer_2 = str(raw_board.get(f"MECHPAIR{pair_index}L2", "")).strip()
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

    route_tool_path_layer = str(raw_board.get("ROUTETOOLPATHLAYER", "")).strip()
    if route_tool_path_layer != ROUTE_TOOL_PATH_LAYER:
        raise RuntimeError(
            f"ROUTETOOLPATHLAYER expected {ROUTE_TOOL_PATH_LAYER}, "
            f"read {route_tool_path_layer!r}"
        )

    layer_set_1 = _split_layer_set(raw_board.get("LAYERSET1LAYERS"))
    expected_layer_set_1 = _expected_layer_set_1_layers()
    if layer_set_1 != expected_layer_set_1:
        raise RuntimeError(
            "LAYERSET1LAYERS did not match enabled mechanical layers: "
            f"expected {expected_layer_set_1!r}, read {layer_set_1!r}"
        )

    layer_set_5 = _split_layer_set(raw_board.get("LAYERSET5LAYERS"))
    expected_layer_set_5 = _expected_layer_set_5_layers()
    if layer_set_5 != expected_layer_set_5:
        raise RuntimeError(
            "LAYERSET5LAYERS did not match enabled mechanical layers: "
            f"expected {expected_layer_set_5!r}, read {layer_set_5!r}"
        )

    primitive_counts = _primitive_counts(parsed)
    if any(primitive_counts.values()):
        raise RuntimeError(
            f"Generated metadata-only PcbDoc unexpectedly has primitives: "
            f"{primitive_counts!r}"
        )

    return {
        "pcbdoc": str(pcbdoc_path.relative_to(SAMPLE_DIR)),
        "registry_layer_count": len(registry),
        "registry": registry,
        "assignment_count": len(assignments),
        "assignments": assignments,
        "mechanical_kind_fields": mechanical_kind_fields,
        "pair_count": len(pairs),
        "component_layer_pairs": pairs,
        "route_tool_path_layer": route_tool_path_layer,
        "layer_set_1_layers": list(layer_set_1),
        "layer_set_5_layers": list(layer_set_5),
        "primitive_counts": primitive_counts,
        "unassigned_layers": ["MECHANICAL1", "MECHANICAL32"],
        "parsed_mapping_entry_count": len(parsed.mechanical_layer_kinds),
    }


def build_pcbdoc(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pcbdoc = AltiumPcbDoc()
    for layer, name, enabled in SAMPLE_LAYER_NAMES:
        pcbdoc.set_mechanical_layer(layer, name=name, enabled=enabled)
    for pair_index, (layer_1, layer_2) in enumerate(SAMPLE_COMPONENT_LAYER_PAIRS):
        pcbdoc.set_mechanical_layer_pair(layer_1, layer_2, pair_index=pair_index)
    for layer, kind in SAMPLE_ASSIGNMENTS:
        pcbdoc.set_mechanical_layer_kind(layer, kind)

    pcbdoc.save(output_path)
    return output_path


def main() -> None:
    output_path = build_pcbdoc()
    manifest = _readback_manifest(output_path)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
