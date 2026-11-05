# Windows launcher for a single, manually opened VRChat World.
# Default: local capture ONLY. AI and public previews require separate flags.
param(
    [string]$WorldId,
    [ValidateRange(5, 120)][int]$Seconds = 45,
    [string]$CaptureDir = "$env:USERPROFILE\Videos\VRCClubCharts",
    [switch]$Diagnose,
    [switch]$AnalyzeVideo,
    [switch]$UseAiMotion,
    [switch]$PublishVisual,
    [switch]$ConfirmPrivateInstance,
    [switch]$AcknowledgeAutomationRisk,
    [switch]$ConfirmRecordingRights,
    [switch]$ConfirmGeminiUpload,
    [switch]$ConfirmPublishingRights
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repo
try {
    $arguments = @("scripts/run_one_world_inspection.py")
    if ($Diagnose) {
        $arguments += "--diagnose"
        if ($AnalyzeVideo) { $arguments += "--analyze-video" }
        if ($UseAiMotion) { $arguments += "--ai-explore" }
    } else {
        if (-not $WorldId) { throw "Provide -WorldId for the World you have already entered." }
        if (-not $ConfirmPrivateInstance) {
            throw "You must confirm a private participant-free instance (-ConfirmPrivateInstance)."
        }
        $arguments += @("--world-id", $WorldId, "--seconds", "$Seconds", "--capture-dir", $CaptureDir)
        $arguments += "--private-instance-confirmed"
        if ($AnalyzeVideo) { $arguments += "--analyze-video" }
        if ($UseAiMotion) { $arguments += "--ai-explore" }
        if ($PublishVisual) { $arguments += "--publish-visual" }
        if ($AcknowledgeAutomationRisk) { $arguments += "--acknowledge-automation-risk" }
        if ($ConfirmRecordingRights) { $arguments += "--confirm-recording-rights" }
        if ($ConfirmGeminiUpload) { $arguments += "--confirm-gemini-upload" }
        if ($ConfirmPublishingRights) { $arguments += "--confirm-publishing-rights" }
    }

    & py -3 @arguments
    $status = $LASTEXITCODE
    if ($status -ne 0) {
        throw "Inspection stopped (exit $status). Review the displayed diagnostics."
    }
} finally {
    Pop-Location
}
