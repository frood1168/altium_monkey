# Embedded PCB Assets

Use embedded asset inventories when a tool needs to preview PcbDoc/PcbLib
binary payloads before writing files or deciding what to import.

Current public Python containers:

1. `AltiumPcbDoc.embedded_asset_inventory(...)`
2. `AltiumPcbLib.embedded_asset_inventory(...)`

The focused embedded inventory is narrower than
`asset_inventory(...)`. It only covers PCB/PcbLib embedded binary payloads:

1. PcbDoc embedded 3D models.
2. PcbDoc embedded TrueType fonts.
3. PcbLib embedded 3D models.
4. PcbLib preserved `Library/EmbeddedFonts` bytes as opaque assets.

Use `asset_inventory(...)` when a consumer also needs selectable logical assets
such as footprints or schematic symbols.

## Preview Pattern

```python
inventory = pcbdoc.embedded_asset_inventory(include_hashes=True)

for model in inventory.models:
    print(model.extraction_filename, model.payload_available, model.payload_sha256)

model = next((item for item in inventory.models if item.payload_available), None)
if model is None:
    raise RuntimeError("no available embedded model payload found")
payload = pcbdoc.get_embedded_model_payload(model.index)
```

Summary APIs do not write files. Payload access is explicit and indexed.

## JSON Contract

`EmbeddedAssetInventory.to_dict()` emits the
`altium_monkey.pcb.embedded_assets.a0` contract documented in
[`embedded_assets_a0.schema.json`](../schemas/altium_monkey/embedded_assets_a0.schema.json).

The JSON shape keeps dedicated arrays for `models`, `fonts`, and
`opaque_assets`. Sizes are numbers, flags are booleans, absent hashes are
`null`, and model references remain structured arrays.

A0 references are emitted only under model summaries, so
`references[].asset_kind` is constrained to `model`. Other reference kinds
should be added in a future schema revision if typed font or opaque-asset
backreferences become public.

## Payload Availability

`payload_available` means the payload stream exists and can be returned by the
current object. Hashes are emitted only when `include_hashes=True` and the
payload is available.

Corrupt supported payloads remain listed for review but report
`payload_available=False`, `payload_sha256=None`, and no decompressed size.
Selecting that payload still raises a clear decompression error.

PcbLib embedded fonts are currently reported as opaque preserved bytes instead
of typed font records. Consumers should use `support_status` and `reason` for
display and import decisions.

## Example

See
[`embedded_asset_inventory`](../../examples/embedded_asset_inventory/README.md)
for a complete preview workflow that writes PcbDoc and PcbLib embedded
inventories, validates the schema shape, and extracts one selected model/font
payload by direct embedded asset index.
