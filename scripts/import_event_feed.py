#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://kafka2306.github.io/cast_event_cal/events.json"
OUT = ROOT / "data/events-auto.json"
USER_AGENT = "VRCClubCharts/0.4 (+https://github.com/showchoo/vrc-club-charts)"
JST = dt.timezone(dt.timedelta(hours=9))

ALLOWED_CATEGORIES = {"音楽・ダンス", "公演・ショー", "music", "dance", "performance", "show"}
STRONG_TERMS = (
    " dj ", "dj event", "dj party", "djbar", "dj bar",
    "club", "nightclub", "rave", "party", "live", "concert", "stage",
    "trance", "techno", "house", "dnb", "drum & bass", "drum and bass",
    "bass music", "garage", "psytrance", "psy-trance", "vocaloid", "mmd",
    "festival", "audiolink", "vrmv", "dance party", "dance event",
    "ライブ", "クラブ", "コンサート", "演奏", "ボカロ", "フェス", "レイブ",
    "パーティ", "音楽イベント", "ダンスイベント",
)

EXCLUDE_TERMS = (
    "karaoke", "カラオケ", "exercise", "fitness", "workout",
    "エクササイズ", "フィットネス", "筋トレ", "yoga", "ヨガ",
)
GENRE_RULES = [
    ("PSYTRANCE", ("psytrance", "psy-trance", "psy trance", "サイケ")),
    ("TRANCE", ("trance",)),
    ("TECHNO", ("techno",)),
    ("HOUSE", ("house",)),
    ("DRUM & BASS", ("drum & bass", "drum and bass", "dnb", "liquid funk")),
    ("GARAGE", ("garage",)),
    ("VOCALOID", ("vocaloid", "ボカロ")),
    ("DJ", (" dj ", "djイベント", "dj event", "djbar", "dj bar")),
    ("RAVE", ("rave",)),
    ("LIVE", ("live", "ライブ", "concert", "演奏")),
    ("DANCE", ("dance", "ダンス")),
]


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(dt.timezone.utc)


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_text(event: dict, *, include_category: bool = True) -> str:
    parts = [
        event.get("title"), event.get("description"), event.get("organizer"),
        event.get("location"), " ".join(event.get("tags") or []),
    ]
    if include_category:
        parts.append(event.get("category"))
    return " " + " ".join(clean(x).lower() for x in parts if x) + " "


def classify_genres(event: dict) -> list[str]:
    text = source_text(event)
    out = []
    for label, needles in GENRE_RULES:
        if any(needle in text for needle in needles):
            out.append(label)
    if not out:
        out.append("MUSIC")
    return out[:5]


def is_music_event(event: dict, now: dt.datetime) -> bool:
    if event.get("status") not in {None, "", "scheduled", "confirmed"}:
        return False
    if event.get("review_required") or event.get("is_archived"):
        return False
    try:
        if float(event.get("confidence", 1.0)) < 0.72:
            return False
    except (TypeError, ValueError):
        return False

    start = parse_dt(event.get("starts_at"))
    if start is None:
        return False
    if start < now - dt.timedelta(hours=8) or start > now + dt.timedelta(days=45):
        return False

    category = clean(event.get("category")).lower()
    category_ok = category in {x.lower() for x in ALLOWED_CATEGORIES}
    # Category is only a coarse gate. It must not satisfy the content keyword
    # test by itself, otherwise every generic "music/dance" calendar entry gets in.
    text = source_text(event, include_category=False)
    keyword_ok = any(term in text for term in STRONG_TERMS)
    excluded = any(term in text for term in EXCLUDE_TERMS)
    return category_ok and keyword_ok and not excluded and bool(clean(event.get("url")))


def stable_id(event: dict) -> str:
    upstream = clean(event.get("id"))
    if upstream:
        return "feed-" + re.sub(r"[^a-z0-9_-]+", "-", upstream.lower())[:80].strip("-")
    raw = "|".join([
        clean(event.get("title")),
        clean(event.get("starts_at")),
        clean(event.get("organizer")),
    ])
    return "feed-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def main() -> int:
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))

    rows = payload.get("events", []) if isinstance(payload, dict) else []
    now = dt.datetime.now(dt.timezone.utc)
    selected = []
    for event in rows:
        if not isinstance(event, dict) or not is_music_event(event, now):
            continue
        selected.append({
            "id": stable_id(event),
            "name": clean(event.get("title")),
            "start": clean(event.get("starts_at")),
            "end": clean(event.get("ends_at")) or None,
            "organizer": clean(event.get("organizer")) or "VRChat community organizer",
            "worldName": clean(event.get("location")) or "VRChat / event instance",
            "genres": classify_genres(event),
            "url": clean(event.get("url")),
            "source": "KAFKA2306/cast_event_cal public event feed",
            "sourceProvider": "cast_event_cal",
            "upstreamId": clean(event.get("id")),
            "upstreamCategory": clean(event.get("category")),
            "autoImported": True,
            "confidence": event.get("confidence"),
        })

    # Stable ordering and hard cap keep the public site focused rather than mirroring
    # the entire upstream calendar.
    selected.sort(key=lambda e: (e["start"], e["name"].casefold()))
    selected = selected[:100]
    OUT.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(selected)} music/dance event candidates from {len(rows)} upstream events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
