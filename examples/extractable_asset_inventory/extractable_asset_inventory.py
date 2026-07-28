from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from altium_monkey import AltiumPcbDoc, AltiumPcbLib, AltiumSchDoc, AltiumSchLib


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
INPUT_SCHDOC = ASSETS_DIR / "projects" / "rt_super_c1" / "RT_SUPER_C1.SchDoc"
INPUT_SCHLIB = ASSETS_DIR / "schlib" / "RT_SUPER_C1.SCHLIB"
INPUT_PCBDOC = ASSETS_DIR / "projects" / "rt_super_c1" / "RT_SUPER_C1.PCBdoc"
INPUT_PCBLIB = ASSETS_DIR / "pcblib" / "RT_SUPER_C1.PcbLib"
OUTPUT_DIR = SAMPLE_DIR / "output"
INVENTORY_DIR = OUTPUT_DIR / "inventories"
SELECTED_DIR = OUTPUT_DIR / "selected"
MANIFEST_PATH = OUTPUT_DIR / "extractable_asset_inventory_manifest.json"


def _sample_relative(path: Path) -> str:
    return str(path.relative_to(SAMPLE_DIR)).replace("\\", "/")


def _examples_relative(path: Path) -> str:
    return str(path.relative_to(EXAMPLES_DIR)).replace("\\", "/")


def _reset_outputs() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _asset_counts(inventory: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in inventory.assets:  # type: ignore[attr-defined]
        counts[asset.kind] = counts.get(asset.kind, 0) + 1
    return counts


def _inventory_summary(
    *,
    label: str,
    source_path: Path,
    inventory: object,
) -> dict[str, object]:
    inventory_payload = inventory.to_dict()  # type: ignore[attr-defined]
    inventory_path = INVENTORY_DIR / f"{label}.json"
    _write_json(inventory_path, inventory_payload)
    return {
        "input": _examples_relative(source_path),
        "inventory": _sample_relative(inventory_path),
        "schema": inventory_payload["schema"],
        "source_kind": inventory_payload["source_kind"],
        "asset_count": len(inventory_payload["assets"]),
        "asset_counts": _asset_counts(inventory),
    }


def _select_first(inventory: object, kind: str, *, require_payload: bool = False) -> object:
    assets = inventory.by_kind(kind)  # type: ignore[attr-defined]
    for asset in assets:
        if not asset.can_extract:
            continue
        if require_payload and not asset.payload_available:
            continue
        return asset
    requirement = "available payload" if require_payload else "extractable"
    raise RuntimeError(f"no {requirement} {kind} asset found")


def _save_schlib(extracted: object, filename: str) -> str:
    if extracted.schlib is None:  # type: ignore[attr-defined]
        raise RuntimeError("selected asset did not produce a SchLib")
    output_path = SELECTED_DIR / filename
    extracted.schlib.save(output_path)  # type: ignore[attr-defined]
    return _sample_relative(output_path)


def _save_pcblib(extracted: object, filename: str) -> str:
    if extracted.pcblib is None:  # type: ignore[attr-defined]
        raise RuntimeError("selected asset did not produce a PcbLib")
    output_path = SELECTED_DIR / filename
    extracted.pcblib.save(output_path)  # type: ignore[attr-defined]
    return _sample_relative(output_path)


def _write_payload(extracted: object, filename: str) -> dict[str, object]:
    payload = extracted.payload  # type: ignore[attr-defined]
    if payload is None:
        raise RuntimeError("selected asset did not produce payload bytes")
    output_path = SELECTED_DIR / filename
    output_path.write_bytes(payload)
    return {
        "path": _sample_relative(output_path),
        "byte_count": output_path.stat().st_size,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "suggested_filename": extracted.filename,  # type: ignore[attr-defined]
    }


def main() -> None:
    _reset_outputs()

    schdoc = AltiumSchDoc(INPUT_SCHDOC)
    schlib = AltiumSchLib(INPUT_SCHLIB)
    pcbdoc = AltiumPcbDoc.from_file(INPUT_PCBDOC)
    pcblib = AltiumPcbLib.from_file(INPUT_PCBLIB)

    schdoc_inventory = schdoc.asset_inventory()
    schlib_inventory = schlib.asset_inventory()
    pcbdoc_inventory = pcbdoc.asset_inventory(include_hashes=True)
    pcblib_inventory = pcblib.asset_inventory(include_hashes=True)

    schdoc_symbol = _select_first(schdoc_inventory, "sch_symbol")
    schlib_symbol = _select_first(schlib_inventory, "sch_symbol")
    pcbdoc_footprint = _select_first(pcbdoc_inventory, "pcb_footprint")
    pcblib_footprint = _select_first(pcblib_inventory, "pcb_footprint")
    pcbdoc_model = _select_first(
        pcbdoc_inventory,
        "embedded_model",
        require_payload=True,
    )

    schdoc_symbol_extracted = schdoc.extract_asset(schdoc_symbol.ref)
    schlib_symbol_extracted = schlib.extract_asset(schlib_symbol.ref)
    pcbdoc_footprint_extracted = pcbdoc.extract_asset(pcbdoc_footprint.ref)
    pcblib_footprint_extracted = pcblib.extract_asset(pcblib_footprint.ref)
    pcbdoc_model_extracted = pcbdoc.extract_asset(pcbdoc_model.ref)

    selected = {
        "schdoc_symbol": {
            "name": schdoc_symbol.name,
            "kind": schdoc_symbol.kind,
            "ref_key": schdoc_symbol.ref.key,
            "suggested_filename": schdoc_symbol_extracted.filename,
            "path": _save_schlib(
                schdoc_symbol_extracted,
                "schdoc_symbol.SchLib",
            ),
        },
        "schlib_symbol": {
            "name": schlib_symbol.name,
            "kind": schlib_symbol.kind,
            "ref_key": schlib_symbol.ref.key,
            "suggested_filename": schlib_symbol_extracted.filename,
            "path": _save_schlib(
                schlib_symbol_extracted,
                "schlib_symbol.SchLib",
            ),
        },
        "pcbdoc_footprint": {
            "name": pcbdoc_footprint.name,
            "kind": pcbdoc_footprint.kind,
            "ref_key": pcbdoc_footprint.ref.key,
            "suggested_filename": pcbdoc_footprint_extracted.filename,
            "path": _save_pcblib(
                pcbdoc_footprint_extracted,
                "pcbdoc_footprint.PcbLib",
            ),
        },
        "pcblib_footprint": {
            "name": pcblib_footprint.name,
            "kind": pcblib_footprint.kind,
            "ref_key": pcblib_footprint.ref.key,
            "suggested_filename": pcblib_footprint_extracted.filename,
            "path": _save_pcblib(
                pcblib_footprint_extracted,
                "pcblib_footprint.PcbLib",
            ),
        },
        "pcbdoc_model": {
            "name": pcbdoc_model.name,
            "kind": pcbdoc_model.kind,
            "ref_key": pcbdoc_model.ref.key,
            **_write_payload(
                pcbdoc_model_extracted,
                "pcbdoc_model.step",
            ),
        },
    }

    manifest = {
        "schema": "altium_monkey.examples.extractable_asset_inventory.a0",
        "inventory_schema": "altium_monkey.extractable_assets.a0",
        "sources": {
            "schdoc": _inventory_summary(
                label="schdoc",
                source_path=INPUT_SCHDOC,
                inventory=schdoc_inventory,
            ),
            "schlib": _inventory_summary(
                label="schlib",
                source_path=INPUT_SCHLIB,
                inventory=schlib_inventory,
            ),
            "pcbdoc": _inventory_summary(
                label="pcbdoc",
                source_path=INPUT_PCBDOC,
                inventory=pcbdoc_inventory,
            ),
            "pcblib": _inventory_summary(
                label="pcblib",
                source_path=INPUT_PCBLIB,
                inventory=pcblib_inventory,
            ),
        },
        "selected": selected,
    }
    _write_json(MANIFEST_PATH, manifest)

    print("Inventoried sources: 4")
    print(f"SchDoc symbols: {manifest['sources']['schdoc']['asset_counts']['sch_symbol']}")
    print(f"SchLib symbols: {manifest['sources']['schlib']['asset_counts']['sch_symbol']}")
    print(
        "PcbDoc footprints: "
        f"{manifest['sources']['pcbdoc']['asset_counts']['pcb_footprint']}"
    )
    print(
        "PcbLib footprints: "
        f"{manifest['sources']['pcblib']['asset_counts']['pcb_footprint']}"
    )
    print(f"Wrote manifest: {_sample_relative(MANIFEST_PATH)}")


if __name__ == "__main__":
    main()
