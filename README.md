# VRC Club Charts — CLUB DISCOVERY

An AI-first visual discovery guide for VRChat club Worlds, with open community field notes and event/DJ directories.

Public site: https://vrc-club-charts.vercel.app/

## Product direction

**CLUB DISCOVERY is the homepage's lead experience.** It automatically discovers public VRChat club Worlds, and uses Gemini image understanding to score *thumbnail visuals only*. This is a discovery signal, not an in-world craftsmanship verdict.

Human field notes are supplementary: anyone can submit a visit review without applying for reviewer status or receiving an access code. Each contribution is a self-reported observation, moderated before appearing publicly. Community scores **never alter Gemini visual scores or chart order**.

A World needs actual in-world measurement before claiming validated sound, dynamic lighting, gimmick behavior or optimization. We never conflate these with a single-image assessment.

## Long-term goal: evidence-based autonomous in-world inspection

The long-term objective is a fully autonomous, **authorized** inspector that can visit public VRChat DJ Worlds, navigate their interiors, test DJ/live-playback equipment and gimmicks, measure performance, and produce a separately substantiated Craftsmanship Ranking. **No autonomous VRChat login or exploration is currently implemented.** An OSC input API is not authorization to run an unattended inspection bot; obtain clear VRChat permission before any such pilot.

Phase 1 is an opt-in, local interior-video evaluator: `scripts/evaluate_interior_video.py`. It analyzes creator-provided or owner-recorded video with Gemini only when explicitly invoked and permitted, emits a **local draft** with timestamped evidence, and never changes the public ranking or asserts real-in-world verification. The script and its tests are deliberately disconnected from scheduled site builds and from public World admission.

Development plan, recording/privacy constraints, and the future authorized-agent gate: [Autonomous World Evaluation](docs/AUTONOMOUS_WORLD_EVALUATION.md).

### One-command Windows inspection (single World, local first)

The new [one-run inspector](docs/ONE_WORLD_INSPECTION.md) provides a
read-only system diagnostic, a synthetic offline FFmpeg/FFprobe recorder
self-test, plus a one-command sequence:
**record foreground VRChat window → consented Gemini video draft →
optional public provisional visual score**. The owner must manually
enter the World and confirm recording rights. No unattended login, World
hopping, real DJ equipment test or verified Craftsmanship publication
is implemented. AI OSC movement remains an explicitly opt-in,
platform-policy-risk experiment, not the default.

### Windows VRChat inspection pilot (manual entry required)

A new opt-in Windows tool records the foreground client window from a
**manually entered private world**, optionally proposes bounded
Gemini-guided OSC movement, and can create an evidence-labeled video
assessment. This is a local pilot, **not a deployed cloud bot or an
auto-publishing Craftsmanship Ranking**. The automated movement mode is
disabled unless explicitly opted into and may conflict with VRChat's
current automation restrictions; support has not granted approval.

Setup, user consent switches, output format and current limitations:
[Windows VRChat Inspection](docs/WINDOWS_VRCHAT_INSPECTION.md).

### Automatic review of consented interior recordings

The optional Windows pipeline picks up new local recordings, processes a
bounded queue through Gemini, compiles provisional *interior visual-only*
scores, and can publish those numeric previews after explicit rights
confirmation and normal Git authentication. This does **not** automate
VRChat login/instance changes or verify DJ equipment operation. The site
never receives private footage. Documentation:
[Automatic inspection evidence pipeline](docs/AUTOMATED_INSPECTION_PIPELINE.md).

## AI SCOUT — automated discovery and visual estimates

- `scripts/build_ai_scout.py` refreshes approved catalog candidates, preserving a separate unapproved discovery queue.
- A GitHub Actions secret named `GEMINI_API_KEY` enables up to four visual assessments each scheduled run with `gemini-3.5-flash-lite`, subject to provider account/free-tier limits.
- The scheduled workflow runs daily; the site publishes its resulting `data/ai-scout.json` after successful completion.
- Each scored result is a **single public thumbnail estimate** with explicitly low confidence; unassessed Worlds are never assigned invented scores.
- The image scores are visually ordered and labelled differently from unscored exploration candidates.
- Independent editor picks, if present, are likewise separate from Gemini and community feedback.

## Privacy-minimized visitor estimates

The site retains existing page view (PV) reporting and now offers separate
**estimated unique browser** counters for Today / 7 days / 30 days in
`reviewer-admin.html`. These are **not unique identified people** and are
not a census of all visitors. Different devices/browsers and the two site
origins are counted separately. Do Not Track and owner opt-out prevent both
PV collection and assignment of an analytics ID.

Implementation:
- `analytics.js` issues a random UUID in origin-specific `localStorage`
  only during non-excluded pageview reporting; no IP/UA fingerprinting.
- `supabase/functions/analytics-track/index.ts` validates the UUID and
  stores only a server-secret-salted SHA-256 hash grouped by JST calendar day,
  updating the last-seen time for the day. The raw UUID is not retained by
  Supabase.
- `public.site_analytics_unique_visits` has RLS and service_role-only
  privileges. Old daily hash entries older than 40 days are purged during
  subsequent pageviews. The original pageview table is unchanged.
- The secured `reviewer-admin` Edge Function fetches recent visitor
  hashes, deduplicates them for 1/7/30-day windows, and returns **only three
  aggregate integers**, not the hashes.
- Historical PVs predating rollout **do not** contribute to visitor counts.
  The all-time PV number is maintained without inventing an all-time unique
  count. More than 10,000 recent anonymous browser-day rows triggers an
  explicit partial-count warning.

Run the existing Node analytics test to verify opt-out, Do Not Track, and
stable browser pseudonyms: `node --test tests/analytics-opt-out.test.cjs`.

## Public listing policy: DJ tag, explicit owner favorites, or independently verified live playback

A World is eligible for publication through any one of the three routes,
as long as its public/available status has not been revoked:

1. **DJ TAG:** An exact `DJ` genre in our catalog, or a genuine
   `author_tag_dj` tag supplied by VRChat on a publicly accessible World.
   Names, screenshots, AI guesses and AudioLink alone are never enough.
   This route does **not** claim a working livestream player.
2. **OWNER CONFIRMED:** World IDs explicitly identified as imported from
   the site owner's VRChat favorites and confirmed by that owner to have
   DJ live playback functionality. The owner confirmation and source batch
   must be recorded in `data/owner-favorite-confirmations.json` using
   `confirmation=owner-attested-live-playback`.
   **This is the owner's attestation, not an independent test.**
3. **DJ LIVE VERIFIED:** Independent playback test or a concrete creator
   statement recorded in `data/dj-stream-verifications.json`, including
   verifier, platform, date, method and HTTPS source.

The three labels must remain distinct in generated World pages and public
ranking JSON. `published_worlds()` in `scripts/dj_stream_policy.py` is the
single admission gate, used by ranking, AI SCOUT feed and static pages.
Neither ordinary public submissions nor someone else's favorites may add
an `owner-attested` record. Exclusions for private, inaccessible, explicitly
moderated-out, or `chartEligible=false` Worlds remain in force.

**Owner favorite import reconciliation (2026-11-04 UTC):**
Supabase `world_submissions` contains a 76-World batch submitted at 13:22,
and a 10-World batch submitted at 13:24. Their World IDs, public-at-submission
status, names, authors and original author tags were retained. These are the
86 identified favorite imports the owner confirmed on 2026-11-05 JST.
Three of the earlier batch were already present in the source catalog;
73 previously missing catalog entries were added without duplicating IDs.
The later 10 were also added, producing **86 unique owner attestations**.
The separately mentioned *one pre-existing World* from the later 11 URL attempts
could not be identified from the submission tables, so it was **not** silently
attested. Do not infer that all 120+ historical catalog Worlds came from favorites.

- `data/worlds.json` is the retained research/catalog source. New World
  submissions and discoveries with a public official DJ tag can still bypass
  Gemini classification; untagged, non-owner Worlds require independent
  live-playback verification for publication.
- No automated workflow can convert arbitrary user submissions into owner
  confirmations. Future owner-favorite batches require a trusted record of
  the exact World IDs and owner approval before receiving this status.
- World cards display `DJ TAG`, `OWNER CONFIRMED`, or
  `DJ LIVE VERIFIED`. A checkmark for independence is only granted by
  the original verification registry.
- The AI research script may skip owner-confirmed Worlds to avoid paying for
  unnecessary independent research unless the owner wants additional evidence.
- Regression tests in `tests/test_dj_stream_policy.py` check provenance,
  non-public exclusion and proper separation of the labels.

## AI-assisted DJ livestream evidence research

The daily `.github/workflows/dj-stream-research.yml` workflow searches for
public evidence of **live DJ audio playback inside specific VRChat Worlds**.
It is independent of thumbnail AI SCOUT and of the World club classifier:

1. Select up to **4 unverified, non-DJ-tagged, non-owner-confirmed catalog Worlds per daily execution**, prioritizing
   music-oriented names and other discovery clues, while remembering research dates and retry
   cooldowns. Owners can trigger an extra bounded run through Actions.
2. Try official VRChat World metadata (ID, public release status, maker description).
   If the public API is blocked by 401/403, continue public-web research but mark
   official metadata as unavailable. Explicitly private Worlds are skipped.
3. Ask Gemini `gemini-3.5-flash-lite` to use **Google Search grounding**
   to find creator documentation, technical setup descriptions and firsthand
   live-playback test notes. The response must reference actual
   `groundingMetadata.groundingChunks` indices *also* mentioned by
   `groundingSupports`. Ungrounded guesses and made-up URLs never count.
   Ordinary video-player listings, AudioLink, decorative DJ booths and event
   history do not establish a working live audio stream.
4. Save a **research-only** queue to `data/dj-stream-research.json` with the
   World ID, checked date, result category, relevant source URLs, and unverified
   search hits marked separately:
   - `evidence_found` — explicit source-backed compatibility *candidate*;
   - `negative_evidence` — cited explicit statement suggesting non-support;
   - `needs_review` — unclear or no suitably grounded evidence;
   - `research_unavailable` — temporary model/metadata failure; retry sooner;
   - `non_public` — VRChat officially reports a non-public World.
5. When new `evidence_found` results appear, create **one GitHub Issue per
   research batch**, with links and a reminder to check the live playback,
   World ID, creator identity and PC/Quest support. Identical findings do
   not re-notify on the next run.

**Important:** This workflow **NEVER** writes
`data/dj-stream-verifications.json`, changes approvals, claims that playback
was personally tested, or adds any World to the public site. After a human checks
the actual source and confirms the live input/playback support, they may enter
a verified record in the independent registry. That grants the independent
DJ LIVE VERIFIED label; exact DJ tags and explicit owner confirmations are
separate publication paths.

The Gemini API key is read only from the existing `GEMINI_API_KEY` Actions
secret. Missing API key leaves all records unchanged. Grounding can incur
**charges per search query**, so research is intentionally capped at four Worlds
per run; Gemini may issue more than one search query per World.
Offline safeguards are in `tests/test_dj_stream_research.py`. This job
does not crawl arbitrary AI-returned URLs or expose secrets to GitHub Issues.

## Automated World coverage

The catalog starts from an existing seed list; it does **not** claim to include every VRChat club.
A daily scheduled collector rotates across VRCmap Music, New, Cafe, Japan,
Trending and Chill listings, plus best-effort searches of the public VRChat
World API. A persistent `vrcmapNextIndex` cursor rotates which unknown IDs
receive detail checks (up to 70 per day), instead of rescanning the same
first 70 every day. Strong nightlife names are independently verified
against the official public World detail endpoint before admission. VRCW **Club** / **DJ** paging code is retained but disabled:
its website currently returns HTTP 403 to unattended GitHub Actions requests. We do not
attempt to evade that access restriction. When an owner-approved access path is available,
`VCC_ENABLE_VRCW=1` permits a newest-page-plus-rotating-historical-page scan (cursor
stored in `data/discovery-state.json`). Search results and supplied World links are
deduplicated by World ID; unapproved matches stay in `data/world-candidates.json`.
The public VRChat search endpoint may also reject anonymous search requests; these
failures are logged without aborting other sources.

Strong club-name matches from the club category are **only added automatically** after the
public VRChat World API independently confirms that the World is public and provides its
official name and creator; rejected/previously registered Worlds are excluded. Verification
is rate-limited (default 16 attempts per run). Other discoveries remain unapproved and are
not assigned visual scores. A World link can be prioritized for verification using
`data/discovery-seeds.json`, without granting it an unverified image score.

Historical coverage builds gradually rather than instantaneously. Crawl failures are logged;
the persistent queue and pagination cursors are preserved rather than falsely reporting
that all Worlds have been scanned. World discovery uses no paid Gemini calls; once a World
is in the catalog, the existing Gemini batch image assessment continues separately.
The catalog and public ranking are rebuilt together after automatic additions.

## Durable World evidence and coverage

Discovery evidence is no longer limited to a 30-day candidate queue.
`scripts/build_discovery_ledger.py` combines the approved catalog, unresolved
candidates, explicit World URLs from curated/imported public events, and owner
nominations into `data/world-discovery-ledger.json`. Each World retains
first/last observation dates and bounded source references even if a source later
stops listing it. The separate `data/discovery-report.json` records how many
IDs are registered, pending or historical plus per-source availability. **These
counts are not an estimate of total VRChat clubs.**

Only a literal `wrld_...` World ID in an event's public metadata can create
an event venue candidate. A plausible club name, group link, or event organizer
is never automatically converted into a World ID. Event-derived IDs remain
unapproved until independently checked, and never receive fabricated visual
scores. This first phase intentionally does **not** claim to discover all
Worlds by creator: VRChat's aggregate search needs authorization.

Optional persistence in Supabase uses the private `world_discovery_records`
and `world_discovery_runs` tables with RLS enabled and no anonymous or
authenticated Data API grants. Add `SUPABASE_SERVICE_ROLE_KEY` as a GitHub
Actions **secret** to enable the server-only mirror; without it, GitHub JSON
remains authoritative and publishing continues. Never expose the key to
browser JavaScript or commit it to source control.

## Gemini screening for automatically discovered World candidates

The automatic VRCmap / directory / official-search / event collector now
**only proposes new candidate World IDs** in `data/world-candidates.json`.
Worlds whose official VRChat metadata explicitly reports a releaseStatus other
than `public` are now **removed**, not left pending. The exclusion is saved
as `excluded_nonpublic` in `data/world-candidate-ai-decisions.json` to block
rediscovery (including from stale VRCmap/seed links); private IDs are also
omitted from the public discovery ledger. Network failures, HTTP 401/403,
and missing releaseStatus are **not** proof of privacy and do not trigger
deletion. Non-public visitor-submitted Worlds are likewise excluded rather than
awaiting human moderation. Club Misery was specifically removed after the
site operator reported VRChat's "private; direct links only" notice; its
suppression record is tagged as operator-reported, not API-verified.

`confidenceScore` from the collector is keyword-based **discovery priority,
not AI confidence or a craftsmanship/visual rating**. Legacy keyword-based
direct auto-registration is disabled in `scripts/discover_worlds.py`.

The existing hourly `review-submitted-worlds.yml` job now runs
`scripts/review_discovery_candidates.py` alongside visitor-submitted URL
reviews, capped at six automatically discovered candidates per run.
Both paths reuse the **same Gemini classifier and admission criteria**:
the current official VRChat World must be public, name/creator verified,
Gemini verdict must be `club` with confidence at least 0.90, and its
description/tags must independently support nightclub/DJ event use.
Auto-approved Worlds are added to `data/worlds.json` and removed from the
pending queue; they have no invented quality ratings.

If the World metadata API is blocked (e.g., HTTP 401/403), no automatic
admission happens and the candidate remains pending. Temporary verification
and Gemini failures are retried no sooner than six hours after the last try.
Ambiguous and non-club predictions are **not auto-rejected**: they remain for
human moderation in VCC Admin, which shows the model's reason separately
from the discovery priority. Classification decisions are retained in
`data/world-candidate-ai-decisions.json`.

Manual Admin candidate approvals and rejections take precedence over AI.
Because `world_candidate_decisions` is a **private Supabase table** (not
anonymous-SELECT readable), a new read-only Edge Function
`world-candidate-status` returns **only World ID and approved/rejected
status**. Both crawler and classifier abort their automatic decisions if
moderation status cannot be verified. The function does not expose
admin credentials, reasons, or contact data.

## URL-only community club submissions with AI approval

The homepage's [Submit](https://vrc-club-charts.vercel.app/#submit-world) section
accepts public VRChat World links without requiring a login. Its POST target
is the deployed `world-submit` Supabase Edge Function, which:
- validates the exact `vrchat.com/home/world/wrld_...` URL;
- independently checks VRChat World ID, public status, official name and creator;
- deduplicates already submitted or listed Worlds;
- accepts at most three new suggestions per day per salted connection-derived
  identifier, plus a honeypot field;
- stores only official World metadata in private RLS-protected tables; no
  raw IP address is written to the database.

GET `world-submit?queue=1&limit=75&offset=0` intentionally returns **only
official, public World metadata** (no visitor identifier, IP hash, or personal
submission records) for the scheduled GitHub AI classifier.

`.github/workflows/review-submitted-worlds.yml` uses the existing
`GEMINI_API_KEY` GitHub Actions secret to classify up to eight unreviewed
Worlds hourly with `scripts/review_world_submissions.py`. The processor
rechecks official public World status and constrains auto-admission to a
Gemini 'club' verdict at >=0.90 confidence **and independent textual nightclub
evidence** (including supporting details beyond the title). Accepted Worlds
enter `data/worlds.json`, the ranking is rebuilt, and Pages republishes.
Ambiguous classifications remain in `data/world-submission-decisions.json`
with status `needs_review`; neither a quality score nor manual approval is
fabricated. If Gemini is unavailable, nothing is approved automatically.

Provider-key secrets live in GitHub Actions, not the browser. Existing
human review, visual quality evaluation and World discovery are separate
from the yes/no nightlife-use classifier.

## Gmail notifications for moderation needed

VCC's scheduled [Notify site owner of pending moderation](.github/workflows/notify-pending-reviews.yml)
GitHub Action runs hourly, and also after changes to the local candidate/AI-decision
queues. It detects:

- Auto-discovered Worlds that Gemini could not approve, or whose official
  public metadata/AI response requires an operator check;
- Submitted Worlds marked as needing human review;
- Newly submitted pending community reviews (no content exposed).

For each newly actionable item, it creates one GitHub Issue with label
`vcc-needs-attention`, assigns the repo owner (`showchoo`) and links to
[VCC Admin](https://vrc-club-charts.vercel.app/reviewer-admin.html).
Duplicate Issues/emails are prevented using a persistent idempotency marker,
including if an Issue is manually closed. Resolved tasks close automatically
when their pending status clears. Browser users' review texts, submitter IDs,
contacts, UUIDs and IP information never enter the Issue.

To receive these GitHub Issues **in Gmail**, the owner must confirm GitHub
[Settings → Notifications](https://github.com/settings/notifications) has
email notifications for participating/assigned Issues enabled, and that the
GitHub account's notification address is their intended Gmail address.
There are **no SMTP or Gmail password secrets** in the repository. GitHub
notification settings control whether/where email is actually delivered; the
Action cannot override the owner's preferences.

The lightweight Supabase Edge Function `pending-review-signals` exposes only
HMAC-pseudonymized pending review tokens (no actual review IDs or contents).
The GitHub worker combines those tokens with public-safe candidate records and
the existing read-only moderator-decision status feed, then creates actionable
Issues. It fails closed if a feed is unavailable or incomplete.

## Community field notes (open submission)

The public page `reviewer.html` accepts World experience reports from any visitor. There is **no reviewer application, approval process, or special code** required to submit.

- `community-reviews.js` runs the public form and shows approved community notes on the homepage and the review page.
- Supabase Edge Function `community-reviews` handles `GET` for published reviews and `POST` for new submissions.
- Submissions enter the dedicated `public.community_reviews` table as `pending`; direct anonymous table read/write access is denied by RLS and privileges.
- The existing `reviewer-admin` Edge Function, protected by the existing administrative key, supports `list_community_reviews`, `publish_community_review`, and `reject_community_review`.
- Posting is bounded to one World per browser-generated visitor identifier per 30 days and three submissions per day per salted address identifier, with manual moderation to limit abuse. These controls are *not* proof of one human per review; spoofing and identity fraud remain possible.
- Published cards show individual self-reported scores and comments. There is no automated aggregate visitor ranking.
- Legacy reviewer applications and panel review records are retained privately as historical data. The old applicant-approval UI is read-only and legacy GitHub Issue templates have been removed.

The Edge Function implementation is tracked in `supabase/functions/community-reviews/index.ts`. It uses the `SUPABASE_SERVICE_ROLE_KEY` server-side only; never put privileged Supabase or Gemini keys into web assets.

## Trust policy

- User statements about World visits and reviewer identity are **unverified**.
- Moderation checks content suitability, not whether somebody genuinely visited the World.
- Publishing a community note does not affect the visual chart or create a validated in-world ranking.
- World creator/staff relationships can be disclosed publicly.
- Sponsors and advertising do not purchase ratings or change AI-scout scores.
- Unverified visual, audio, interactive or performance metrics are never presented as confirmed in-world tests.

## Popularity data

Visits / Favorites snapshots are still collected because they are useful context for discovery and momentum.

They are **not** craftsmanship scores and do not determine the visual chart order.

The public site never calls the VRChat API during page views. A scheduled collector stores static snapshots under `data/snapshots/`.

## Events

Events are separate from World craftsmanship.

Two sources are shown distinctly:

- **CURATED** — manually checked event records
- **PUBLIC FEED** — events deterministically filtered from the public VRChat Event Calendar feed

`scripts/import_event_feed.py` refreshes the filtered public feed daily at 07:15 JST.

Adult-only, fitness / exercise and obvious non-nightlife noise is excluded from the automated feed.

## Community submissions

GitHub Issue Forms are available for:

- World submissions
- Event submissions
- DJ submissions

World submissions are automatically checked for duplicate `wrld_...` IDs.

After manual verification, applying the `verified` label can generate a catalog PR automatically.

## Gemini self-healing site monitor

`.github/workflows/site-self-heal.yml` checks the live Vercel production URL **hourly**.
It verifies public routes, generated World profiles, images, published feeds,
JavaScript assets and the bilingual toggle. Every six hours (and on initial
deployment/manual runs), a Playwright Chromium probe checks *rendered* World
images, AI SCOUT cards, and the EN/日本語 button. The monitor is read-only.

If it finds a new reproducible incident, it makes **one** bounded request to
the existing `GEMINI_API_KEY` using `gemini-3.5-flash-lite`. Healthy hours
cost no Gemini API tokens. Gemini may suggest up to two unique text
replacements in a small allowlist of public-facing source files. It cannot
modify GitHub Actions, secrets, tests, World/review data, Supabase, moderation
or the official scoring policy. Prompts treat site/World content as untrusted.

Suggested changes run Python/Node tests and the actual Vercel static build in
a separate no-secret step. The bot then creates a repair branch and a GitHub
PR. **Only an isolated, relative internal HTML link correction may be merged
automatically.** JavaScript, Python generator, styling and config changes
require manual review and merge. Auto-merge never means the bot is free to
redesign, alter rankings or modify privacy/security.

For automatic PR creation, the repository owner must enable:

**GitHub → Settings → Actions → General → Workflow permissions →
"Allow GitHub Actions to create and approve pull requests".**

If the setting is disabled, the workflow retains a branch and creates an
assigned GitHub Issue linking to that branch instead. Ensure GitHub's **Email
notifications for assigned Issues** are enabled to receive Gmail alerts.
GitHub notification delivery should be tested with a real incident.
The Issue is not duplicated hourly and closes after a successful health check.

The existing `GEMINI_API_KEY` repository secret is reused; no new credential
is needed. The API may have quotas or charges under Google's current pricing.
The monitor and model are **best-effort**, not a guarantee of autonomous
recovery. External VRChat/Supabase outages trigger notification rather than
speculative code changes, and layout bugs beyond current browser assertions
may go undetected.

Local smoke tests:

```bash
python -m unittest discover -s tests -p "test_site_self_heal.py"
python scripts/monitor_site_health.py --report /tmp/vcc-site-health.json
```

## Key files

- `index.html` — CLUB DISCOVERY visual-first homepage
- `reviewer.html` — open community field notes
- `worlds/` — generated World directory and profiles
- `events.html` — event calendar
- `djs.html` — DJ / artist directory
- `data/worlds.json` — World registry
- `data/reviewers.json` — archived legacy approved reviewer registry
- `data/reviews.json` — archived panel reviewer submissions (not included in current ranking)
- `data/review-scores.json` — legacy panel score output (not shown as AI visual ranking)
- `community-reviews.js` — community field notes and open form
- `scripts/snapshot.py` — conservative VRChat data collector
- `scripts/build_rankings.py` — popularity / momentum data builder
- `scripts/build_static_pages.py` — static detail pages, sitemap and ICS generator
- `scripts/import_event_feed.py` — public event feed filter
- `.github/workflows/pages.yml` — GitHub Pages deployment
- `.github/workflows/validate.yml` — catalog / review / frontend validation

## Monetization policy

Future monetization can include display ads, clearly labeled sponsored events / featured clubs, or creator analytics.

**Visual chart positions and community scores are never for sale.**

## Trademark

VRC Club Charts is an independent project and is not affiliated with VRChat Inc. “VRChat” is a trademark of VRChat Inc.
