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

## Local source-frame evidence for facility observations

The combined Windows one-World analyzer now also extracts up to six
small private JPEG frames at model-proposed facility timestamps. Before
decoding, it checks the original video SHA-256, FFprobe duration and
recording rights. A local static HTML review index labels each frame
unreviewed; no image goes to GitHub, Vercel or a published World page.
If extraction fails, automatic publication of that run stops.

[Private facility keyframe guide](PRIVATE_FACILITY_KEYFRAMES.md).

## Recognition accuracy calibration — private, offline only

The [Facility Recognition Calibration](FACILITY_RECOGNITION_CALIBRATION.md)
workflow is available for the existing six-category video inventory.
It generates a local review HTML page that plays the original MP4 and
lets an operator label whether each facility is visible anywhere in
the FULL video, not necessarily anywhere in the World. It then compares
the labels to model sightings at the current 0.80 visibility-confidence
threshold, reporting TP/FP/FN/TN and per-class/micro precision, recall
and F1.

**No automated truth labels are invented.** The reviewer must explicitly
attest full-video review, uncertain samples are excluded, and media
digest/duration provenance is checked before scoring. Reports and videos
stay local and never flow into verified Craftsmanship ranks or live DJ
equipment attestations. Synthetic fixtures in GitHub CI verify arithmetic
and privacy boundaries; they cannot establish real-world accuracy.

## DJ/club facility visual inventory (appearance only)

The Gemini video pass now requests a **six-category facility inventory**:
DJ booth, DJ-deck-shaped objects, video screens, lighting rig, stage, and
control-panel-shaped objects. Each sighting is an AI observation backed by
at most two proposed timestamps and confidence estimates.

The local timeline audit checks that each timestamp is within the
actual FFprobe-verified MP4 duration. Only observations with confidence
at least 0.80 can enter the **provisional visual feed**. Public JSON
contains only a category ID, time in clip, confidence and
`equipmentFunctionalityVerified: false` — never usernames, prose,
screenshots, audio or arbitrary AI text.

World detail pages may show the label **映像で見えた設備（AI推定）** alongside
timestamped tags. The presence of a booth or screen does **not** establish
live-streaming capability, working controls, playback, sound, or independent
in-World verification; verified DJ stream rules and Craftsmanship score
are unchanged. Legacy reports without facility observations still work.

This inventory is only produced on real consented video analysis. Offline
integration tests use fixed synthetic facility labels, not actual VRChat
sightings.

## Evidence timestamp provenance

Video analysis models occasionally propose time references that do not
exist in the source clip. The processor records a **locally verified**
FFprobe duration, checks each model-suggested observation timestamp
against it (up to 0.25 s tolerance), and requires a passing local
visual-quality screen before the resulting private draft can contribute
any provisional public numeric score. Legacy reports lacking a verified
duration are not automatically eligible for publication. A failed
timeline audit is marked as rejected so the same video cannot incur
repeated Gemini processing charges without new input.

This does NOT prove the scene contained the described equipment or that
DJ streaming really worked; it rules out one specific kind of
hallucinated evidence.

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

## Offline interior-visual-quality gate

Before invoking Gemini, all one-run clips and queued local videos go through
`scripts/inspection_visual_quality.py`. FFmpeg extracts a very small
32x18 grayscale frame every second and checks for near-black screens,
insufficient visible detail, and long recordings without visual change.
This rejects black, frozen and empty captures **without paid AI calls**.
For queued videos, rejected footage is journaled as `rejected` instead of
being retried repeatedly every day. Raw frame samples are not stored or
uploaded.

It is an approximate heuristic, not an objective World coverage or
authenticity check. It may reject a valid static scene or accept a moving
overlay. The original MP4 stays private locally for manual inspection.



The one-command inspection and the local batch queue now verify each MP4 with
**FFprobe** before it can be uploaded to Gemini. The checks require a single
H.264 stream, no audio track, plausible dimensions and duration, and a minimum
frame count when available. FFprobe must be installed with FFmpeg.
The optional `py -3 scripts/inspection_encoder_selftest.py` tests the encoder
entirely on synthetic frames, leaving no recordings or user data behind.
Metadata validation is not full decoding or a substitute for a Windows client
recording test.

### Synthetic MP4 integration smoke test

Run `py -3 scripts/inspection_pipeline_smoketest.py` (or use
`-SmokeTest` with the Windows launcher) to create a **real temporary
silent H.264 MP4** and test metadata verification, hash provenance,
schema validation, consent-gated numeric visual scoring and the separate
World page preview. All AI responses in this test are fixed fixtures,
**not real Gemini inference**. No videos or drafts leave the temporary
folder. GitHub CI executes this test with FFmpeg/FFprobe to catch pipeline
regressions prior to merging. Passing does not substitute for real
Windows/VRChat testing.

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
