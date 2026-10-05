# VRC Club Charts — Public Beta

A static-first weekly ranking and discovery site for VRChat club / DJ / music worlds.

Public site: https://showchoo.github.io/vrc-club-charts/

## Current build

- 60 tracked VRChat club / DJ / music worlds
- 6 provisional editorial-ranked worlds
- 54 discovery / pending-review worlds
- Overall / Trending / Craftsmanship views
- Search + curated genre filters
- Discovery sorting by popularity / visits / favorites / name
- Static world directory and one SEO-friendly detail page per tracked world
- Weekly visits / favorites snapshots
- VRChat thumbnail capture when available
- Automatic hiding of worlds confirmed unavailable by the snapshot collector
- Canonical metadata, JSON-LD and generated sitemap
- GitHub Pages hosting with no database/backend required
- Event calendar with 4 verified seed events, ICS feed, structured data and public submission form
- World and event submissions via GitHub Issue Forms
- 14 non-ranked DJ profiles with genre filters, static profiles and event relationships
- DJ submissions via GitHub Issue Forms

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

Until a prior snapshot at least roughly six days old exists, the site is shown as **Seed mode**. Trending remains in data-collection mode.

Unreviewed Discovery worlds do not receive a Craftsmanship score and are excluded from editorial Overall ranking until reviewed. They can participate in Trending once weekly data exists.

## Data collection

The public site never calls the VRChat API during page views.

The scheduled collector:
- reads the curated World IDs from `data/worlds.json`
- uses no VRChat login credentials
- sends a descriptive User-Agent
- spaces requests conservatively
- adds a randomized start delay
- stops on HTTP 429
- records skipped / unavailable worlds
- stores snapshots under `data/snapshots/`

The full VRChat snapshot workflow runs **weekly or by explicit manual dispatch only**, not on ordinary code commits.

## Static publishing

GitHub Pages deploys:
- the main chart
- About / Privacy
- the public ranking JSON
- a generated `/worlds/` directory
- a generated detail page for every tracked world
- a generated sitemap containing world and DJ profile pages
- `events.ics` for calendar subscription/import

`scripts/build_static_pages.py` generates the directory, detail pages and sitemap at deploy time.

## Key files

- `index.html` — main charts and discovery
- `about.html` — methodology / editorial policy
- `privacy.html` — privacy policy
- `events.html` / `events.js` — upcoming VRChat music event calendar
- `data/events.json` — curated event registry
- `djs.html` / `djs.js` — non-ranked DJ directory
- `data/djs.json` — DJ profile registry
- `app.js` / `styles.css` — frontend
- `data/worlds.json` — curated registry
- `data/weekly-ranking.json` — public chart payload
- `scripts/snapshot.py` — conservative VRChat collector
- `scripts/build_rankings.py` — ranking builder
- `scripts/build_static_pages.py` — static world page + sitemap generator
- `.github/workflows/update-rankings.yml` — weekly snapshot
- `.github/workflows/pages.yml` — GitHub Pages deployment

## Editorial / monetization policy

Starter editorial scores are provisional public-beta placeholders and should be reviewed in-world before being treated as final editorial judgments.

Future monetization can include display ads, clearly labeled sponsored events / featured clubs, and creator analytics. Ranking positions themselves should not be sold.

## Trademark

This is an independent project and is not affiliated with VRChat Inc. “VRChat” is a trademark of VRChat Inc.


### Submission automation

- New World / Event / DJ Issue Forms are automatically labeled for verification.
- World submissions are checked for duplicate `wrld_...` IDs.
- Maintainers can apply the `verified` label after source verification.
- Verified submissions can generate a catalog PR automatically.
- World PRs update both `data/worlds.json` and the Discovery row in `data/weekly-ranking.json` so validation stays green.
- 34 DJ / artist profiles and 8 curated event records are currently connected to the World / Event / DJ portal structure.


### Daily public event import

- `scripts/import_event_feed.py` reads the canonical public JSON from `KAFKA2306/cast_event_cal`.
- It applies an independent, deterministic club / DJ / live-event filter.
- `data/events-auto.json` is refreshed daily at 07:15 JST.
- Curated events win when a matching public-feed variant exists.
- The static build merges both sources into the public `data/events.json`, event detail pages, sitemap and ICS feed.
- Events UI can switch between **ALL**, **CURATED**, and **PUBLIC FEED**.


### Catalog scope at 100 worlds

- 100 tracked worlds total
- 92 chart-eligible nightlife worlds
- 8 directory-only music / dance / DJ-adjacent worlds
- 6 provisional editorial-scored worlds
- Unreviewed worlds never receive a fabricated Craftsmanship score
