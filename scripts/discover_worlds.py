#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "world-candidates.json"
WORLDS = ROOT / "data" / "worlds.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"

LISTING_SOURCES = [
    ("vrcmap_music", "https://vrcmap.com/?category=music", 28),
    ("vrcmap_new", "https://vrcmap.com/?category=new", 25),
    ("vrcmap_cafe", "https://vrcmap.com/?category=cafe", 28),
    ("vrcmap_japan", "https://vrcmap.com/?category=japan", 27),
    ("vrcmap_trending", "https://vrcmap.com/?category=trending", 26),
    ("vrcmap_chill", "https://vrcmap.com/?category=chill", 24),
]

WORLD_ID_RE = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")
WORLD_LINK_RE = re.compile(r"/world/(wrld_[0-9a-fA-F-]{36})")
TAG_RE = re.compile(r"<[^>]+>")
H1_RE = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
MAX_DETAIL_FETCHES = 70

POSITIVE = {
    "club": 30,
    "クラブ": 30,
    "nightclub": 35,
    "dj": 24,
    "rave": 24,
    "レイブ": 24,
    "techno": 18,
    "テクノ": 18,
    "house music": 18,
    "dancefloor": 18,
    "dance floor": 18,
    "party": 12,
    "disco": 15,
    "ディスコ": 15,
    "audiolink": 8,
    "ltcgi": 8,
    "topazchat": 8,
    "stage": 5,
    "ステージ": 5,
    "music": 5,
    "音楽": 5,
}

NEGATIVE = {
    "avatar": 50,
    "アバター": 50,
    "mmd": 55,
    "studio": 35,
    "スタジオ": 35,
    "sleep": 35,
    "睡眠": 35,
    "chill": 22,
    "pool": 20,
    "プール": 20,
    "home": 18,
    "game": 18,
    "ゲーム": 18,
    "karaoke": 25,
    "カラオケ": 25,
    "livehouse": 15,
    "ライブハウス": 15,
}

STRONG_NIGHTLIFE = (
    "club", "クラブ", "nightclub", "dj", "rave", "レイブ",
    "techno", "テクノ", "dancefloor", "dance floor", "disco", "ディスコ",
)

HARD_EXCLUDE = (
    "content_adult", "content_sex", "adult only", "18+",
)


def fetch_text(url: str) -> str:
    headers = {
        "User-Agent": "VRCClubCharts/0.5 (+https://showchoo.github.io/vrc-club-charts/)",
        "Accept": "text/html,application/xhtml+xml,text/plain",
    }
    attempts = [url]
    if url.startswith("https://"):
        attempts.append("https://r.jina.ai/http://" + url.removeprefix("https://"))

    errors: list[str] = []
    for candidate_url in attempts:
        try:
            req = urllib.request.Request(candidate_url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as response:
                text = response.read().decode("utf-8", errors="replace")
                if "wrld_" in text:
                    if candidate_url != url:
                        print(f"INFO: using text fallback for {url}")
                    return text
                errors.append(f"{candidate_url}: response contained no World IDs")
        except Exception as exc:
            errors.append(f"{candidate_url}: {exc}")
    raise RuntimeError("; ".join(errors))


def public_rest(path: str) -> list[dict]:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Accept": "application/json",
            "User-Agent": "VRC-Club-Charts-Discovery/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"WARN: public Supabase read failed for {path}: {exc}")
        return []


def plain_text(raw_html: str) -> str:
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "\n", raw_html)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", "\n", cleaned)
    cleaned = TAG_RE.sub("\n", cleaned)
    cleaned = html.unescape(cleaned)
    lines = []
    for part in cleaned.splitlines():
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", part)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def listing_world_ids(raw_html: str) -> list[str]:
    ids = []
    seen = set()
    for match in WORLD_LINK_RE.finditer(raw_html):
        wid = match.group(1)
        if wid not in seen:
            seen.add(wid)
            ids.append(wid)
    # Reader-mode fallback can expose bare World IDs even if hrefs are normalized.
    if not ids:
        for wid in re.findall(r"wrld_[0-9a-fA-F-]{36}", raw_html):
            if wid not in seen:
                seen.add(wid)
                ids.append(wid)
    return ids


def detail_candidate(world_id: str, source_name: str, source_url: str, base_score: int) -> dict | None:
    detail_url = f"https://vrcmap.com/world/{world_id}"
    raw = fetch_text(detail_url)
    text = plain_text(raw)

    # Similar-world blocks contain unrelated keywords; ignore them for classification.
    lower_text = text.lower()
    cut = len(text)
    for marker in ("\nsimilar worlds", "\n似ている vrchat ワールド", "\nmore by", "\n作者の他のワールド"):
        pos = lower_text.find(marker.lower())
        if pos >= 0:
            cut = min(cut, pos)
    core = text[:cut]
    context = core.lower()

    if any(term in context for term in HARD_EXCLUDE):
        return None

    if not any(term in context for term in STRONG_NIGHTLIFE):
        return None

    score = base_score
    reasons = [f"source:{source_name}", "+explicit-nightlife"]
    for keyword, weight in POSITIVE.items():
        if keyword.lower() in context:
            score += weight
            reasons.append(f"+{keyword}")
    for keyword, weight in NEGATIVE.items():
        if keyword.lower() in context:
            score -= weight
            reasons.append(f"-{keyword}")

    score = max(0, min(100, score))

    name = ""
    h1 = H1_RE.search(raw)
    if h1:
        name = re.sub(r"\s+", " ", html.unescape(TAG_RE.sub("", h1.group(1)))).strip()
    if not name:
        lines = [x.strip() for x in core.splitlines() if x.strip()]
        for line in lines[:20]:
            if line != world_id and not line.lower().startswith(("vrcmap", "image:")):
                name = line
                break

    author = None
    lines = [x.strip() for x in core.splitlines() if x.strip()]
    for i, line in enumerate(lines[:40]):
        m = re.match(r"^by:\s*(.+)$", line, re.I)
        if m:
            author = m.group(1).strip()
            break
        if name and line == name and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt and not nxt.startswith(("#", "Image:")) and len(nxt) <= 120:
                author = nxt
                break

    # A title naming a nightlife venue is stronger evidence than a broad
    # Music/Japan/Bar category. Reject non-nightlife 'clubs' such as fight clubs.
    if re.search(r"fight(?:ing)?[\\s-]*club|avatar|アバター|mmd|karaoke|カラオケ", name, re.I):
        return None
    if re.search(r"club|クラブ|disco|ディスコ|nightclub|rave|レイブ", name, re.I):
        score = min(100, score + 25)
        reasons.append("+explicit-club-name")
    if score < 55:
        return None

    return {
        "id": world_id,
        "name": name or world_id,
        "authorHint": author,
        "source": detail_url,
        "sourceCategories": [source_name],
        "confidenceScore": score,
        "confidence": "high" if score >= 80 else "medium",
        "reasons": reasons[:14],
    }


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    existing_catalog = json.loads(WORLDS.read_text(encoding="utf-8"))
    existing_ids = {
        str(item.get("id"))
        for item in existing_catalog
        if isinstance(item, dict) and item.get("id")
    }

    approved_extra = public_rest("worlds_public?select=id")
    existing_ids.update(str(item.get("id")) for item in approved_extra if item.get("id"))

    decisions = public_rest("world_candidate_decisions?select=world_id,status")
    decided_ids = {
        str(item.get("world_id"))
        for item in decisions
        if item.get("world_id") and item.get("status") in {"approved", "rejected"}
    }

    previous: list[dict] = []
    if OUT.exists():
        try:
            parsed = json.loads(OUT.read_text(encoding="utf-8"))
            previous = parsed if isinstance(parsed, list) else []
        except Exception:
            previous = []

    source_membership: dict[str, list[tuple[str, str, int]]] = {}
    successful_sources = 0

    for source_name, source_url, base_score in LISTING_SOURCES:
        try:
            raw = fetch_text(source_url)
            ids = listing_world_ids(raw)
            successful_sources += 1
            print(f"{source_name}: found {len(ids)} listed World IDs")
            for wid in ids:
                if wid in existing_ids or wid in decided_ids:
                    continue
                source_membership.setdefault(wid, []).append((source_name, source_url, base_score))
        except Exception as exc:
            print(f"WARN: discovery source failed {source_url}: {exc}")

    if successful_sources == 0:
        print("WARN: VRCmap sources unavailable; checking independent club directories")

    # Rotate a bounded sample through each category. The old deterministic
    # first-70 selection rechecked the same Worlds every day forever.
    from discover_vrcw import STATE, read_json
    discovery_state = read_json(STATE, {})
    discovery_state = discovery_state if isinstance(discovery_state, dict) else {}
    saved_positions = discovery_state.get("vrcmapNextIndex", {})
    saved_positions = saved_positions if isinstance(saved_positions, dict) else {}
    next_positions = dict(saved_positions)
    selected_ids = []
    seen_ids = set()
    per_source = max(5, min(24, int(os.environ.get("VCC_VRCMAP_DETAILS_PER_SOURCE", "12"))))
    for source_name, _, _ in LISTING_SOURCES:
        pool = sorted(wid for wid, memberships in source_membership.items()
                      if any(member[0] == source_name for member in memberships))
        if not pool:
            continue
        start = max(0, int(saved_positions.get(source_name, 0))) % len(pool)
        cycle = pool[start:] + pool[:start]
        for wid in cycle[:per_source]:
            if wid not in seen_ids and len(selected_ids) < MAX_DETAIL_FETCHES:
                selected_ids.append(wid)
                seen_ids.add(wid)
        next_positions[source_name] = (start + per_source) % len(pool)
        print(f"{source_name}: rotating detail index {start} -> {next_positions[source_name]} "
              f"from {len(pool)} unregistered IDs")
    ordered = [(wid, source_membership[wid]) for wid in selected_ids]
    if successful_sources:
        discovery_state["vrcmapNextIndex"] = next_positions
        discovery_state["updatedAt"] = today
        STATE.write_text(json.dumps(discovery_state, ensure_ascii=False, indent=2)
                         + "\\n", encoding="utf-8")

    by_id: dict[str, dict] = {}
    for idx, (wid, memberships) in enumerate(ordered):
        source_name, source_url, base_score = max(memberships, key=lambda x: x[2])
        try:
            item = detail_candidate(wid, source_name, source_url, base_score)
            if item is None:
                continue
            item["sourceCategories"] = sorted({m[0] for m in memberships})
            by_id[wid] = item
            print(f"CANDIDATE {wid} {item['name']} score={item['confidenceScore']}")
        except Exception as exc:
            print(f"WARN: detail fetch failed {wid}: {exc}")
        if idx < len(ordered) - 1:
            time.sleep(0.15)

    # Independently crawl verified club/DJ category listings with resumable paging.
    # A VRCmap outage must not block this source, and vice versa.
    from discover_vrcw import discover_candidates, priority_seeds, auto_register
    vrcw_items, vrcw_ok = discover_candidates(today)
    from discover_official import collect_candidates
    official_items, official_ok = collect_candidates(today)
    for item in vrcw_items + official_items + priority_seeds(today):
        wid = item["id"]
        if wid in existing_ids or wid in decided_ids:
            continue
        prior = by_id.get(wid)
        if prior:
            prior["sourceCategories"] = sorted(set(
                prior.get("sourceCategories", []) + item.get("sourceCategories", [])
            ))
            prior["reasons"] = list(dict.fromkeys(
                prior.get("reasons", []) + item.get("reasons", [])
            ))
            if item["confidenceScore"] > prior.get("confidenceScore", 0):
                by_id[wid] = {**prior, **item,
                              "sourceCategories": prior["sourceCategories"],
                              "reasons": prior["reasons"]}
        else:
            by_id[wid] = item

    previous_by_id = {
        str(item.get("id")): item
        for item in previous
        if isinstance(item, dict) and item.get("id")
    }

    for wid, item in list(by_id.items()):
        old = previous_by_id.get(wid)
        item["firstDiscoveredAt"] = (old.get("firstDiscoveredAt") if old else None) or today
        item["lastSeenAt"] = today

    cutoff = dt.date.fromisoformat(today) - dt.timedelta(days=30)
    for wid, old in previous_by_id.items():
        if wid in by_id or wid in existing_ids or wid in decided_ids:
            continue
        try:
            last_seen = dt.date.fromisoformat(str(old.get("lastSeenAt") or old.get("firstDiscoveredAt")))
        except Exception:
            continue
        if last_seen >= cutoff:
            by_id[wid] = old

    if not successful_sources and not vrcw_ok and not official_ok and not by_id:
        print("ERROR: all discovery sources failed; preserving previous candidate file")
        return 2

    # Incremental promotion does not require manual approval for independently
    # verified, public club Worlds. No legacy data or decisions are deleted.
    new_ids = auto_register(list(by_id.values()), existing_catalog, decided_ids)
    if new_ids:
        existing_catalog.sort(key=lambda w: str(w.get("name", "")).casefold())
        WORLDS.write_text(json.dumps(existing_catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for wid in new_ids:
            by_id.pop(wid, None)

    candidates = sorted(
        by_id.values(),
        key=lambda x: (
            -int(x.get("confidenceScore") or 0),
            str(x.get("firstDiscoveredAt") or ""),
            str(x.get("name") or "").casefold(),
        ),
    )

    OUT.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}: {len(candidates)} unresolved candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
