from __future__ import annotations

import json
from pathlib import Path

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import AltiumLayerStackDocument

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_layer_stack.PcbDoc"
OUTPUT_MANIFEST = OUTPUT_DIR / "layer_stack_manifest.json"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _semantic_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    return {
        "active_stack_ref": document.active_stack_ref,
        "physical_stacks": [
            {
                "stack_ref": stack.stack_ref,
                "display_name": stack.display_name,
                "source_family": stack.source_family,
                "is_flex": stack.is_flex,
                "layers": [
                    {
                        "stack_index": layer.stack_index,
                        "display_name": layer.display_name,
                        "family": layer.family,
                        "source_family": layer.source_family,
                        "copper_thickness_mils": layer.copper_thickness_mils,
                        "dielectric_height_mils": layer.dielectric_height_mils,
                        "legacy_layer_id": layer.legacy_layer_id,
                        "registry_ref": layer.registry_ref,
                    }
                    for layer in stack.layers
                ],
            }
            for stack in document.physical_stacks
        ],
        "substacks": [
            {
                "source_stackup_ref": substack.source_stackup_ref,
                "name": substack.name,
                "is_flex": substack.is_flex,
                "enabled_layer_refs": list(substack.enabled_layer_refs),
            }
            for substack in document.substacks
        ],
        "layer_pairs": [
            {
                "pair_index": pair.pair_index,
                "low_layer_token": pair.low_layer_token,
                "high_layer_token": pair.high_layer_token,
                "source_substack_refs": list(pair.source_substack_refs),
            }
            for pair in document.layer_pairs
        ],
    }


def build_pcbdoc(
    output_path: Path = OUTPUT_PCBDOC,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    authored_stack = AltiumLayerStackDocument.canonical_empty()
    builder = PcbDocBuilder()
    builder.board_data = authored_stack.to_canonical_empty_board_data()
    builder.save(output_path)

    readback_pcbdoc = AltiumPcbDoc.from_file(output_path)
    readback_stack = AltiumLayerStackDocument.from_pcbdoc(readback_pcbdoc)
    authored_signature = _semantic_signature(authored_stack)
    readback_signature = _semantic_signature(readback_stack)
    semantic_match = authored_signature == readback_signature
    if not semantic_match:
        raise RuntimeError("Reparsed PcbDoc layer stack did not match authored stack")

    manifest = {
        "output_pcbdoc": _relative_to_examples(output_path),
        "semantic_match": semantic_match,
        "authored": authored_signature,
        "readback": readback_signature,
        "authored_stack_entry_count": len(
            authored_stack.to_authored_board_data_entries()
        ),
        "readback_source": readback_stack.source.to_debug_json(),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path, manifest_path


def main() -> None:
    output_path, manifest_path = build_pcbdoc()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layer_count = len(manifest["authored"]["physical_stacks"][0]["layers"])
    print(f"Wrote {output_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(f"Physical layers: {layer_count}")


if __name__ == "__main__":
    main()
