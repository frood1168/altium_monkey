from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from altium_monkey import AltiumPcbDoc
from altium_monkey.altium_layer_stack_document import (
    AltiumLayerStackDocument,
    AltiumStackBranch,
    AltiumStackLayer,
    AltiumStackRegion,
    AltiumStackSubstack,
)
from altium_monkey.altium_resolved_layer_stack import ResolvedStackEnvelope

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
DEFAULT_INPUT_PCBDOC = (
    EXAMPLES_ROOT / "assets" / "pcbdoc" / "rigid_flex_topology_fixture.PcbDoc"
)
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_JSON = OUTPUT_DIR / "flex_topology_report.json"
OUTPUT_TEXT = OUTPUT_DIR / "flex_topology_report.txt"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _layer_summary(layer: AltiumStackLayer) -> dict[str, object]:
    return {
        "stack_index": layer.stack_index,
        "name": layer.display_name,
        "family": layer.family,
        "layer_id": layer.layer_id,
        "legacy_layer_id": layer.legacy_layer_id,
        "thickness_mils": (
            layer.copper_thickness_mils
            if layer.family == "copper"
            else layer.dielectric_height_mils
        ),
        "material": layer.dielectric_material,
        "dielectric_constant": layer.dielectric_constant,
        "is_stiffener": layer.is_stiffener,
        "coverlay_expansion": layer.coverlay_expansion,
    }


def _bend_line_summary(region: AltiumStackRegion) -> list[dict[str, object]]:
    return [
        {
            "angle_deg": line.angle_deg,
            "radius_mils": line.radius_mils,
            "fold_index": line.fold_index,
            "start_raw": [line.x1, line.y1],
            "end_raw": [line.x2, line.y2],
        }
        for line in region.bending_lines
    ]


def _envelope_summary(
    envelope: ResolvedStackEnvelope | None,
) -> dict[str, object] | None:
    if envelope is None:
        return None
    return envelope.to_debug_json()


def _substack_summary(
    document: AltiumLayerStackDocument,
    resolved,
    substack: AltiumStackSubstack,
) -> dict[str, object]:
    layers = document.layers_for_substack(substack.source_stackup_ref)
    regions = document.board_regions_for_layerstack_id(substack.source_stackup_ref)
    branches = document.branches_for_stack_ref(substack.source_stackup_ref)
    envelope = resolved.stack_envelope_for_substack(substack.source_stackup_ref)
    return {
        "source_stackup_ref": substack.source_stackup_ref,
        "name": substack.name,
        "is_flex": substack.is_flex,
        "field_family": substack.field_family,
        "raw_stackup_type": substack.raw_stackup_type,
        "enabled_layer_names": [layer.display_name for layer in layers],
        "region_names": [region.name for region in regions],
        "branch_names": [branch.name for branch in branches],
        "stack_envelope": _envelope_summary(envelope),
    }


def _region_summary(
    document: AltiumLayerStackDocument,
    resolved,
    region: AltiumStackRegion,
) -> dict[str, object]:
    substack = document.substack_by_source_ref(region.layerstack_id)
    layers = document.layers_for_board_region(region)
    envelope = resolved.stack_envelope_for_board_region(region)
    return {
        "name": region.name,
        "layerstack_id": region.layerstack_id,
        "substack_name": substack.name if substack is not None else "",
        "is_flex": substack.is_flex if substack is not None else None,
        "locked_3d": region.locked_3d,
        "enabled_layer_names": [layer.display_name for layer in layers],
        "bend_line_count": region.bending_line_count,
        "bend_lines": _bend_line_summary(region),
        "outline_vertex_count": len(region.outline_vertices),
        "hole_count": len(region.hole_vertices),
        "stack_envelope": _envelope_summary(envelope),
    }


def _branch_stack_name(
    document: AltiumLayerStackDocument,
    stack_ref: str,
) -> str:
    substack = document.substack_by_source_ref(stack_ref)
    if substack is not None:
        return substack.name
    physical_stack = document.physical_stack_by_ref(stack_ref)
    if physical_stack is not None:
        return physical_stack.display_name
    return ""


def _branch_summary(
    document: AltiumLayerStackDocument,
    branch: AltiumStackBranch,
) -> dict[str, object]:
    return {
        "source_branch_id": branch.source_branch_id,
        "name": branch.name,
        "description": branch.description,
        "parent_branch_id": branch.parent_branch_id,
        "root_stack_ref": branch.root_stack_ref,
        "root_stack_name": _branch_stack_name(document, branch.root_stack_ref),
        "sections": [
            {
                "source_section_id": section.source_section_id,
                "name": section.name,
                "parent_section_id": section.parent_section_id,
                "stacks": [
                    {
                        "source_stack_ref": stack.source_stack_ref,
                        "stack_name": _branch_stack_name(
                            document,
                            stack.source_stack_ref,
                        ),
                        "description": stack.description,
                        "source": stack.source,
                        "material_usage": stack.material_usage,
                        "parent_layer_id": stack.parent_layer_id,
                        "source_layer_id": stack.source_layer_id,
                        "intrusions": {
                            "is_left_linked": stack.is_left_intrusions_linked,
                            "left_bottom": stack.intrusion_left_bottom,
                            "left_top": stack.intrusion_left_top,
                            "is_right_linked": stack.is_right_intrusions_linked,
                            "right_bottom": stack.intrusion_right_bottom,
                            "right_top": stack.intrusion_right_top,
                        },
                    }
                    for stack in section.stacks
                ],
            }
            for section in branch.sections
        ],
    }


def _query_examples(document: AltiumLayerStackDocument) -> dict[str, object]:
    flex_substacks = tuple(
        substack for substack in document.substacks if substack.is_flex is True
    )
    flex_region_names = {
        substack.source_stackup_ref: [
            region.name
            for region in document.board_regions_for_layerstack_id(
                substack.source_stackup_ref
            )
        ]
        for substack in flex_substacks
    }
    region_layer_names = {
        region.name: [
            layer.display_name for layer in document.layers_for_board_region(region)
        ]
        for region in document.board_regions
    }
    return {
        "stable_join_key": "AltiumStackSubstack.source_stackup_ref == AltiumStackRegion.layerstack_id",
        "name_lookup_warning": "Substack and region names are display labels; use ids for joins.",
        "flex_substack_ids": [
            substack.source_stackup_ref for substack in flex_substacks
        ],
        "regions_by_flex_substack_id": flex_region_names,
        "layers_by_region_name": region_layer_names,
        "research_flex_name_matches": [
            substack.source_stackup_ref
            for substack in document.substacks_by_name("Research Flex")
        ],
    }


def _build_report(
    input_path: Path, *, uses_packaged_fixture: bool
) -> dict[str, object]:
    pcbdoc = AltiumPcbDoc.from_file(input_path)
    document = AltiumLayerStackDocument.from_pcbdoc(pcbdoc)
    resolved = document.to_resolved_layer_stack()
    flex_substack_count = sum(1 for substack in document.substacks if substack.is_flex)
    bend_line_count = sum(
        region.bending_line_count for region in document.board_regions
    )

    return {
        "input_pcbdoc": _relative_to_examples(input_path),
        "uses_packaged_fixture": uses_packaged_fixture,
        "summary": {
            "rigid_flex_mode": document.rigid_flex_mode,
            "active_stack_ref": document.active_stack_ref,
            "physical_stack_count": len(document.physical_stacks),
            "substack_count": len(document.substacks),
            "flex_substack_count": flex_substack_count,
            "board_region_count": len(document.board_regions),
            "bend_line_count": bend_line_count,
            "branch_count": len(document.branches),
            "layer_pair_count": len(document.layer_pairs),
            "resolved_substack_count": len(resolved.substacks),
            "resolved_region_context_count": len(resolved.board_region_contexts),
        },
        "physical_stacks": [
            {
                "stack_ref": stack.stack_ref,
                "name": stack.display_name,
                "source_family": stack.source_family,
                "is_flex": stack.is_flex,
                "layers": [_layer_summary(layer) for layer in stack.layers],
            }
            for stack in document.physical_stacks
        ],
        "substacks": [
            _substack_summary(document, resolved, substack)
            for substack in document.substacks
        ],
        "board_regions": [
            _region_summary(document, resolved, region)
            for region in document.board_regions
        ],
        "branches": [_branch_summary(document, branch) for branch in document.branches],
        "layer_pairs": [pair.to_debug_json() for pair in document.layer_pairs],
        "query_examples": _query_examples(document),
    }


def _report_lines(report: dict[str, object]) -> list[str]:
    summary = report["summary"]
    substacks = report["substacks"]
    board_regions = report["board_regions"]
    branches = report["branches"]
    if not isinstance(summary, dict):
        raise TypeError("summary must be a dict")
    if not isinstance(substacks, list):
        raise TypeError("substacks must be a list")
    if not isinstance(board_regions, list):
        raise TypeError("board_regions must be a list")
    if not isinstance(branches, list):
        raise TypeError("branches must be a list")

    lines = [
        f"Input PCB: {report['input_pcbdoc']}",
        f"Rigid-flex mode: {summary['rigid_flex_mode']}",
        (
            "Topology counts: "
            f"{summary['substack_count']} substacks, "
            f"{summary['board_region_count']} board regions, "
            f"{summary['bend_line_count']} bend lines, "
            f"{summary['branch_count']} branches"
        ),
        "",
        "Substacks",
    ]
    for item in substacks:
        if not isinstance(item, dict):
            continue
        layer_names = ", ".join(str(name) for name in item["enabled_layer_names"])
        region_names = ", ".join(str(name) for name in item["region_names"]) or "-"
        kind = "flex" if item["is_flex"] else "rigid"
        lines.append(f"  - {item['name']} ({kind})")
        lines.append(f"    id: {item['source_stackup_ref']}")
        lines.append(f"    layers: {layer_names}")
        lines.append(f"    regions: {region_names}")

    lines.extend(["", "Board Regions"])
    for item in board_regions:
        if not isinstance(item, dict):
            continue
        layer_names = ", ".join(str(name) for name in item["enabled_layer_names"])
        bend_radii = [
            line["radius_mils"]
            for line in item["bend_lines"]
            if isinstance(line, dict) and line["radius_mils"] is not None
        ]
        radius_text = ", ".join(f"{float(radius):g} mil" for radius in bend_radii)
        if not radius_text:
            radius_text = "-"
        lines.append(
            f"  - {item['name']} -> {item['substack_name']} "
            f"({item['bend_line_count']} bends)"
        )
        lines.append(f"    layers: {layer_names}")
        lines.append(f"    bend radii: {radius_text}")

    lines.extend(["", "Substack Local Z Envelopes"])
    for item in substacks:
        if not isinstance(item, dict):
            continue
        envelope = item.get("stack_envelope")
        if not isinstance(envelope, dict):
            continue
        layers = envelope.get("layers")
        layer_count = len(layers) if isinstance(layers, list) else 0
        kind = "flex" if item["is_flex"] else "rigid"
        lines.append(
            f"  - {item['name']} ({kind}): "
            f"{float(envelope['total_thickness_mils']):g} mil total, "
            f"z0={envelope['z_zero']}, rows={layer_count}"
        )
        lines.append(
            f"    top={float(envelope['top_z_mils']):g} mil, "
            f"bottom={float(envelope['bottom_z_mils']):g} mil"
        )

    lines.extend(["", "Branches"])
    if not branches:
        lines.append("  (none in this standard rigid-flex fixture)")
    for branch in branches:
        if isinstance(branch, dict):
            lines.append(
                f"  - {branch['name']} root={branch['root_stack_name']} "
                f"parent={branch['parent_branch_id'] or '-'}"
            )
    return lines


def write_flex_topology_report(
    input_path: Path | None = None,
    *,
    output_json: Path = OUTPUT_JSON,
    output_text: Path = OUTPUT_TEXT,
) -> tuple[Path, Path]:
    uses_packaged_fixture = input_path is None
    resolved_input_path = DEFAULT_INPUT_PCBDOC if input_path is None else input_path
    output_json.parent.mkdir(parents=True, exist_ok=True)

    report = _build_report(
        resolved_input_path,
        uses_packaged_fixture=uses_packaged_fixture,
    )
    output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_text.write_text("\n".join(_report_lines(report)) + "\n", encoding="utf-8")
    return output_json, output_text


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Inspect a rigid-flex PcbDoc and write a topology report.")
    )
    parser.add_argument(
        "input_pcbdoc",
        nargs="?",
        type=Path,
        help="Optional input PcbDoc. If omitted, this sample inspects the packaged rigid-flex fixture.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=OUTPUT_JSON,
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-text",
        type=Path,
        default=OUTPUT_TEXT,
        help="Output text report path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_json, output_text = write_flex_topology_report(
        args.input_pcbdoc,
        output_json=args.output_json,
        output_text=args.output_text,
    )
    report = json.loads(output_json.read_text(encoding="utf-8"))
    summary = report["summary"]
    print(f"Input PCB: {report['input_pcbdoc']}")
    print(f"Rigid-flex mode: {summary['rigid_flex_mode']}")
    print(f"Substacks: {summary['substack_count']}")
    print(f"Board regions: {summary['board_region_count']}")
    print(f"Bend lines: {summary['bend_line_count']}")
    print(f"Branches: {summary['branch_count']}")
    print(f"Wrote {output_json}")
    print(f"Wrote {output_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
