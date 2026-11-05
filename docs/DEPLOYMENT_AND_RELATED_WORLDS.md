# Production deploy and low-cost previews — VRC Club Charts

This project's public Vercel URL is `https://vrc-club-charts.vercel.app/`.

## Why the latest GitHub commit may not be live

GitHub Actions green checks mean source/tests passed. They **do not** mean a
Vercel production release happened. Vercel Hobby build-rate limits can prevent
new deployments after frequent branch commits or PR activity. To check
production, inspect the actual production deployment commit SHA and compare
it with GitHub `main`.

On 2026-11-06, Vercel's production domain still served commit
`369dfff522c67671917b4957daca924b65c2db22` while subsequent PRs
were already merged to GitHub `main`. This document records the observation
at that time, not a claim about future deployments.

## Cost control during development

The project was configured with Vercel
`previewDeploymentsDisabled=true` to avoid a new preview build on *every*
development-branch commit. GitHub Actions remain the review gate for Python
tests, JavaScript tests, synthetic MP4 verification and generated static HTML.

Disabling previews does **not** disable or repair production builds, and it
does **not** override any Hobby plan build quota. Re-enable previews in Vercel
when browser validation on a preview URL is useful, or use a temporary,
specifically approved preview deployment.

## Safe release procedure

1. Check that required GitHub Actions checks passed on the final PR head.
2. Merge to `main` only once checks pass.
3. Inspect `vrc-club-charts.vercel.app` and confirm both the deployment state
   is `READY` and its commit SHA matches the intended `main` release.
4. If Vercel reports `build-rate-limit`, avoid retry loops; inspect the
   team's available build quota/reset period and retry once eligible. A paid
   upgrade should be a separate explicit decision.
5. Inspect `/worlds/`, a few existing `/worlds/wrld_*.html` profiles, and
   `/sitemap.xml` once deployment finishes.
6. Only after the new build is live, check Google Search Console's indexing
   and search performance. Search recrawling may take additional time.

Never promote an old preview build as a shortcut: old build artifacts may
have older World discovery and content rules, and previews may use different
environment variables.

## Related public World links

`scripts/related_worlds.py` and `scripts/build_static_pages.py` generate
up to four cross-links on a published World profile when the admitted catalog
contains candidates with the same creator or a shared genre.

- The relatedness explanation is based on public profile metadata, not
  visual similarity, live equipment functionality, rankings or visit data.
- Candidates must already be admitted by the same DJ-tag/owner-confirmed/
  verified-evidence rules as the public catalog, and must not be unavailable,
  private, hidden or explicitly disabled.
- Links are regular static links which work without JavaScript and point to
  generated World profile files; no extra VRChat API calls are performed.
- The feature never admits a new World by itself.
