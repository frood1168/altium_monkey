from __future__ import annotations

import json
from pathlib import Path
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
sys.path.insert(0, str(EXAMPLES_ROOT))

from _pcbdoc_rigid_flex_authoring import (  # noqa: E402
    add_flex_stiffener_primitives,
    build_flex_stiffener_document,
    flex_stiffener_board_outline_mils,
    flex_stiffener_reference_stackup_path,
    flex_stiffener_reference_stackupx_path,
    write_case_outputs,
)

OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_flex_stiffener.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_flex_stiffener.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_flex_stiffener.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "flex_stiffener_manifest.json"


def build_outputs() -> tuple[Path, Path, Path, Path]:
    outputs = write_case_outputs(
        build_flex_stiffener_document(),
        pcbdoc_path=OUTPUT_PCBDOC,
        stackup_path=OUTPUT_STACKUP,
        stackupx_path=OUTPUT_STACKUPX,
        manifest_path=OUTPUT_MANIFEST,
        board_outline_mils=flex_stiffener_board_outline_mils(),
        examples_root=EXAMPLES_ROOT,
        add_primitives=add_flex_stiffener_primitives,
        reference_stackup_path=flex_stiffener_reference_stackup_path(),
        reference_stackupx_path=flex_stiffener_reference_stackupx_path(),
    )
    return (
        outputs.pcbdoc_path,
        outputs.stackup_path,
        outputs.stackupx_path,
        outputs.manifest_path,
    )


def main() -> None:
    pcbdoc_path, stackup_path, stackupx_path, manifest_path = build_outputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    readback = manifest["pcbdoc_readback"]
    print(f"Wrote {pcbdoc_path}")
    print(f"Wrote {stackup_path}")
    print(f"Wrote {stackupx_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(f"Substacks: {len(readback['substacks'])}")
    print(f"Board regions: {len(readback['regions'])}")
    print(f"Branches: {len(readback['branches'])}")
    print(f"Stiffener layers: {', '.join(readback['stiffener_layers'])}")
    print(f"Board cutouts: {manifest['pcbdoc_geometry']['board_cutout_count']}")
    print(f"Region primitives: {manifest['pcbdoc_geometry']['region_count']}")


if __name__ == "__main__":
    main()
