from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from altium_monkey import AltiumDesign, AltiumSchDesignator, AltiumSchDoc
from altium_monkey.altium_prjpcb import AltiumPrjPcb


# Arg-free demo defaults: a bundled project and a designator verified to have
# pins in that project (U1 resolves to 176 pins in RT_SUPER_C1).
_HERE = Path(__file__).resolve().parent
_DEFAULT_PROJECT = (
    _HERE.parent / "assets" / "projects" / "rt_super_c1" / "RT_SUPER_C1.PrjPcb"
)
_DEFAULT_DESIGNATOR = "U1"


def _natural_sort_key(s: str) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def _get_component_designator(component: object) -> str:
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchDesignator):
            return param.text or ""
    return ""


def _collect_pins(
    prjpcb_path: Path, target_designator: str
) -> list[tuple[int, str, str]]:
    """
    Walk all SchDocs in the project and collect (part_id, pin_number, pin_name)
    for the target designator. Deduplicates pins that appear across multiple sheets
    or compile variants.
    """
    target_upper = target_designator.upper()
    seen: set[tuple[int, str]] = set()
    pins: list[tuple[int, str, str]] = []

    prjpcb = AltiumPrjPcb(prjpcb_path)
    for schdoc_path in prjpcb.get_reachable_schdoc_paths():
        schdoc = AltiumSchDoc(schdoc_path)
        for component in schdoc.components:
            if _get_component_designator(component).upper() != target_upper:
                continue
            for pin in getattr(component, "pins", []):
                part_id = int(getattr(pin, "owner_part_id", None) or 1)
                pin_num = str(getattr(pin, "designator", "") or "")
                pin_name = str(getattr(pin, "name", "") or "")
                key = (part_id, pin_num)
                if key not in seen:
                    seen.add(key)
                    pins.append((part_id, pin_num, pin_name))

    return sorted(
        pins,
        key=lambda p: (max(p[0], 0), _natural_sort_key(p[1])),
    )


def build_connection_table(
    prjpcb_path: Path,
    target_designator: str,
    *,
    filter_nets: set[str] | None = None,
    include_nc: bool = True,
) -> list[dict[str, str]]:
    """
    Return CSV rows for a component's pin connections.

    Columns: Designator, Part, Pin, Pin Name, Net.
    Pins not present in the compiled netlist are reported as 'NC'.
    """
    design = AltiumDesign.from_prjpcb(prjpcb_path)
    netlist = design.to_netlist()

    # (component_designator_upper, pin_number) → net_name
    pin_net: dict[tuple[str, str], str] = {}
    for net in netlist.nets:
        for terminal in net.terminals:
            pin_net[(terminal.designator.upper(), terminal.pin)] = net.name

    all_pins = _collect_pins(prjpcb_path, target_designator)
    if not all_pins:
        return []

    target_upper = target_designator.upper()
    rows: list[dict[str, str]] = []
    for part_id, pin_num, pin_name in all_pins:
        net_name = pin_net.get((target_upper, pin_num), "NC")
        if not include_nc and net_name == "NC":
            continue
        if filter_nets and net_name.upper() in filter_nets:
            continue
        rows.append({
            "Designator": target_designator,
            "Part": str(part_id),
            "Pin": pin_num,
            "Pin Name": pin_name,
            "Net": net_name,
        })

    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a CSV pin-connection table for a component designator. "
            "NC (unconnected) pins are included by default."
        ),
    )
    parser.add_argument(
        "project",
        metavar="PROJECT.PrjPcb",
        nargs="?",
        default=str(_DEFAULT_PROJECT),
        help=(
            "Path to the .PrjPcb file. Defaults to the bundled "
            "RT_SUPER_C1 sample project."
        ),
    )
    parser.add_argument(
        "designator",
        metavar="DESIGNATOR",
        nargs="?",
        default=_DEFAULT_DESIGNATOR,
        help=(
            "Component designator (e.g. U1, R5). Case-insensitive. "
            f"Defaults to {_DEFAULT_DESIGNATOR}."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE.csv",
        help=(
            "Output CSV path. Defaults to output/<DESIGNATOR>_connections.csv "
            "next to this script."
        ),
    )
    parser.add_argument(
        "--filter-nets",
        nargs="+",
        metavar="NET",
        help="Net names to exclude (e.g. GND VCC +3V3). Case-insensitive.",
    )
    parser.add_argument(
        "--no-nc",
        action="store_true",
        help="Exclude unconnected (NC) pins from the output.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    prjpcb_path = Path(args.project).resolve()
    if not prjpcb_path.exists():
        print(f"Project file not found: {prjpcb_path}", file=sys.stderr)
        sys.exit(1)

    filter_nets = {n.upper() for n in args.filter_nets} if args.filter_nets else None

    rows = build_connection_table(
        prjpcb_path,
        args.designator,
        filter_nets=filter_nets,
        include_nc=not args.no_nc,
    )

    if not rows:
        print(
            f"No pins found for '{args.designator}'. "
            "Verify the designator exists in the project.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_path = (
        Path(args.output) if args.output
        else _HERE / "output" / f"{args.designator}_connections.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["Designator", "Part", "Pin", "Pin Name", "Net"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    nc_count = sum(1 for r in rows if r["Net"] == "NC")
    connected_count = len(rows) - nc_count
    print(f"Component:  {args.designator}")
    print(f"Total pins: {len(rows)}")
    print(f"Connected:  {connected_count}  NC: {nc_count}")
    if filter_nets:
        print(f"Filtered:   {', '.join(sorted(args.filter_nets))}")
    print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
