# VRC Club Charts — Public Beta 0.2

A static-first weekly ranking site for VRChat club / DJ / music worlds.

## Current build

- Japanese / English responsive ranking UI
- Overall / Trending / Craftsmanship charts
- Genre filtering and search
- Curated starter world list
- Editorial craftsmanship score out of 100
- Conservative weekly public-world snapshot collector
- Weekly delta + ranking builder
- GitHub Actions auto-refresh workflow
- Vercel-ready security headers
- About / methodology / privacy pages
- No database, no backend, no paid dependency required for the beta

## Ranking model

After two usable snapshots exist:

**Overall = 55% weekly momentum + 45% craftsmanship**

Weekly momentum:
- 65% normalized log of 7-day visit growth
- 35% normalized log of 7-day favorite growth

Craftsmanship category maxima:
- Visual 20
- Lighting / VJ 20
- Sound 15
- Spatial design 15
- Interaction 10
- VR originality 10
- Optimization 10

Until the second snapshot is available, the site is explicitly shown as **Seed mode**. Overall uses the provisional craftsmanship order and Trending is shown as collecting data.

The starter craftsmanship scores are provisional editorial placeholders. Review them in-world before treating them as a final published editorial ranking.

## VRChat API constraints

This project does **not** ask for or store VRChat login credentials.

The collector is designed around a curated list of public World IDs, caching, a descriptive User-Agent, conservative spacing between requests, randomized start delay, and stopping on HTTP 429 rather than retrying aggressively.

Before the first automated snapshot, create the GitHub Actions repository variable:

`VRC_USER_AGENT=VRCClubCharts/0.2 https://YOUR-LIVE-SITE.example/about`

The community VRChat API documentation describes `GET /worlds/{worldId}` as usable without authentication, but some fields can be absent or zero for unauthenticated requests. Confirm `visits` and `favorites` are populated during the first production run before relying on them commercially.

## Local preview

```bash
python -m http.server 8000
```

Open `http://localhost:8000`.

## First data run

After the first public URL exists:

```bash
export VRC_USER_AGENT='VRCClubCharts/0.2 https://YOUR-LIVE-SITE.example/about'
python scripts/snapshot.py --no-jitter
python scripts/build_rankings.py
```

A second snapshot at least about six days later activates weekly momentum.

## Vercel deployment

This repository is ready for a plain static Vercel project.

- Framework preset: Other / no framework
- Root directory: repository root
- Build command: none
- Output directory: repository root / default static output
- `vercel.json` supplies security and cache headers
- `.vercelignore` keeps automation/source files out of the public deployment

Recommended flow:

1. Create a GitHub repository named `vrc-club-charts`.
2. Push this folder to the default branch.
3. Import the repository into Vercel.
4. Deploy the seed site.
5. Use the live `/about` URL in the `VRC_USER_AGENT` repository variable.
6. Run `Update weekly rankings` manually once.
7. Verify the snapshot contains non-zero `visits` and `favorites` where expected.
8. Let the scheduled workflow run weekly; each committed ranking update triggers a new Vercel deployment.

## Add a world

Edit `data/worlds.json`. Each entry needs a valid `wrld_...` World ID and editorial metadata. The collector validates World ID format before sending requests.

## Monetization policy

Future monetization can include display advertising, clearly labeled sponsored events / featured clubs, and creator analytics. Ranking positions themselves should not be sold.

## Files

- `index.html` — charts
- `about.html` — methodology and editorial policy
- `privacy.html` — initial privacy policy
- `app.js` / `styles.css` — frontend
- `data/worlds.json` — curated world registry
- `data/weekly-ranking.json` — generated public chart data
- `scripts/snapshot.py` — conservative world snapshot collector
- `scripts/build_rankings.py` — ranking builder
- `.github/workflows/update-rankings.yml` — scheduled update
- `vercel.json` — deployment headers

## Trademark

This is an independent project and is not affiliated with VRChat Inc. “VRChat” is a trademark of VRChat Inc.
