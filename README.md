# VRC Club Charts — CLUB DISCOVERY

An AI-first visual discovery guide for VRChat club Worlds, with open community field notes and event/DJ directories.

Public site: https://vrc-club-charts.vercel.app/

## Product direction

**CLUB DISCOVERY is the homepage's lead experience.** It automatically discovers public VRChat club Worlds, and uses Gemini image understanding to score *thumbnail visuals only*. This is a discovery signal, not an in-world craftsmanship verdict.

Human field notes are supplementary: anyone can submit a visit review without applying for reviewer status or receiving an access code. Each contribution is a self-reported observation, moderated before appearing publicly. Community scores **never enter AI visual scores or the legacy reviewer panel ranking**.

A World needs actual in-world measurement before claiming validated sound, dynamic lighting, gimmick behavior or optimization. We never conflate these with a single-image assessment.

## AI SCOUT — automated discovery and visual estimates

- `scripts/build_ai_scout.py` refreshes approved catalog candidates, preserving a separate unapproved discovery queue.
- A GitHub Actions secret named `GEMINI_API_KEY` enables up to four visual assessments each scheduled run with `gemini-3.5-flash-lite`, subject to provider account/free-tier limits.
- The scheduled workflow runs daily; the site publishes its resulting `data/ai-scout.json` after successful completion.
- Each scored result is a **single public thumbnail estimate** with explicitly low confidence; unassessed Worlds are never assigned invented scores.
- The image scores are visually ordered and labelled differently from unscored exploration candidates.
- Independent editor picks, if present, are likewise separate from Gemini and community feedback.

## Community field notes (open submission)

The public page `reviewer.html` accepts World experience reports from any visitor. There is **no reviewer application, approval process, or special code** required to submit.

- `community-reviews.js` runs the public form and shows approved community notes on the homepage and the review page.
- Supabase Edge Function `community-reviews` handles `GET` for published reviews and `POST` for new submissions.
- Submissions enter the dedicated `public.community_reviews` table as `pending`; direct anonymous table read/write access is denied by RLS and privileges.
- The existing `reviewer-admin` Edge Function, protected by the existing administrative key, supports `list_community_reviews`, `publish_community_review`, and `reject_community_review`.
- Posting is bounded to one World per browser-generated visitor identifier per 30 days and three submissions per day per salted address identifier, with manual moderation to limit abuse. These controls are *not* proof of one human per review; spoofing and identity fraud remain possible.
- Published cards show individual self-reported scores and comments. There is no automated aggregate visitor ranking.
- Legacy approved-reviewer data, if any, is preserved but not presented as the site's primary ranking.

The Edge Function implementation is tracked in `supabase/functions/community-reviews/index.ts`. It uses the `SUPABASE_SERVICE_ROLE_KEY` server-side only; never put privileged Supabase or Gemini keys into web assets.

## Trust policy

- User statements about World visits and reviewer identity are **unverified**.
- Moderation checks content suitability, not whether somebody genuinely visited the World.
- Publishing a community note does not create or change the official ranking.
- World creator/staff relationships can be disclosed publicly.
- Sponsors and advertising do not purchase ratings or change AI-scout scores.
- Unverified visual, audio, interactive or performance metrics are never presented as confirmed in-world tests.

## Popularity data

Visits / Favorites snapshots are still collected because they are useful context for discovery and momentum.

They are **not** the source of truth for Craftsmanship.

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
- Reviewer applications

World submissions are automatically checked for duplicate `wrld_...` IDs.

After manual verification, applying the `verified` label can generate a catalog PR automatically.

## Key files

- `index.html` — craftsmanship-first homepage
- `reviewer.html` — open community field notes
- `worlds/` — generated World directory and profiles
- `events.html` — event calendar
- `djs.html` — DJ / artist directory
- `data/worlds.json` — World registry
- `data/reviewers.json` — approved reviewer registry
- `data/reviews.json` — reviewer submissions used for aggregation
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

**Ranking positions and reviewer scores are never for sale.**

## Trademark

VRC Club Charts is an independent project and is not affiliated with VRChat Inc. “VRChat” is a trademark of VRChat Inc.
