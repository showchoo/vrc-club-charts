# One-command local processing of consented VRChat recordings.
# No unattended VRChat login/traversal.
# .\scripts\run_inspection_pipeline.ps1
# .\scripts\run_inspection_pipeline.ps1 -Run -ConfirmRecordingRights -AllowCloudUpload
# To additionally publish numeric scores, add -PublishVisualEstimates -ConfirmPublishingRights
param(
    [string]$CaptureDir = "$env:USERPROFILE\Videos\VRCClubCharts",
    [string]$OutDir = "$env:USERPROFILE\Videos\VRCClubCharts\private-evaluations",
    [ValidateRange(1, 4)][int]$MaxVideos = 2,
    [switch]$Run,
    [switch]$ConfirmRecordingRights,
    [switch]$AllowCloudUpload,
    [switch]$PublishVisualEstimates,
    [switch]$ConfirmPublishingRights
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repo
$script = "scripts/auto_evaluate_local_captures.py"
$argsList = @($script, "--capture-dir", $CaptureDir, "--out-dir", $OutDir, "--max-videos", "$MaxVideos")
if (-not $Run) {
    $argsList += "--dry-run"
    & py -3 @argsList
    if ($LASTEXITCODE -ne 0) { throw "Local capture inventory failed" }
    Write-Host "Dry run only: no video uploads or public changes."
    exit 0
}
if (-not ($ConfirmRecordingRights -and $AllowCloudUpload)) {
    throw "You must separately confirm recording rights and consent to Gemini cloud upload."
}
if ($PublishVisualEstimates -and -not $ConfirmPublishingRights) {
    throw "Public numeric video scores require explicit publishing-rights confirmation."
}
$argsList += @("--run", "--attest-recording-rights", "--allow-cloud-upload")
if ($PublishVisualEstimates) { $argsList += "--allow-visual-publication" }
& py -3 @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Evaluation queue returned an error; publication was not attempted."
}
if ($PublishVisualEstimates) {
    & py -3 scripts/publish_interior_visual_previews.py --draft-dir $OutDir --publish-and-push --confirm-publishing-rights
    if ($LASTEXITCODE -ne 0) {
        throw "Publishing was stopped. Check repository state/rights/remote."
    }
} else {
    Write-Host "Private AI drafts updated; public site unchanged."
}
