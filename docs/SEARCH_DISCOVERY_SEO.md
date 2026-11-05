# Search discovery improvements: published World profiles

The site received its first Google Search Console email confirming five clicks
in a 28-day window in early November 2026. This is a **click count**, not a
visitor count or evidence that individual pages rank highly.

## What the build generates

- Static, crawlable HTML at `/worlds/<worldId>.html` for published Worlds only.
- A unique title and snippet description based on the World name, creator,
  known genre tags, and the **actual publication basis**.
- A schema.org `WebPage` containing one `CreativeWork` `mainEntity`, with
  the original VRChat World URL, creator, genres and public image.
- HTML-safe structured-data serialization, so unusual or adversarial World
  names cannot prematurely close a JSON-LD `<script>` element.
- The existing generated `/sitemap.xml` lists the canonical `/worlds/`
  profile URLs, not their legacy root aliases. Existing Robots/Sitemap linkage
  and World admission rules remain unchanged.

**Critical distinction:** An official DJ tag means a World is listed, **not**
that its DJ-streaming equipment works. An owner's confirmation is not an
independent test. Even a separately recorded DJ playback check does not prove
all equipment, acoustics or full-world craftsmanship. Structured data does
**not** include star ratings, reviews, pricing, or verified functional claims
which are not backed by appropriate evidence.

The new description is based on actual catalog fields; it is not AI-generated
ad copy, and no extra World entry is created.

## Google Search Console verification after Vercel deployment

1. In Google Search Console, open the property
   `https://vrc-club-charts.vercel.app/`.
2. Check the Sitemaps report for
   `https://vrc-club-charts.vercel.app/sitemap.xml`. This sitemap is built
   dynamically; the short `sitemap.xml` tracked in Git is only a fallback.
3. Inspect several **published** `/worlds/wrld_....html` URLs. Check
   Google-selected canonical, indexing status and discovered sitemap. Some
   pages may take time to be discovered or indexed.
4. In Performance > Search results, compare last 28 days with the prior
   28 days for clicks, impressions, CTR and queries. Check which World names
   and DJ club searches actually lead to the site.

A build passed on GitHub is **not** proof that Vercel has deployed it.
Check Vercel's production deployment SHA and build quota separately.
Search metadata does not guarantee ranking or indexing.

## Developer checks

```bash
python -m unittest tests.test_world_search_metadata tests.test_search_sitemap
python scripts/build_vercel.py
```

The tests verify privacy-safe JSON-LD, truthful DJ verification status,
published-only canonical sitemap URLs, and a build-independent real
`<title>` + `<meta name="description">` on every admitted World page.
