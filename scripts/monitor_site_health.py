#!/usr/bin/env python3
"""Read-only production checks. No private tokens, database writes or AI calls."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://vrc-club-charts.vercel.app"
THUMB = "https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-thumb"
MAX_BODY = 2_000_000
WORLD_ID = re.compile(r"^wrld_[a-f0-9-]{36}$", re.I)
HEADERS = {"User-Agent": "VCC-SiteHealth/1.0", "Accept": "*/*"}

# Keep these exact; health checks cannot fetch arbitrary URLs from AI or World data.
PAGES = {
    "home": ("/", "aiScoutGrid"),
    "worlds": ("/worlds/", "worldCatalog"),
    "events": ("/events.html", "eventGrid"),
    "djs": ("/djs.html", "djGrid"),
    "reviews": ("/reviewer.html", "reviewSubmitForm"),
    "about": ("/about.html", "evaluation-method"),
    "privacy": ("/privacy.html", "Privacy Policy"),
}
SCRIPTS = ("app.js", "ai-scout.js", "i18n.js")


def fetch(url: str) -> tuple[int, str, bytes]:
    """Bounded requests, with one retry for intermittent edge/CDN errors."""
    if not (url.startswith(SITE + "/") or url.startswith(THUMB + "?id=")):
        raise ValueError("Unapproved health-check URL")
    error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=14) as response:
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                return response.status, mime, response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return exc.code, "text/plain", b""
            error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = type(exc).__name__
        if attempt == 0:
            time.sleep(2)
    return 0, "", str(error or "network unavailable").encode("utf-8")[:150]


def validate_site(fetcher=fetch) -> dict:
    problems = []
    checks = {}

    def fail(code: str, category: str, detail: str, *, auto_fixable: bool = True):
        problems.append({
            "code": code,
            "category": category,
            "detail": str(detail)[:260],
            "auto_fixable": auto_fixable,
        })

    def get(path: str, category: str, expected: str = "") -> str:
        url = SITE + path
        status, mime, body = fetcher(url)
        checks[path] = {"status": status, "mime": mime}
        if status != 200 or len(body) > MAX_BODY:
            fail(category + "_http", category, f"{path}: HTTP {status}", auto_fixable=status in (404, 405))
            return ""
        if mime not in ("text/html", "text/javascript", "application/javascript", "application/json", "text/plain"):
            fail(category + "_mime", category, f"{path}: unexpected MIME {mime}")
            return ""
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            fail(category + "_encoding", category, f"{path}: invalid UTF-8")
            return ""
        if expected and expected not in text:
            fail(category + "_missing", category, f"{path}: expected marker '{expected}' absent")
        return text

    htmls = {name: get(path, name, marker) for name, (path, marker) in PAGES.items()}
    home, worlds = htmls.get("home", ""), htmls.get("worlds", "")

    if home:
        if 'href="worlds/"' not in home:
            fail("home_worlds_link", "home", "Homepage is missing the Worlds directory link")
        if 'src="i18n.js' not in home:
            fail("home_language_asset", "home", "Homepage does not load the language toggle")
        if "focusWorldGrid" not in home or "aiScoutGrid" not in home:
            fail("home_discovery", "home", "World cards or discovery grid missing")
    if worlds:
        count = len(re.findall(r'class="world-catalog-row"', worlds))
        thumb_count = worlds.count("world-thumb?id=wrld_")
        checks["world_catalog"] = {"rows": count, "thumbnail_sources": thumb_count}
        if count < 1:
            fail("worlds_empty", "worlds", "Worlds directory contains no listed World cards")
        elif thumb_count < count // 2:
            fail("worlds_images", "worlds", f"Only {thumb_count}/{count} Worlds have thumbnail image sources")
        if '../i18n.js' not in worlds:
            fail("worlds_language_asset", "worlds", "Generated Worlds directory lacks translation script")

    for filename in SCRIPTS:
        js = get("/" + filename, "asset_" + filename.replace(".", "_"))
        if filename == "i18n.js" and js and "vccLanguageToggle" not in js:
            fail("language_toggle", "language", "Language script lacks the EN/JA toggle")
        if filename == "app.js" and js and "world-thumb" not in js:
            fail("home_image_fallback", "home", "Homepage JS lacks cached VRChat World thumbnail proxy")

    ranking = get("/data/weekly-ranking.json", "rankings")
    valid_worlds = []
    if ranking:
        try:
            data = json.loads(ranking)
            valid_worlds = [row["id"] for row in data.get("worlds", [])
                            if isinstance(row, dict) and WORLD_ID.fullmatch(str(row.get("id", "")))]
            checks["rankings"] = {"world_count": len(valid_worlds)}
            if not valid_worlds:
                fail("ranking_empty", "rankings", "Published rankings contain no Worlds")
        except (ValueError, TypeError, KeyError) as exc:
            fail("rankings_invalid", "rankings", type(exc).__name__)
    get("/data/ai-scout.json", "scout_data")

    if valid_worlds:
        world_id = valid_worlds[0]
        path = "/worlds/" + world_id + ".html"
        profile = get(path, "world_profile", world_id)
        if profile and "world-thumb?id=" + world_id not in profile:
            fail("profile_image", "world_profile", f"{world_id}: missing thumbnail URL")
        # The first listed World has a known-good cached thumbnail in normal operation.
        # External API outages should be alerted, not blindly fixed by Gemini.
        url = THUMB + "?id=" + world_id
        status, mime, image = fetcher(url)
        checks["thumbnail_proxy"] = {"status": status, "mime": mime, "bytes": len(image)}
        if status != 200 or not mime.startswith("image/") or len(image) < 80:
            fail("thumbnail_delivery", "external_image",
                 f"Thumbnail proxy for a catalog World: HTTP {status}, MIME {mime}",
                 auto_fixable=False)

    return {
        "schema": 1,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": SITE,
        "healthy": not problems,
        "issues": problems[:20],
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="/tmp/vcc-site-health.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = validate_site()
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"VCC production health: {'OK' if report['healthy'] else 'DEGRADED'}; "
          f"{len(report['issues'])} problems; report={out}")
    for item in report["issues"]:
        print(f"- {item['code']}: {item['detail']}")
    return 1 if args.strict and not report["healthy"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
