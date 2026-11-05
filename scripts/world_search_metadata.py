"""Conservative, server-rendered search metadata for published VRChat Worlds.

Only catalog fields and an explicit publication basis are used. Never turn
DJ tags, thumbnail AI scores, or operator attestations into measured features.
"""
from __future__ import annotations

import json
import re

MAX_NAME = 100
MAX_AUTHOR = 60
MAX_GENRES = 5
STATUS_TEXT = {
    "dj-tag": "DJタグを掲載根拠としています。DJ配信設備の動作は未確認です。",
    "owner-favorite-confirmed": (
        "サイト運営者による配信機能の確認申告があります。独立した実地検証ではありません。"
    ),
    "live-playback-verified": (
        "公開されたDJ再生検査記録があります。検査内容と限界は個別ページをご確認ください。"
    ),
}
DEFAULT_STATUS = "掲載情報は公式ワールドページなどの公開資料を参照してください。"


def _readable(raw, limit: int) -> str:
    """Normalise public labels; omit control characters and bound SEO fields."""
    value = re.sub(r"\s+", " ", str(raw or "")).strip()
    value = "".join(char for char in value if ord(char) >= 32 and ord(char) != 127)
    return value[:limit]


def world_search_metadata(world: dict, *, canonical: str, thumbnail: str) -> dict:
    name = _readable(world.get("name"), MAX_NAME) or _readable(world.get("id"), MAX_NAME)
    author = _readable(world.get("author"), MAX_AUTHOR)
    genres = []
    for item in world.get("genres") or []:
        label = _readable(item, 32)
        if label and label not in genres:
            genres.append(label)
        if len(genres) >= MAX_GENRES:
            break

    status = STATUS_TEXT.get(world.get("publicationBasis"), DEFAULT_STATUS)
    genre_text = "、".join(genres[:3])
    description = (
        f"VRChatワールド「{name}」。"
        + (f"制作者：{author}。" if author else "")
        + (f"ジャンル：{genre_text}。" if genre_text else "")
        + status
        + " ワールド情報と関連イベントを紹介。"
    )
    entity = {
        "@type": "CreativeWork",
        "@id": canonical + "#world",
        "name": name,
        "description": description,
        "identifier": str(world.get("id") or ""),
        "url": "https://vrchat.com/home/world/" + str(world.get("id") or ""),
        "mainEntityOfPage": canonical,
        "isPartOf": {"@type": "VideoGame", "name": "VRChat",
                     "url": "https://hello.vrchat.com/"},
    }
    if author:
        entity["creator"] = author
    if genres:
        entity["genre"] = genres
    if thumbnail.startswith("https://"):
        entity["image"] = thumbnail
    return {
        "title": f"{name}｜VRChatクラブ・DJワールド紹介 - VRC Club Charts",
        "description": description,
        "entity": entity,
    }


def safe_json_ld(value: dict | list) -> str:
    """Serialize JSON-LD without allowing untrusted names to close HTML script."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))
