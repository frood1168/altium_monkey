from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from altium_monkey import AltiumPcbDoc
from altium_monkey.altium_layer_stack_document import AltiumLayerStackDocument

SAMPLE_DIR = Path(__file__).resolve().parent
EXAMPLES_ROOT = SAMPLE_DIR.parent
INPUT_PCBDOC = EXAMPLES_ROOT / "assets" / "pcbdoc" / "blank.PcbDoc"
OUTPUT_DIR = SAMPLE_DIR / "output"
OUTPUT_JSON = OUTPUT_DIR / "layer_stack.json"
SUPPORTED_SUFFIXES = {".pcbdoc", ".stackup", ".stackupx"}


def _relative_to_examples(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXAMPLES_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _compact_summary(document: AltiumLayerStackDocument) -> dict[str, object]:
    physical_stack = document.physical_stacks[0] if document.physical_stacks else None
    layers = tuple(physical_stack.layers) if physical_stack is not None else ()
    return {
        "active_stack_ref": document.active_stack_ref,
        "physical_stack_count": len(document.physical_stacks),
        "physical_layer_count": len(layers),
        "registry_entry_count": len(document.layer_registry.entries),
        "substack_count": len(document.substacks),
        "layer_pair_count": len(document.layer_pairs),
        "board_region_count": len(document.board_regions),
        "impedance_profile_count": len(document.impedance_profiles),
        "transmission_line_count": len(document.transmission_lines),
        "top_layer": layers[0].display_name if layers else None,
        "bottom_layer": layers[-1].display_name if layers else None,
    }


def _input_kind(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix == ".pcbdoc":
        return "pcbdoc"
    if suffix == ".stackupx":
        return "stackupx"
    if suffix == ".stackup":
        return "stackup"
    supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
    raise ValueError(f"Unsupported layer-stack input '{input_path}'. Use {supported}.")


def _load_layer_stack_document(input_path: Path) -> tuple[str, AltiumLayerStackDocument]:
    input_kind = _input_kind(input_path)
    if input_kind == "pcbdoc":
        pcbdoc = AltiumPcbDoc.from_file(input_path)
        return input_kind, AltiumLayerStackDocument.from_pcbdoc(pcbdoc)
    if input_kind == "stackupx":
        return input_kind, AltiumLayerStackDocument.from_stackupx(input_path)
    return input_kind, AltiumLayerStackDocument.from_stackup(input_path)


def inspect_pcbdoc_layer_stack(
    input_path: Path = INPUT_PCBDOC,
    output_path: Path = OUTPUT_JSON,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_kind, layer_stack = _load_layer_stack_document(input_path)
    input_path_text = _relative_to_examples(input_path)
    payload = {
        "input_kind": input_kind,
        "input_path": input_path_text,
        "summary": _compact_summary(layer_stack),
        "layer_stack": layer_stack.to_debug_json(),
    }
    if input_kind == "pcbdoc":
        payload["input_pcbdoc"] = input_path_text
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect an Altium PcbDoc, .stackup, or .stackupx layer stack and "
            "write normalized JSON."
        )
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=INPUT_PCBDOC,
        help="Input .PcbDoc, .stackup, or .stackupx file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_JSON,
        help="Output JSON path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = inspect_pcbdoc_layer_stack(args.input_path, args.output)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    print(f"Input: {payload['input_path']}")
    print(f"Input kind: {payload['input_kind']}")
    print(f"Physical layers: {summary['physical_layer_count']}")
    print(f"Layer pairs: {summary['layer_pair_count']}")
    print(f"Impedance profiles: {summary['impedance_profile_count']}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
