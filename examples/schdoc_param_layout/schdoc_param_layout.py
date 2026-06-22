from __future__ import annotations

import argparse
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
_PINS_KEY = "__pins__"

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


def _rot_key_candidates(component: object) -> list[str]:
    """Return rot keys to try in priority order for this component."""
    base = _ROT_KEY[int(component.orientation)]
    mirrored = getattr(component, "is_mirrored", False)
    opt = _get_layout_opt(component)

    candidates: list[str] = []
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

        if name == _LAYOUT_OPT_PARAM:
            continue  # control parameter — leave visibility unchanged

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
                    if name is not None and name != _LAYOUT_OPT_PARAM:
                        param.is_hidden = True
                rot_missing += 1
            else:
                _apply_matched_component(component, rot_layout, counts)
                matched += 1
        elif default_vis:
            _apply_default_visibility(component, default_vis, counts)
            defaulted += 1

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
        "parameter_placements": dict(sorted(counts.items())),
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
            "Path to the .PrjPcb file. "
            "Reads <project_dir>/clean/param_layout.toml and writes to <project_dir>/clean/. "
            "Defaults to the bundled hydroscope example project."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.project:
        prjpcb_path = Path(args.project).resolve()
        clean_dir = prjpcb_path.parent / "clean"
        layout_toml = clean_dir / "param_layout.toml"
        output_dir = clean_dir
    else:
        prjpcb_path = _DEFAULT_PRJPCB
        layout_toml = _DEFAULT_LAYOUT_TOML
        output_dir = SAMPLE_DIR / "output" / "hydroscope_param"

    if not layout_toml.exists():
        print(
            f"param_layout.toml not found at {layout_toml}\n"
            "Run schdoc_param_layout_extract.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    layout = tomllib.loads(layout_toml.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        raise RuntimeError(f"No SchDoc files found in project: {prjpcb_path}")

    output_prjpcb = output_dir / prjpcb_path.name
    output_paths = [output_dir / p.name for p in schdoc_paths]
    snapshot_dir = _take_history_snapshot(output_dir, output_paths)

    documents = [
        apply_layout_to_schdoc(p, output_dir / p.name, layout)
        for p in schdoc_paths
    ]

    if not output_prjpcb.exists() or not files_equal(prjpcb_path, output_prjpcb, shallow=False):
        shutil.copy2(prjpcb_path, output_prjpcb)

    manifest = {
        "source_project": str(prjpcb_path),
        "output_project": str(output_prjpcb),
        "layout_config": str(layout_toml),
        "document_count": len(documents),
        "documents": documents,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    manifest_paths = [output_dir / "schdoc_param_layout_manifest.json"]
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

    print(f"Loaded project: {prjpcb_path}")
    print(f"Layout config: {layout_toml}")
    print(f"Processed SchDocs: {len(documents)}")
    print(f"Components matched: {total_matched}  defaulted: {total_defaulted}")
    if total_rot_missing:
        print(
            f"Components with missing rotation entry: {total_rot_missing}"
            " (lib_ref in template but rotation not — all params hidden)"
        )
    print(f"Total parameter placements: {total_placements}")
    if total_dnp_set or total_dnp_reset:
        print(f"DNP → Standard (No BOM): {total_dnp_set}  reset → Standard: {total_dnp_reset}")
    if snapshot_dir:
        print(f"History snapshot: {snapshot_dir}")
    print(f"Wrote SchDocs: {output_dir}")
    print(f"Wrote manifest: {manifest_paths[0]}")


if __name__ == "__main__":
    main()
