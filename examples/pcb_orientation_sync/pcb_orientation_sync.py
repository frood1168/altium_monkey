"""Rotate PCB components to match schematic orientation changes.

Workflow:
  1. Run pcb_orientation_snapshot.py BEFORE making schematic changes → before.json
  2. Edit schematic orientations (normalize resistors, caps, inductors to 0°/90°)
  3. Run this tool with the before-snapshot and the updated project:
       pcb_orientation_sync.py before.json PROJECT.PrjPcb

The tool diffs the before-snapshot schematic orientations against the current
schematic, computes per-component rotation deltas, and rotates each affected
PCB component (plus its designator/comment overlay text) by that delta.

A JSON report is written alongside the modified PcbDoc.

Usage:
    uv run python examples/pcb_orientation_sync/pcb_orientation_sync.py \\
        PROJECT.PrjPcb --before BEFORE_SNAPSHOT.json [--output-pcb OUTPUT.PcbDoc]

    # Project only — auto-finds the most recent snapshot in output/:
    uv run python examples/pcb_orientation_sync/pcb_orientation_sync.py PROJECT.PrjPcb

    # Defaults (uses output/snapshot.json and rt_super_c1 project):
    uv run python examples/pcb_orientation_sync/pcb_orientation_sync.py
"""

from __future__ import annotations

import argparse
import json
import shutil
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
# Rotation helpers
# ---------------------------------------------------------------------------

def _format_pcb_rotation(degrees: float) -> str:
    """Format a rotation value as Altium's legacy scientific-notation string."""
    text = f"{float(degrees): .14E}"
    mantissa, exponent = text.split("E", 1)
    return f"{mantissa}E{int(exponent):+05d}"


def _normalize_deg(degrees: float) -> float:
    """Normalize to [0, 360)."""
    return float(degrees % 360)


def _rotation_delta(before_deg: float, after_deg: float) -> float:
    """Compute the smallest equivalent positive rotation delta."""
    return _normalize_deg(after_deg - before_deg)


# ---------------------------------------------------------------------------
# Current-schematic orientation reader
# ---------------------------------------------------------------------------

def _sch_designator(component: object) -> str:
    for p in getattr(component, "parameters", []):
        if isinstance(p, AltiumSchDesignator):
            return p.text or ""
    return ""


def read_current_sch_orientations(schdoc_paths: list[Path]) -> dict[str, float]:
    """Return {designator: orientation_degrees} from the current schematic."""
    result: dict[str, float] = {}
    for path in schdoc_paths:
        schdoc = AltiumSchDoc(path)
        for comp in schdoc.components:
            desig = _sch_designator(comp)
            if desig:
                result[desig] = float(int(comp.orientation) * 90)
    return result


# ---------------------------------------------------------------------------
# PCB rotation applicator
# ---------------------------------------------------------------------------

def _rotate_component(component: object, delta_deg: float) -> None:
    """Rotate a PCB component in-place by delta_deg degrees."""
    current = float(component.get_rotation_degrees())
    new_rot = _normalize_deg(current + delta_deg)
    component.raw_record["ROTATION"] = _format_pcb_rotation(new_rot)


def _rotate_text(text: object, delta_deg: float) -> None:
    """Rotate a PCB text overlay by delta_deg degrees."""
    current = float(getattr(text, "rotation", 0.0))
    text.rotation = _normalize_deg(current + delta_deg)


def apply_rotation_deltas(
    pcbdoc_path: Path,
    output_path: Path,
    deltas: dict[str, float],
) -> dict[str, object]:
    """Apply per-designator rotation deltas to a PcbDoc and save.

    Returns a dict of {designator: {delta, before_rot, after_rot}} for
    every component that was changed.
    """
    shutil.copy2(pcbdoc_path, output_path)
    pcb = AltiumPcbDoc.from_file(output_path)
    comps = list(pcb.components)
    texts = list(pcb.texts)

    # Build lookup: component_index -> {desig_text, comment_text}
    desig_texts: dict[int, object] = {}
    comment_texts: dict[int, object] = {}
    for t in texts:
        ci = t.component_index
        if ci is None:
            continue
        if getattr(t, "is_designator", False) and ci not in desig_texts:
            desig_texts[ci] = t
        elif getattr(t, "is_comment", False) and ci not in comment_texts:
            comment_texts[ci] = t

    applied: dict[str, dict] = {}
    skipped_not_found: list[str] = []

    for desig, delta in sorted(deltas.items()):
        if delta == 0.0:
            continue

        idx = next(
            (i for i, c in enumerate(comps) if c.designator == desig), None
        )
        if idx is None:
            skipped_not_found.append(desig)
            continue

        comp = comps[idx]
        before_rot = comp.get_rotation_degrees()
        _rotate_component(comp, delta)
        after_rot = _normalize_deg(before_rot + delta)

        if idx in desig_texts:
            _rotate_text(desig_texts[idx], delta)
        if idx in comment_texts:
            _rotate_text(comment_texts[idx], delta)

        applied[desig] = {
            "delta_degrees": delta,
            "pcb_rotation_before": round(before_rot, 4),
            "pcb_rotation_after": round(after_rot, 4),
        }

    if applied:
        # Force component stream re-serialization
        pcb._union_authoring_dirty = True

    pcb.save(output_path)
    return {
        "changed": applied,
        "skipped_not_on_pcb": skipped_not_found,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rotate PCB components to match schematic orientation changes. "
            "Compares orientation in the before-snapshot against the current "
            "schematic and applies matching rotation deltas to the PCB."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        metavar="PROJECT.PrjPcb",
        help=(
            "Path to the updated .PrjPcb (reads current SchDocs + PcbDoc). "
            "Defaults to the bundled rt_super_c1 example project."
        ),
    )
    parser.add_argument(
        "--before",
        metavar="BEFORE_SNAPSHOT.json",
        dest="before_snapshot",
        help=(
            "JSON snapshot taken before schematic changes "
            "(from pcb_orientation_snapshot.py). "
            "Defaults to the most recent snapshot*.json in output/."
        ),
    )
    parser.add_argument(
        "--output-pcb",
        metavar="OUTPUT.PcbDoc",
        help="Where to write the modified PcbDoc. Defaults to output/<name>_synced.PcbDoc.",
    )
    return parser.parse_args()


def _find_latest_snapshot(output_dir: Path) -> Path | None:
    snapshots = sorted(output_dir.glob("snapshot*.json"), reverse=True)
    return snapshots[0] if snapshots else None


def main() -> None:
    args = _parse_args()

    # --- Before snapshot ---
    if args.before_snapshot:
        before_path = Path(args.before_snapshot).resolve()
    else:
        before_path = _find_latest_snapshot(SAMPLE_DIR / "output")
        if before_path is None:
            raise FileNotFoundError(
                "No before-snapshot found in output/. "
                "Run pcb_orientation_snapshot.py first."
            )

    before = json.loads(before_path.read_text(encoding="utf-8-sig"))
    before_sch: dict[str, float] = {
        d: float(info["orientation_degrees"])
        for d, info in before.get("schematic", {}).items()
    }

    # --- Current project ---
    if args.project:
        project_path = Path(args.project).resolve()
    else:
        project_path = _DEFAULT_PRJPCB

    project = AltiumPrjPcb(project_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    pcb_paths = project.get_pcbdoc_paths()

    if not schdoc_paths:
        raise RuntimeError(f"No SchDoc files found in project: {project_path}")
    if not pcb_paths:
        raise RuntimeError(f"No PcbDoc files found in project: {project_path}")

    pcbdoc_path = pcb_paths[0]

    # --- Compute deltas ---
    after_sch = read_current_sch_orientations(schdoc_paths)

    deltas: dict[str, float] = {}
    no_before: list[str] = []
    for desig, after_deg in after_sch.items():
        if desig not in before_sch:
            no_before.append(desig)
            continue
        delta = _rotation_delta(before_sch[desig], after_deg)
        deltas[desig] = delta

    changed_count = sum(1 for d in deltas.values() if d != 0.0)

    # --- Output path ---
    if args.output_pcb:
        output_pcb = Path(args.output_pcb).resolve()
    else:
        output_dir = SAMPLE_DIR / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_pcb = output_dir / f"{pcbdoc_path.stem}_synced{pcbdoc_path.suffix}"

    # --- Apply ---
    result = apply_rotation_deltas(pcbdoc_path, output_pcb, deltas)

    # --- Report ---
    report = {
        "before_snapshot": str(before_path),
        "source_project": str(project_path),
        "source_pcbdoc": str(pcbdoc_path),
        "output_pcbdoc": str(output_pcb),
        "sch_components_before": len(before_sch),
        "sch_components_after": len(after_sch),
        "components_with_delta": changed_count,
        "components_rotated": len(result["changed"]),
        "components_not_on_pcb": len(result["skipped_not_on_pcb"]),
        "components_new_in_sch": len(no_before),
        "rotation_changes": result["changed"],
        "skipped_not_on_pcb": result["skipped_not_on_pcb"],
        "new_in_sch_no_before": no_before,
    }

    report_path = output_pcb.with_suffix(".sync_report.json")
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Before snapshot:     {before_path.name}  ({len(before_sch)} SCH components)")
    print(f"Current project:     {project_path.name}")
    print(f"Components compared: {len(after_sch)}")
    print(f"  With rotation delta: {changed_count}")
    print(f"  Rotated on PCB:      {len(result['changed'])}")
    if result["skipped_not_on_pcb"]:
        print(f"  Not on PCB:          {len(result['skipped_not_on_pcb'])} "
              f"({', '.join(result['skipped_not_on_pcb'][:5])}{'...' if len(result['skipped_not_on_pcb'])>5 else ''})")
    if no_before:
        print(f"  New (no before):     {len(no_before)}")
    print(f"Wrote PCB:           {output_pcb}")
    print(f"Wrote report:        {report_path.name}")


if __name__ == "__main__":
    main()
