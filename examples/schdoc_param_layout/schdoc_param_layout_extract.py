from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from altium_monkey import (
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchParameter,
    AltiumSchPin,
)


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
_DEFAULT_REF_SCHDOC = ASSETS_DIR / "projects" / "hydroscope" / "CPU.SchDoc"
_DEFAULT_OUTPUT = SAMPLE_DIR / "output" / "param_layout.toml"

_BASE_ROT_ORDER = ["DEG_0", "DEG_90", "DEG_180", "DEG_270"]
_PINS_KEY = "__pins__"
_ROT_KEY = {0: "DEG_0", 1: "DEG_90", 2: "DEG_180", 3: "DEG_270"}
_LAYOUT_OPT_PARAM = "sch_layout_opt"


def _rot_sort_key(rot: str) -> tuple[int, int, int]:
    for i, base in enumerate(_BASE_ROT_ORDER):
        if rot == base:
            return (i, 0, 0)
        if rot == f"{base}_MIRROR":
            return (i, 1, 0)
        opt_prefix = f"{base}_OPT"
        if rot.startswith(opt_prefix) and "_MIRROR" not in rot:
            suffix = rot[len(opt_prefix):]
            return (i, 0, int(suffix) if suffix.isdigit() else 99)
        mirror_opt_prefix = f"{base}_MIRROR_OPT"
        if rot.startswith(mirror_opt_prefix):
            suffix = rot[len(mirror_opt_prefix):]
            return (i, 1, int(suffix) if suffix.isdigit() else 99)
    return (99, 0, 0)

_ORIENT_NAME = {0: "DEGREES_0", 1: "DEGREES_90", 2: "DEGREES_180", 3: "DEGREES_270"}
_JUST_NAME = {
    0: "BOTTOM_LEFT",  1: "BOTTOM_CENTER",  2: "BOTTOM_RIGHT",
    3: "CENTER_LEFT",  4: "CENTER_CENTER",  5: "CENTER_RIGHT",
    6: "TOP_LEFT",     7: "TOP_CENTER",     8: "TOP_RIGHT",
}

_DEFAULT_SECTION = """\
[default]
# Visibility for parameters on components not matched above.
# true = visible on schematic, false = hidden.
# No position is applied for default entries.
Comment = false
Value = true
PartNumber = true
"""


def _toml_key(k: str) -> str:
    return k if re.match(r"^[A-Za-z0-9_-]+$", k) else f'"{k}"'


def _toml_section(lib_ref: str, rot_key: str, param_name: str) -> str:
    return f"[{_toml_key(lib_ref)}.{rot_key}.{_toml_key(param_name)}]"


def _layout_lines(layout: dict[str, Any]) -> list[str]:
    # Presence in the TOML means the parameter is visible — no is_hidden field needed.
    return [
        f"offset_x = {layout['offset_x']}",
        f"offset_y = {layout['offset_y']}",
        f"orientation = \"{layout['orientation']}\"",
        f"justification = \"{layout['justification']}\"",
    ]


def _extract_pin_visibility(component: object) -> dict[str, dict[str, bool]] | None:
    """Return {pin_designator: {show_name, show_designator}} if any pin hides name or number."""
    result: dict[str, dict[str, bool]] = {}
    for pin in getattr(component, "pins", []):
        if not isinstance(pin, AltiumSchPin):
            continue
        desig = pin.designator
        if not desig:
            continue
        result[desig] = {
            "show_name": bool(pin.show_name),
            "show_designator": bool(pin.show_designator),
        }
    if not result:
        return None
    if all(v["show_name"] and v["show_designator"] for v in result.values()):
        return None
    return result


def _extract_layout(component: object, param: object) -> dict[str, Any]:
    world_dx = param.location.x_mils - component.location.x_mils
    world_dy = param.location.y_mils - component.location.y_mils
    return {
        "offset_x": round(world_dx, 1),
        "offset_y": round(world_dy, 1),
        "orientation": _ORIENT_NAME[int(param.orientation)],
        "justification": _JUST_NAME.get(int(param.justification), "BOTTOM_LEFT"),
    }


_CanonicalT = dict[str, dict[str, dict[str, dict]]]
_ConflictsT = dict[str, dict[str, dict[str, list]]]


def _get_layout_opt(component: object) -> int | None:
    """Return the integer value of sch_layout_opt if present, else None."""
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchParameter) and param.name == _LAYOUT_OPT_PARAM:
            try:
                return int(param.text or "")
            except (ValueError, TypeError):
                return None
    return None


def extract_param_layouts(schdoc: AltiumSchDoc) -> tuple[_CanonicalT, _ConflictsT]:
    canonical: _CanonicalT = {}
    conflicts: _ConflictsT = {}

    for component in schdoc.components:
        lib_ref = component.lib_reference
        if not lib_ref or lib_ref == "*":
            continue

        base_rot_key = _ROT_KEY[int(component.orientation)]
        mirror = "_MIRROR" if component.is_mirrored else ""
        opt = _get_layout_opt(component)
        opt_suffix = f"_OPT{opt}" if opt is not None else ""
        rot_key = f"{base_rot_key}{mirror}{opt_suffix}"

        rot_entry = canonical.setdefault(lib_ref, {}).setdefault(rot_key, {})

        for param in getattr(component, "parameters", []):
            if isinstance(param, AltiumSchDesignator):
                param_name = "Designator"
            elif isinstance(param, AltiumSchParameter):
                param_name = param.name
                if not param_name or param_name == _LAYOUT_OPT_PARAM:
                    continue
            else:
                continue

            # Only capture visible parameters — absence from the TOML means hidden.
            if param.is_hidden:
                continue

            layout = _extract_layout(component, param)

            if param_name not in rot_entry:
                rot_entry[param_name] = layout
            elif rot_entry[param_name] != layout:
                (
                    conflicts
                    .setdefault(lib_ref, {})
                    .setdefault(rot_key, {})
                    .setdefault(param_name, [])
                    .append(layout)
                )

        pin_vis = _extract_pin_visibility(component)
        if pin_vis is not None:
            if _PINS_KEY not in rot_entry:
                rot_entry[_PINS_KEY] = pin_vis
            elif rot_entry[_PINS_KEY] != pin_vis:
                (
                    conflicts
                    .setdefault(lib_ref, {})
                    .setdefault(rot_key, {})
                    .setdefault(_PINS_KEY, [])
                    .append(pin_vis)
                )

    return canonical, conflicts


def _generate_toml(
    canonical: _CanonicalT,
    conflicts: _ConflictsT,
    header: list[str],
) -> str:
    lines: list[str] = list(header) + [""]

    for lib_ref in sorted(canonical):
        rot_map = canonical[lib_ref]
        for rot_key in sorted(rot_map, key=_rot_sort_key):
            if rot_key not in rot_map:
                continue
            for param_name, layout in rot_map[rot_key].items():
                if param_name == _PINS_KEY:
                    continue

                lines.append(_toml_section(lib_ref, rot_key, param_name))
                lines.extend(_layout_lines(layout))

                for conflict in (
                    conflicts.get(lib_ref, {}).get(rot_key, {}).get(param_name, [])
                ):
                    lines.append("# Conflicts found:")
                    for line in _layout_lines(conflict):
                        lines.append(f"# {line}")

                lines.append("")

            if _PINS_KEY in rot_map[rot_key]:
                pin_vis = rot_map[rot_key][_PINS_KEY]
                lines.append(f"[{_toml_key(lib_ref)}.{rot_key}.{_PINS_KEY}]")
                for pin_desig, vis in sorted(pin_vis.items()):
                    sn = "true" if vis["show_name"] else "false"
                    sd = "true" if vis["show_designator"] else "false"
                    lines.append(
                        f"{_toml_key(pin_desig)} = {{show_name = {sn}, show_designator = {sd}}}"
                    )
                for conflict in (
                    conflicts.get(lib_ref, {}).get(rot_key, {}).get(_PINS_KEY, [])
                ):
                    lines.append("# Conflicts found:")
                    for pin_desig, vis in sorted(conflict.items()):
                        sn = "true" if vis["show_name"] else "false"
                        sd = "true" if vis["show_designator"] else "false"
                        lines.append(
                            f"# {_toml_key(pin_desig)} = {{show_name = {sn}, show_designator = {sd}}}"
                        )
                lines.append("")

    lines.append(_DEFAULT_SECTION)
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract visible parameter positions from a reference schematic into "
            "param_layout.toml. Only visible parameters are captured — absent entries "
            "mean hidden when applied."
        ),
    )
    parser.add_argument(
        "schdoc",
        nargs="?",
        metavar="REFERENCE.SchDoc",
        help=(
            "Reference schematic with parameters manually positioned and visibility set. "
            "Writes param_layout.toml to <schematic_dir>/clean/. "
            "Defaults to the bundled hydroscope example schematic."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.schdoc:
        ref_path = Path(args.schdoc).resolve()
        output_toml = ref_path.parent / "clean" / "param_layout.toml"
    else:
        ref_path = _DEFAULT_REF_SCHDOC
        output_toml = _DEFAULT_OUTPUT

    schdoc = AltiumSchDoc(ref_path)
    canonical, conflicts = extract_param_layouts(schdoc)

    total_rot_entries = sum(len(rot_map) for rot_map in canonical.values())
    total_params = sum(
        len(params)
        for rot_map in canonical.values()
        for params in rot_map.values()
    )
    total_conflicts = sum(
        len(clist)
        for lib_c in conflicts.values()
        for rot_c in lib_c.values()
        for clist in rot_c.values()
    )

    header = [
        "# Generated by schdoc_param_layout_extract.py",
        f"# Reference schematic: {ref_path}",
        f"# Component types: {len(canonical)}",
        f"# Orientation variants: {total_rot_entries}",
        f"# Parameter entries: {total_params}",
        "#",
        "# Sections: [LibraryReference.Rotation.ParameterName]",
        "# Rotations: DEG_0, DEG_90, DEG_180, DEG_270",
        "# Mirrored variants: DEG_0_MIRROR, DEG_90_MIRROR, ... (from component.is_mirrored)",
        "# Layout options: DEG_0_OPT1, DEG_0_MIRROR_OPT1, ... (from sch_layout_opt parameter on component)",
        "# Fallback order when applying: MIRROR_OPT -> MIRROR -> OPT -> base -> hide all",
        "# Presence = visible; absence = hidden when applied to a matched component.",
        "# offset_x/y: world-frame mils from component origin.",
        "# orientation: DEGREES_0, DEGREES_90, DEGREES_180, DEGREES_270",
        "# justification: BOTTOM_LEFT / BOTTOM_CENTER / BOTTOM_RIGHT",
        "#                CENTER_LEFT / CENTER_CENTER / CENTER_RIGHT",
        "#                TOP_LEFT    / TOP_CENTER    / TOP_RIGHT",
        "# Pin visibility: [LibRef.Rotation.__pins__] pin_desig = {show_name, show_designator}",
        "#   Only written when at least one pin hides name or number (non-default).",
        "#   show_name: show pin name label; show_designator: show pin number label.",
    ]

    output_toml.parent.mkdir(parents=True, exist_ok=True)
    output_toml.write_text(_generate_toml(canonical, conflicts, header), encoding="utf-8")

    print(f"Reference schematic: {ref_path}")
    print(f"Component types: {len(canonical)}")
    print(f"Orientation variants: {total_rot_entries}")
    print(f"Parameter entries: {total_params}  (visible only)")
    if total_conflicts:
        print(f"Conflicts (commented out): {total_conflicts}")
    print(f"Wrote: {output_toml}")


if __name__ == "__main__":
    main()
