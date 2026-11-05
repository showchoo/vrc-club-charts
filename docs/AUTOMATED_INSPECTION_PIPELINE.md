# VRC Club Charts — automatic video inspection evidence pipeline

## What is implemented (November 2026)

This is the operational pipeline for **consented video evidence** captured with
the local Windows inspector or provided directly by a World creator:

1. Owner enters a private, participant-free VRChat instance using the **official**
   client. The existing opt-in inspector can record the foreground window.
2. `scripts/auto_evaluate_local_captures.py` discovers locally recorded videos
   from corresponding `*.inspection.json` audit logs. It requires a rights
   attestation and a cloud-upload opt-in to process any videos.
3. `scripts/auto_process_interior_queue.py` uploads up to 4 opted-in videos per
   run to Gemini, caches processing by video SHA-256, and retries failed calls
   no more than 3 times with 24h backoff. Private JSON drafts remain local.
4. `scripts/compile_interior_visual_estimates.py` extracts only provisional
   visual values when 3+ visual dimensions and credible timestamped evidence
   exist, and when disclosure permission is explicitly granted.
5. `scripts/publish_interior_visual_previews.py` optionally updates a **single**
   Git-tracked JSON feed and pushes it to `main` after verifying the repo is
   clean, up to date, and owned by `showchoo/vrc-club-charts`.
6. The existing Vercel pipeline publishes those numeric values alongside the
   proper World pages. **No videos or observations appear on GitHub.**
   Thumbnail estimates, preliminary interior visuals, and verified World
   Craftsmanship are intentionally separate.

This is NOT a completely autonomous VRChat crawler. Login, World joining,
physical DJ player interaction, sound quality measurement, arbitrary
obstacle avoidance, actual client session verification, and end-to-end testing
on the owner's Windows computer are still missing. The new navigation safety
monitor observes limited screenshot changes and aborts or turns when frames
stagnate, but it is not a reliable obstacle or collision detector.

## Platform restrictions

VRChat Terms Section 13.2(i/j):
https://hello.vrchat.com/legal

Official OSC input reference:
https://docs.vrchat.com/docs/osc-as-input-controller

The VRChat support response did NOT authorize unattended AI agents.
Only use automated client movement where VRChat's terms/authorization allow
it. The batch video review works independently of any automated VRChat
client movement and can be run with volunteered creator videos.

## Set up the local pipeline on Windows

From your local checked-out project directory in PowerShell:

- Install Python 3.10+, Git and FFmpeg.
- For window capture, install `mss`.
- For local video novelty detection, install `Pillow`.
- For Gemini image/video AI, install `google-genai`.
- Set `GEMINI_API_KEY` **locally**, never in GitHub or a shared log.
- Ensure the Git remote matches `showchoo/vrc-club-charts` and the local `main`
  is up to date. Git credentials must be configured for normal pushes.

Example:

```powershell
py -m pip install mss pillow google-genai
$env:GEMINI_API_KEY = "<paste-your-key-locally>"
.\scripts\run_inspection_pipeline.ps1
```

The last command is a **dry run**, with no Gemini uploads or public changes.

For automatic evaluation of local videos after inspecting recording rights,
other users' privacy, and the provider data-processing terms:

```powershell
.\scripts\run_inspection_pipeline.ps1 -Run -ConfirmRecordingRights -AllowCloudUpload
```

This evaluates at most 2 new captures per run by default, writing private
`*.draft.json` in your Videos/VRCClubCharts folder. It never publishes scores
by default.

If you also have **permission to publish numeric visual assessments** from
the videos, the following optional mode produces and pushes a public **visual
preview only**. It does NOT produce a verified Craftsmanship score.

```powershell
.\scripts\run_inspection_pipeline.ps1 -Run -ConfirmRecordingRights -AllowCloudUpload -PublishVisualEstimates -ConfirmPublishingRights
```

When set up on the owner's PC, this can be scheduled with Windows Task
Scheduler, but **no scheduled job has been installed** and user consent must
remain valid for every recording. Cloud processing may incur costs and can
exceed quota; choose a conservative schedule and check provider billing.

## Creator-provided video manifest

You can alternatively analyze creator-provided videos without operating
VRChat at all. Store a JSON manifest OUTSIDE the Git repository, with this
shape (use a real World ID and local MP4 path):

```json
{
  "schemaVersion": 1,
  "videos": [
    {
      "worldId": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05",
      "video": "D:\\VRC-Captures\\example.mp4",
      "source": "creator-provided",
      "recordingConsentConfirmed": true,
      "aiAnalysisConsentConfirmed": true,
      "permissionToPublish": false
    }
  ]
}
```

Inspect the queue without uploading:

```powershell
py scripts/auto_process_interior_queue.py --manifest "D:\VRC-Captures\manifest.json" --dry-run
```

To execute:

```powershell
py scripts/auto_process_interior_queue.py --manifest "D:\VRC-Captures\manifest.json" --run --allow-cloud-upload --max-videos 2
```

You may later set `permissionToPublish` to `true` **only if the creator
authorized such publication**, then run the queue command again to update
the local draft consent without paying for another inference. Run
`scripts/publish_interior_visual_previews.py --draft-dir "<folder>"
--publish-and-push --confirm-publishing-rights` separately if desired.

To revoke permission, change the manifest flag back to false and rerun
the two commands. The publisher updates the public feed to remove revoked
entries. To avoid accidental data loss, it does not erase the feed when
the private draft directory itself is empty.

## Site ranking and provenance guarantees

The production World list retains the existing eligibility rules: DJ tag,
owner-attested favorite or independent livestream verification.

Preliminary interior video visual scores have the separate method
`consented-video-visual-only-provisional`. The public output exposes only
the World ID, a 0–100 visual estimate, category coverage, mean model confidence,
assessment timestamp, and abbreviated media digest.

These values do NOT prove:

- independent visits or that the AI physically entered VRChat;
- functionality of streaming players, mixing consoles, buttons or gimmicks;
- audio fidelity, frame rate, performance or optimization;
- any user identity or creator endorsement beyond the explicit consent
  attestation for disclosure.

Public video-derived visual estimates are **not added** to Craftsmanship
Ranking, trending, or overall scores. Video-only, subjective impressions
are not equivalent to independent functional measurements.

## Test and deployment

The project CI runs all `test_*.py` regression files. The new modules do
not call Gemini, GitHub, Vercel or VRChat during tests.

Local examples:

```powershell
py -m unittest discover -s tests -p "test_auto_process_interior_queue.py"
py -m unittest discover -s tests -p "test_compile_interior_visual_estimates.py"
py -m unittest discover -s tests -p "test_inspection_navigation_guard.py"
```

Validation on an actual Windows/VRChat/Gemini setup is still required.
Do not mistake GitHub CI passing for working unattended World navigation.
