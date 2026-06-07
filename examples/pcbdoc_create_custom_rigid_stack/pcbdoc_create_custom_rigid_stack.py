from __future__ import annotations

import json
from pathlib import Path

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import (
    AltiumLayerStackDocument,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_custom_rigid_stack.PcbDoc"
OUTPUT_MANIFEST = OUTPUT_DIR / "custom_rigid_stack_manifest.json"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _build_custom_stack() -> AltiumLayerStackDocument:
    return AltiumLayerStackDocument.from_rigid_stack(
        name="public-custom-rigid-4",
        copper_layers=(
            AltiumRigidCopperLayerSpec("TOP_SIG", copper_thickness_mils=1.2),
            AltiumRigidCopperLayerSpec("L2_GND", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L3_PWR", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("BOT_SIG", copper_thickness_mils=1.2),
        ),
        dielectrics_between=(
            AltiumRigidDielectricLayerSpec(
                "PP_TOP",
                thickness_mils=3.1,
                dielectric_constant=3.7,
                material="PP-TEST",
                dielectric_type=2,
                loss_tangent=0.019,
            ),
            AltiumRigidDielectricLayerSpec(
                "CORE_TEST",
                thickness_mils=41.0,
                dielectric_constant=4.2,
                material="FR4-TEST",
                dielectric_type=0,
            ),
            AltiumRigidDielectricLayerSpec(
                "PP_BOTTOM",
                thickness_mils=3.1,
                dielectric_constant=3.7,
                material="PP-TEST",
                dielectric_type=2,
                loss_tangent=0.019,
            ),
        ),
    )


def _semantic_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    stacks: list[dict[str, object]] = []
    for stack in document.physical_stacks:
        stacks.append(
            {
                "display_name": stack.display_name,
                "source_family": stack.source_family,
                "is_flex": stack.is_flex,
                "layers": [
                    {
                        "stack_index": layer.stack_index,
                        "display_name": layer.display_name,
                        "family": layer.family,
                        "copper_thickness_mils": layer.copper_thickness_mils,
                        "dielectric_height_mils": layer.dielectric_height_mils,
                        "dielectric_constant": layer.dielectric_constant,
                        "dielectric_loss_tangent": layer.dielectric_loss_tangent,
                        "dielectric_material": layer.dielectric_material,
                        "dielectric_type": layer.dielectric_type,
                        "legacy_layer_id": layer.legacy_layer_id,
                    }
                    for layer in stack.layers
                    if layer.family in {"copper", "dielectric"}
                ],
            }
        )
    return {
        "active_stack_ref": document.active_stack_ref,
        "physical_stacks": stacks,
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

    authored_stack = _build_custom_stack()
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(authored_stack)
    builder.save(output_path)

    readback_stack = AltiumLayerStackDocument.from_pcbdoc(
        AltiumPcbDoc.from_file(output_path)
    )
    authored_signature = _semantic_signature(authored_stack)
    readback_signature = _semantic_signature(readback_stack)
    semantic_match = authored_signature == readback_signature
    if not semantic_match:
        raise RuntimeError("Reparsed PcbDoc layer stack did not match authored stack")

    resolved = readback_stack.to_resolved_layer_stack()
    manifest = {
        "output_pcbdoc": _relative_to_examples(output_path),
        "semantic_match": semantic_match,
        "authored": authored_signature,
        "readback": readback_signature,
        "resolved": {
            "standard_layer_names": dict(resolved.standard_layer_names),
            "inner_signal_layers": list(resolved.inner_signal_layers),
            "drill_pair_layer_names": list(resolved.drill_pair_layer_names),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path, manifest_path


def main() -> None:
    output_path, manifest_path = build_pcbdoc()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layers = manifest["readback"]["physical_stacks"][0]["layers"]
    copper_layers = [layer for layer in layers if layer["family"] == "copper"]
    print(f"Wrote {output_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(
        f"Copper layers: {', '.join(layer['display_name'] for layer in copper_layers)}"
    )


if __name__ == "__main__":
    main()
