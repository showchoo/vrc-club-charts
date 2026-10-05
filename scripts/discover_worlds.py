#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "world-candidates.json"
WORLDS = ROOT / "data" / "worlds.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"

SOURCES = [
    ("club", "https://www.vrcw.net/category/detail/club", 80),
    ("event_venue", "https://www.vrcw.net/category/detail/event_venue", 35),
]

WORLD_ID_RE = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")
TAG_RE = re.compile(r"<[^>]+>")

POSITIVE = {
    "club": 30,
    "クラブ": 30,
    "nightclub": 30,
    "dj": 20,
    "rave": 20,
    "techno": 15,
    "house music": 15,
    "dance": 10,
    "ダンス": 10,
    "music": 10,
    "音楽": 10,
    "event": 8,
    "イベント会場": 8,
    "stage": 5,
    "ステージ": 5,
    "audiolink": 8,
    "オーディオリンク": 8,
    "disco": 12,
}

NEGATIVE = {
    "avatar": 45,
    "アバター": 45,
    "mmd": 45,
    "studio": 35,
    "スタジオ": 35,
    "clubhouse": 25,
    "sleep": 30,
    "睡眠": 30,
    "chill": 25,
    "pool": 20,
    "プール": 20,
    "home": 20,
    "game": 15,
    "ゲーム": 15,
}


def fetch_text(url: str) -> str:
    headers = {
        "User-Agent": "VRCClubCharts/0.4 (+https://showchoo.github.io/vrc-club-charts/)",
        "Accept": "text/html,application/xhtml+xml,text/plain",
    }
    attempts = [url]
    if url.startswith("https://"):
        # VRCW may block GitHub-hosted runners. Jina Reader is used only as a
        # read-only text fallback so the source site still receives just one
        # lightweight fetch per category per day.
        attempts.append("https://r.jina.ai/http://" + url.removeprefix("https://"))

    last_error: Exception | None = None
    for candidate_url in attempts:
        try:
            req = urllib.request.Request(candidate_url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as response:
                text = response.read().decode("utf-8", errors="replace")
                if "wrld_" in text:
                    if candidate_url != url:
                        print(f"INFO: using text fallback for {url}")
                    return text
        except Exception as exc:
            last_error = exc
            print(f"WARN: fetch failed {candidate_url}: {exc}")

    if last_error:
        raise last_error
    raise RuntimeError(f"no usable response for {url}")


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


def visible_lines(raw_html: str) -> list[str]:
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
    return lines


def parse_vrcw(raw_html: str, source_name: str, source_url: str, base_score: int) -> list[dict]:
    lines = visible_lines(raw_html)
    world_positions = [i for i, line in enumerate(lines) if WORLD_ID_RE.fullmatch(line)]
    found: list[dict] = []

    for pos, i in enumerate(world_positions):
        line = lines[i]
        next_i = world_positions[pos + 1] if pos + 1 < len(world_positions) else len(lines)

        name = ""
        for j in range(i - 1, max(-1, i - 8), -1):
            candidate = lines[j]
            if candidate in {"ワールドID", "World ID"}:
                continue
            if WORLD_ID_RE.fullmatch(candidate):
                break
            if len(candidate) > 1:
                name = candidate
                break

        author = ""
        for j in range(i + 1, min(next_i, i + 10)):
            if lines[j] in {"制作", "Creator", "Author"} and j + 1 < next_i:
                author = re.sub(r"\s*さん$", "", lines[j + 1]).strip()
                break

        # Score only this World's own block. Avoid leaking keywords from adjacent entries.
        block_end = max(i + 1, next_i - 2)
        context_lines = lines[max(0, i - 4): block_end]
        context = " ".join(context_lines).lower()

        score = base_score
        reasons = [f"source:{source_name}"]
        for keyword, weight in POSITIVE.items():
            if keyword.lower() in context:
                score += weight
                reasons.append(f"+{keyword}")
        for keyword, weight in NEGATIVE.items():
            if keyword.lower() in context:
                score -= weight
                reasons.append(f"-{keyword}")

        if source_name == "event_venue":
            has_strong = any(k in context for k in ["club", "クラブ", "dj", "rave", "techno"])
            if not has_strong:
                score -= 20
                reasons.append("-weak-event-match")

        score = max(0, min(100, score))
        if score < 55:
            continue

        found.append(
            {
                "id": line,
                "name": name or line,
                "authorHint": author or None,
                "source": source_url,
                "sourceCategories": [source_name],
                "confidenceScore": score,
                "confidence": "high" if score >= 80 else "medium",
                "reasons": reasons[:12],
            }
        )
    return found


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

    by_id: dict[str, dict] = {}
    successful_sources = 0

    for source_name, source_url, base_score in SOURCES:
        try:
            raw = fetch_text(source_url)
            parsed = parse_vrcw(raw, source_name, source_url, base_score)
            successful_sources += 1
            print(f"{source_name}: parsed {len(parsed)} candidate-like worlds")
            for item in parsed:
                wid = item["id"]
                if wid in existing_ids or wid in decided_ids:
                    continue
                old = by_id.get(wid)
                if old:
                    merged_sources = sorted(set(old.get("sourceCategories", [])) | set(item.get("sourceCategories", [])))
                    old["sourceCategories"] = merged_sources
                    if item["confidenceScore"] > old["confidenceScore"]:
                        old.update({k: v for k, v in item.items() if k != "sourceCategories"})
                        old["sourceCategories"] = merged_sources
                else:
                    by_id[wid] = item
        except Exception as exc:
            print(f"WARN: discovery source failed {source_url}: {exc}")

    if successful_sources == 0:
        print("ERROR: all discovery sources failed; preserving previous candidate file")
        return 2

    previous_by_id = {
        str(item.get("id")): item
        for item in previous
        if isinstance(item, dict) and item.get("id")
    }

    for wid, item in list(by_id.items()):
        old = previous_by_id.get(wid)
        item["firstDiscoveredAt"] = (
            old.get("firstDiscoveredAt") if old else None
        ) or today
        item["lastSeenAt"] = today

    # Preserve unresolved candidates briefly even if a source page rotates them off.
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
