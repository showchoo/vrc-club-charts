#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://showchoo.github.io/vrc-club-charts/"


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def fmt_num(value):
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def page_head(title: str, description: str, canonical: str, prefix: str = "") -> str:
    json_ld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": description,
        "url": canonical,
        "isPartOf": {
            "@type": "WebSite",
            "name": "VRC Club Charts",
            "url": BASE_URL,
        },
    }
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <meta name="theme-color" content="#0d171c" />
  <meta name="robots" content="index,follow,max-image-preview:large" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta property="og:site_name" content="VRC Club Charts" />
  <link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="{prefix}styles.css?v=20261005-12" />
  <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
</head>
<body>
  <div class="noise"></div>
"""


def site_header(prefix: str = "") -> str:
    return f"""  <header class="site-header">
    <a class="brand" href="{prefix}index.html"><span class="brand-mark">VCC</span><span>VRC CLUB CHARTS</span></a>
    <nav class="nav">
      <a class="nav-link" href="{prefix}index.html">Charts</a>
      <a class="nav-link active" href="{prefix}worlds/index.html">Worlds</a>
      <a class="nav-link" href="{prefix}events.html">Events</a>
      <a class="nav-link" href="{prefix}djs.html">DJs</a>
      <a class="nav-link" href="{prefix}about.html">About</a>
    </nav>
  </header>
"""


def footer(prefix: str = "") -> str:
    return f"""  <footer class="site-footer shell">
    <span>VRC CLUB CHARTS / PUBLIC BETA</span>
    <span class="footer-links"><a href="{prefix}index.html">Charts</a><a href="{prefix}worlds/index.html">Worlds</a><a href="{prefix}events.html">Events</a><a href="{prefix}djs.html">DJs</a><a href="{prefix}about.html">About</a><a href="{prefix}privacy.html">Privacy</a></span>
  </footer>
</body>
</html>
"""


def ics_escape(value) -> str:
    text = str(value or "")
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_utc(value: str) -> str:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(events: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VRC Club Charts//Event Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:VRC Club Charts Events",
    ]
    for event in events:
        if not event.get("name") or not event.get("start"):
            continue
        start = event["start"]
        start_dt = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
        end = event.get("end")
        if not end:
            end_dt = start_dt + dt.timedelta(hours=3)
            end = end_dt.isoformat()
        uid_seed = f"{event.get('name')}|{start}|{event.get('organizer')}"
        uid = hashlib.sha1(uid_seed.encode("utf-8")).hexdigest()[:20] + "@vrc-club-charts"
        world = event.get("worldName") or event.get("worldId") or "VRChat"
        description = f"Organizer: {event.get('organizer') or '—'}\\nWorld/Instance: {world}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{ics_utc(start)}",
            f"DTEND:{ics_utc(end)}",
            f"SUMMARY:{ics_escape(event.get('name'))}",
            f"DESCRIPTION:{ics_escape(description)}",
            f"LOCATION:{ics_escape(world)}",
        ])
        if event.get("url"):
            lines.append(f"URL:{event['url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def inject_event_json_ld(out: Path, events: list[dict]) -> None:
    path = out / "events.html"
    if not path.exists():
        return
    doc = path.read_text(encoding="utf-8")
    items = []
    for event in events:
        if not event.get("name") or not event.get("start"):
            continue
        item = {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": event["name"],
            "startDate": event["start"],
            "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "VirtualLocation",
                "name": event.get("worldName") or "VRChat",
                "url": event.get("url") or BASE_URL + "events.html",
            },
            "organizer": {
                "@type": "Organization",
                "name": event.get("organizer") or "VRChat community organizer",
            },
            "url": event.get("url") or BASE_URL + "events.html",
        }
        if event.get("end"):
            item["endDate"] = event["end"]
        items.append(item)
    block = '<script type="application/ld+json">' + json.dumps(items, ensure_ascii=False) + '</script>'
    doc = doc.replace("</head>", f"  {block}\n</head>")
    path.write_text(doc, encoding="utf-8")


def world_page(w: dict) -> str:
    wid = w.get("id", "")
    name = w.get("name") or wid
    author = w.get("author") or "—"
    genres = w.get("genres") or []
    editorial_status = w.get("editorialStatus") or "unreviewed"
    score = (w.get("scores") or {}).get("craftsmanship")
    totals = w.get("totals") or {}
    weekly = w.get("weekly") or {}
    thumbnail = w.get("thumbnail")
    canonical = f"{BASE_URL}worlds/{quote(wid)}.html"
    description = f"{name} by {author} — VRChat club / DJ world profile on VRC Club Charts."
    tags = "".join(f'<span class="tag">{esc(g)}</span>' for g in genres[:8])
    status_text = "PROVISIONAL EDITORIAL" if editorial_status != "unreviewed" else "PENDING REVIEW"
    score_html = fmt_num(score) if score is not None else "—"
    image = f'<img class="world-detail-image" src="{esc(thumbnail)}" alt="{esc(name)}" />' if thumbnail else '<div class="world-detail-image world-detail-image-placeholder">VRC</div>'
    vrchat = f"https://vrchat.com/home/world/{wid}"

    return page_head(f"{name} — VRC Club Charts", description, canonical, "../") + site_header("../") + f"""
  <main class="shell world-detail-page">
    <a class="world-back" href="../index.html#discoverySection">← VRC Club Charts</a>
    <section class="world-detail-hero">
      <div class="world-detail-copy">
        <p class="kicker">{esc(status_text)}</p>
        <h1>{esc(name)}</h1>
        <p class="world-detail-author">by {esc(author)}</p>
        <div class="tags">{tags}</div>
        <div class="world-detail-actions">
          <a class="primary-button" href="{esc(vrchat)}" target="_blank" rel="noreferrer">OPEN IN VRCHAT ↗</a>
        </div>
      </div>
      {image}
    </section>

    <section class="world-detail-stats">
      <article><span>CRAFT</span><strong>{esc(score_html)}</strong></article>
      <article><span>TOTAL VISITS</span><strong>{esc(fmt_num(totals.get("visits")))}</strong></article>
      <article><span>TOTAL FAVS</span><strong>{esc(fmt_num(totals.get("favorites")))}</strong></article>
      <article><span>7D VISITS</span><strong>{esc(fmt_num(weekly.get("visits")))}</strong></article>
      <article><span>7D FAVS</span><strong>{esc(fmt_num(weekly.get("favorites")))}</strong></article>
    </section>

    <section class="world-detail-meta">
      <div><span>WORLD ID</span><code>{esc(wid)}</code></div>
      <div><span>STATUS</span><strong>{esc(editorial_status.upper())}</strong></div>
      <div><span>CAPACITY</span><strong>{esc(fmt_num(w.get("capacity")))}</strong></div>
      <div><span>WORLD UPDATED</span><strong>{esc(w.get("worldUpdatedAt") or "—")}</strong></div>
    </section>

    <p class="disclaimer">Editorial scores marked provisional are public-beta placeholders. Unreviewed worlds are not assigned a Craftsmanship score until review.</p>
  </main>
""" + footer("../")


def index_page(worlds: list[dict]) -> str:
    canonical = f"{BASE_URL}worlds/"
    description = "Browse VRChat club, DJ, rave and AudioLink worlds tracked by VRC Club Charts."
    cards = []
    for w in sorted(worlds, key=lambda x: (x.get("name") or "").casefold()):
        if w.get("availabilityStatus") == "unavailable":
            continue
        genres = " / ".join((w.get("genres") or [])[:4])
        cards.append(f"""<a class="world-catalog-row" href="{esc(w.get('id'))}.html">
          <span class="world-catalog-name">{esc(w.get('name'))}</span>
          <span>{esc(w.get('author'))}</span>
          <span>{esc(genres)}</span>
          <span>↗</span>
        </a>""")
    return page_head("Worlds — VRC Club Charts", description, canonical, "../") + site_header("../") + f"""
  <main class="shell world-catalog-page">
    <p class="kicker">WORLD DIRECTORY</p>
    <h1>VRChat club worlds.</h1>
    <p class="lead">{len(cards)} tracked worlds. Reviewed rankings and discovery candidates in one directory.</p>
    <div class="world-catalog">{''.join(cards)}</div>
  </main>
""" + footer("../")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: build_static_pages.py OUTPUT_DIR", file=sys.stderr)
        return 2
    out = Path(sys.argv[1])
    data = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
    worlds = data.get("worlds", [])
    events = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))

    world_dir = out / "worlds"
    world_dir.mkdir(parents=True, exist_ok=True)
    for w in worlds:
        (world_dir / f"{w['id']}.html").write_text(world_page(w), encoding="utf-8")
    (world_dir / "index.html").write_text(index_page(worlds), encoding="utf-8")
    (out / "events.ics").write_text(build_ics(events), encoding="utf-8", newline="")
    inject_event_json_ld(out, events)

    urls = [
        BASE_URL,
        f"{BASE_URL}about.html",
        f"{BASE_URL}privacy.html",
        f"{BASE_URL}events.html",
        f"{BASE_URL}djs.html",
        f"{BASE_URL}worlds/",
    ]
    urls.extend(
        f"{BASE_URL}worlds/{quote(w['id'])}.html"
        for w in worlds
        if w.get("availabilityStatus") != "unavailable"
    )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for i, url in enumerate(urls):
        priority = "1.0" if i == 0 else ("0.8" if "/worlds/" in url else "0.5")
        change = "weekly" if (i == 0 or "/worlds/" in url) else "monthly"
        sitemap += f"  <url><loc>{esc(url)}</loc><changefreq>{change}</changefreq><priority>{priority}</priority></url>\n"
    sitemap += "</urlset>\n"
    (out / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"Generated {len(worlds)} world pages, {len(events)} calendar events, ICS feed and sitemap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
