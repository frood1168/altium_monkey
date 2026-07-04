param(
    [Parameter(Mandatory)]
    [string]$ProjectDir
)

$ErrorActionPreference = "Stop"

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prjFile) {
    Write-Error "No .PrjPcb file found in: $ProjectDir"
    exit 1
}

# 1. Extract the parameter layout from the reference schematic.
#    Writes examples/schdoc_param_layout/clean/param_layout.toml
Write-Host "Extracting layout from reference..."
uv run python examples/schdoc_param_layout/schdoc_param_layout_extract.py examples/schdoc_param_layout/Reference_Layout.SchDoc

# 2. Stage param_layout.toml at the PROJECT ROOT, where the apply step reads it.
#    (The apply script reads <ProjectDir>\param_layout.toml, not clean\.)
$layoutSrc = "examples\schdoc_param_layout\clean\param_layout.toml"
$layoutDst = Join-Path $ProjectDir "param_layout.toml"
Write-Host "Copying param_layout.toml to $ProjectDir ..."
Copy-Item $layoutSrc $layoutDst -Force

# 3. Apply the layout in place. The apply script snapshots every touched SchDoc
#    into <ProjectDir>\History\<timestamp>\ before rewriting it atomically, so no
#    manual copy-back is required. It also writes the manifest and
#    unmatched_symbols.csv into that same History snapshot folder.
Write-Host "Applying layout to $($prjFile.Name) (in place) ..."
uv run python examples\schdoc_param_layout\schdoc_param_layout.py "$($prjFile.FullName)"

Write-Host "Done. Originals were snapshotted to $ProjectDir\History\<timestamp>\ before edit."
