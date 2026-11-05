# One-run Windows inspection: record -> analyze -> optional visual preview

This is a **local Windows prototype** for one manually entered VRChat World.
It DOES NOT log in to VRChat, enter Worlds, click DJ equipment, autonomously
visit multiple Worlds or verify DJ streaming. Neither this script nor the
Vercel website can control your PC without being run on that PC.

VRChat's Terms section 13.2(i/j) restrict external automated agents. Support
did NOT authorize unattended AI exploration. The optional AI OSC mode is
therefore disabled by default and must only be used where the intended
automation is permitted. Official OSC inputs are documented at
https://docs.vrchat.com/docs/osc-as-input-controller.

## Setup on your Windows PC

1. Use the existing checked-out `showchoo/vrc-club-charts` repository and
   open PowerShell in that directory.
2. Install Python 3.10+, FFmpeg with `libx264` available in PATH, and:
   `py -m pip install mss pillow google-genai`
3. Open the official VRChat desktop client and enter the target World
   **manually** in a private, participant-free instance with recording rights.
4. For AI video evaluation, set your `GEMINI_API_KEY` in the local PowerShell
   environment. Never send keys to ChatGPT or commit them to GitHub.

Run the read-only diagnostic FIRST (no account, capture, OSC, or cloud access):

```powershell
.\scripts\launch_one_world_inspection.ps1 -Diagnose -AnalyzeVideo
```

The diagnostic checks Windows, Python, FFmpeg/libx264, FFprobe, `mss`, Gemini SDK/key,
and the visible VRChat window. It only reports whether a window was found;
it cannot determine which World is open or whether OSC is authorized/enabled.

**Recommended next check:** Test local H.264 encoding without starting VRChat or
recording your desktop. This uses a **synthetic black test image**, saves a
temporary MP4, verifies it using FFprobe, then deletes it:

```powershell
py -3 scripts/inspection_encoder_selftest.py
```

If this fails, fix FFmpeg/FFprobe or `libx264` before trying a real World.
After any actual capture, the pipeline now inspects MP4 metadata and blocks
AI upload of malformed, truncated, silent-track-invalid or audio-bearing files.
A passing metadata probe does **not** prove all video frames are visually
correct; it is a preliminary integrity check.

### Synthetic end-to-end test (no VRChat needed)

After the FFmpeg encoder self-test, you can also verify the **full local
evidence-processing path** using one entirely synthetic MP4 video:

```powershell
.\scripts\launch_one_world_inspection.ps1 -SmokeTest
```

This creates temporary, real H.264 frames with FFmpeg; probes the MP4;
computes its SHA-256 digest; builds a **synthetic** evidence report from
fixed fixture values; compiles a provisional visual estimate; and verifies
that a generated World page labels the estimate correctly **without
publishing it**. The clip is deleted after the test. It does not connect
to VRChat, Gemini, Supabase, GitHub or the Internet.

A result with `"status": "passed"` establishes only that this **offline
local data pipeline** operates. It does not prove real-world recording,
AI reasoning, navigation, DJ equipment or production publication.

### Automated visual-content checks before AI billing

After the MP4 container/codec has been verified, the local program decodes
**one 32x18 grayscale frame per second** with FFmpeg. If most frames are
entirely black, show almost no visible detail, or a long recording never
changes visually, the capture is marked `capture-unusable`: it is retained
locally for troubleshooting but is **not sent to Gemini** and cannot be
published as evidence. A dark VRChat club can still pass when lighting and
visible surfaces provide real detail and some variation.

Inspect any existing local clip without a cloud request:

```powershell
py -3 scripts/inspection_visual_quality.py --video "C:\path\to\your.mp4"
```

The `-SmokeTest` integration now verifies two **real** FFmpeg videos:
a moving color-pattern clip is accepted, and an all-black clip is rejected.
A moving logo, UI overlay, or animated decorative element could fool this
heuristic; it does **not** prove room coverage, DJ playback, FPS or permissions.

### Frame timestamp consistency check

The final AI draft now records the **actual FFprobe-measured video duration**
and checks **every timestamp** proposed by Gemini. For example, a model
claiming evidence at 50 seconds in a 5-second MP4 will be rejected even
if its text sounds plausible. The check runs before a draft can enter the
public numeric visual-preview feed, and before a one-command publication.
Clips rejected for impossible timestamps retain a local journal record
and are not uploaded repeatedly on scheduled retries.

This is a sanity check rather than proof the described object was really
present in that frame. Scene contents and any DJ equipment still need
independent functional testing for verified Craftsmanship scores.

### A. Capture without AI movement or cloud upload

Use the **actual** ID of the World you manually entered:

```powershell
.\scripts\launch_one_world_inspection.ps1 -WorldId wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 -Seconds 45 -ConfirmPrivateInstance
```

After launching from PowerShell, switch to the VRChat window **within 15
seconds**, and keep it foregrounded. The program automatically records the
window's content as a silent MP4. The output stays under
`%USERPROFILE%\Videos\VRCClubCharts`. Alt+Tab to stop recording, or use
Ctrl+C in a terminal if the VRChat window is no longer focused.

### B. Capture plus automatic AI video analysis

This sends the recording to Gemini and saves a private, clearly provisional
report, but does not publish anything. Make sure all recording/creator/other
participants' rights are cleared first.

```powershell
.\scripts\launch_one_world_inspection.ps1 -WorldId wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 -Seconds 45 -ConfirmPrivateInstance -AnalyzeVideo -ConfirmRecordingRights -ConfirmGeminiUpload
```

One command does all of the following in sequence:
- checks Windows, FFmpeg and required Python dependencies;
- records the *already open* VRChat World locally;
- validates the recording is not corrupted or too short;
- uploads that single clip to Gemini with explicit opt-in;
- saves a draft AI report, the video, and the inspection record locally.

Idempotency is by media SHA-256; no fake World visit or equipment score is
created. A stopped or invalid recording never triggers publication.

### C. Optional numeric visual preview update on your site

Use this only with the copyright/consent right to publish an AI-generated
visual estimate from the recording. It is **not** a tested Craftsmanship score:

```powershell
.\scripts\launch_one_world_inspection.ps1 -WorldId wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 -Seconds 45 -ConfirmPrivateInstance -AnalyzeVideo -ConfirmRecordingRights -ConfirmGeminiUpload -PublishVisual -ConfirmPublishingRights
```

The local repo must be on a clean up-to-date `main` branch with an
authenticated, expected GitHub origin. If the analysis passes a strict visual
evidence threshold, a separate numeric video score may be committed and
pushed. Vercel then deploys through GitHub. This is never considered proof
of DJ player operation, sound performance, or independent inspection.

Publishing is **not the default**. Consent can later be revoked using the
documented local queue and feed recompile workflow.

### D. Experimental AI-directed movement

If the automated use is allowed by VRChat and you choose to try it,
add `-UseAiMotion -AcknowledgeAutomationRisk -ConfirmGeminiUpload`. VRChat
OSC must be enabled first. The script uses only bounded forward/back,
strafe, and turn axes, with automatic release, 12 decisions maximum, visual
stagnation detection, and a hard recording time limit. It does not interact
with any equipment. This is still **untested on your Windows PC**, not
reliable mapping or navigation.

## Known limitations and non-goals

- The World ID is supplied by the operator and is not independently verified
  against the open VRChat scene.
- No other players should be present; there is no reliable face/name blurring.
- Video recording has no audio, so sound performance is unmeasured.
- OSC movement can vary with VRChat mode, avatar and World constraints.
- Screenshots/videos are sent to Gemini only if the separate AI options
  and consent switches are used. Provider quota/costs may apply.
- A visual score is always **provisional** and never replaces the verified
  Craftsmanship Ranking, which remains unfinished.
- Technical code and offline unit tests cannot establish functionality on
  the owner's actual PC; it needs an on-device smoke test.

Next real-world validation: verify local MP4, validate screenshot
quality/timestamps, record movement failures and model decisions, then
develop creator-consented technical equipment measurements.
