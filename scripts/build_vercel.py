#!/usr/bin/env python3
"""Build the existing VRC Club Charts static site for Vercel without changing GitHub Pages."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
PAGES_BASE = "https://showchoo.github.io/vrc-club-charts/"
VERCEL_BASE = os.environ.get(
    "VCC_PUBLIC_BASE_URL", "https://vrc-club-charts.vercel.app/"
).rstrip("/") + "/"

PUBLIC_FILES = (
    "index.html", "about.html", "privacy.html", "reviewer.html",
    "reviewer-admin.html", "events.html", "djs.html",
    "app.js", "analytics.js", "ai-scout.js", "events.js", "djs.js",
    "styles.css", "favicon.svg", "site.webmanifest", "robots.txt",
)
DATA_FILES = (
    "weekly-ranking.json", "review-scores.json", "ai-scout.json", "events.json",
    "djs.json", "world-candidates.json",
)
BUILD_STEPS = (
    "sync_worlds_from_supabase.py",
    "build_rankings.py",
    "sync_reviewers_from_supabase.py",
    "sync_reviews_from_supabase.py",
    "build_review_scores.py",
)


def main() -> int:
    if not VERCEL_BASE.startswith("https://"):
        raise SystemExit("VCC_PUBLIC_BASE_URL must use HTTPS")

    for script in BUILD_STEPS:
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=True)

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    for name in PUBLIC_FILES:
        shutil.copy2(ROOT / name, OUTPUT / name)

    data_dir = OUTPUT / "data"
    data_dir.mkdir()
    for name in DATA_FILES:
        shutil.copy2(ROOT / "data" / name, data_dir / name)

    for script in ("build_static_pages.py", "build_og_image.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script), str(OUTPUT)],
                       cwd=ROOT, check=True)

    # Keep the existing Pages address live, but use Vercel URLs for this deployment.
    for path in OUTPUT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".js", ".xml", ".txt"}:
            original = path.read_text(encoding="utf-8")
            modified = original.replace(PAGES_BASE, VERCEL_BASE)
            modified = modified.replace(PAGES_BASE.removesuffix("/"), VERCEL_BASE.removesuffix("/"))
            if modified != original:
                path.write_text(modified, encoding="utf-8")

    (OUTPUT / ".nojekyll").touch()
    print(f"Built Vercel site to {OUTPUT} with public URL {VERCEL_BASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
