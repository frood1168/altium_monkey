from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from altium_monkey import (
    AltiumComponentPlacement,
    AltiumCopperMaterialSpec,
    AltiumDielectricMaterialSpec,
    AltiumLayerPair,
    AltiumLayerStackDocument,
    AltiumPcbDoc,
    AltiumRigidStackRowSpec,
    AltiumStackupRoughnessModel,
    AltiumStackupSettings,
    PcbDocBuilder,
)

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_PCBDOC = OUTPUT_DIR / "pcbdoc_create_jlcpcb_rigid_stack.PcbDoc"
OUTPUT_STACKUP = OUTPUT_DIR / "pcbdoc_create_jlcpcb_rigid_stack.stackup"
OUTPUT_STACKUPX = OUTPUT_DIR / "pcbdoc_create_jlcpcb_rigid_stack.stackupx"
OUTPUT_MANIFEST = OUTPUT_DIR / "jlcpcb_rigid_stack_manifest.json"

STACK_NAME = "JLCPCB 8L 1.2mm 1oz JLC081211-1080"
SOURCE_REFERENCE = "JLCPCB JLC081211-1080 8-layer 1.2mm stackup"


class LayerSignature(TypedDict):
    stack_index: int
    display_name: str
    family: str
    copper_thickness_mils: float | None
    dielectric_height_mils: float | None
    dielectric_constant: float | None
    dielectric_loss_tangent: float | None
    dielectric_material: str
    dielectric_type: int | None
    component_placement: int | None
    property_values: dict[str, str]


class LayerPairSignature(TypedDict):
    pair_index: int
    low_layer_token: str
    high_layer_token: str
    drill_pair_type_raw: int | None
    is_backdrill: bool | None


class StackSignature(TypedDict):
    layers: list[LayerSignature]
    layer_pairs: list[LayerPairSignature]


STACKUP_SETTINGS = AltiumStackupSettings(
    roughness_model=AltiumStackupRoughnessModel.MODIFIED_HAMMERSTAD,
    roughness_factor_model_sr="1um",
    roughness_factor_model_rf="2%",
    copper_resistance="17.24nohm",
    via_plating_thickness="18um",
    ambient_temperature="20C",
    temperature_rise="50C",
)

COPPER_FOIL = AltiumCopperMaterialSpec(
    weight="1oz",
    process="ED",
    manufacturer="Altium Designer",
    description="Copper Foil",
    copper_orientation=0,
)

NP_155F_1080 = AltiumDielectricMaterialSpec(
    name="NP-155F",
    construction="1080",
    resin="67%",
    frequency="1GHz",
    dielectric_constant=3.91,
    loss_tangent=0.02,
    glass_transition_temperature="150C",
    manufacturer="Nan Ya Plastics",
)

NP_155F_3313 = AltiumDielectricMaterialSpec(
    name="NP-155F",
    construction="3313",
    resin="57%",
    frequency="1GHz",
    dielectric_constant=4.1,
    loss_tangent=0.02,
    glass_transition_temperature="150C",
    manufacturer="Nan Ya Plastics",
)

NP_155F_CORE = AltiumDielectricMaterialSpec(
    name="NP-155F",
    construction="Core",
    frequency="1GHz",
    dielectric_constant=4.36,
    loss_tangent=0.02,
    glass_transition_temperature="150C",
    manufacturer="Nan Ya Plastics",
)

SOLDER_RESIST = AltiumDielectricMaterialSpec(
    name="Solder Resist",
    dielectric_constant=3.8,
)


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _solder_mask(name: str) -> AltiumRigidStackRowSpec:
    return AltiumRigidStackRowSpec.solder_mask(
        name,
        thickness_mils=0.6,
        material=SOLDER_RESIST,
    )


def _copper(
    name: str,
    thickness_mm: float,
    component_placement: AltiumComponentPlacement,
) -> AltiumRigidStackRowSpec:
    return AltiumRigidStackRowSpec.copper(
        name,
        thickness_mm=thickness_mm,
        component_placement=component_placement,
        material=COPPER_FOIL,
    )


def _prepreg(
    name: str,
    thickness_mm: float,
    material: AltiumDielectricMaterialSpec,
) -> AltiumRigidStackRowSpec:
    return AltiumRigidStackRowSpec.prepreg(
        name,
        thickness_mm=thickness_mm,
        material=material,
    )


def _core(name: str, thickness_mm: float):
    return AltiumRigidStackRowSpec.core(
        name,
        thickness_mm=thickness_mm,
        material=NP_155F_CORE,
    )


def _build_jlcpcb_stack() -> AltiumLayerStackDocument:
    return AltiumLayerStackDocument.from_rigid_layer_rows(
        name=STACK_NAME,
        rows=(
            AltiumRigidStackRowSpec.overlay("Top Overlay"),
            _solder_mask("Top Solder"),
            _copper("Top Layer", 0.035, AltiumComponentPlacement.BODY_UP),
            _prepreg("Dielectric 1", 0.069, NP_155F_1080),
            _copper("Inner Layer 1", 0.03, AltiumComponentPlacement.NONE),
            _core("Dielectric 2", 0.15),
            _copper("Inner Layer 2", 0.03, AltiumComponentPlacement.NONE),
            _prepreg("Dielectric 3", 0.092, NP_155F_3313),
            _prepreg("Dielectric 4", 0.092, NP_155F_3313),
            _copper("Inner Layer 3", 0.03, AltiumComponentPlacement.NONE),
            _core("Dielectric 5", 0.15),
            _copper("Inner Layer 4", 0.03, AltiumComponentPlacement.NONE),
            _prepreg("Dielectric 6", 0.092, NP_155F_3313),
            _prepreg("Dielectric 7", 0.092, NP_155F_3313),
            _copper("Inner Layer 5", 0.03, AltiumComponentPlacement.NONE),
            _core("Dielectric 8", 0.15),
            _copper("Inner Layer 6", 0.03, AltiumComponentPlacement.NONE),
            _prepreg("Dielectric 9", 0.069, NP_155F_1080),
            _copper("Bottom Layer", 0.035, AltiumComponentPlacement.BODY_DOWN),
            _solder_mask("Bottom Solder"),
            AltiumRigidStackRowSpec.overlay("Bottom Overlay"),
        ),
        layer_pairs=(
            AltiumLayerPair(
                0,
                "TOP",
                "BOTTOM",
                drill_pair_type_raw=0,
                is_backdrill=False,
            ),
        ),
        stackup_settings=STACKUP_SETTINGS,
    )


def _normalized_number(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    return round(float(value), 9)


def _property_values(properties: tuple[tuple[str, str, str], ...]) -> dict[str, str]:
    return {name.lower(): value for name, _type_name, value in properties}


def _stack_signature(document: AltiumLayerStackDocument) -> StackSignature:
    stack = document.physical_stacks[0]
    layers: list[LayerSignature] = [
        {
            "stack_index": layer.stack_index,
            "display_name": layer.display_name,
            "family": layer.family,
            "copper_thickness_mils": _normalized_number(layer.copper_thickness_mils),
            "dielectric_height_mils": _normalized_number(layer.dielectric_height_mils),
            "dielectric_constant": _normalized_number(layer.dielectric_constant),
            "dielectric_loss_tangent": _normalized_number(
                layer.dielectric_loss_tangent
            ),
            "dielectric_material": (
                "" if layer.family == "copper" else layer.dielectric_material
            ),
            "dielectric_type": layer.dielectric_type,
            "component_placement": layer.component_placement,
            "property_values": (
                {}
                if layer.family == "copper"
                else _property_values(layer.stackupx_properties)
            ),
        }
        for layer in stack.layers
    ]
    layer_pairs: list[LayerPairSignature] = [
        LayerPairSignature(
            pair_index=pair.pair_index,
            low_layer_token=pair.low_layer_token,
            high_layer_token=pair.high_layer_token,
            drill_pair_type_raw=pair.drill_pair_type_raw,
            is_backdrill=pair.is_backdrill,
        )
        for pair in document.layer_pairs
    ]
    return {"layers": layers, "layer_pairs": layer_pairs}


def build_outputs(
    pcbdoc_path: Path = OUTPUT_PCBDOC,
    stackup_path: Path = OUTPUT_STACKUP,
    stackupx_path: Path = OUTPUT_STACKUPX,
    manifest_path: Path = OUTPUT_MANIFEST,
) -> tuple[Path, Path, Path, Path]:
    pcbdoc_path.parent.mkdir(parents=True, exist_ok=True)

    authored_stack = _build_jlcpcb_stack()
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
        raise RuntimeError("Generated JLCPCB stack readback did not match")

    copper_layers = [
        layer["display_name"]
        for layer in signatures["pcbdoc_readback"]["layers"]
        if layer["family"] == "copper"
    ]
    dielectric_layers = [
        layer["display_name"]
        for layer in signatures["pcbdoc_readback"]["layers"]
        if layer["family"] == "dielectric"
    ]
    manifest = {
        "source_reference": SOURCE_REFERENCE,
        "output_pcbdoc": _relative_to_examples(pcbdoc_path),
        "output_stackup": _relative_to_examples(stackup_path),
        "output_stackupx": _relative_to_examples(stackupx_path),
        "semantic_match": semantic_match,
        "copper_layers": copper_layers,
        "dielectric_layers": dielectric_layers,
        "stack_names": {
            "authored": authored_stack.physical_stacks[0].display_name,
            "pcbdoc_readback": pcbdoc_stack.physical_stacks[0].display_name,
            "stackup_readback": stackup_stack.physical_stacks[0].display_name,
            "stackupx_readback": stackupx_stack.physical_stacks[0].display_name,
        },
        "stackup_attributes": {
            "authored": dict(authored_stack.stackup_attributes),
            "pcbdoc_readback": dict(pcbdoc_stack.stackup_attributes),
            "stackup_readback": dict(stackup_stack.stackup_attributes),
            "stackupx_readback": dict(stackupx_stack.stackup_attributes),
        },
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
    print(f"Wrote {pcbdoc_path}")
    print(f"Wrote {stackup_path}")
    print(f"Wrote {stackupx_path}")
    print(f"Wrote {manifest_path}")
    print(f"Semantic match: {manifest['semantic_match']}")
    print(f"Copper layers: {', '.join(manifest['copper_layers'])}")
    print(f"Dielectric rows: {len(manifest['dielectric_layers'])}")


if __name__ == "__main__":
    main()
