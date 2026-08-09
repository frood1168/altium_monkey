from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from altium_monkey import (
    AltiumSchDesignator,
    AltiumSchDoc,
    AltiumSchParameter,
    AltiumSchSheetSymbol,
)
from altium_monkey.altium_prjpcb import AltiumPrjPcb


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
DEFAULT_PROJECT = ASSETS_DIR / "projects" / "rt_super_c1" / "RT_SUPER_C1.PrjPcb"
DEFAULT_VARIANT = "1v8-2x3USON"
OUTPUT_DIR = SAMPLE_DIR / "output"


_LAYOUT_DNP_PARAM = "sch_layout_dnp"

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


def _get_designator(component: object) -> str | None:
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchDesignator):
            return (param.text or "").strip() or None
    return None


def _build_uid_path_map(
    schdoc_cache: dict[Path, AltiumSchDoc],
) -> dict[Path, list[str]]:
    """
    Return {schdoc_path: [sheet_sym_uid, ...]} giving the chain of sheet symbol
    UIDs from the root sheet down to each SchDoc.

    Root sheets (not referenced by any other sheet symbol) get [].
    For a component in SchDocX with comp_uid=ABCDEF:
      uid_path = uid_path_map[X]  # e.g. ['FDSFGEWG', 'LTGJOYOU']
      altium_uid = '\\' + '\\'.join(uid_path + ['ABCDEF'])
    """
    schdoc_paths = list(schdoc_cache.keys())
    name_to_path: dict[str, Path] = {p.name.lower(): p for p in schdoc_paths}

    # Build: child_path → list of (parent_path, sheet_sym_uid)
    parents_of: dict[Path, list[tuple[Path, str]]] = {p: [] for p in schdoc_paths}

    for parent_path, schdoc in schdoc_cache.items():
        for ss in schdoc.sheet_symbols:
            if not isinstance(ss, AltiumSchSheetSymbol):
                continue
            ss_uid = getattr(ss, "unique_id", None)
            fname_obj = ss.file_name
            if ss_uid is None or fname_obj is None:
                continue
            fname_text = getattr(fname_obj, "text", None)
            if not fname_text:
                continue
            child_base = Path(fname_text).name.lower()
            child_path = name_to_path.get(child_base)
            if child_path is not None:
                parents_of[child_path].append((parent_path, ss_uid))

    # Root sheets = not referenced by any sheet symbol
    uid_path_map: dict[Path, list[str]] = {}
    queue: list[Path] = []
    for path in schdoc_paths:
        if not parents_of[path]:
            uid_path_map[path] = []
            queue.append(path)

    # BFS from roots, assigning paths
    while queue:
        current = queue.pop(0)
        current_path = uid_path_map[current]
        for ss in schdoc_cache[current].sheet_symbols:
            if not isinstance(ss, AltiumSchSheetSymbol):
                continue
            ss_uid = getattr(ss, "unique_id", None)
            fname_obj = ss.file_name
            if ss_uid is None or fname_obj is None:
                continue
            fname_text = getattr(fname_obj, "text", None)
            if not fname_text:
                continue
            child_base = Path(fname_text).name.lower()
            child_path = name_to_path.get(child_base)
            if child_path is not None and child_path not in uid_path_map:
                uid_path_map[child_path] = current_path + [ss_uid]
                queue.append(child_path)

    # Fallback for any unreachable sheets
    for p in schdoc_paths:
        if p not in uid_path_map:
            uid_path_map[p] = []

    return uid_path_map


def _collect_dnp_components(schdoc_paths: list[Path]) -> dict[str, str]:
    """
    Return {designator: altium_hierarchical_uid} for all DNP components.

    The uid uses Altium's PrjPcb variant format:
      flat design:        \\COMPUID
      hierarchical:       \\SHEETSYM1\\SHEETSYM2\\COMPUID
    """
    schdoc_cache = {p: AltiumSchDoc(p) for p in schdoc_paths}
    uid_path_map = _build_uid_path_map(schdoc_cache)

    dnp: dict[str, str] = {}
    for path, schdoc in schdoc_cache.items():
        sheet_uid_path = uid_path_map.get(path, [])
        for component in schdoc.components:
            if not _is_dnp(component):
                continue
            des = _get_designator(component)
            if not des:
                continue
            comp_uid = getattr(component, "unique_id", "") or ""
            all_uids = sheet_uid_path + ([comp_uid] if comp_uid else [])
            hierarchical_uid = "\\" + "\\".join(all_uids) if all_uids else ""
            dnp[des] = hierarchical_uid

    return dnp


def _parse_variation_str(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for pair in (raw or "").split("|"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            fields[k] = v
    return fields


def _build_variation_str(fields: dict[str, str]) -> str:
    return "|".join(f"{k}={v}" for k, v in fields.items())


def _update_variant_not_fitted(
    project: AltiumPrjPcb,
    variant_name: str,
    dnp: dict[str, str],
) -> tuple[int, int]:
    """
    Replace Not Fitted (Kind=1) entries in the named variant with the DNP set.
    Keeps all other variation kinds (alternates, explicit fit overrides) unchanged.

    Returns (not_fitted_set, not_fitted_reset).
    """
    target_section: str | None = None
    for section in project.config.sections():
        if not section.lower().startswith("projectvariant"):
            continue
        desc = project.config.get(section, "Description", fallback="").strip()
        if desc.lower() == variant_name.strip().lower():
            target_section = section
            break

    if target_section is None:
        available = [
            project.config.get(s, "Description", fallback="?").strip()
            for s in project.config.sections()
            if s.lower().startswith("projectvariant")
        ]
        print(
            f"Variant '{variant_name}' not found in project.\n"
            f"Available variants: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    variation_count = project.config.getint(target_section, "VariationCount", fallback=0)
    param_variation_count = project.config.getint(target_section, "ParamVariationCount", fallback=0)

    # Read and remove existing VariationN entries
    existing: list[dict[str, str]] = []
    for i in range(1, variation_count + 1):
        key = f"Variation{i}"
        if project.config.has_option(target_section, key):
            existing.append(_parse_variation_str(project.config.get(target_section, key)))
            project.config.remove_option(target_section, key)

    # Remove ParamVariationCount and ParamVariationN/ParamDesignatorN so we can
    # re-append them AFTER the VariationN entries — Altium requires this ordering.
    param_variations: list[tuple[str, str]] = []
    project.config.remove_option(target_section, "ParamVariationCount")
    for i in range(1, param_variation_count + 1):
        for key in (f"ParamVariation{i}", f"ParamDesignator{i}"):
            if project.config.has_option(target_section, key):
                param_variations.append((key, project.config.get(target_section, key)))
                project.config.remove_option(target_section, key)

    keep = [v for v in existing if v.get("Kind") != "1"]
    old_not_fitted = {v.get("Designator", "") for v in existing if v.get("Kind") == "1"}

    new_not_fitted: list[dict[str, str]] = []
    for des in sorted(dnp.keys()):
        uid = dnp[des]
        fields: dict[str, str] = {"Designator": des}
        if uid:
            fields["UniqueId"] = uid  # already in Altium format: \SHEETSYM\COMPUID
        fields["Kind"] = "1"
        fields["AlternatePart"] = ""  # required by Altium even when empty
        new_not_fitted.append(fields)

    set_count = len(new_not_fitted)
    reset_count = len(old_not_fitted - set(dnp.keys()))

    # Write in Altium-native order: VariationCount, then VariationN entries,
    # then ParamVariationCount and its entries.
    all_variations = keep + new_not_fitted
    project.config.set(target_section, "VariationCount", str(len(all_variations)))
    for i, v in enumerate(all_variations, start=1):
        project.config.set(target_section, f"Variation{i}", _build_variation_str(v))
    project.config.set(target_section, "ParamVariationCount", str(param_variation_count))
    for key, val in param_variations:
        project.config.set(target_section, key, val)

    return set_count, reset_count


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Set Not Fitted variant flags from DNP parameter values. "
            "Scans all SchDocs for components marked DNP -- either the "
            "sch_layout_dnp control parameter equals 'DNP', or a value "
            "parameter (Value, Resistance, Capacitance, etc.) equals 'DNP' "
            "-- then updates the named variant in the .PrjPcb file. Components "
            "previously marked Not Fitted that no longer have DNP are cleared."
        )
    )
    parser.add_argument(
        "project",
        metavar="PROJECT.PrjPcb",
        nargs="?",
        default=None,
        help=(
            "Path to the .PrjPcb project file. Defaults to the bundled "
            "RT_SUPER_C1 sample project."
        ),
    )
    parser.add_argument(
        "variant",
        metavar="VARIANT_NAME",
        nargs="?",
        default=None,
        help=(
            "Exact name of the variant to update (e.g. 'Initial Design'). "
            f"Defaults to '{DEFAULT_VARIANT}'."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    prjpcb_path = (
        Path(args.project).resolve() if args.project else DEFAULT_PROJECT.resolve()
    )
    variant_name = args.variant if args.variant else DEFAULT_VARIANT

    if not prjpcb_path.exists():
        print(f"Project file not found: {prjpcb_path}", file=sys.stderr)
        sys.exit(1)

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        print(f"No SchDoc files found in project: {prjpcb_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Project:  {prjpcb_path}")
    print(f"Variant:  {variant_name}")
    print(f"SchDocs:  {len(schdoc_paths)}")

    dnp = _collect_dnp_components(schdoc_paths)

    if dnp:
        print(f"\nDNP components ({len(dnp)}):")
        for des in sorted(dnp):
            print(f"  {des}  uid={dnp[des]}")
    else:
        print("\nNo DNP components found.")

    set_count, reset_count = _update_variant_not_fitted(project, variant_name, dnp)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / prjpcb_path.name
    project.save(output_path)

    summary = {
        "source_project": str(prjpcb_path),
        "output_project": str(output_path),
        "variant": variant_name,
        "dnp_components": {des: uid for des, uid in sorted(dnp.items())},
        "not_fitted_set": set_count,
        "not_fitted_reset": reset_count,
    }
    manifest_path = OUTPUT_DIR / "schdoc_variant_dnp_manifest.json"
    manifest_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nNot Fitted set:   {set_count}")
    print(f"Not Fitted reset: {reset_count}")
    print(f"\nWrote: {output_path}")
    print(f"Wrote: {manifest_path}")
    print("\nReview the output then copy it over the original .PrjPcb (with Altium closed).")


if __name__ == "__main__":
    main()
