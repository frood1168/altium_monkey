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
    Write-Error "style.toml not found at $stylePath`nRun schdoc_style_extract.py first to generate it."
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"

Write-Host "Applying style to $($prjFile.Name) ..."
uv run python examples/schdoc_style/schdoc_style.py "$($prjFile.FullName)"

Write-Host "Copying styled .SchDoc files back to their original locations..."
$manifest = Get-Content (Join-Path $cleanDir "schdoc_style_manifest.json") | ConvertFrom-Json
foreach ($doc in $manifest.documents) {
    Copy-Item $doc.output $doc.source -Force
    Write-Host "  $($doc.output) -> $($doc.source)"
}

Write-Host "Done."
