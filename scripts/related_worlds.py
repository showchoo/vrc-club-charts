"""Deterministic, admission-safe internal links among published DJ Worlds.

Only Worlds already admitted to the public catalog are eligible. A shared
tag or creator is a browsing cue, never proof of DJ equipment functionality.
"""
from __future__ import annotations

import re

WORLD_ID = re.compile(r"wrld_[0-9a-fA-F-]{36}\Z")
ADMISSION = frozenset(("dj-tag", "owner-favorite-confirmed",
                       "live-playback-verified"))
GENERAL_TAGS = frozenset(("dj", "music", "club", "vrchat", "world", "event"))


def _clean(value: object, limit: int = 75) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _genres(world: dict) -> dict[str, str]:
    result = {}
    raw = world.get("genres")
    if not isinstance(raw, list):
        return result
    for value in raw[:32]:
        tag = _clean(value, 30)
        if tag:
            result.setdefault(tag.casefold(), tag)
    return result


def _eligible(world: dict) -> bool:
    if not isinstance(world, dict):
        return False
    wid = world.get("id")
    return (
        isinstance(wid, str)
        and WORLD_ID.fullmatch(wid) is not None
        and world.get("publicationBasis") in ADMISSION
        and world.get("availabilityStatus") != "unavailable"
        and world.get("releaseStatus") not in ("private", "hidden")
        and world.get("chartEligible") is not False
    )


def related_worlds(current: dict, public_catalog: list[dict],
                   *, limit: int = 4) -> list[dict]:
    """Return strongest shared-creator or shared-genre matches.

    Ties are alphabetical, so chart position, visits and unverified score
    never influence the recommendations. No World outside the public,
    DJ-admitted catalog is eligible.
    """
    if not _eligible(current) or not isinstance(public_catalog, list):
        return []
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 8:
        raise ValueError("Related World limit must be between 1 and 8")
    own_id = current["id"]
    own_author = _clean(current.get("author")).casefold()
    own_genres = _genres(current)
    seen = {own_id}
    choices = []
    for candidate in public_catalog:
        if not _eligible(candidate) or candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        author = _clean(candidate.get("author"))
        same_author = bool(own_author and author.casefold() == own_author)
        common = set(own_genres).intersection(_genres(candidate))
        specific = sorted(common - GENERAL_TAGS)
        general = sorted(common & GENERAL_TAGS)
        # Don't invent a relatedness claim from unrelated page views or
        # popularity. A shared generic tag is still explicitly labelled.
        if not (same_author or specific or general):
            continue
        score = (20 if same_author else 0) + 4 * len(specific) + len(general)
        reason = ("同じ制作者" if same_author else
                  "共通ジャンル：" + "・".join(
                      own_genres[key] for key in (specific or general)[:2]))
        name = _clean(candidate.get("name"), 120) or candidate["id"]
        choices.append((-score, name.casefold(), candidate["id"], {
            "id": candidate["id"], "name": name, "reason": reason,
        }))
    choices.sort(key=lambda row: (row[0], row[1], row[2]))
    return [entry for _, _, _, entry in choices[:limit]]
