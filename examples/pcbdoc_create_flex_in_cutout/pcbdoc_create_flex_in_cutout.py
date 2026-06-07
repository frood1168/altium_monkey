from __future__ import annotations

import json
from pathlib import Path
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
sys.path.insert(0, str(EXAMPLES_ROOT))

from _pcbdoc_rigid_flex_authoring import (  # noqa: E402
    add_recreation_primitives,
    build_recreation_document,
    recreation_board_outline_mils,
    recreation_reference_stackup_path,
    recreation_reference_stackupx_path,
    write_case_outputs,
)

SPEC_NAME = "flex_in_cutout"
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_flex_in_cutout.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_flex_in_cutout.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_flex_in_cutout.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "flex_in_cutout_manifest.json"


def build_outputs() -> tuple[Path, Path, Path, Path]:
    outputs = write_case_outputs(
        build_recreation_document(SPEC_NAME),
        pcbdoc_path=OUTPUT_PCBDOC,
        stackup_path=OUTPUT_STACKUP,
        stackupx_path=OUTPUT_STACKUPX,
        manifest_path=OUTPUT_MANIFEST,
        board_outline_mils=recreation_board_outline_mils(SPEC_NAME),
        examples_root=EXAMPLES_ROOT,
        add_primitives=lambda builder: add_recreation_primitives(builder, SPEC_NAME),
        reference_stackup_path=recreation_reference_stackup_path(SPEC_NAME),
        reference_stackupx_path=recreation_reference_stackupx_path(SPEC_NAME),
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
    print(f"Mode: {readback['rigid_flex_mode']}")
    print(f"Substacks: {len(readback['substacks'])}")
    print(f"Board regions: {len(readback['regions'])}")
    print(f"Board cutouts: {manifest['pcbdoc_geometry']['board_cutout_count']}")
    print(
        "Bend radii: "
        + ", ".join(
            str(radius)
            for region in readback["regions"]
            for radius in region["bend_radii_mils"]
        )
    )


if __name__ == "__main__":
    main()
