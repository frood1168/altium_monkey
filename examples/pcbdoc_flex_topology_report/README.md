# pcbdoc_flex_topology_report

Read a packaged rigid-flex PcbDoc fixture with the source-aware layer-stack
model, and write a practical topology report.

This example complements `pcbdoc_stats`, which shows ordinary board and simple
resolved-layer-stack statistics. This sample focuses on rigid-flex questions:
which substacks exist, which board regions are assigned to each substack, which
physical layers are enabled in each region, where bend lines live, and how
advanced branch records would be queried when present.

## What It Shows

1. Loading the packaged rigid-flex fixture
2. `AltiumPcbDoc.from_file(...)`
3. `AltiumLayerStackDocument.from_pcbdoc(...)`
4. Joining `AltiumStackSubstack.source_stackup_ref` to
   `AltiumStackRegion.layerstack_id`
5. `AltiumLayerStackDocument.layers_for_substack(...)`
6. `AltiumLayerStackDocument.layers_for_board_region(...)`
7. `AltiumLayerStackDocument.board_regions_for_layerstack_id(...)`
8. `AltiumLayerStackDocument.branches_for_stack_ref(...)`
9. `ResolvedLayerStack.stack_envelope_for_substack(...)`
10. `ResolvedLayerStack.stack_envelope_for_board_region(...)`
11. Writing deterministic JSON and text reports for regression tests

The default packaged fixture is a standard rigid-flex board with two substacks,
nine board regions, four bend lines, and no advanced branch rows. The same
command can inspect a different PcbDoc to report branch topology when the input
contains Advanced Rigid-Flex branch records. Z-envelope values are substack-local
midplane values; they do not claim global board Z placement, folded branch
transforms, or cross-region alignment.

## Run

From the repository root:

```powershell
uv run python examples\pcbdoc_flex_topology_report\pcbdoc_flex_topology_report.py
```

Inspect a specific PcbDoc:

```powershell
uv run python examples\pcbdoc_flex_topology_report\pcbdoc_flex_topology_report.py path\to\board.PcbDoc --output-json output\topology.json --output-text output\topology.txt
```

## Output

```text
examples/pcbdoc_flex_topology_report/output/flex_topology_report.json
examples/pcbdoc_flex_topology_report/output/flex_topology_report.txt
```
