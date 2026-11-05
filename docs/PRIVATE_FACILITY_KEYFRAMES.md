# Private DJ facility evidence frames

This step adds a **local evidence-review packet** to VRC Club Charts.
After an authorized video is captured and Gemini has produced a private
`*.draft.json` report, the extractor takes the source MP4 and selects
a representative timestamp for each of the six known facility categories.

## What is actually checked

- The private report is a draft, not a published Craftsmanship score.
- The source MP4 SHA-256 matches the report exactly.
- FFprobe's recording duration matches the report, and all proposed
  video timestamps are in range.
- Recording/participant rights have been confirmed.
- An appearance must have an AI confidence of at least 0.80.
- At most 6 small JPGs (640px wide) are extracted; each is an **actual
  frame from the submitted MP4**, not an AI-generated image.
- A local `index.html` and `frames.json` describe the candidates with
  accurate timestamps, confidence, and an explicit unreviewed flag.
- No model prose, private names, account data, screenshots or video files
  are uploaded to GitHub, Vercel or Supabase by this step.

**It does not prove that the detected equipment really is a DJ mixer,
that streaming/playback works, or that a World has been independently
visited.** A model might point at an irrelevant frame. The exported
screenshots are available for a private visual review before trusting
any appearance claim.

## Windows usage

First, use the consented [one-World video evaluation](ONE_WORLD_INSPECTION.md)
or a creator-supplied video in the
[automatic inspection queue](AUTOMATED_INSPECTION_PIPELINE.md).

For one-World capture with `-AnalyzeVideo`, **the keyframe packet is now
generated automatically** under:

```text
%USERPROFILE%\Videos\VRCClubCharts\private-evaluations\private-keyframes\
  wrld_<world-id>_<full-sha256>\
    index.html
    frames.json
    dj_booth_002000ms.jpg
    ...
```

The exact category and timestamp vary with observations. Open the
`index.html` file locally to inspect the frames. A World without any
high-confidence observed equipment produces no folder and no false
positive claim.

To extract privately from an existing consented video and draft, without
paying for a second Gemini call:

```powershell
py -3 scripts/inspection_facility_keyframes.py --draft "C:\path\private.draft.json" --video "C:\path\video.mp4" --confirm-recording-rights
```

The standalone command defaults to
`%USERPROFILE%\Videos\VRCClubCharts\private-keyframes`; override with
`--out-dir` to store it in another **private path outside the Git repository**.

## Failure and safety behavior

- Source video mismatch, implausible timestamps, incomplete or altered
  recordings, and missing consent are rejected before extracting images.
- The extractor refuses to overwrite an existing or incomplete evidence
  directory. A matching completed directory can be reused without re-encoding.
- The combined one-World launcher blocks optional site publishing if a
  requested frame extraction fails.
- The packet contains visual pixels from the original World recording,
  which might include avatars, UI, copyrighted artwork or usernames.
  **Do not publicly share this private packet without appropriate permission
  and a privacy review.**
- Screenshots and local HTML never go into the site's published ranking feed.
  Visual preview labels on World pages remain model-generated provisional
  observations, not independently certified DJ functionality.

Run the all-offline synthetic regression test on Windows:

```powershell
.\scripts\launch_one_world_inspection.ps1 -SmokeTest
```

This generates a disposable real H.264 MP4 and extracts a real JPG from
it based on **synthetic test-category labels**. It does not contact
VRChat, Gemini or the network, and does not publish anything. Real-world
Windows and VRChat trials are still required.
