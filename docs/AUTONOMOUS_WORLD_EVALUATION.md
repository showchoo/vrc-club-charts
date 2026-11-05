# Autonomous VRChat world inspection — roadmap and safety gate

## Final objective

VRC Club Charts should eventually discover eligible public DJ Worlds, visit their interiors under an authorized access method, navigate and operate equipment, record measurable evidence, and publish a reliable **Craftsmanship Ranking** with minimal owner intervention.

**This is a development goal, not an existing capability.** There is no autonomous VRChat login or traversal in this repository today. Do not simulate an actual visit with a thumbnail or AI-generated narrative.

## Current platform access gate

- VRChat's current Terms of Service restrict third-party automated tools/agents used to access, search or extract from the platform, and access inconsistent with individual human use. Do not assume OSC input capability constitutes blanket permission for unattended account/client bots. See https://hello.vrchat.com/legal .
- OSC Input Controller documents movement, look, jump and interaction inputs for the client: https://docs.vrchat.com/docs/osc-as-input-controller . This is a possible technical interface **only if VRChat authorizes the intended automated use**.
- Creator Guidelines have separate guidance on applications interacting with the API; this is not proof of authorization for unattended in-world walking: https://hello.vrchat.com/creator-guidelines .
- Creator Guidelines caution about recording other players; respect privacy/permissions, avoid names and private conversations in captured media. https://hello.vrchat.com/video-content-guidelines .

**Stop/go:** obtain written confirmation from VRChat about a dedicated inspection account, unattended OSC-controlled client, automated joining/traversing, recording, and periodic public-world inspection before enabling any live bot. No modified clients, security bypasses, access scraping or unauthorized account automation. Until then, test agent navigation in an owned 3D test environment/offline Unity scene, or inspect volunteered videos only.

## Phase 1 implemented: local, opt-in video analysis

`python scripts/evaluate_interior_video.py` takes an owner-recorded or creator-provided **local** walkthrough video. A real Gemini inference is optional and requires `--analyze --confirm-sharing` and a local `GEMINI_API_KEY`. It uses Google's Files API through the optional `google-genai` SDK and attempts deletion after analysis. Gemini bills/quotas and the service's data processing policy are governed by the connected Google account. The video is never stored in the GitHub repo, public Vercel site, or Supabase by this script.

The output is a **local draft JSON** with the media SHA-256, World ID, provenance, timestamped observations and explicit unknowns. Only directly visible aspects (visual design, lighting, spatial design, originality) may receive provisional 0–5 scores. Other categories require direct tests and always receive `null` scores. The output is *not* a site ranking or DJ livestream verification. An AI timestamp is still an unverified suggestion until reviewed.

The script intentionally limits video size to **250 MiB**, asks for source/rights confirmation, has no batch crawler, and performs at most one inference per CLI call. No scheduled AI calls or paid operations are created.

### Example: analysis on a local Windows development PC

```powershell
py -m pip install google-genai
$env:GEMINI_API_KEY="<your local key>"    # set locally, never commit it
py scripts/evaluate_interior_video.py `
  --world-id wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 `
  --video "D:\VRC-Captures\world-visit.mp4" `
  --source owner-recorded `
  --confirm-sharing --analyze `
  --out "D:\VRC-Captures\world-visit-draft.json"
```

Use the actual visited World ID, video path, and own recording or creator-authorized video. Check the recorded video does not expose uninvolved people without permission. For a purely offline parse/validation test, use `--analysis-json path/to/analysis.json` instead of `--analyze` (same structured dimensions as the schema).

`python -m unittest discover -s tests -p 'test_interior_video_evaluation.py'` runs offline regression tests.

## Phase 2 baseline: offline autonomous route + local WebM recording

The **offline camera lab** is in `experiments/offline-camera/index.html`. Open that file locally in a recent Chrome or Edge browser (or serve the repository on localhost). Click **自動巡回して録画（WebM）** to run a short autonomous grid-based inspection of a *synthetic club environment* and save a WebM video. The separate JSON audit link records the planned route, recording duration, and video SHA-256 where supported. Use **Esc** or the stop button to end recording early. No external dependencies, API key, camera/microphone permission, service account or VRChat connection is required. Browser download restrictions may require clicking the generated video link.

In the same directory:
- `navigation.js` includes walkability constraints, obstacle-aware shortest-path planning, target selection, and a deterministic timeline.
- `camera.js` renders a local synthetic first-person view and uses Canvas `captureStream` plus browser `MediaRecorder` to record only that Canvas; no tab/desktop capture is used.
- `tests/offline-camera.test.cjs` verifies route continuity, wall collision checks, detours, unreachable goals, emergency-stop wiring, and absence of network/camera APIs.

This is **not yet an AI vision agent** and **not actual VRChat recording**. It proves the navigation → synthesized camera → local video → audit-report pipeline, and preserves separate interfaces so a vision-driven agent and an approved real-world sensor can be integrated later. Simulated clips MUST NOT be submitted as evidence for VRChat World craftsmanship or DJ playback.

Run the offline Node tests via `node --test tests/offline-camera.test.cjs`. Browser MediaRecorder availability and a saved clip must still be confirmed on the intended Windows PC; CI tests do not substitute for a manual browser smoke test.

## Windows prototype (not a permitted unattended bot)

The local `scripts/windows_vrchat_inspector.py` adds real Windows VRChat
foreground-window silent MP4 capture and optional bounded Gemini image
navigation via the documented OSC input axes. The user must manually open
a private instance and provide a World ID. Video assessment integrates
with the draft video evaluator; no score is automatically published.

**This feature remains a policy-risk experiment:** VRChat has NOT approved
unattended automated access. Do not mistake technical OSC support or support's
non-answer for authorization. There is no automatic login, world hopping,
interactive equipment verification, reliable navigation, or verified ranking.
It has not been end-to-end tested on Windows. For prerequisites and exact
owner controls, see [Windows VRChat Inspection](WINDOWS_VRCHAT_INSPECTION.md).

## Local review queue and provisional visual evidence

A consent-gated batch pipeline now processes locally recorded or creator-provided
interior videos, records retry/idempotency state, optionally produces
provisional visual-only scores and (when separately authorized) publishes a
numeric feed. The new screenshot novelty guard bounds recovery turns when
AI-controlled movement appears stuck. None of this verifies real-world
navigation, audio, or DJ equipment functionality. See
[Automated Inspection Pipeline](AUTOMATED_INSPECTION_PIPELINE.md).

## Next phases (not yet implemented)

1. **Evaluation calibration:** sample several intentionally selected, creator-consented interior videos. Verify Gemini's timestamps manually, measure false positive rate for DJ gear and lighting, determine whether an optional second evaluator is useful. Record inter-rater agreement.
2. **Offline autonomy:** owned Unity test world, synthetic camera feed, navigation loop, path memory, obstacle recovery, stop/emergency kill switch. No VRChat login.
3. **Authorized VRChat pilot:** written authorization and a limited inspection account; explicit approval scopes and recording permissions; independent tests for playback (source connected → controls set → sound output measured), scene interactivity and device FPS. Keep telemetry local/aggregate.
4. **Ranking integration:** publish Craftsmanship only when independent evidence meets a published completeness threshold. Expose video-only impressions separately and show per-dimension `not measured` values, last-inspection date, source and confidence. Never equate creator video with independent verification.

## Exit criteria before publishing fully automated rankings

- Validated permission model and user privacy measures
- Repeatable measurements across multiple authorized visits/world updates
- Evidence tied to a World ID, timestamp, media hash and inspection protocol
- False-positive and safety evaluation; no unsupported device/audio/performance claims
- Explicit owner approval of publishing/appeal policy, rollback and cost budgets
