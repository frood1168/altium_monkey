# extractable_asset_inventory

Inventory extractable assets from SchDoc, SchLib, PcbDoc, and PcbLib sources,
then extract one selected asset from each source by using the returned
`AltiumAssetRef`.

This is useful for preview tools, library browsers, import dry-runs, and UI
workflows that need to list what a file contains before extracting only one
symbol, footprint, or embedded payload.

## What It Shows

1. `asset_inventory(include_hashes=...)`
2. `AltiumAssetInventory.to_dict()`
3. `inventory.by_kind(...)`
4. `extract_asset(asset.ref)`
5. Extracting one SchDoc symbol as SchLib
6. Extracting one SchLib symbol as SchLib
7. Extracting one PcbDoc footprint as PcbLib
8. Extracting one PcbLib footprint as PcbLib
9. Extracting one PcbDoc embedded model payload

## Run

From the repository root:

```powershell
uv run python examples\extractable_asset_inventory\extractable_asset_inventory.py
```

## Output

The script writes:

```text
examples/extractable_asset_inventory/output/extractable_asset_inventory_manifest.json
examples/extractable_asset_inventory/output/inventories/schdoc.json
examples/extractable_asset_inventory/output/inventories/schlib.json
examples/extractable_asset_inventory/output/inventories/pcbdoc.json
examples/extractable_asset_inventory/output/inventories/pcblib.json
examples/extractable_asset_inventory/output/selected/schdoc_symbol.SchLib
examples/extractable_asset_inventory/output/selected/schlib_symbol.SchLib
examples/extractable_asset_inventory/output/selected/pcbdoc_footprint.PcbLib
examples/extractable_asset_inventory/output/selected/pcblib_footprint.PcbLib
examples/extractable_asset_inventory/output/selected/pcbdoc_model.step
```
