#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
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


def event_id(event: dict) -> str:
    explicit = str(event.get("id") or "").strip()
    if explicit:
        return re.sub(r"[^a-z0-9_-]+", "-", explicit.lower()).strip("-")[:96]
    seed = f"{event.get('name')}|{event.get('start')}|{event.get('organizer')}"
    return "event-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def event_match_key(event: dict) -> tuple[str, str]:
    name = re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龯]+", "", str(event.get("name") or "").casefold())
    raw_start = str(event.get("start") or "")
    try:
        parsed = dt.datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        start_key = parsed.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        start_key = raw_start[:16]
    return name, start_key


def merge_events(manual: list[dict], automatic: list[dict]) -> list[dict]:
    """Merge curated and imported events. Curated/manual records always win."""
    merged: list[dict] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()

    def add(event: dict) -> bool:
        eid = event_id(event)
        key = event_match_key(event)
        url = str(event.get("url") or "").strip().rstrip("/")
        if eid in seen_ids or key in seen_keys or (url and url in seen_urls):
            return False
        seen_ids.add(eid)
        seen_keys.add(key)
        if url:
            seen_urls.add(url)
        merged.append(event)
        return True

    for event in manual:
        if isinstance(event, dict):
            add(event)
    for event in automatic:
        if isinstance(event, dict):
            add(event)

    merged.sort(key=lambda e: (str(e.get("start") or ""), str(e.get("name") or "").casefold()))
    return merged


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
  <link rel="stylesheet" href="{prefix}styles.css?v=20261005-16" />
  <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
</head>
<body>
  <div class="noise"></div>
"""


def site_header(prefix: str = "", active: str = "") -> str:
    def cls(key: str) -> str:
        return "nav-link active" if key == active else "nav-link"
    return f"""  <header class="site-header">
    <a class="brand" href="{prefix}index.html"><span class="brand-mark">VCC</span><span>VRC CLUB CHARTS</span></a>
    <nav class="nav">
      <a class="{cls('charts')}" href="{prefix}index.html">Charts</a>
      <a class="{cls('worlds')}" href="{prefix}worlds/index.html">Worlds</a>
      <a class="{cls('events')}" href="{prefix}events.html">Events</a>
      <a class="{cls('djs')}" href="{prefix}djs.html">DJs</a>
      <a class="{cls('about')}" href="{prefix}about.html">About</a>
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


def event_page(event: dict, djs: list[dict]) -> str:
    eid = event_id(event)
    name = event.get("name") or eid
    organizer = event.get("organizer") or "—"
    world_name = event.get("worldName") or event.get("worldId") or "VRChat"
    genres = event.get("genres") or []
    tags = "".join(f'<span class="tag">{esc(g)}</span>' for g in genres[:8])
    start = str(event.get("start") or "")
    end = str(event.get("end") or "")
    canonical = f"{BASE_URL}events/{quote(eid)}.html"
    description = f"{name} — VRChat DJ / music event details on VRC Club Charts."
    public_url = event.get("url")
    world_id = event.get("worldId")
    world_link = f'../worlds/{esc(world_id)}.html' if world_id else None

    dj_by_id = {str(d.get("id")): d for d in djs if d.get("id")}
    dj_cards = []
    for dj_id in event.get("djIds") or []:
        dj = dj_by_id.get(str(dj_id))
        if not dj:
            continue
        genres_text = " / ".join((dj.get("genres") or [])[:3])
        dj_cards.append(
            f'<a class="relation-dj" href="../djs/{esc(dj_id)}.html">'
            f'<strong>{esc(dj.get("name"))}</strong><span>{esc(genres_text or dj.get("role") or "DJ")}</span><b>↗</b></a>'
        )
    djs_html = "".join(dj_cards) if dj_cards else '<div class="relation-empty">Lineup profiles are being connected.</div>'

    buttons = []
    if public_url:
        buttons.append(f'<a class="primary-button" href="{esc(public_url)}" target="_blank" rel="noreferrer">PUBLIC INFO ↗</a>')
    if world_link:
        buttons.append(f'<a class="secondary-button" href="{world_link}">WORLD PROFILE ↗</a>')
    actions = "".join(buttons)

    event_ld = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": name,
        "startDate": start,
        "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
        "eventStatus": "https://schema.org/EventScheduled",
        "location": {"@type": "VirtualLocation", "name": world_name, "url": public_url or canonical},
        "organizer": {"@type": "Organization", "name": organizer},
        "url": public_url or canonical,
    }
    if end:
        event_ld["endDate"] = end

    return page_head(f"{name} — VRC Club Charts", description, canonical, "../") + site_header("../", "events") + f"""
  <main class="shell world-detail-page event-detail-page">
    <a class="world-back" href="../events.html">← Event Calendar</a>
    <section class="world-detail-hero event-detail-hero">
      <div class="world-detail-copy">
        <p class="kicker">VRCHAT EVENT</p>
        <h1>{esc(name)}</h1>
        <p class="world-detail-author">{esc(organizer)}</p>
        <div class="tags">{tags}</div>
        <div class="world-detail-actions">{actions}</div>
      </div>
      <div class="world-detail-image world-detail-image-placeholder event-detail-mark">LIVE</div>
    </section>

    <section class="world-detail-meta event-detail-meta">
      <div><span>START</span><strong>{esc(start.replace("T", " ")[:16])}</strong></div>
      <div><span>END</span><strong>{esc(end.replace("T", " ")[:16] if end else "—")}</strong></div>
      <div><span>WORLD / INSTANCE</span><strong>{esc(world_name)}</strong></div>
      <div><span>SOURCE</span><strong>{esc(event.get("source") or "Public organizer information")}</strong></div>
    </section>

    <section class="world-relations">
      <div class="section-heading"><div><p class="kicker">LINEUP</p><h2>Connected DJs</h2></div></div>
      <div class="relation-dj-grid">{djs_html}</div>
    </section>

    <script type="application/ld+json">{json.dumps(event_ld, ensure_ascii=False)}</script>
  </main>
""" + footer("../")


def world_page(w: dict, events: list[dict], djs: list[dict]) -> str:
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
    source_url = w.get("source")

    now = dt.datetime.now(dt.timezone.utc)
    related_events = []
    linked_dj_ids = set()
    for event in events:
        if event.get("worldId") != wid or not event.get("start"):
            continue
        try:
            event_start = dt.datetime.fromisoformat(str(event["start"]).replace("Z", "+00:00"))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if event_start < now - dt.timedelta(hours=8):
            continue
        related_events.append((event_start, event))
        linked_dj_ids.update(event.get("djIds") or [])
    related_events.sort(key=lambda x: x[0])

    dj_by_id = {str(d.get("id")): d for d in djs if d.get("id")}
    related_djs = [dj_by_id[dj_id] for dj_id in sorted(linked_dj_ids) if dj_id in dj_by_id]

    event_rows = []
    for _, event in related_events[:6]:
        when = str(event.get("start") or "").replace("T", " ")[:16]
        event_rows.append(
            f'<a class="relation-row" href="../events/{esc(event_id(event))}.html">'
            f'<span>{esc(when)}</span><strong>{esc(event.get("name"))}</strong>'
            f'<span>{esc(event.get("organizer") or "—")}</span><b>↗</b></a>'
        )
    events_html = "".join(event_rows) if event_rows else '<div class="relation-empty">Upcoming linked events are being collected.</div>'

    dj_cards = []
    for dj in related_djs[:12]:
        genres_text = " / ".join((dj.get("genres") or [])[:3])
        dj_cards.append(
            f'<a class="relation-dj" href="../djs/{esc(dj.get("id"))}.html">'
            f'<strong>{esc(dj.get("name"))}</strong><span>{esc(genres_text or dj.get("role") or "DJ")}</span><b>↗</b></a>'
        )
    djs_html = "".join(dj_cards) if dj_cards else '<div class="relation-empty">Linked DJ profiles will appear when event lineups are connected.</div>'

    return page_head(f"{name} — VRC Club Charts", description, canonical, "../") + site_header("../", "worlds") + f"""
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
          {f'<a class="secondary-button" href="{esc(source_url)}" target="_blank" rel="noreferrer">PUBLIC SOURCE ↗</a>' if source_url else ""}
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

    <section class="world-relations">
      <div class="section-heading">
        <div><p class="kicker">UPCOMING HERE</p><h2>Events at this world</h2></div>
      </div>
      <div class="relation-list">{events_html}</div>
    </section>

    <section class="world-relations">
      <div class="section-heading">
        <div><p class="kicker">CONNECTED DJs</p><h2>People on the lineup</h2></div>
      </div>
      <div class="relation-dj-grid">{djs_html}</div>
    </section>

    <p class="disclaimer">Editorial scores marked provisional are public-beta placeholders. Unreviewed worlds are not assigned a Craftsmanship score until review.</p>
  </main>
""" + footer("../")


def dj_page(dj: dict, events: list[dict]) -> str:
    dj_id = dj.get("id", "")
    name = dj.get("name") or dj_id
    role = dj.get("role") or "DJ"
    affiliations = dj.get("affiliations") or []
    genres = dj.get("genres") or []
    source = dj.get("source")
    canonical = f"{BASE_URL}djs/{quote(dj_id)}.html"
    description = f"{name} — VRChat DJ profile, genres and upcoming appearances on VRC Club Charts."
    tags = "".join(f'<span class="tag">{esc(g)}</span>' for g in genres)
    crews = " / ".join(affiliations) or "—"

    appearances = []
    for event in sorted(events, key=lambda e: e.get("start", "")):
        if dj_id not in (event.get("djIds") or []):
            continue
        when = str(event.get("start") or "").replace("T", " ")[:16]
        appearances.append(
            f'<a class="dj-event-row" href="../events/{esc(event_id(event))}.html"><span>{esc(when)}</span>'
            f'<strong>{esc(event.get("name"))}</strong><span>{esc(event.get("worldName") or "VRChat")}</span><span>↗</span></a>'
        )

    person_ld = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "description": role,
        "url": canonical,
        "knowsAbout": genres,
        "memberOf": affiliations,
    }
    source_button = (
        f'<a class="secondary-button" href="{esc(source)}" target="_blank" rel="noreferrer">PUBLIC SOURCE ↗</a>'
        if source else ""
    )
    appearances_html = "".join(appearances) if appearances else '<div class="dj-events-empty">Upcoming linked appearances are being collected.</div>'

    return page_head(f"{name} — VRC Club Charts", description, canonical, "../") + site_header("../", "djs") + f"""
  <main class="shell world-detail-page dj-detail-page">
    <a class="world-back" href="../djs.html">← DJ Directory</a>
    <section class="world-detail-hero dj-detail-hero">
      <div class="world-detail-copy">
        <p class="kicker">NON-RANKED DJ PROFILE</p>
        <h1>{esc(name)}</h1>
        <p class="world-detail-author">{esc(role)}</p>
        <div class="tags">{tags}</div>
        <div class="world-detail-actions">{source_button}</div>
      </div>
      <div class="world-detail-image world-detail-image-placeholder dj-detail-mark">DJ</div>
    </section>

    <section class="world-detail-meta dj-detail-meta">
      <div><span>AFFILIATION</span><strong>{esc(crews)}</strong></div>
      <div><span>PROFILE TYPE</span><strong>DIRECTORY / NON-RANKED</strong></div>
    </section>

    <section class="dj-appearances">
      <div class="section-heading">
        <div><p class="kicker">APPEARANCES</p><h2>Upcoming events</h2></div>
      </div>
      <div class="dj-event-list">{appearances_html}</div>
    </section>
    <script type="application/ld+json">{json.dumps(person_ld, ensure_ascii=False)}</script>
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
        status = "reviewed" if w.get("editorialStatus") != "unreviewed" else "discovery"
        hay = " ".join([
            str(w.get("name") or ""),
            str(w.get("author") or ""),
            " ".join(w.get("genres") or []),
        ]).casefold()
        cards.append(f"""<a class="world-catalog-row" href="{esc(w.get('id'))}.html" data-status="{esc(status)}" data-hay="{esc(hay)}">
          <span class="world-catalog-name">{esc(w.get('name'))}</span>
          <span>{esc(w.get('author'))}</span>
          <span>{esc(genres)}</span>
          <span>↗</span>
        </a>""")
    return page_head("Worlds — VRC Club Charts", description, canonical, "../") + site_header("../", "worlds") + f"""
  <main class="shell world-catalog-page">
    <p class="kicker">WORLD DIRECTORY</p>
    <h1>VRChat club worlds.</h1>
    <p class="lead">{len(cards)} tracked worlds. Reviewed rankings and discovery candidates in one directory.</p>
    <div class="world-directory-controls">
      <label class="search-wrap world-directory-search"><span>⌕</span><input id="worldDirectorySearch" type="search" placeholder="World, creator, genre" /></label>
      <div class="chip-row" id="worldDirectoryFilters">
        <button class="chip active" type="button" data-status-filter="all">ALL</button>
        <button class="chip" type="button" data-status-filter="reviewed">REVIEWED</button>
        <button class="chip" type="button" data-status-filter="discovery">DISCOVERY</button>
      </div>
      <span id="worldDirectoryCount" class="discovery-count">{len(cards)} WORLDS</span>
    </div>
    <div id="worldCatalog" class="world-catalog">{''.join(cards)}</div>
    <script>
      (() => {{
        const input = document.getElementById('worldDirectorySearch');
        const rows = [...document.querySelectorAll('.world-catalog-row')];
        const count = document.getElementById('worldDirectoryCount');
        const buttons = [...document.querySelectorAll('[data-status-filter]')];
        let status = 'all';
        function apply() {{
          const q = (input.value || '').trim().toLowerCase();
          let visible = 0;
          rows.forEach(row => {{
            const okStatus = status === 'all' || row.dataset.status === status;
            const okQuery = !q || (row.dataset.hay || '').includes(q);
            const show = okStatus && okQuery;
            row.hidden = !show;
            if (show) visible += 1;
          }});
          count.textContent = visible + ' WORLDS';
        }}
        input.addEventListener('input', apply);
        buttons.forEach(button => button.addEventListener('click', () => {{
          status = button.dataset.statusFilter;
          buttons.forEach(b => b.classList.toggle('active', b === button));
          apply();
        }}));
      }})();
    </script>
  </main>
""" + footer("../")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: build_static_pages.py OUTPUT_DIR", file=sys.stderr)
        return 2
    out = Path(sys.argv[1])
    data = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
    worlds = data.get("worlds", [])
    manual_events = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
    auto_events_path = ROOT / "data/events-auto.json"
    auto_events = json.loads(auto_events_path.read_text(encoding="utf-8")) if auto_events_path.exists() else []
    events = merge_events(manual_events, auto_events)
    djs = json.loads((ROOT / "data/djs.json").read_text(encoding="utf-8"))

    public_data_dir = out / "data"
    public_data_dir.mkdir(parents=True, exist_ok=True)
    (public_data_dir / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    world_dir = out / "worlds"
    world_dir.mkdir(parents=True, exist_ok=True)
    for w in worlds:
        (world_dir / f"{w['id']}.html").write_text(world_page(w, events, djs), encoding="utf-8")
    (world_dir / "index.html").write_text(index_page(worlds), encoding="utf-8")

    dj_dir = out / "djs"
    dj_dir.mkdir(parents=True, exist_ok=True)
    for dj in djs:
        if dj.get("id"):
            (dj_dir / f"{dj['id']}.html").write_text(dj_page(dj, events), encoding="utf-8")

    event_dir = out / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    for event in events:
        if event.get("name") and event.get("start"):
            (event_dir / f"{event_id(event)}.html").write_text(event_page(event, djs), encoding="utf-8")

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
    urls.extend(
        f"{BASE_URL}djs/{quote(dj['id'])}.html"
        for dj in djs
        if dj.get("id")
    )
    urls.extend(
        f"{BASE_URL}events/{quote(event_id(event))}.html"
        for event in events
        if event.get("name") and event.get("start")
    )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for i, url in enumerate(urls):
        priority = "1.0" if i == 0 else ("0.8" if "/worlds/" in url else "0.5")
        change = "weekly" if (i == 0 or "/worlds/" in url) else "monthly"
        sitemap += f"  <url><loc>{esc(url)}</loc><changefreq>{change}</changefreq><priority>{priority}</priority></url>\n"
    sitemap += "</urlset>\n"
    (out / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"Generated {len(worlds)} world pages, {len(djs)} DJ pages, {len(events)} merged event pages, ICS feed and sitemap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
