param(
    [Parameter(Mandatory)]
    [string]$ProjectDir,

    [Parameter(Mandatory)]
    [string]$Variant
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProjectDir)) {
    Write-Error "Project directory not found: $ProjectDir"
    exit 1
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prjFile) {
    Write-Error "No .PrjPcb file found in: $ProjectDir"
    exit 1
}

$dnpScript = Join-Path $PSScriptRoot "examples\schdoc_variant_dnp\schdoc_variant_dnp.py"
if (-not (Test-Path $dnpScript)) {
    Write-Error "schdoc_variant_dnp.py not found at $dnpScript (tracked on the sch-cleanup-tools branch)"
    exit 1
}

# schdoc_variant_dnp.py stages its output next to itself, NOT in the project dir.
# (It moved from <ProjectDir>\clean\ to here in 1f73ec0, "Make sch-cleanup tools
# self-contained, arg-free examples" -- this script still pointed at the old path.)
$outputDir = Join-Path $PSScriptRoot "examples\schdoc_variant_dnp\output"
$manifestPath = Join-Path $outputDir "schdoc_variant_dnp_manifest.json"
$runStart = Get-Date

# Update the named variant's Not Fitted set from DNP markers; output is staged
# to output/ (the .PrjPcb plus a manifest), and we copy it back in place below.
# Run from the repo root so `uv run` resolves this project's environment.
Write-Host "Updating variant '$Variant' in $($prjFile.Name) ..."
Push-Location $PSScriptRoot
try {
    uv run python $dnpScript "$($prjFile.FullName)" "$Variant"
}
finally {
    Pop-Location
}

# $ErrorActionPreference does not trap native-command failures, so check explicitly.
# Without this the script would copy a *previous* run's clean\*.PrjPcb back over
# the original and report success.
if ($LASTEXITCODE -ne 0) {
    Write-Error "schdoc_variant_dnp.py failed (exit $LASTEXITCODE). Nothing was copied back."
    exit $LASTEXITCODE
}
if (-not (Test-Path $manifestPath)) {
    Write-Error "No manifest at $manifestPath. Nothing was copied back."
    exit 1
}
if ((Get-Item $manifestPath).LastWriteTime -lt $runStart) {
    Write-Error "Manifest at $manifestPath is stale (not written by this run). Nothing was copied back."
    exit 1
}

$manifest = Get-Content $manifestPath | ConvertFrom-Json

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
