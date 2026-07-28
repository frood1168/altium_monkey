# Extractable Assets

Use extractable asset inventories when a tool needs to preview or select one
thing from an Altium source without running a bulk extraction workflow.

Current public Python containers:

1. `AltiumPcbDoc.asset_inventory(...)`
2. `AltiumPcbLib.asset_inventory(...)`
3. `AltiumSchDoc.asset_inventory(...)`
4. `AltiumSchLib.asset_inventory(...)`

The shared pattern is:

```python
inventory = source.asset_inventory(include_hashes=True)
footprint = next(
    (item for item in inventory.by_kind("pcb_footprint") if item.can_extract),
    None,
)
if footprint is None:
    raise RuntimeError("no extractable footprint found")
extracted = source.extract_asset(footprint.ref)
extracted.pcblib.save(extracted.filename)
```

## Inventory Shape

`asset_inventory(...)` returns `AltiumAssetInventory`.

Key objects:

1. `AltiumAssetInventory`: source kind, source path, and asset summaries.
2. `AltiumAssetSummary`: display name, extractability flags, optional payload
   hash, typed details, and one `AltiumAssetRef`.
3. `AltiumAssetRef`: source-local selection handle returned by the inventory.
4. `AltiumExtractedAsset`: result for one selected asset.

Current asset kinds:

1. `embedded_model`: embedded PCB/PcbLib 3D model payload bytes.
2. `embedded_font`: embedded PcbDoc TrueType font payload bytes.
3. `opaque_embedded`: preserved embedded bytes that are not yet parsed as a
   supported typed payload.
4. `pcb_footprint`: one PCB footprint extracted as a single-footprint PcbLib.
5. `sch_symbol`: one schematic symbol extracted as a single-symbol SchLib.

`sch_image` is reserved in the in-process API vocabulary for future schematic
image inventory work. It is not valid in the
`altium_monkey.extractable_assets.a0` JSON schema until a future schema
revision adds a typed details branch for it.

## Typed Details

The public contract uses typed detail objects instead of a loose metadata map.
Counts are numbers, flags are booleans, and repeated fields are arrays.

Current detail variants:

1. `EmbeddedModelAssetDetails`: model format, asset id, sizes, embedded flag,
   and PCB object references.
2. `EmbeddedFontAssetDetails`: font style, sizes, and support status.
3. `OpaqueEmbeddedAssetDetails`: raw size, support status, and reason.
4. `PcbFootprintAssetDetails`: footprint pattern, occurrence, source library,
   component indexes/designators, pad count, and primitive count.
5. `SchSymbolAssetDetails`: display names, selected designator, library
   identity fields, pin count, object count, part count, and grouped
   designators.

Use `asset.details` for consumer logic. `asset.extras` is reserved for
non-contract annotations; A0 JSON output requires it to be an empty object.

## References

Use refs returned by the same inventory you are extracting from:

```python
symbol = next(
    (item for item in schdoc.asset_inventory().by_kind("sch_symbol") if item.can_extract),
    None,
)
if symbol is None:
    raise RuntimeError("no extractable schematic symbol found")
single_symbol = schdoc.extract_asset(symbol.ref)
single_symbol.schlib.save("selected_symbol.SchLib")
```

File-backed refs are durable through normalized `source_path` identity. Refs
from live unsaved containers carry an opaque process-local
`source_instance_id`. Live refs are valid only for the live source instance in
the current process and are not durable across reloads or serialization
boundaries.

Exact-name and index selection are still available on kind-specific helpers,
but refs are the safest automation boundary because they carry source kind,
semantic key, index, name, and source identity.

## Hashes

Pass `include_hashes=True` when a downstream tool needs payload identity:

```python
inventory = pcbdoc.asset_inventory(include_hashes=True)
models = inventory.by_kind("embedded_model")
model = next((item for item in models if item.payload_available), None)
if model is None:
    raise RuntimeError("no available embedded model payload found")
print(model.payload_sha256)
```

Hashes are emitted only for assets with direct payload bytes, such as embedded
models, embedded fonts, and opaque embedded streams. Footprints and symbols
extract as library objects, so `payload_sha256` is normally `None` for those
asset kinds.

## JSON Contract

`AltiumAssetInventory.to_dict()` emits the
`altium_monkey.extractable_assets.a0` contract documented in
[`extractable_assets_a0.schema.json`](../schemas/altium_monkey/extractable_assets_a0.schema.json).
Use that shape for CLI, preview, and UI contracts that need typed JSON values.

For a runnable workflow, see
[`extractable_asset_inventory`](../../examples/extractable_asset_inventory/README.md).
