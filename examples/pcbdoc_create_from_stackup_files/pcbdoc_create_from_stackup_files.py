from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import AltiumLayerStackDocument

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
INPUT_DIR = SAMPLE_DIR / "input"
OUTPUT_DIR = SAMPLE_DIR / "output"
INPUT_STACKUP = INPUT_DIR / "rigid_source.stackup"
INPUT_STACKUPX = INPUT_DIR / "rigid_source.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "from_stackup_files_manifest.json"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _layer_signature(document: AltiumLayerStackDocument) -> list[dict[str, object]]:
    return [
        {
            "display_name": layer.display_name,
            "family": layer.family,
            "copper_thickness_mils": layer.copper_thickness_mils,
            "dielectric_height_mils": layer.dielectric_height_mils,
        }
        for stack in document.physical_stacks
        for layer in stack.layers
    ]


def _author_from_interchange(
    *,
    source_path: Path,
    source_kind: str,
    loader: Callable[[Path], AltiumLayerStackDocument],
    output_path: Path,
) -> dict[str, object]:
    imported_stack = loader(source_path)
    support = imported_stack.native_pcbdoc_write_support()
    if not support.supported:
        details = "; ".join(support.reasons) or "unsupported stack shape"
        raise RuntimeError(f"{source_kind} cannot author a new PcbDoc: {details}")

    builder = PcbDocBuilder()
    builder.set_layer_stack_document(imported_stack)
    builder.save(output_path)

    readback_stack = AltiumLayerStackDocument.from_pcbdoc(
        AltiumPcbDoc.from_file(output_path)
    )
    imported_signature = _layer_signature(imported_stack)
    readback_signature = _layer_signature(readback_stack)
    semantic_match = imported_signature == readback_signature
    if not semantic_match:
        raise RuntimeError(f"{source_kind} PcbDoc readback did not match input stack")

    return {
        "source_kind": source_kind,
        "source_path": _relative_to_examples(source_path),
        "source_origin": imported_stack.source.origin,
        "output_pcbdoc": _relative_to_examples(output_path),
        "semantic_match": semantic_match,
        "layer_count": len(readback_signature),
        "families": [layer["family"] for layer in readback_signature],
        "imported": imported_signature,
        "readback": readback_signature,
    }


def build_pcbdocs(
    output_dir: Path = OUTPUT_DIR,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stackup_output = output_dir / "from_stackup.PcbDoc"
    stackupx_output = output_dir / "from_stackupx.PcbDoc"

    cases = [
        _author_from_interchange(
            source_path=INPUT_STACKUP,
            source_kind="stackup",
            loader=AltiumLayerStackDocument.from_stackup,
            output_path=stackup_output,
        ),
        _author_from_interchange(
            source_path=INPUT_STACKUPX,
            source_kind="stackupx",
            loader=AltiumLayerStackDocument.from_stackupx,
            output_path=stackupx_output,
        ),
    ]
    manifest = {
        "cases": cases,
        "all_semantic_matches": all(case["semantic_match"] for case in cases),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return stackup_output, stackupx_output, manifest_path


def main() -> None:
    stackup_output, stackupx_output, manifest_path = build_pcbdocs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"Wrote {stackup_output}")
    print(f"Wrote {stackupx_output}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic matches: {manifest['all_semantic_matches']}")


if __name__ == "__main__":
    main()
