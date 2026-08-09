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

$extractScript = Join-Path $PSScriptRoot "examples\schdoc_param_layout\schdoc_param_layout_extract.py"
$applyScript   = Join-Path $PSScriptRoot "examples\schdoc_param_layout\schdoc_param_layout.py"
$referenceDoc  = Join-Path $PSScriptRoot "examples\schdoc_param_layout\Reference_Layout.SchDoc"
foreach ($required in @($extractScript, $applyScript, $referenceDoc)) {
    if (-not (Test-Path $required)) {
        Write-Error "Required file not found: $required (tracked on the sch-cleanup-tools branch)"
        exit 1
    }
}

$layoutSrc = Join-Path $PSScriptRoot "examples\schdoc_param_layout\clean\param_layout.toml"
$layoutDst = Join-Path $ProjectDir "param_layout.toml"
$runStart  = Get-Date

# 1. Extract the parameter layout from the reference schematic.
#    Writes examples/schdoc_param_layout/clean/param_layout.toml
#    Run from the repo root so `uv run` resolves this project's environment.
Write-Host "Extracting layout from reference..."
Push-Location $PSScriptRoot
try {
    uv run python $extractScript $referenceDoc
}
finally {
    Pop-Location
}

# $ErrorActionPreference does not trap native-command failures, so check explicitly.
# Without this a failed extract would stage a *previous* run's param_layout.toml
# and apply that stale layout to the project's SchDocs.
if ($LASTEXITCODE -ne 0) {
    Write-Error "schdoc_param_layout_extract.py failed (exit $LASTEXITCODE). Project not touched."
    exit $LASTEXITCODE
}
if (-not (Test-Path $layoutSrc)) {
    Write-Error "Extract produced no layout at $layoutSrc. Project not touched."
    exit 1
}
if ((Get-Item $layoutSrc).LastWriteTime -lt $runStart) {
    Write-Error "Layout at $layoutSrc is stale (not written by this run). Project not touched."
    exit 1
}

# 2. Stage param_layout.toml at the PROJECT ROOT, where the apply step reads it.
#    (The apply script reads <ProjectDir>\param_layout.toml, not clean\.)
Write-Host "Copying param_layout.toml to $ProjectDir ..."
Copy-Item $layoutSrc $layoutDst -Force

# 3. Apply the layout in place. The apply script snapshots every touched SchDoc
#    into <ProjectDir>\History\<timestamp>\ before rewriting it atomically, so no
#    manual copy-back is required. It also writes the manifest and
#    unmatched_symbols.csv into that same History snapshot folder.
Write-Host "Applying layout to $($prjFile.Name) (in place) ..."
Push-Location $PSScriptRoot
try {
    uv run python $applyScript "$($prjFile.FullName)"
}
finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "schdoc_param_layout.py failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "Done. Originals were snapshotted to $ProjectDir\History\<timestamp>\ before edit."
