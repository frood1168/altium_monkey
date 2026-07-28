from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from altium_monkey import AltiumPcbDoc, AltiumPcbLib, embedded_asset_schema_id


SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = SAMPLE_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
INPUT_PCBDOC = ASSETS_DIR / "projects" / "rt_super_c1" / "RT_SUPER_C1.PCBdoc"
INPUT_PCBLIB = ASSETS_DIR / "pcblib" / "RT_SUPER_C1.PcbLib"
OUTPUT_DIR = SAMPLE_DIR / "output"
INVENTORY_DIR = OUTPUT_DIR / "inventories"
SELECTED_DIR = OUTPUT_DIR / "selected"
MANIFEST_PATH = OUTPUT_DIR / "embedded_asset_inventory_manifest.json"


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


def _inventory_summary(
    *,
    label: str,
    source_path: Path,
    inventory: object,
) -> dict[str, object]:
    payload = inventory.to_dict()  # type: ignore[attr-defined]
    inventory_path = INVENTORY_DIR / f"{label}.json"
    _write_json(inventory_path, payload)
    return {
        "input": _examples_relative(source_path),
        "inventory": _sample_relative(inventory_path),
        "schema": payload["schema"],
        "source_kind": payload["source_kind"],
        "model_count": len(payload["models"]),
        "font_count": len(payload["fonts"]),
        "opaque_count": len(payload["opaque_assets"]),
    }


def _write_payload(
    path: Path,
    payload: bytes,
    *,
    suggested_filename: str,
) -> dict[str, object]:
    path.write_bytes(payload)
    return {
        "path": _sample_relative(path),
        "byte_count": path.stat().st_size,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "suggested_filename": suggested_filename,
    }


def _first_available_asset(items: Iterable[Any], label: str) -> Any:
    for item in items:
        if item.payload_available:
            return item
    raise RuntimeError(f"no available {label} payload found")


def main() -> None:
    _reset_outputs()

    pcbdoc = AltiumPcbDoc.from_file(INPUT_PCBDOC)
    pcblib = AltiumPcbLib.from_file(INPUT_PCBLIB)

    pcbdoc_inventory = pcbdoc.embedded_asset_inventory(include_hashes=True)
    pcblib_inventory = pcblib.embedded_asset_inventory(include_hashes=True)

    pcbdoc_model = _first_available_asset(
        pcbdoc_inventory.models,
        "PcbDoc embedded model",
    )
    pcbdoc_font = _first_available_asset(
        pcbdoc_inventory.fonts,
        "PcbDoc embedded font",
    )
    pcblib_model = _first_available_asset(
        pcblib_inventory.models,
        "PcbLib embedded model",
    )

    selected = {
        "pcbdoc_model": {
            "source": "pcbdoc",
            "name": pcbdoc_model.name,
            **_write_payload(
                SELECTED_DIR / "pcbdoc_model.step",
                pcbdoc.get_embedded_model_payload(pcbdoc_model.index),
                suggested_filename=pcbdoc_model.extraction_filename,
            ),
        },
        "pcbdoc_font": {
            "source": "pcbdoc",
            "name": pcbdoc_font.family_name,
            **_write_payload(
                SELECTED_DIR / "pcbdoc_font.ttf",
                pcbdoc.get_embedded_font_payload(pcbdoc_font.index),
                suggested_filename=pcbdoc_font.extraction_filename,
            ),
        },
        "pcblib_model": {
            "source": "pcblib",
            "name": pcblib_model.name,
            **_write_payload(
                SELECTED_DIR / "pcblib_model.step",
                pcblib.get_embedded_model_payload(pcblib_model.index),
                suggested_filename=pcblib_model.extraction_filename,
            ),
        },
    }

    manifest = {
        "schema": "altium_monkey.examples.embedded_asset_inventory.a0",
        "inventory_schema": embedded_asset_schema_id(),
        "sources": {
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

    print("Inventoried embedded asset sources: 2")
    print(f"PcbDoc models: {manifest['sources']['pcbdoc']['model_count']}")
    print(f"PcbDoc fonts: {manifest['sources']['pcbdoc']['font_count']}")
    print(f"PcbLib models: {manifest['sources']['pcblib']['model_count']}")
    print(f"PcbLib opaque streams: {manifest['sources']['pcblib']['opaque_count']}")
    print(f"Wrote manifest: {_sample_relative(MANIFEST_PATH)}")


if __name__ == "__main__":
    main()
