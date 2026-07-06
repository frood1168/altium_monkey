# pcb_orientation_sync

A two-step workflow for keeping PCB component orientations in sync with
schematic orientation changes. Two scripts live here:

| Script | Role |
|--------|------|
| `pcb_orientation_snapshot.py` | Capture a **before** snapshot of schematic + PCB component orientations to JSON. |
| `pcb_orientation_sync.py` | Diff the before-snapshot against the current schematic and rotate matching PCB components (and their designator/comment overlay text) by the computed deltas. |

## Workflow

1. Snapshot the baseline **before** touching the schematic:
   ```powershell
   uv run python examples\pcb_orientation_sync\pcb_orientation_snapshot.py PROJECT.PrjPcb
   ```
2. Normalize component orientations in the schematic (e.g. resistors/caps/inductors to 0°/90°).
3. Apply the matching rotations to the PCB:
   ```powershell
   uv run python examples\pcb_orientation_sync\pcb_orientation_sync.py PROJECT.PrjPcb
   ```
   With no `--before`, the sync step auto-finds the most recent `snapshot*.json`
   in `output/`.

## Arg-free demo

Both scripts run with no arguments against the bundled `rt_super_c1` project:

```powershell
uv run python examples\pcb_orientation_sync\pcb_orientation_snapshot.py
uv run python examples\pcb_orientation_sync\pcb_orientation_sync.py
```

The snapshot writes `output/snapshot.json` (the capture time is recorded inside
the JSON); the sync step reads it and writes the modified PcbDoc plus a report.

## Inputs

```text
examples/assets/projects/rt_super_c1/RT_SUPER_C1.PrjPcb
examples/assets/projects/rt_super_c1/RT_SUPER_C1.SchDoc
examples/assets/projects/rt_super_c1/RT_SUPER_C1.PCBdoc
```

## Output

```text
examples/pcb_orientation_sync/output/snapshot.json                         # snapshot step
examples/pcb_orientation_sync/output/RT_SUPER_C1_synced.PCBdoc             # sync step
examples/pcb_orientation_sync/output/RT_SUPER_C1_synced.sync_report.json   # sync step
```

The snapshot JSON records, per component, schematic orientation/mirroring and
PCB location, rotation, layer, and designator-text position/font/size.
