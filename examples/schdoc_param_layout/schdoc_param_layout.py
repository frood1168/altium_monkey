from __future__ import annotations

import argparse
import csv
import datetime
import json
import shutil
import sys
import tomllib
from collections import Counter
from filecmp import cmp as files_equal
from pathlib import Path

from altium_monkey import (
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchParameter,
    AltiumSchPin,
    ComponentKind,
    CoordPoint,
    TextJustification,
    TextOrientation,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
_DEFAULT_PRJPCB = ASSETS_DIR / "projects" / "hydroscope" / "Hydroscope.PrjPcb"
_DEFAULT_LAYOUT_TOML = SAMPLE_DIR / "param_layout.toml"

_ROT_KEY = {0: "DEG_0", 1: "DEG_90", 2: "DEG_180", 3: "DEG_270"}
_LAYOUT_OPT_PARAM = "sch_layout_opt"
_LAYOUT_DNP_PARAM = "sch_layout_dnp"
_PINS_KEY = "__pins__"

# Value-type parameters to swap out when sch_layout_dnp = "DNP", in priority order.
# The first one that is currently visible is the one that gets replaced.
_DNP_SWAP_PARAM_NAMES: tuple[str, ...] = (
    "Resistance", "Capacitance", "Inductance", "PartNumber", "Value",
)

# Win32 BGR color for the DNP label: #FF0000 red → R=0xFF, G=0, B=0 → 0xFF
_DNP_LABEL_COLOR: int = 0xFF

_ORIENT_MAP = {"DEGREES_0": 0, "DEGREES_90": 1, "DEGREES_180": 2, "DEGREES_270": 3}
_JUST_MAP = {
    "BOTTOM_LEFT": 0,  "BOTTOM_CENTER": 1, "BOTTOM_RIGHT": 2,
    "CENTER_LEFT": 3,  "CENTER_CENTER": 4, "CENTER_RIGHT": 5,
    "TOP_LEFT":    6,  "TOP_CENTER":    7, "TOP_RIGHT":    8,
}


_DNP_PARAM_NAMES: frozenset[str] = frozenset({
    "value", "resistance", "inductance", "capacitance",
    "voltage", "current", "power", "tolerance",
})


def _is_dnp(component: object) -> bool:
    for param in getattr(component, "parameters", []):
        if not isinstance(param, AltiumSchParameter):
            continue
        # The sch_layout_dnp control parameter is the explicit DNP marker.
        if param.name == _LAYOUT_DNP_PARAM:
            if (param.text or "").strip().upper() == "DNP":
                return True
            continue
        if param.name and param.name.lower() in _DNP_PARAM_NAMES:
            if (param.text or "").strip().upper() == "DNP":
                return True
    return False


def _param_name(param: object) -> str | None:
    if isinstance(param, AltiumSchDesignator):
        return "Designator"
    if isinstance(param, AltiumSchParameter):
        return param.name or None
    return None


def _component_designator(component: object) -> str:
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchDesignator):
            return (param.text or "").strip()
    return ""


def _rot_key_candidates(component: object) -> list[str]:
    """Return rot keys to try in priority order for this component.

    For multi-part components (part_count > 1) the part-specific variants
    (_P{n} suffix) are tried first so each gate/section can have its own
    parameter layout. Falls back to generic (no part suffix) entries so a
    template built without part awareness still applies correctly.
    """
    base = _ROT_KEY[int(component.orientation)]
    mirrored = getattr(component, "is_mirrored", False)
    opt = _get_layout_opt(component)
    part_count = getattr(component, "part_count", 1)
    part_id = getattr(component, "current_part_id", 1)
    part_suffix = f"_P{part_id}" if part_count > 1 else ""

    candidates: list[str] = []

    # Part-specific candidates first (only generated for multi-part components)
    if part_suffix:
        if mirrored and opt is not None:
            candidates.append(f"{base}_MIRROR_OPT{opt}{part_suffix}")
        if mirrored:
            candidates.append(f"{base}_MIRROR{part_suffix}")
        if opt is not None:
            candidates.append(f"{base}_OPT{opt}{part_suffix}")
        candidates.append(f"{base}{part_suffix}")

    # Generic candidates (always present as fallback)
    if mirrored and opt is not None:
        candidates.append(f"{base}_MIRROR_OPT{opt}")
    if mirrored:
        candidates.append(f"{base}_MIRROR")
    if opt is not None:
        candidates.append(f"{base}_OPT{opt}")
    candidates.append(base)
    return candidates


def _get_layout_opt(component: object) -> int | None:
    """Return the integer value of sch_layout_opt if present, else None."""
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchParameter) and param.name == _LAYOUT_OPT_PARAM:
            try:
                return int(param.text or "")
            except (ValueError, TypeError):
                return None
    return None


def _apply_matched_component(
    component: object,
    rot_layout: dict,
    counts: Counter,
) -> None:
    """Apply a full TOML rotation entry to a component.

    Parameters present in rot_layout get their position applied and are made
    visible. Parameters absent from rot_layout are hidden.
    """
    comp_x = component.location.x_mils
    comp_y = component.location.y_mils

    for param in getattr(component, "parameters", []):
        name = _param_name(param)
        if name is None:
            continue

        if name in (_LAYOUT_OPT_PARAM, _LAYOUT_DNP_PARAM):
            continue  # control parameters — handled separately

        if name in rot_layout:
            entry = rot_layout[name]
            param.location = CoordPoint.from_mils(
                comp_x + float(entry["offset_x"]),
                comp_y + float(entry["offset_y"]),
            )
            param.orientation = TextOrientation(
                _ORIENT_MAP.get(entry.get("orientation", "DEGREES_0"), 0)
            )
            if "justification" in entry:
                param.justification = TextJustification(
                    _JUST_MAP.get(entry["justification"], 0)
                )
            param.is_hidden = False
            param.auto_position = False
            counts[name] += 1
        else:
            # Not listed in the template for this component → hide
            param.is_hidden = True

    pin_vis = rot_layout.get(_PINS_KEY)
    if pin_vis:
        for pin in getattr(component, "pins", []):
            if not isinstance(pin, AltiumSchPin):
                continue
            entry = pin_vis.get(pin.designator)
            if entry is not None:
                pin.show_name = bool(entry.get("show_name", True))
                pin.show_designator = bool(entry.get("show_designator", True))


def _apply_default_visibility(
    component: object,
    default_vis: dict,
    counts: Counter,
) -> None:
    """Apply [default] visibility rules to an unmatched component.

    Only sets is_hidden; does not touch position or auto_position.
    """
    for param in getattr(component, "parameters", []):
        name = _param_name(param)
        if name is None or name not in default_vis:
            continue
        param.is_hidden = not bool(default_vis[name])
        counts[f"default.{name}"] += 1


def _apply_dnp_swap(component: object, counts: Counter) -> None:
    """
    Handle sch_layout_dnp visual swap for one component.

    sch_layout_dnp = "DNP":
      Find the first visible value-type parameter (Resistance, Capacitance,
      Inductance, PartNumber, Value), hide it, and position sch_layout_dnp
      at the same location/orientation/justification and make it visible.

    sch_layout_dnp = anything else (including "0"):
      Ensure sch_layout_dnp is hidden. The value-type parameter is already
      visible because the template step ran before this call.
    """
    dnp_param: object | None = None
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchParameter) and param.name == _LAYOUT_DNP_PARAM:
            dnp_param = param
            break
    if dnp_param is None:
        return

    if (dnp_param.text or "").strip().upper() == "DNP":
        value_param: object | None = None
        for param in getattr(component, "parameters", []):
            if (
                isinstance(param, AltiumSchParameter)
                and param.name in _DNP_SWAP_PARAM_NAMES
                and not param.is_hidden
            ):
                value_param = param
                break

        if value_param is not None:
            dnp_param.location = CoordPoint.from_mils(
                value_param.location.x_mils,
                value_param.location.y_mils,
            )
            dnp_param.orientation = value_param.orientation
            dnp_param.justification = value_param.justification
            dnp_param.font_id = value_param.font_id
            value_param.is_hidden = True

        dnp_param.color = _DNP_LABEL_COLOR
        dnp_param.is_hidden = False
        dnp_param.auto_position = False
        counts["sch_layout_dnp_shown"] += 1
    else:
        dnp_param.is_hidden = True


def apply_layout_to_schdoc(
    input_path: Path,
    output_path: Path,
    layout: dict,
) -> dict:
    default_vis: dict = layout.get("default", {})

    schdoc = AltiumSchDoc(input_path)
    counts: Counter[str] = Counter()
    matched = 0
    rot_missing = 0
    defaulted = 0
    dnp_set = 0
    dnp_reset = 0
    unmatched: dict[str, list[str]] = {}  # lib_ref → [designators]

    for component in schdoc.components:
        lib_ref = component.lib_reference
        if not lib_ref:
            continue

        if lib_ref in layout:
            lib_layout = layout[lib_ref]
            rot_layout = None
            for candidate in _rot_key_candidates(component):
                rot_layout = lib_layout.get(candidate)
                if rot_layout is not None:
                    break

            if rot_layout is None:
                # lib_ref is in the template but no matching rotation entry found.
                # Hide all parameters — the template is the authority for this lib_ref.
                for param in getattr(component, "parameters", []):
                    name = _param_name(param)
                    if name is not None and name not in (_LAYOUT_OPT_PARAM, _LAYOUT_DNP_PARAM):
                        param.is_hidden = True
                rot_missing += 1
            else:
                _apply_matched_component(component, rot_layout, counts)
                matched += 1
        else:
            des = _component_designator(component)
            unmatched.setdefault(lib_ref, []).append(des or "?")
            if default_vis:
                _apply_default_visibility(component, default_vis, counts)
                defaulted += 1

        _apply_dnp_swap(component, counts)

        if _is_dnp(component):
            if component.component_kind != ComponentKind.STANDARD_NO_BOM:
                component.component_kind = ComponentKind.STANDARD_NO_BOM
                dnp_set += 1
        elif component.component_kind == ComponentKind.STANDARD_NO_BOM:
            component.component_kind = ComponentKind.STANDARD
            dnp_reset += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    schdoc.save(output_path)

    return {
        "source": str(input_path),
        "output": str(output_path),
        "components_matched": matched,
        "components_rotation_missing": rot_missing,
        "components_defaulted": defaulted,
        "dnp_set_no_bom": dnp_set,
        "dnp_reset_to_standard": dnp_reset,
        "sch_layout_dnp_shown": counts["sch_layout_dnp_shown"],
        "parameter_placements": dict(sorted(counts.items())),
        "unmatched_lib_refs": {lr: sorted(des) for lr, des in unmatched.items()},
    }


def _take_history_snapshot(output_dir: Path, output_paths: list[Path]) -> Path | None:
    """Copy existing output SchDocs to clean/history/<timestamp>/ before overwriting."""
    existing = [p for p in output_paths if p.exists()]
    if not existing:
        return None
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    snap_dir = output_dir / "history" / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)
    for src in existing:
        shutil.copy2(src, snap_dir / src.name)
    return snap_dir


def _snapshot_touched_schdocs(schdoc_paths: list[Path], history_root: Path) -> Path:
    """Copy every SchDoc the script will modify into ``History/<timestamp>/``.

    Runs before any in-place edit so the pre-run state of every touched file is
    recoverable. Writes into Altium's History folder with a timestamped
    subdirectory matching Altium's own naming.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snap_dir = history_root / timestamp
    snap_dir.mkdir(parents=True, exist_ok=True)
    for src in schdoc_paths:
        if src.exists():
            shutil.copy2(src, snap_dir / src.name)
    return snap_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply param_layout.toml to every SchDoc in a project. "
            "Matched components: listed params positioned and shown, unlisted params hidden. "
            "Unmatched components: [default] visibility rules applied."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        metavar="PROJECT.PrjPcb",
        help=(
            "Path to the .PrjPcb file. Reads <project_dir>/param_layout.toml, "
            "snapshots every touched SchDoc into <project_dir>/History/<timestamp>/, "
            "then rewrites the project's SchDocs in place. "
            "Omit to run the bundled hydroscope example (writes to output/)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.project:
        prjpcb_path = Path(args.project).resolve()
        project_dir = prjpcb_path.parent
        layout_toml = project_dir / "param_layout.toml"
        in_place = True
    else:
        prjpcb_path = _DEFAULT_PRJPCB
        project_dir = SAMPLE_DIR / "output" / "hydroscope_param"
        layout_toml = _DEFAULT_LAYOUT_TOML
        in_place = False

    if not layout_toml.exists():
        print(
            f"param_layout.toml not found at {layout_toml}\n"
            "Run schdoc_param_layout_extract.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    layout = tomllib.loads(layout_toml.read_text(encoding="utf-8"))

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        raise RuntimeError(f"No SchDoc files found in project: {prjpcb_path}")

    if in_place:
        # Snapshot every SchDoc we are about to modify into the Altium History
        # folder, then rewrite each one atomically in place (write to a temp
        # file and replace, so the original is never left half-written).
        snapshot_dir = _snapshot_touched_schdocs(
            schdoc_paths, project_dir / "History"
        )
        artifacts_dir = snapshot_dir
        documents = []
        for src in schdoc_paths:
            tmp = src.parent / (src.name + ".tmp")
            result = apply_layout_to_schdoc(src, tmp, layout)
            tmp.replace(src)
            result["output"] = str(src)
            documents.append(result)
    else:
        # Bundled example: copy the read-only assets into output/ so the
        # committed test assets stay untouched.
        output_dir = project_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = _take_history_snapshot(
            output_dir, [output_dir / p.name for p in schdoc_paths]
        )
        artifacts_dir = output_dir
        documents = [
            apply_layout_to_schdoc(p, output_dir / p.name, layout)
            for p in schdoc_paths
        ]
        output_prjpcb = output_dir / prjpcb_path.name
        if not output_prjpcb.exists() or not files_equal(
            prjpcb_path, output_prjpcb, shallow=False
        ):
            shutil.copy2(prjpcb_path, output_prjpcb)

    manifest = {
        "source_project": str(prjpcb_path),
        "layout_config": str(layout_toml),
        "in_place": in_place,
        "document_count": len(documents),
        "documents": documents,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    manifest_paths = [artifacts_dir / "schdoc_param_layout_manifest.json"]
    if not args.project:
        manifest_paths.append(SAMPLE_DIR / "output" / "schdoc_param_layout_manifest.json")

    for mp in manifest_paths:
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(manifest_text, encoding="utf-8")

    total_placements = sum(
        sum(doc["parameter_placements"].values()) for doc in documents
    )
    total_matched = sum(doc["components_matched"] for doc in documents)
    total_rot_missing = sum(doc["components_rotation_missing"] for doc in documents)
    total_defaulted = sum(doc["components_defaulted"] for doc in documents)
    total_dnp_set = sum(doc["dnp_set_no_bom"] for doc in documents)
    total_dnp_reset = sum(doc["dnp_reset_to_standard"] for doc in documents)
    total_dnp_shown = sum(doc["sch_layout_dnp_shown"] for doc in documents)

    # Aggregate unmatched lib_refs across all documents
    all_unmatched: dict[str, list[str]] = {}
    for doc in documents:
        for lib_ref, designators in doc.get("unmatched_lib_refs", {}).items():
            all_unmatched.setdefault(lib_ref, []).extend(designators)
    for des_list in all_unmatched.values():
        des_list.sort()

    total_unmatched_instances = sum(len(v) for v in all_unmatched.values())
    unmatched_rows = sorted(
        [(lr, len(des), ", ".join(des)) for lr, des in all_unmatched.items()],
        key=lambda x: (-x[1], x[0].lower()),
    )
    unmatched_path = artifacts_dir / "unmatched_symbols.csv"
    with unmatched_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["LibRef", "InstanceCount", "Designators"])
        writer.writerows(unmatched_rows)

    print(f"Loaded project: {prjpcb_path}")
    print(f"Layout config: {layout_toml}")
    print(f"Processed SchDocs: {len(documents)}")
    print(f"Components matched: {total_matched}  defaulted: {total_defaulted}")
    if total_rot_missing:
        print(
            f"Components with missing rotation entry: {total_rot_missing}"
            " (lib_ref in template but rotation not -- all params hidden)"
        )
    print(f"Total parameter placements: {total_placements}")
    if total_dnp_set or total_dnp_reset:
        print(f"DNP -> Standard (No BOM): {total_dnp_set}  reset -> Standard: {total_dnp_reset}")
    if total_dnp_shown:
        print(f"sch_layout_dnp shown (value param swapped for DNP label): {total_dnp_shown}")
    if all_unmatched:
        print(
            f"Symbols not in layout template: {len(all_unmatched)}"
            f" ({total_unmatched_instances} instances)"
        )
    if snapshot_dir:
        print(f"History snapshot: {snapshot_dir}")
    if in_place:
        print(f"Updated SchDocs in place: {project_dir}")
    else:
        print(f"Wrote SchDocs: {artifacts_dir}")
    print(f"Wrote manifest: {manifest_paths[0]}")
    print(f"Wrote unmatched: {unmatched_path}")


if __name__ == "__main__":
    main()
