from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


SAMPLE_DIR = Path(__file__).resolve().parent
_DEFAULT_MEGAMAID_DIR = SAMPLE_DIR / "sample_megamaid"
_DEFAULT_OUTPUT = SAMPLE_DIR / "output" / "unmanaged_parts_report.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_schematic_components(schdoc_json_dir: Path) -> dict[str, dict]:
    """
    Parse all SchDoc JSONs and return {unique_id: component_info}.

    Managed components have a non-empty VaultGUID field.
    Unmanaged components have no VaultGUID (sourced from local .SchLib files).
    """
    all_components: dict[str, dict] = {}
    for json_file in sorted(schdoc_json_dir.glob("*.json")):
        data = _load_json(json_file)
        objects = data.get("document", {}).get("Objects", [])
        for obj in objects:
            if obj.get("ObjectType") != "Component":
                continue
            uid = obj.get("UniqueID", "")
            if not uid:
                continue
            all_components[uid] = {
                "lib_ref": obj.get("LibReference", ""),
                "design_item_id": obj.get("DesignItemId", ""),
                "vault_guid": obj.get("VaultGUID", ""),
                "source_lib": obj.get("SourceLibraryName", ""),
            }
    return all_components


def _collect_netlist_info(netlist_path: Path) -> dict[str, dict]:
    """Parse netlist JSON, return {svg_id: component_info}. svg_id == SchDoc UniqueID."""
    data = _load_json(netlist_path)
    result: dict[str, dict] = {}
    for comp in data.get("components", []):
        svg_id = comp.get("svg_id", "")
        if not svg_id:
            continue
        params: dict = comp.get("parameters") or {}
        result[svg_id] = {
            "designator": comp.get("designator", ""),
            "library_ref": comp.get("library_ref", ""),
            "footprint": comp.get("footprint", ""),
            "description": comp.get("description", ""),
            "part_number": params.get("PartNumber", ""),
            "manufacturer": params.get("Manufacturer", ""),
            "value": params.get("Comment") or params.get("Value", ""),
            "parameters": params,
        }
    return result


def _des_sort_key(des: str) -> tuple[str, int, str]:
    """Sort designators by prefix then numeric suffix (R1 < R2 < R10)."""
    prefix = des.rstrip("0123456789")
    suffix = des[len(prefix):]
    try:
        return (prefix, int(suffix), "")
    except ValueError:
        return (prefix, 0, suffix)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Report unmanaged parts from a MegaMaid output directory. "
            "Unmanaged parts are those sourced from local .SchLib/.PcbLib files "
            "rather than the managed online vault. "
            "Groups by schematic symbol, footprint, and PartNumber parameter so "
            "generic symbols (L, R, C) with different actual parts appear as "
            "separate rows."
        )
    )
    parser.add_argument(
        "megamaid_dir",
        metavar="MEGAMAID_DIR",
        nargs="?",
        default=None,
        help=(
            "Path to the MegaMaid project output directory (e.g. MegaMaid/Rfboard/). "
            "Defaults to the bundled sample_megamaid/ fixture."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help=(
            "Write JSON report to FILE "
            "(default: <example>/output/unmanaged_parts_report.json)."
        ),
    )
    args = parser.parse_args()

    maid_dir = (
        Path(args.megamaid_dir).resolve()
        if args.megamaid_dir
        else _DEFAULT_MEGAMAID_DIR
    )
    if not maid_dir.is_dir():
        print(f"Directory not found: {maid_dir}", file=sys.stderr)
        sys.exit(1)

    schdoc_json_dir = maid_dir / "json" / "schdoc"
    if not schdoc_json_dir.is_dir():
        print(f"SchDoc JSON dir not found: {schdoc_json_dir}", file=sys.stderr)
        sys.exit(1)

    netlist_files = sorted((maid_dir / "netlist").glob("*.json"))
    if not netlist_files:
        print(f"No netlist JSON found in: {maid_dir / 'netlist'}", file=sys.stderr)
        sys.exit(1)
    netlist_path = netlist_files[0]

    schlib_split_dir = maid_dir / "schlib" / "split"
    pcblib_split_dir = maid_dir / "pcblib" / "split"

    schlib_by_name = (
        {p.stem: p for p in sorted(schlib_split_dir.glob("*.SchLib"))}
        if schlib_split_dir.is_dir()
        else {}
    )
    pcblib_by_name = (
        {p.stem: p for p in sorted(pcblib_split_dir.glob("*.PcbLib"))}
        if pcblib_split_dir.is_dir()
        else {}
    )

    print(f"MegaMaid dir:  {maid_dir}")
    print(f"SchDoc JSONs:  {len(list(schdoc_json_dir.glob('*.json')))}")
    print(f"Split SchLibs: {len(schlib_by_name)}")
    print(f"Split PcbLibs: {len(pcblib_by_name)}")
    print()

    all_components = _collect_schematic_components(schdoc_json_dir)
    unmanaged_uids = {
        uid for uid, info in all_components.items()
        if not info["vault_guid"]
    }
    print(f"Total schematic components: {len(all_components)}")
    print(f"Unmanaged components:       {len(unmanaged_uids)}")
    print()

    netlist = _collect_netlist_info(netlist_path)

    # Group by (lib_ref, footprint, part_number) so generic symbols like L/R/C
    # with different actual part numbers appear as separate rows.
    GroupKey = tuple[str, str, str]
    groups: dict[GroupKey, list[str]] = {}
    group_meta: dict[GroupKey, dict] = {}
    skipped_uids: list[str] = []

    for uid in unmanaged_uids:
        net_info = netlist.get(uid)
        if net_info is None:
            skipped_uids.append(uid)
            continue
        lib_ref = all_components[uid]["lib_ref"]
        footprint = net_info["footprint"]
        part_number = net_info["part_number"]
        key: GroupKey = (lib_ref, footprint, part_number)
        groups.setdefault(key, []).append(net_info["designator"])
        if key not in group_meta:
            group_meta[key] = {
                "source_lib": all_components[uid]["source_lib"],
                "description": net_info["description"],
                "manufacturer": net_info["manufacturer"],
                "value": net_info["value"],
            }

    for des_list in groups.values():
        des_list.sort(key=_des_sort_key)

    # Build report entries sorted by lib_ref → part_number → footprint
    report_parts: list[dict] = []
    for key in sorted(groups.keys(), key=lambda k: (k[0].lower(), k[2].lower(), k[1].lower())):
        lib_ref, footprint, part_number = key
        designators = groups[key]
        meta = group_meta[key]
        schlib_file = schlib_by_name.get(lib_ref)
        pcblib_file = pcblib_by_name.get(footprint)

        report_parts.append({
            "lib_ref": lib_ref,
            "footprint": footprint,
            "part_number": part_number,
            "manufacturer": meta["manufacturer"],
            "value": meta["value"],
            "source_lib": meta["source_lib"],
            "description": meta["description"],
            "designators": designators,
            "designator_count": len(designators),
            "schlib_file": (
                str(schlib_file.relative_to(maid_dir)).replace("\\", "/")
                if schlib_file else None
            ),
            "pcblib_file": (
                str(pcblib_file.relative_to(maid_dir)).replace("\\", "/")
                if pcblib_file else None
            ),
        })

    report = {
        "megamaid_dir": str(maid_dir),
        "total_unmanaged_components": len(unmanaged_uids),
        "unique_unmanaged_parts": len(report_parts),
        "parts": report_parts,
    }

    output_path = Path(args.output).resolve() if args.output else _DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "LibRef", "Footprint", "PartNumber", "Manufacturer", "Value",
            "Count", "Designators", "SourceLib", "Description", "SchLibFile", "PcbLibFile",
        ])
        for part in report_parts:
            writer.writerow([
                part["lib_ref"],
                part["footprint"],
                part["part_number"],
                part["manufacturer"],
                part["value"],
                part["designator_count"],
                ", ".join(part["designators"]),
                part["source_lib"],
                part["description"],
                part["schlib_file"] or "",
                part["pcblib_file"] or "",
            ])

    # Console table
    lr_w, fp_w, pn_w = 24, 32, 22
    print(f"Unique unmanaged parts: {len(report_parts)}")
    print()
    hdr = (f"{'LibRef':<{lr_w}}  {'Footprint':<{fp_w}}  {'PartNumber':<{pn_w}}"
           f"  {'#':>3}  {'Manufacturer / Value'}")
    print(hdr)
    print("-" * len(hdr))

    for part in report_parts:
        lr = part["lib_ref"][:lr_w]
        fp = part["footprint"][:fp_w]
        pn = part["part_number"][:pn_w] if part["part_number"] else "(no part number)"
        cnt = part["designator_count"]
        mfr_val = ""
        if part["manufacturer"] and part["value"]:
            mfr_val = f"{part['manufacturer']} / {part['value']}"
        elif part["manufacturer"]:
            mfr_val = part["manufacturer"]
        elif part["value"]:
            mfr_val = part["value"]
        flag = "  *** NO PN" if not part["part_number"] else ""
        print(f"{lr:<{lr_w}}  {fp:<{fp_w}}  {pn:<{pn_w}}  {cnt:>3}  {mfr_val}{flag}")

    no_pn = [p for p in report_parts if not p["part_number"]]
    if no_pn:
        print(f"\n*** {len(no_pn)} part(s) have no PartNumber -- check parameters manually")
    if skipped_uids:
        print(f"\nNote: {len(skipped_uids)} unmanaged UIDs had no netlist entry (may be DNP or power symbols)")

    print(f"\nWrote: {output_path}")
    print(f"Wrote: {csv_path}")


if __name__ == "__main__":
    main()
