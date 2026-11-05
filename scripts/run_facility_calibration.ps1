# Local-only calibration: discover prior video analyses, create private review
# pages and automatically score completed label JSON files.
# No VRChat login, Gemini calls or website changes are performed.
param(
    [string]$CaptureDir = "$env:USERPROFILE\Videos\VRCClubCharts",
    [string]$DraftDir = "$env:USERPROFILE\Videos\VRCClubCharts\private-evaluations",
    [string]$Workspace = "$env:USERPROFILE\Videos\VRCClubCharts\private-calibration",
    [string]$LabelsDir = "$env:USERPROFILE\Downloads",
    [switch]$OpenReview
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repo
try {
    $arguments = @(
        "scripts/auto_prepare_facility_calibration.py",
        "--video-dir", $CaptureDir,
        "--draft-dir", $DraftDir,
        "--work-dir", $Workspace,
        "--labels-dir", $LabelsDir
    )
    & py -3 @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Local review preparation stopped: inspect errors above."
    }
    $index = Join-Path $Workspace "review-queue.html"
    if ($OpenReview -and (Test-Path -LiteralPath $index -PathType Leaf)) {
        Start-Process -FilePath $index
    }
} finally {
    Pop-Location
}
