"""Published World profile facts: bounded labels, factual provenance and safe links.

Use only already-admitted public catalog fields; never infer that a tag
confirms the existence or operation of DJ equipment.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlsplit

# Only the existing public directory sources may become clickable outbound
# links. Every World has a separate canonical official VRChat link.
KNOWN_SOURCE_HOSTS = frozenset({
    "vrchat.com", "www.vrchat.com",
    "vrcw.net", "www.vrcw.net", "en.vrcw.net",
    "vrcmap.com", "www.vrcmap.com",
})
CREATOR_TAG = re.compile(r"author_tag_([A-Za-z0-9_]{1,35})\Z", re.IGNORECASE)


def safe_source_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 500:
        return ""
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme.lower() != "https" or
                parsed.hostname not in KNOWN_SOURCE_HOSTS or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in (None, 443) or
                not parsed.path or any(ord(c) < 32 for c in raw)):
            return ""
    except ValueError:
        return ""
    return raw


def creator_tags(world: dict, *, limit: int = 8) -> list[str]:
    """Public author tags are *labels*, not independent functionality proof."""
    if not isinstance(world, dict):
        return []
    raw = world.get("officialTags")
    if not isinstance(raw, list):
        return []
    result = []
    seen = set()
    for item in raw[:100]:
        if not isinstance(item, str):
            continue
        m = CREATOR_TAG.fullmatch(item)
        if m is None:
            continue
        label = m.group(1).replace("_", " ").strip().upper()
        key = label.casefold()
        if key not in seen:
            seen.add(key)
            result.append(label)
        if len(result) >= limit:
            break
    return result


def count_text(value: object) -> str:
    if type(value) is not int or not 1 <= value <= 5000:
        return "—"
    return str(value)


def update_day(value: object, *, today: dt.date | None = None) -> str:
    if not isinstance(value, str) or len(value) > 40:
        return "—"
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "—"
        day = parsed.astimezone(dt.timezone.utc).date()
    except ValueError:
        return "—"
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if not dt.date(2014, 1, 1) <= day <= today:
        return "—"
    return day.isoformat()


def provenance(world: dict) -> tuple[str, str]:
    """Three clearly separated evidence levels; unknown stays unknown."""
    basis = world.get("publicationBasis")
    if basis == "live-playback-verified" and world.get("djStreamTested") is True:
        return ("検査記録あり",
                "DJ動画再生の検査記録が登録されています。"
                "音響全体・ライブ配信・全設備の動作を保証するものではありません。")
    if basis == "owner-favorite-confirmed" and world.get("djStreamOwnerConfirmed") is True:
        return ("運営者による確認申告",
                "サイト運営者がDJ配信機能を確認したと申告しています。"
                "独立した機器検証ではありません。")
    if basis == "dj-tag":
        return ("DJタグによる掲載",
                "DJタグを掲載根拠としています。"
                "ワールド内のDJ配信設備や音声出力の動作は未確認です。")
    return ("確認情報なし", "DJ設備の動作を確認できる情報はありません。")
