param(
    [Parameter(Mandatory)]
    [string]$ProjectDir
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

$stylePath = Join-Path $PSScriptRoot "examples\assets\style.toml"
if (-not (Test-Path $stylePath)) {
    Write-Error "style.toml not found at $stylePath"
    exit 1
}

$styleScript = Join-Path $PSScriptRoot "examples\schdoc_style\schdoc_style.py"
if (-not (Test-Path $styleScript)) {
    Write-Error "schdoc_style.py not found at $styleScript (it is tracked on the sch-cleanup-tools branch)"
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"
$manifestPath = Join-Path $cleanDir "schdoc_style_manifest.json"
$runStart = Get-Date

# Stage styled SchDocs to clean/; we also copy them back in place below.
# Run from the repo root so `uv run` resolves this project's environment.
Write-Host "Applying style.toml to $($prjFile.Name) ..."
Push-Location $PSScriptRoot
try {
    uv run python $styleScript "$($prjFile.FullName)"
}
finally {
    Pop-Location
}

# $ErrorActionPreference does not trap native-command failures, so check explicitly.
# Without this the script would happily copy a *previous* run's clean/ files back
# over the originals and report success.
if ($LASTEXITCODE -ne 0) {
    Write-Error "schdoc_style.py failed (exit $LASTEXITCODE). Nothing was copied back."
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

# Back up the original SchDocs before overwriting them in place.
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$historyDir = Join-Path $ProjectDir "history\$timestamp"
New-Item -ItemType Directory -Path $historyDir | Out-Null
Write-Host "Snapshotting originals to history\$timestamp ..."
foreach ($doc in $manifest.documents) {
    $destPath = Join-Path $historyDir (Split-Path $doc.source -Leaf)
    Copy-Item $doc.source $destPath -Force
    Write-Host "  $($doc.source) -> $destPath"
}

# Apply the styled documents over the originals.
Write-Host "Copying styled .SchDoc files back to their original locations..."
foreach ($doc in $manifest.documents) {
    Copy-Item $doc.output $doc.source -Force
    Write-Host "  $($doc.output) -> $($doc.source)"
}

Write-Host "Done. To undo, restore files from history\$timestamp"
