#!/usr/bin/env python3
"""Paged, resumable World discovery from public VRChat club/DJ directories.

This collector never assigns image scores. Only currently public VRChat Worlds
with authoritative metadata can enter the scored catalog automatically.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "discovery-state.json"
SEEDS = DATA / "discovery-seeds.json"
WORLD_ID = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")
WORLD_ID_IN_TEXT = re.compile(r"wrld_[0-9a-fA-F-]{36}")
H3 = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.I | re.S)
TAG = re.compile(r"<[^>]*>")
PAGES = {
    "vrcw_club": "https://www.vrcw.net/category/detail/club",
    "vrcw_dj": "https://www.vrcw.net/category/detail/dj",
}
USER_AGENT = "VRCClubCharts-Discovery/1.0 (+https://vrc-club-charts.vercel.app/about.html)"
BLOCKED_NAME = re.compile(
    r"fight(?:ing)?[\s-]*club|avatar|アバター|clubhouse|クラブハウス|sleep|睡眠|"
    r"mmd|karaoke|カラオケ|training|sparring|格闘|ジム|gym", re.I
)
CLUB_NAME = re.compile(r"\bclub\b|nightclub|discotheque|disco|rave|dj[\s_-]?booth|"
                       r"クラブ|ディスコ|レイブ|ナイトクラブ", re.I)


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", value))).strip()


def parse_listing(raw: str, source_name: str, url: str, today: str) -> list[dict]:
    """Parse one card per H3, never copy a World ID from unrelated sidebar items."""
    matches = list(H3.finditer(raw))
    items: dict[str, dict] = {}
    for i, match in enumerate(matches):
        name = compact(match.group(1))[:120]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        section = raw[match.end():end]
        text = html.unescape(re.sub(r"(?is)<[^>]*>", "\n", section))
        if "ワールドID" not in text or "VRChatから削除済み" in text:
            continue
        wid = WORLD_ID_IN_TEXT.search(text)
        if not wid or not WORLD_ID.fullmatch(wid.group()):
            continue
        lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]
        author = ""
        for index, line in enumerate(lines):
            if line == "制作" and index + 1 < len(lines):
                author = re.sub(r"\s*さん$", "", lines[index + 1]).strip()[:120]
                break
            if line.startswith("制作 ") and len(line) > 3:
                author = re.sub(r"\s*さん$", "", line[3:]).strip()[:120]
                break
        if not name or not author or BLOCKED_NAME.search(name):
            continue

        has_club_name = bool(CLUB_NAME.search(name))
        is_club = source_name == "vrcw_club" or "クラブ" in lines
        is_dj = source_name == "vrcw_dj" or "DJ" in lines
        score = min(100, (57 if is_club else 48) +
                    (36 if has_club_name else 0) + (7 if is_dj else 0))
        items[wid.group()] = {
            "id": wid.group(),
            "name": name,
            "authorHint": author,
            "source": url,
            "sourceCategories": [source_name],
            "confidenceScore": score,
            "confidence": "high" if score >= 85 else "medium",
            "reasons": ["source:" + source_name] +
                       (["+explicit-club-name"] if has_club_name else []) +
                       (["+club-category"] if is_club else []) +
                       (["+dj-category"] if is_dj else []),
            "firstDiscoveredAt": today,
            "lastSeenAt": today,
        }
    return list(items.values())


def fetch_listing(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT,
                      "Accept": "text/html,application/xhtml+xml"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = response.read(1_500_000).decode("utf-8", errors="replace")
    if "wrld_" not in result:
        raise ValueError("Listing has no World IDs")
    return result


def discover_candidates(today: str) -> tuple[list[dict], bool]:
    """Fetch newest plus rotating historical pages; persist cursor only on success."""
    existing = read_json(STATE, {})
    cursors = existing.get("nextPage", {}) if isinstance(existing, dict) else {}
    if not isinstance(cursors, dict):
        cursors = {}
    next_pages = dict(cursors)
    count = max(2, min(30, int(os.environ.get("VCC_DISCOVERY_PAGES_PER_SOURCE", "12"))))
    unique: dict[str, dict] = {}
    successful = False

    # The public directory currently returns HTTP 403 to GitHub Actions.
    # Respect that access restriction instead of retrying it every day.
    if os.environ.get("VCC_ENABLE_VRCW", "0") != "1":
        print("INFO: VRCW crawling disabled after HTTP 403; using other sources")
        return [], False

    for name, base in PAGES.items():
        start = max(2, int(cursors.get(name, 2)))
        pages = [1] + list(range(start, start + count - 1))
        for page in pages:
            url = base + "?" + urllib.parse.urlencode(
                {"date_type": "vrc_created_at", "orderby": "create", "page": page}
            )
            try:
                raw = fetch_listing(url)
                parsed = parse_listing(raw, name, url, today)
                if not parsed:
                    # Reached the end of historical pagination. Restart next cycle.
                    if page > 1:
                        next_pages[name] = 2
                    print(f"INFO: {name} page {page}: no usable World cards")
                    break
                successful = True
                if page > 1:
                    next_pages[name] = page + 1
                print(f"{name} page={page}: {len(parsed)} candidate cards")
                for entry in parsed:
                    old = unique.get(entry["id"])
                    if old:
                        old["sourceCategories"] = sorted(set(
                            old["sourceCategories"] + entry["sourceCategories"]
                        ))
                        old["reasons"] = list(dict.fromkeys(
                            old["reasons"] + entry["reasons"]
                        ))
                        if entry["confidenceScore"] > old["confidenceScore"]:
                            old.update({
                                "confidenceScore": entry["confidenceScore"],
                                "confidence": entry["confidence"],
                            })
                    else:
                        unique[entry["id"]] = entry
            except (OSError, ValueError, urllib.error.URLError) as exc:
                print(f"WARN: {name} page {page}: {type(exc).__name__}: {exc}")
                break
            if page != pages[-1]:
                time.sleep(0.35)

    if successful:
        STATE.write_text(json.dumps({"nextPage": next_pages, "updatedAt": today},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list(unique.values()), successful


def priority_seeds(today: str) -> list[dict]:
    out = []
    for item in read_json(SEEDS, []):
        wid = str(item.get("id", "")) if isinstance(item, dict) else ""
        if not WORLD_ID.fullmatch(wid):
            continue
        out.append({
            "id": wid,
            "name": "調査中のクラブWorld",
            "authorHint": "Unverified",
            "source": "https://vrchat.com/home/world/" + wid + "/info",
            "sourceCategories": ["direct-world-link"],
            "confidenceScore": 100,
            "confidence": "awaiting-public-metadata",
            "reasons": ["user-supplied-world-link"],
            "firstDiscoveredAt": today,
            "lastSeenAt": today,
        })
    return out


def eligible_for_admission(item: dict) -> bool:
    if "direct-world-link" in item.get("sourceCategories", []):
        return True  # Only after authoritative metadata is retrieved below.
    if "vrchat_search" in item.get("sourceCategories", []):
        return (item.get("confidenceScore", 0) >= 85
                and "+explicit-club-name" in item.get("reasons", []))
    return (item.get("confidenceScore", 0) >= 85
            and "+explicit-club-name" in item.get("reasons", [])
            and "vrcw_club" in item.get("sourceCategories", []))


def verify_public_world(wid: str, user_agent: str) -> dict | None:
    req = urllib.request.Request(
        f"https://api.vrchat.cloud/api/1/worlds/{wid}",
        headers={"User-Agent": user_agent, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        payload = json.loads(response.read(250_000))
    if (not isinstance(payload, dict) or payload.get("id") != wid
            or str(payload.get("releaseStatus", "")).lower() != "public"):
        return None
    name = str(payload.get("name") or "").strip()[:120]
    author = str(payload.get("authorName") or "").strip()[:120]
    return {"name": name, "author": author} if name and author else None


def auto_register(candidates: list[dict], catalog: list[dict],
                  decided_ids: set[str]) -> list[str]:
    """Auto-register only public Worlds with verified name/author and strong club evidence."""
    known = {w.get("id") for w in catalog}
    user_agent = os.environ.get("VRC_USER_AGENT", "").strip() or (
        "VRCClubCharts/1.0 (+https://github.com/showchoo/vrc-club-charts/issues)"
    )
    max_checks = max(1, min(40, int(os.environ.get("VCC_DISCOVERY_VERIFY_PER_RUN", "16"))))
    state = read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    checked = state.get("verification", {})
    checked = checked if isinstance(checked, dict) else {}
    today = dt.datetime.now(dt.timezone.utc).date()
    ordered = sorted(candidates, key=lambda e: (
        0 if "direct-world-link" in e.get("sourceCategories", []) else 1,
        -int(e.get("confidenceScore", 0)), e.get("id", "")
    ))
    attempts, added = 0, []
    for candidate in ordered:
        wid = candidate.get("id")
        if (wid in known or wid in decided_ids or not WORLD_ID.fullmatch(str(wid))
                or not eligible_for_admission(candidate)):
            continue
        last = checked.get(wid, {})
        try:
            last_day = dt.date.fromisoformat(str(last.get("date", "")))
            # Failed or inaccessible Worlds are retried after a cooldown instead
            # of starving all other candidates in each daily 16-check batch.
            if (today - last_day).days < 3:
                continue
        except (ValueError, TypeError, AttributeError):
            pass
        if attempts >= max_checks:
            break
        attempts += 1
        checked[wid] = {"date": today.isoformat()}
        if attempts > 1:
            time.sleep(1.0)
        try:
            actual = verify_public_world(wid, user_agent)
        except urllib.error.HTTPError as exc:
            print(f"WARN: official World lookup failed {wid} HTTP {exc.code}")
            if exc.code == 429:
                break  # Do not retry a rate-limited endpoint.
            continue
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"WARN: official World lookup failed {wid}: {type(exc).__name__}")
            continue
        if not actual:
            print(f"INFO: not a currently public World: {wid}")
            continue
        if ("direct-world-link" not in candidate.get("sourceCategories", [])
                and (BLOCKED_NAME.search(actual["name"]) or
                     not CLUB_NAME.search(actual["name"]))):
            print(f"INFO: official World name does not confirm club venue: {wid}")
            continue
        # A direct URL explicitly submitted by the site owner is treated as a
        # club nomination; other automatic listings require trusted category.
        catalog.append({
            "id": wid,
            "name": actual["name"],
            "author": actual["author"],
            "genres": ["CLUB"] + (["DJ"] if "vrcw_dj" in candidate.get(
                "sourceCategories", []) else []),
            "editorialStatus": "unreviewed",
            "chartEligible": True,
            "source": candidate.get("source"),
            "discoveredBy": "auto-discovery",
        })
        known.add(wid)
        added.append(wid)
        print(f"REGISTERED {wid} {actual['name']}")
    if attempts:
        state = read_json(STATE, {})
        state = state if isinstance(state, dict) else {}
        state["verification"] = checked
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


if __name__ == "__main__":
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    rows, ok = discover_candidates(today)
    print(f"VRCW discovery: {len(rows)} distinct cards, source_available={ok}")
