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

$stylePath = Join-Path $PSScriptRoot "examples\assets\style.toml"
if (-not (Test-Path $stylePath)) {
    Write-Error "style.toml not found at $stylePath"
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"

# Stage styled SchDocs to clean/; we also copy them back in place below.
Write-Host "Applying style.toml to $($prjFile.Name) ..."
uv run python examples/schdoc_style/schdoc_style.py "$($prjFile.FullName)"

$manifest = Get-Content (Join-Path $cleanDir "schdoc_style_manifest.json") | ConvertFrom-Json

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
