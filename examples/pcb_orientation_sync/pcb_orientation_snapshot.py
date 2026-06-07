"""Capture a snapshot of schematic and PCB component orientations to JSON.

Run this BEFORE making schematic orientation changes to record the baseline
state. After normalizing component orientations in the schematic, use
pcb_orientation_sync.py with the before-snapshot to rotate matching PCB
components by the same delta.

Captures for every component:
  Schematic: designator, lib_reference, orientation (degrees), is_mirrored
  PCB:       location (x/y mils), rotation (degrees), layer,
             designator text location / rotation / font / size

Usage:
    # Snapshot using project file (reads all SchDocs + PcbDoc):
    uv run python examples/pcb_orientation_sync/pcb_orientation_snapshot.py [PROJECT.PrjPcb]

    # Snapshot using separate SCH + PCB:
    uv run python examples/pcb_orientation_sync/pcb_orientation_snapshot.py \\
        --schdoc MY.SchDoc --pcbdoc MY.PcbDoc

    # Defaults to the bundled rt_super_c1 example project.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from altium_monkey import (
    AltiumPcbDoc,
    AltiumSchDesignator,
    AltiumSchDoc,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
_DEFAULT_PRJPCB = ASSETS_DIR / "projects" / "rt_super_c1" / "RT_SUPER_C1.PrjPcb"


# ---------------------------------------------------------------------------
# Schematic snapshot
# ---------------------------------------------------------------------------

def _sch_designator(component: object) -> str:
    for p in getattr(component, "parameters", []):
        if isinstance(p, AltiumSchDesignator):
            return p.text or ""
    return ""


def snapshot_schematic(schdoc_paths: list[Path]) -> dict[str, dict]:
    """Return {designator: {lib_reference, orientation_degrees, is_mirrored, source}}."""
    result: dict[str, dict] = {}
    for path in schdoc_paths:
        schdoc = AltiumSchDoc(path)
        for comp in schdoc.components:
            desig = _sch_designator(comp)
            if not desig:
                continue
            lib_ref = comp.lib_reference or ""
            orientation_index = int(comp.orientation)
            result[desig] = {
                "lib_reference": lib_ref,
                "orientation_index": orientation_index,
                "orientation_degrees": orientation_index * 90,
                "is_mirrored": bool(comp.is_mirrored),
                "source_schdoc": path.name,
            }
    return result


# ---------------------------------------------------------------------------
# PCB snapshot
# ---------------------------------------------------------------------------

def _text_snapshot(text: object) -> dict:
    return {
        "x_mils": round(float(text.x_mils), 4),
        "y_mils": round(float(text.y_mils), 4),
        "rotation": round(float(text.rotation), 4),
        "height_mils": round(float(text.height_mils), 4),
        "font_type": int(getattr(text, "font_type", 0)),
        "font_name": str(getattr(text, "font_name", "") or ""),
        "is_bold": bool(getattr(text, "is_bold", False)),
        "is_italic": bool(getattr(text, "is_italic", False)),
        "autoposition": int(getattr(text, "autoposition", 0) or 0),
    }


def snapshot_pcb(pcbdoc_path: Path) -> dict[str, dict]:
    """Return {designator: {x_mils, y_mils, rotation_degrees, layer, designator_text, comment_text}}."""
    pcb = AltiumPcbDoc.from_file(pcbdoc_path)
    comps = list(pcb.components)
    texts = list(pcb.texts)

    # Build lookup: component_index -> {designator_text, comment_text}
    desig_text: dict[int, object] = {}
    comment_text: dict[int, object] = {}
    for t in texts:
        ci = t.component_index
        if ci is None:
            continue
        if getattr(t, "is_designator", False) and ci not in desig_text:
            desig_text[ci] = t
        elif getattr(t, "is_comment", False) and ci not in comment_text:
            comment_text[ci] = t

    result: dict[str, dict] = {}
    for idx, comp in enumerate(comps):
        desig = comp.designator
        if not desig:
            continue
        entry: dict = {
            "footprint": comp.footprint,
            "layer": comp.get_layer_normalized(),
            "x_mils": round(comp.get_x_mils(), 4),
            "y_mils": round(comp.get_y_mils(), 4),
            "rotation_degrees": round(comp.get_rotation_degrees(), 4),
        }
        if idx in desig_text:
            entry["designator_text"] = _text_snapshot(desig_text[idx])
        if idx in comment_text:
            entry["comment_text"] = _text_snapshot(comment_text[idx])
        result[desig] = entry

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Snapshot schematic and PCB component orientations to a JSON file. "
            "Run before and after making schematic changes to enable "
            "pcb_orientation_sync.py to rotate PCB components by matching deltas."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        metavar="PROJECT.PrjPcb",
        help=(
            "Path to the .PrjPcb file. Reads all linked SchDocs and PcbDoc. "
            "Defaults to the bundled rt_super_c1 example project."
        ),
    )
    parser.add_argument(
        "--schdoc",
        metavar="SCHDOC",
        action="append",
        default=[],
        help="Explicit SchDoc path (may be repeated). Overrides project SchDocs.",
    )
    parser.add_argument(
        "--pcbdoc",
        metavar="PCBDOC",
        help="Explicit PcbDoc path. Overrides project PcbDoc.",
    )
    parser.add_argument(
        "--output",
        metavar="SNAPSHOT.json",
        help=(
            "Output JSON path. "
            "Defaults to output/snapshot_<timestamp>.json next to this script."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Resolve SchDoc + PcbDoc paths
    schdoc_paths: list[Path] = [Path(p).resolve() for p in args.schdoc]
    pcbdoc_path: Path | None = Path(args.pcbdoc).resolve() if args.pcbdoc else None
    project_path: Path | None = None

    if not schdoc_paths or pcbdoc_path is None:
        if args.project:
            project_path = Path(args.project).resolve()
        else:
            project_path = _DEFAULT_PRJPCB

        project = AltiumPrjPcb(project_path)
        if not schdoc_paths:
            schdoc_paths = project.get_reachable_schdoc_paths()
        if pcbdoc_path is None:
            pcb_paths = project.get_pcbdoc_paths()
            pcbdoc_path = pcb_paths[0] if pcb_paths else None

    if not schdoc_paths:
        raise RuntimeError("No SchDoc files found.")
    if pcbdoc_path is None:
        raise RuntimeError("No PcbDoc file found.")

    # Build snapshot
    sch = snapshot_schematic(schdoc_paths)
    pcb = snapshot_pcb(pcbdoc_path)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot = {
        "timestamp": timestamp,
        "source_project": str(project_path) if project_path else None,
        "source_schdocs": [str(p) for p in schdoc_paths],
        "source_pcbdoc": str(pcbdoc_path),
        "schematic_component_count": len(sch),
        "pcb_component_count": len(pcb),
        "schematic": dict(sorted(sch.items())),
        "pcb": dict(sorted(pcb.items())),
    }

    # Output path
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_dir = SAMPLE_DIR / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"snapshot_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    sch_only = len(set(sch) - set(pcb))
    pcb_only = len(set(pcb) - set(sch))
    both = len(set(sch) & set(pcb))

    print(f"Source project: {project_path or '(explicit files)'}")
    print(f"SchDocs: {len(schdoc_paths)}  SCH components: {len(sch)}")
    print(f"PCB components: {len(pcb)}")
    print(f"Matched (sch+pcb): {both}  SCH-only: {sch_only}  PCB-only: {pcb_only}")
    print(f"Wrote snapshot: {output_path}")


if __name__ == "__main__":
    main()
