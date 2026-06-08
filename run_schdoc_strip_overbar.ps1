param(
    [Parameter(Mandatory)]
    [string]$ProjectDir,

    [switch]$DryRun,
    [switch]$ShowChanges
)

$ErrorActionPreference = "Stop"

$prjFile = Get-Item "$ProjectDir\*.PrjPcb" -ErrorAction SilentlyContinue | Select-Object -First 1

$extraArgs = @()
if ($DryRun)      { $extraArgs += "--dry-run" }
if ($ShowChanges) { $extraArgs += "--verbose" }

if ($prjFile) {
    Write-Host "Project: $($prjFile.Name)"
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py --in-place @extraArgs $prjFile.FullName
} else {
    $schDocs = Get-ChildItem "$ProjectDir\*.SchDoc" -File -ErrorAction SilentlyContinue
    if (-not $schDocs) {
        Write-Error "No .PrjPcb or .SchDoc files found in: $ProjectDir"
        exit 1
    }
    Write-Host "No .PrjPcb found — processing $($schDocs.Count) .SchDoc file(s) directly."
    uv run python examples/schdoc_strip_overbar/schdoc_strip_overbar.py --in-place @extraArgs ($schDocs | ForEach-Object { $_.FullName })
}
