from __future__ import annotations

import json
from pathlib import Path

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import (
    AltiumLayerPair,
    AltiumLayerStackDocument,
    AltiumRigidStackRowSpec,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_custom_rigid_stack.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_custom_rigid_stack.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_custom_rigid_stack.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "custom_rigid_stack_manifest.json"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _build_custom_stack() -> AltiumLayerStackDocument:
    return AltiumLayerStackDocument.from_rigid_layer_rows(
        name="public-custom-rigid-4",
        rows=(
            AltiumRigidStackRowSpec(
                "Top Overlay",
                "overlay",
                dielectric_height_mils=0.5,
                dielectric_material="LegendInk-TEST",
            ),
            AltiumRigidStackRowSpec(
                "Top Solder",
                "solder_mask",
                dielectric_height_mils=0.8,
                dielectric_material="LPI-Green",
            ),
            AltiumRigidStackRowSpec(
                "TOP_SIG",
                "copper",
                copper_thickness_mils=1.2,
            ),
            AltiumRigidStackRowSpec(
                "PP_TOP_1080",
                "dielectric",
                dielectric_height_mils=1.6,
                dielectric_constant=3.7,
                dielectric_material="PP-TEST",
                dielectric_type=2,
                dielectric_loss_tangent=0.019,
            ),
            AltiumRigidStackRowSpec(
                "PP_TOP_2116",
                "dielectric",
                dielectric_height_mils=1.5,
                dielectric_constant=3.7,
                dielectric_material="PP-TEST",
                dielectric_type=2,
                dielectric_loss_tangent=0.019,
            ),
            AltiumRigidStackRowSpec("L2_GND", "copper", copper_thickness_mils=0.7),
            AltiumRigidStackRowSpec(
                "CORE_TEST",
                "dielectric",
                dielectric_height_mils=41.0,
                dielectric_constant=4.2,
                dielectric_material="FR4-TEST",
                dielectric_type=0,
            ),
            AltiumRigidStackRowSpec("L3_PWR", "copper", copper_thickness_mils=0.7),
            AltiumRigidStackRowSpec(
                "PP_BOTTOM_2116",
                "dielectric",
                dielectric_height_mils=1.5,
                dielectric_constant=3.7,
                dielectric_material="PP-TEST",
                dielectric_type=2,
                dielectric_loss_tangent=0.019,
            ),
            AltiumRigidStackRowSpec(
                "PP_BOTTOM_1080",
                "dielectric",
                dielectric_height_mils=1.6,
                dielectric_constant=3.7,
                dielectric_material="PP-TEST",
                dielectric_type=2,
                dielectric_loss_tangent=0.019,
            ),
            AltiumRigidStackRowSpec(
                "BOT_SIG",
                "copper",
                copper_thickness_mils=1.2,
            ),
            AltiumRigidStackRowSpec(
                "Bottom Solder",
                "solder_mask",
                dielectric_height_mils=0.8,
                dielectric_material="LPI-Green",
            ),
            AltiumRigidStackRowSpec(
                "Bottom Overlay",
                "overlay",
                dielectric_height_mils=0.5,
                dielectric_material="LegendInk-TEST",
            ),
        ),
        layer_pairs=(AltiumLayerPair(0, "TOP", "BOTTOM"),),
    )


def _semantic_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    stacks: list[dict[str, object]] = []
    for stack in document.physical_stacks:
        stacks.append(
            {
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
        "physical_stacks": stacks,
        "layer_pairs": [
            {
                "pair_index": pair.pair_index,
                "low_layer_token": pair.low_layer_token,
                "high_layer_token": pair.high_layer_token,
            }
            for pair in document.layer_pairs
        ],
    }


def build_pcbdoc(
    output_path: Path = OUTPUT_PCBDOC,
    stackup_path: Path = OUTPUT_STACKUP,
    stackupx_path: Path = OUTPUT_STACKUPX,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path, Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    authored_stack = _build_custom_stack()
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(authored_stack)
    builder.save(output_path)
    authored_stack.to_stackup().write(stackup_path)
    authored_stack.to_stackupx().write(stackupx_path)

    readback_stack = AltiumLayerStackDocument.from_pcbdoc(
        AltiumPcbDoc.from_file(output_path)
    )
    stackup_stack = AltiumLayerStackDocument.from_stackup(stackup_path)
    stackupx_stack = AltiumLayerStackDocument.from_stackupx(stackupx_path)
    authored_signature = _semantic_signature(authored_stack)
    readback_signature = _semantic_signature(readback_stack)
    stackup_signature = _semantic_signature(stackup_stack)
    stackupx_signature = _semantic_signature(stackupx_stack)
    semantic_match = (
        authored_signature
        == readback_signature
        == stackup_signature
        == stackupx_signature
    )
    if not semantic_match:
        raise RuntimeError("Reparsed PcbDoc layer stack did not match authored stack")

    resolved = readback_stack.to_resolved_layer_stack()
    manifest = {
        "output_pcbdoc": _relative_to_examples(output_path),
        "output_stackup": _relative_to_examples(stackup_path),
        "output_stackupx": _relative_to_examples(stackupx_path),
        "semantic_match": semantic_match,
        "authored": authored_signature,
        "readback": readback_signature,
        "stackup_readback": stackup_signature,
        "stackupx_readback": stackupx_signature,
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
    return output_path, stackup_path, stackupx_path, manifest_path


def main() -> None:
    output_path, stackup_path, stackupx_path, manifest_path = build_pcbdoc()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layers = manifest["readback"]["physical_stacks"][0]["layers"]
    copper_layers = [layer for layer in layers if layer["family"] == "copper"]
    print(f"Wrote {output_path}")
    print(f"Wrote {stackup_path}")
    print(f"Wrote {stackupx_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(
        f"Copper layers: {', '.join(layer['display_name'] for layer in copper_layers)}"
    )


if __name__ == "__main__":
    main()
