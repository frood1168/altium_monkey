param(
    [Parameter(Mandatory)]
    [string]$ProjectDir
)

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prjFile) {
    Write-Error "No .PrjPcb file found in: $ProjectDir"
    exit 1
}

$cleanDir = Join-Path $ProjectDir "clean"
if (-not (Test-Path $cleanDir)) {
    New-Item -ItemType Directory -Path $cleanDir | Out-Null
}

Write-Host "Extracting layout from reference..."
uv run python examples/schdoc_param_layout/schdoc_param_layout_extract.py examples/schdoc_param_layout/Reference_Layout.SchDoc

Write-Host "Copying param_layout.toml to $cleanDir ..."
Copy-Item "examples\schdoc_param_layout\clean\param_layout.toml" $cleanDir

Write-Host "Applying layout to $($prjFile.Name) ..."
uv run python examples\schdoc_param_layout\schdoc_param_layout.py $prjFile.FullName

Write-Host "Copying clean .SchDoc files back to their original locations..."
$manifest = Get-Content (Join-Path $cleanDir "schdoc_param_layout_manifest.json") | ConvertFrom-Json
foreach ($doc in $manifest.documents) {
    Copy-Item $doc.output $doc.source -Force
    Write-Host "  $($doc.output) -> $($doc.source)"
}

Write-Host "Done."
