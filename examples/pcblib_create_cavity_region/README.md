# pcblib_create_cavity_region

Create a PcbLib footprint with a Mechanical 1 cavity definition region and an
embedded STEP model.

## What It Shows

1. `AltiumPcbLib.add_footprint(...)`
2. `AltiumPcbLib.add_embedded_model(...)`
3. `AltiumPcbFootprint.add_pad(...)`
4. `AltiumPcbFootprint.add_region(...)`
5. `PcbRegionKind.CAVITY_DEFINITION`
6. `cavity_height_mils`
7. `AltiumPcbFootprint.add_embedded_3d_model(...)`
8. Reopening the generated PcbLib to verify the native region and embedded
   model contracts

## Run

From the repository root:

```powershell
uv run python examples\pcblib_create_cavity_region\pcblib_create_cavity_region.py
```

## Output

```text
examples/pcblib_create_cavity_region/output/pcblib_create_cavity_region.PcbLib
examples/pcblib_create_cavity_region/output/pcblib_create_cavity_region.json
```
