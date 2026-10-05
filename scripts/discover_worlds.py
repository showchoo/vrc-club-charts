#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "world-candidates.json"
WORLDS = ROOT / "data" / "worlds.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"

BLUECAT_RAW = "https://raw.githubusercontent.com/BlueCatVRC/AdventureDailyLists/main"
BLUECAT_WEB = "https://github.com/BlueCatVRC/AdventureDailyLists/blob/main"
VRCHAT_WORLD_API = "https://api.vrchat.cloud/api/1/worlds"

WORLD_ID_RE = re.compile(r"wrld_[0-9a-fA-F-]{36}")

# This is only a cheap prefilter. Every surviving ID is verified against
# VRChat's official World-by-ID endpoint before it enters the moderation queue.
NAME_PREFILTER = re.compile(
    r"("
    r"night\s*club|nightclub|club|クラブ|"
    r"\bdj\b|rave|レイブ|techno|disco|ディスコ|"
    r"party|dance|ダンス|music|音楽|ライブ|live\s*house|"
    r"warehouse|underground|venue"
    r")",
    re.IGNORECASE,
)

POSITIVE = {
    "nightclub": 45,
    "night club": 45,
    "author_tag_nightclub": 45,
    "dj": 30,
    "author_tag_dj": 30,
    "rave": 35,
    "techno": 25,
    "dancefloor": 25,
    "dance floor": 25,
    "live_music": 20,
    "live music": 20,
    "author_tag_live_music": 20,
    "vrsl": 12,
    "audiolink": 10,
    "audio link": 10,
    "dancing": 12,
    "author_tag_dancing": 12,
    "club": 20,
    "クラブ": 20,
    "disco": 18,
    "ディスコ": 18,
    "party": 10,
    "music": 8,
    "音楽": 8,
    "dance": 8,
    "ダンス": 8,
    "stage": 6,
    "venue": 6,
}

NEGATIVE = {
    "comedy club": 60,
    "golf club": 60,
    "billiards club": 60,
    "language practice club": 60,
    "book club": 60,
    "sports club": 60,
    "fan club": 35,
    "clubhouse": 30,
    "avatar": 50,
    "アバター": 50,
    "mmd": 50,
    "studio": 30,
    "スタジオ": 30,
    "chill": 25,
    "pool": 25,
    "プール": 25,
    "home": 25,
    "game": 25,
    "ゲーム": 25,
}

STRONG_SIGNALS = (
    "nightclub",
    "night club",
    "author_tag_nightclub",
    "dj",
    "author_tag_dj",
    "rave",
    "techno",
    "dancefloor",
    "dance floor",
    "live_music",
    "author_tag_live_music",
    "vrsl",
)


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VRCClubCharts/0.5 (+https://showchoo.github.io/vrc-club-charts/)",
            "Accept": "text/plain,application/json,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 30) -> dict | list:
    return json.loads(fetch_text(url, timeout=timeout))


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


def jst_today() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()


def parse_daily_list(text: str, date: dt.date) -> list[dict]:
    rows: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        match = WORLD_ID_RE.search(line)
        if not match:
            continue
        world_id = match.group(0)
        if "https://" in line:
            name = line.split("https://", 1)[0].rstrip(" :：").strip()
        else:
            name = line[: match.start()].rstrip(" :：-").strip()
        if not name:
            name = world_id
        rows.append(
            {
                "id": world_id,
                "sourceName": name,
                "sourceDate": date.isoformat(),
                "source": f"{BLUECAT_WEB}/{date.year}/{date.isoformat()}.txt",
            }
        )
    return rows


def load_recent_source_worlds(days: int = 7) -> list[dict]:
    today = jst_today()
    by_id: dict[str, dict] = {}
    successful_files = 0

    for offset in range(days):
        date = today - dt.timedelta(days=offset)
        url = f"{BLUECAT_RAW}/{date.year}/{date.isoformat()}.txt"
        try:
            text = fetch_text(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            print(f"WARN: source fetch failed {url}: HTTP {exc.code}")
            continue
        except Exception as exc:
            print(f"WARN: source fetch failed {url}: {exc}")
            continue

        successful_files += 1
        parsed = parse_daily_list(text, date)
        print(f"BlueCat {date.isoformat()}: {len(parsed)} Worlds")
        for item in parsed:
            # Keep the newest occurrence of a repeated World ID.
            by_id.setdefault(item["id"], item)

    if successful_files == 0:
        raise RuntimeError("no recent BlueCat daily files were reachable")

    return list(by_id.values())


def official_world(world_id: str) -> dict | None:
    try:
        data = fetch_json(f"{VRCHAT_WORLD_API}/{world_id}", timeout=30)
    except urllib.error.HTTPError as exc:
        print(f"WARN: VRChat {world_id}: HTTP {exc.code}")
        return None
    except Exception as exc:
        print(f"WARN: VRChat {world_id}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def score_world(world: dict, source_name: str) -> tuple[int, list[str]]:
    tags = [str(tag) for tag in world.get("tags", []) if isinstance(tag, str)]
    text = " ".join(
        [
            str(world.get("name") or ""),
            str(world.get("description") or ""),
            " ".join(tags),
            source_name,
        ]
    ).lower()

    score = 0
    reasons: list[str] = []
    for keyword, weight in POSITIVE.items():
        if keyword.lower() in text:
            score += weight
            reasons.append(f"+{keyword}")
    for keyword, weight in NEGATIVE.items():
        if keyword.lower() in text:
            score -= weight
            reasons.append(f"-{keyword}")

    strong = any(signal in text for signal in STRONG_SIGNALS)
    name_has_club = bool(re.search(r"(^|\W)(club|クラブ)(\W|$)", str(world.get("name") or ""), re.IGNORECASE))
    if strong:
        score += 10
        reasons.append("+strong-nightlife")
    elif name_has_club:
        score += 5
        reasons.append("+club-name")
    else:
        # A weak name hit like "party" or "music" is not enough on its own.
        score -= 20
        reasons.append("-no-strong-nightlife")

    publication = str(world.get("publicationDate") or "")
    try:
        published = dt.datetime.fromisoformat(publication.replace("Z", "+00:00")).date()
        age = (jst_today() - published).days
        if 0 <= age <= 90:
            score += 10
            reasons.append("+published<=90d")
        elif 0 <= age <= 365:
            score += 5
            reasons.append("+published<=365d")
    except Exception:
        pass

    return max(0, min(100, score)), reasons[:16]


def main() -> int:
    today = jst_today().isoformat()

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

    try:
        source_worlds = load_recent_source_worlds(days=7)
    except Exception as exc:
        print(f"ERROR: discovery source unavailable: {exc}")
        print("Preserving previous candidate file.")
        return 2

    # Cheap name prefilter keeps VRChat API traffic conservative.
    source_candidates = [
        item for item in source_worlds
        if item["id"] not in existing_ids
        and item["id"] not in decided_ids
        and NAME_PREFILTER.search(str(item.get("sourceName") or ""))
    ]
    source_candidates.sort(key=lambda x: (x["sourceDate"], x["sourceName"]), reverse=True)
    source_candidates = source_candidates[:12]

    print(
        f"Recent source Worlds: {len(source_worlds)}; "
        f"name-prefilter candidates: {len(source_candidates)}"
    )

    by_id: dict[str, dict] = {}
    for index, source in enumerate(source_candidates):
        if index:
            # Keep automated traffic to the anonymous World-by-ID endpoint modest.
            time.sleep(8)

        world = official_world(source["id"])
        if not world:
            continue
        if str(world.get("releaseStatus") or "").lower() != "public":
            continue

        score, reasons = score_world(world, source["sourceName"])
        if score < 45:
            print(f"Rejected by metadata score {score}: {world.get('name')} ({source['id']})")
            continue

        official_name = str(world.get("name") or source["sourceName"] or source["id"]).strip()
        author = str(world.get("authorName") or "").strip() or None
        description = str(world.get("description") or "").strip()
        tags = [str(tag) for tag in world.get("tags", []) if isinstance(tag, str)]

        by_id[source["id"]] = {
            "id": source["id"],
            "name": official_name,
            "authorHint": author,
            "descriptionHint": description[:500] or None,
            "officialTags": tags[:24],
            "source": source["source"],
            "sourceCategories": ["bluecat-daily-new-worlds"],
            "sourceDate": source["sourceDate"],
            "confidenceScore": score,
            "confidence": "high" if score >= 70 else "medium",
            "reasons": ["source:bluecat-daily"] + reasons,
            "publicationDate": world.get("publicationDate"),
            "worldUpdatedAt": world.get("updated_at"),
        }
        print(f"Candidate {score}: {official_name} ({source['id']})")

    previous_by_id = {
        str(item.get("id")): item
        for item in previous
        if isinstance(item, dict) and item.get("id")
    }

    for wid, item in by_id.items():
        old = previous_by_id.get(wid)
        item["firstDiscoveredAt"] = (
            old.get("firstDiscoveredAt") if old else None
        ) or today
        item["lastSeenAt"] = today

    # Preserve unresolved candidates for 30 days even after they rotate out of
    # the recent source window.
    cutoff = dt.date.fromisoformat(today) - dt.timedelta(days=30)
    for wid, old in previous_by_id.items():
        if wid in by_id or wid in existing_ids or wid in decided_ids:
            continue
        try:
            last_seen = dt.date.fromisoformat(
                str(old.get("lastSeenAt") or old.get("firstDiscoveredAt"))
            )
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
