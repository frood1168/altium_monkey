# embedded_asset_inventory

Inventory embedded PCB/PcbLib binary assets without writing every payload.

This is the focused embedded-asset API for preview, dedupe, import dry-runs,
and selective payload extraction. Use `extractable_asset_inventory` when the
workflow also needs logical assets such as footprints or schematic symbols.

## What It Shows

1. `AltiumPcbDoc.embedded_asset_inventory(...)`
2. `AltiumPcbLib.embedded_asset_inventory(...)`
3. `EmbeddedAssetInventory.to_dict()`
4. `get_embedded_model_payload(index)`
5. `get_embedded_font_payload(index)`
6. PcbLib `Library/EmbeddedFonts` reporting as opaque metadata

## Run

From the repository root:

```powershell
uv run python examples\embedded_asset_inventory\embedded_asset_inventory.py
```

## Output

The script writes:

```text
examples/embedded_asset_inventory/output/embedded_asset_inventory_manifest.json
examples/embedded_asset_inventory/output/inventories/pcbdoc.json
examples/embedded_asset_inventory/output/inventories/pcblib.json
examples/embedded_asset_inventory/output/selected/pcbdoc_model.step
examples/embedded_asset_inventory/output/selected/pcbdoc_font.ttf
examples/embedded_asset_inventory/output/selected/pcblib_model.step
```
