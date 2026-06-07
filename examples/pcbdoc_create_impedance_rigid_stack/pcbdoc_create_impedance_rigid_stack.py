from __future__ import annotations

import json
from pathlib import Path

from altium_monkey import AltiumPcbDoc, PcbDocBuilder
from altium_monkey.altium_layer_stack_document import (
    AltiumImpedanceProfileSpec,
    AltiumLayerStackDocument,
    AltiumRigidCopperLayerSpec,
    AltiumRigidDielectricLayerSpec,
    AltiumTransmissionLineSpec,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_impedance_rigid_stack.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_impedance_rigid_stack.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_impedance_rigid_stack.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "impedance_rigid_stack_manifest.json"


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _build_impedance_stack() -> AltiumLayerStackDocument:
    return AltiumLayerStackDocument.from_rigid_stack(
        name="public-impedance-rigid-8",
        copper_layers=(
            AltiumRigidCopperLayerSpec("TOP_SIG", copper_thickness_mils=1.2),
            AltiumRigidCopperLayerSpec("L2_GND", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L3_SIG", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L4_PWR", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L5_GND", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L6_SIG", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("L7_GND", copper_thickness_mils=0.7),
            AltiumRigidCopperLayerSpec("BOT_SIG", copper_thickness_mils=1.2),
        ),
        dielectrics_between=(
            AltiumRigidDielectricLayerSpec(
                "PP_1080_TOP",
                thickness_mils=3.2,
                dielectric_constant=3.65,
                material="Megtron6-PP",
                dielectric_type=2,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "CORE_1",
                thickness_mils=7.5,
                dielectric_constant=3.45,
                material="Megtron6-Core",
                dielectric_type=0,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "PP_2116_A",
                thickness_mils=5.0,
                dielectric_constant=3.65,
                material="Megtron6-PP",
                dielectric_type=2,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "CORE_CENTER",
                thickness_mils=30.0,
                dielectric_constant=3.45,
                material="Megtron6-Core",
                dielectric_type=0,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "PP_2116_B",
                thickness_mils=5.0,
                dielectric_constant=3.65,
                material="Megtron6-PP",
                dielectric_type=2,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "CORE_2",
                thickness_mils=7.5,
                dielectric_constant=3.45,
                material="Megtron6-Core",
                dielectric_type=0,
                loss_tangent=0.004,
            ),
            AltiumRigidDielectricLayerSpec(
                "PP_1080_BOTTOM",
                thickness_mils=3.2,
                dielectric_constant=3.65,
                material="Megtron6-PP",
                dielectric_type=2,
                loss_tangent=0.004,
            ),
        ),
        impedance_profiles=(
            AltiumImpedanceProfileSpec(
                name="SE50_TOP",
                impedance="50ohm",
                tolerance="10%",
                transmission_lines=(
                    AltiumTransmissionLineSpec(
                        layer="TOP_SIG",
                        bottom_reference="L2_GND",
                        width="4.6mil",
                        tl_type_name="Surface Microstrip",
                        use_solder_mask=True,
                    ),
                ),
            ),
            AltiumImpedanceProfileSpec(
                name="SE50_L3",
                impedance="50ohm",
                tolerance="10%",
                transmission_lines=(
                    AltiumTransmissionLineSpec(
                        layer="L3_SIG",
                        top_reference="L2_GND",
                        bottom_reference="L4_PWR",
                        width="4.0mil",
                        tl_type_name="Stripline",
                    ),
                ),
            ),
            AltiumImpedanceProfileSpec(
                name="DIFF90_L6",
                profile_type="Differential",
                impedance="90ohm",
                tolerance="10%",
                transmission_lines=(
                    AltiumTransmissionLineSpec(
                        layer="L6_SIG",
                        top_reference="L5_GND",
                        bottom_reference="L7_GND",
                        is_differential=True,
                        width="4.0mil",
                        gap="6.0mil",
                        tl_type_name="Differential Stripline",
                    ),
                ),
            ),
            AltiumImpedanceProfileSpec(
                name="SE50_BOTTOM",
                impedance="50ohm",
                tolerance="10%",
                transmission_lines=(
                    AltiumTransmissionLineSpec(
                        layer="BOT_SIG",
                        top_reference="L7_GND",
                        width="4.6mil",
                        tl_type_name="Surface Microstrip",
                        use_solder_mask=True,
                    ),
                ),
            ),
        ),
    )


def _stack_signature(document: AltiumLayerStackDocument) -> dict[str, object]:
    stack = document.physical_stacks[0]
    copper_layers = [
        layer.display_name for layer in stack.layers if layer.family == "copper"
    ]
    dielectric_layers = [
        {
            "display_name": layer.display_name,
            "dielectric_material": layer.dielectric_material,
            "dielectric_height_mils": layer.dielectric_height_mils,
            "dielectric_constant": layer.dielectric_constant,
            "dielectric_loss_tangent": layer.dielectric_loss_tangent,
            "dielectric_type": layer.dielectric_type,
        }
        for layer in stack.layers
        if layer.family == "dielectric"
    ]
    return {
        "copper_layers": copper_layers,
        "dielectric_layers": dielectric_layers,
        "impedance_profiles": [
            {
                "name": profile.name,
                "profile_type": profile.profile_type,
                "impedance": profile.impedance,
                "tolerance": profile.tolerance,
                "transmission_line_count": profile.transmission_line_count,
            }
            for profile in document.impedance_profiles
        ],
        "transmission_lines": [
            {
                "layer_token": line.layer_token,
                "top_ref_token": line.top_ref_token,
                "bottom_ref_token": line.bottom_ref_token,
                "is_differential": line.is_differential,
                "width": line.width,
                "gap": line.gap,
                "tl_type_name": line.tl_type_name,
                "use_solder_mask": line.use_solder_mask,
            }
            for line in document.transmission_lines
        ],
    }


def build_outputs(
    pcbdoc_path: Path = OUTPUT_PCBDOC,
    stackup_path: Path = OUTPUT_STACKUP,
    stackupx_path: Path = OUTPUT_STACKUPX,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path, Path, Path]:
    pcbdoc_path.parent.mkdir(parents=True, exist_ok=True)

    authored_stack = _build_impedance_stack()
    builder = PcbDocBuilder()
    builder.set_layer_stack_document(authored_stack)
    builder.save(pcbdoc_path)
    authored_stack.to_stackup().write(stackup_path)
    authored_stack.to_stackupx().write(stackupx_path)

    pcbdoc_stack = AltiumLayerStackDocument.from_pcbdoc(
        AltiumPcbDoc.from_file(pcbdoc_path)
    )
    stackup_stack = AltiumLayerStackDocument.from_stackup(stackup_path)
    stackupx_stack = AltiumLayerStackDocument.from_stackupx(stackupx_path)

    signatures = {
        "authored": _stack_signature(authored_stack),
        "pcbdoc_readback": _stack_signature(pcbdoc_stack),
        "stackup_readback": _stack_signature(stackup_stack),
        "stackupx_readback": _stack_signature(stackupx_stack),
    }
    semantic_match = (
        signatures["authored"]
        == signatures["pcbdoc_readback"]
        == signatures["stackup_readback"]
        == signatures["stackupx_readback"]
    )
    if not semantic_match:
        raise RuntimeError("Generated impedance stack readback did not match")

    manifest = {
        "output_pcbdoc": _relative_to_examples(pcbdoc_path),
        "output_stackup": _relative_to_examples(stackup_path),
        "output_stackupx": _relative_to_examples(stackupx_path),
        "semantic_match": semantic_match,
        **signatures,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pcbdoc_path, stackup_path, stackupx_path, manifest_path


def main() -> None:
    pcbdoc_path, stackup_path, stackupx_path, manifest_path = build_outputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = manifest["pcbdoc_readback"]["impedance_profiles"]
    print(f"Wrote {pcbdoc_path}")
    print(f"Wrote {stackup_path}")
    print(f"Wrote {stackupx_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(f"Copper layers: {', '.join(manifest['pcbdoc_readback']['copper_layers'])}")
    print(f"Impedance profiles: {', '.join(item['name'] for item in profiles)}")


if __name__ == "__main__":
    main()
