from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from altium_monkey import AltiumSchDoc, AltiumSchParameter
from altium_monkey.altium_prjpcb import AltiumPrjPcb


def _find_param(component: object, name: str) -> AltiumSchParameter | None:
    """Return first parameter matching name (case-insensitive), or None."""
    for param in getattr(component, "parameters", []):
        if isinstance(param, AltiumSchParameter) and (param.name or "").lower() == name.lower():
            return param
    return None


def fix_inductor_params_in_schdoc(
    input_path: Path,
    output_path: Path,
    lib_refs: set[str] | None,
) -> dict:
    schdoc = AltiumSchDoc(input_path)
    inductance_created = 0
    inductance_updated = 0
    partnumber_hidden = 0

    for component in schdoc.components:
        lib_ref = component.lib_reference or ""
        if lib_refs is not None and lib_ref not in lib_refs:
            continue

        # Hide PartNumber for all matched inductors
        pn_param = _find_param(component, "PartNumber")
        if pn_param is not None and not pn_param.is_hidden:
            pn_param.is_hidden = True
            partnumber_hidden += 1

        # Copy Value → Inductance only if Value exists
        value_param = _find_param(component, "Value")
        if value_param is None:
            continue

        value_text = value_param.text or ""

        ind_param = _find_param(component, "Inductance")
        if ind_param is not None:
            # Update value and unhide; leave location untouched
            ind_param.text = value_text
            ind_param.is_hidden = False
            inductance_updated += 1
        else:
            component.add_parameter("Inductance", value_text, visible=True)
            inductance_created += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    schdoc.save(output_path)

    return {
        "source": str(input_path),
        "output": str(output_path),
        "inductance_created": inductance_created,
        "inductance_updated": inductance_updated,
        "partnumber_hidden": partnumber_hidden,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "For inductor components: copy Value → Inductance (visible), hide PartNumber. "
            "Writes processed SchDocs to <project_dir>/clean/."
        )
    )
    parser.add_argument("project", metavar="PROJECT.PrjPcb", help="Path to .PrjPcb file.")
    parser.add_argument(
        "--lib-ref",
        dest="lib_refs",
        action="append",
        metavar="LIB_REF",
        help=(
            "Lib reference to target (may be given multiple times). "
            "If omitted, all components with a Value parameter are processed."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    prjpcb_path = Path(args.project).resolve()
    output_dir = prjpcb_path.parent / "clean"
    lib_refs = set(args.lib_refs) if args.lib_refs else None

    project = AltiumPrjPcb(prjpcb_path)
    schdoc_paths = project.get_reachable_schdoc_paths()
    if not schdoc_paths:
        print(f"No SchDoc files found in project: {prjpcb_path}", file=sys.stderr)
        sys.exit(1)

    documents = [
        fix_inductor_params_in_schdoc(p, output_dir / p.name, lib_refs)
        for p in schdoc_paths
    ]

    manifest = {
        "source_project": str(prjpcb_path),
        "output_dir": str(output_dir),
        "lib_refs_filter": sorted(lib_refs) if lib_refs else None,
        "document_count": len(documents),
        "documents": documents,
    }
    manifest_path = output_dir / "fix_inductor_params_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total_created = sum(d["inductance_created"] for d in documents)
    total_updated = sum(d["inductance_updated"] for d in documents)
    total_pn_hidden = sum(d["partnumber_hidden"] for d in documents)

    print(f"Loaded project: {prjpcb_path}")
    print(f"Processed SchDocs: {len(documents)}")
    if lib_refs:
        print(f"Lib ref filter: {sorted(lib_refs)}")
    print(f"Inductance created: {total_created}  updated: {total_updated}")
    print(f"PartNumber hidden: {total_pn_hidden}")
    print(f"Wrote SchDocs: {output_dir}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
