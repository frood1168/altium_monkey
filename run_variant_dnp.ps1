param(
    [Parameter(Mandatory)]
    [string]$ProjectDir,

    [Parameter(Mandatory)]
    [string]$Variant
)

$ErrorActionPreference = "Stop"

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prjFile) {
    Write-Error "No .PrjPcb file found in: $ProjectDir"
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"

# Update the named variant's Not Fitted set from DNP markers; output is staged
# to clean/ (the .PrjPcb plus a manifest), and we copy it back in place below.
Write-Host "Updating variant '$Variant' in $($prjFile.Name) ..."
uv run python examples/schdoc_variant_dnp/schdoc_variant_dnp.py "$($prjFile.FullName)" "$Variant"

$manifest = Get-Content (Join-Path $cleanDir "schdoc_variant_dnp_manifest.json") | ConvertFrom-Json

# Back up the original .PrjPcb before overwriting it in place.
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$historyDir = Join-Path $ProjectDir "history\$timestamp"
New-Item -ItemType Directory -Path $historyDir | Out-Null
$backupPath = Join-Path $historyDir (Split-Path $manifest.source_project -Leaf)
Copy-Item $manifest.source_project $backupPath -Force
Write-Host "Snapshotted original to history\$timestamp"
Write-Host "  $($manifest.source_project) -> $backupPath"

# Apply the updated .PrjPcb over the original (close Altium first).
Write-Host "Copying updated .PrjPcb back to its original location..."
Copy-Item $manifest.output_project $manifest.source_project -Force
Write-Host "  $($manifest.output_project) -> $($manifest.source_project)"

Write-Host "Done. To undo, restore the .PrjPcb from history\$timestamp"
