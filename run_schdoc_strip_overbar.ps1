param(
    [Parameter(Mandatory)]
    [string]$ProjectDir,

    [switch]$DryRun,
    [switch]$ShowChanges
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProjectDir)) {
    Write-Error "Project directory not found: $ProjectDir"
    exit 1
}
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

$stripScript = Join-Path $PSScriptRoot "examples\schdoc_strip_overbar\schdoc_strip_overbar.py"
if (-not (Test-Path $stripScript)) {
    Write-Error "schdoc_strip_overbar.py not found at $stripScript (tracked on the sch-cleanup-tools branch)"
    exit 1
}

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1

$extraArgs = @()
if ($DryRun)      { $extraArgs += "--dry-run" }
if ($ShowChanges) { $extraArgs += "--verbose" }

$targets = @()
if ($prjFile) {
    Write-Host "Project: $($prjFile.Name)"
    $targets = @($prjFile.FullName)
} else {
    $schDocs = Get-ChildItem "$ProjectDir\*.SchDoc" -File -ErrorAction SilentlyContinue
    if (-not $schDocs) {
        Write-Error "No .PrjPcb or .SchDoc files found in: $ProjectDir"
        exit 1
    }
    Write-Host "No .PrjPcb found - processing $($schDocs.Count) .SchDoc file(s) directly."
    $targets = @($schDocs | ForEach-Object { $_.FullName })
}

# Run from the repo root so `uv run` resolves this project's environment.
Push-Location $PSScriptRoot
try {
    uv run python $stripScript --in-place @extraArgs @targets
}
finally {
    Pop-Location
}

# $ErrorActionPreference does not trap native-command failures, so check explicitly:
# without this the script reports success even when nothing was stripped.
if ($LASTEXITCODE -ne 0) {
    Write-Error "schdoc_strip_overbar.py failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
