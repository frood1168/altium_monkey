param(
    [Parameter(Mandatory)]
    [string]$ProjectDir
)

$ErrorActionPreference = "Stop"

$refPrjPcb = "C:\Workspace\!__GeoFab\600-\600-Power\600-Power, System\600-Power, System.PrjPcb"

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prjFile) {
    Write-Error "No .PrjPcb file found in: $ProjectDir"
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"
if (-not (Test-Path $cleanDir)) {
    New-Item -ItemType Directory -Path $cleanDir | Out-Null
}

Write-Host "Extracting style from reference project..."
uv run python examples/schdoc_style/schdoc_style_extract.py $refPrjPcb

Write-Host "Applying style to $($prjFile.Name) ..."
uv run python examples/schdoc_style/schdoc_style.py $prjFile.FullName

Write-Host "Copying styled .SchDoc files back to their original locations..."
$manifest = Get-Content (Join-Path $cleanDir "schdoc_style_manifest.json") | ConvertFrom-Json
foreach ($doc in $manifest.documents) {
    Copy-Item $doc.output $doc.source -Force
    Write-Host "  $($doc.output) -> $($doc.source)"
}

Write-Host "Done."
