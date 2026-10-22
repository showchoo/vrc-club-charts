#!/usr/bin/env python3
"""Conservative, robots-aware discovery of club World URLs from public Sia VR articles.

This yields *leads only*. It never claims a World is public, adds it to the
published catalog, or imports article text/images into the site.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

try:
    from scripts.discover_vrcw import BLOCKED_NAME, CLUB_NAME, STATE, WORLD_ID, read_json
except ModuleNotFoundError:
    from discover_vrcw import BLOCKED_NAME, CLUB_NAME, STATE, WORLD_ID, read_json

BASE = "https://sia-vr.com"
INDEX = BASE + "/category/building/club"
UA = "VRCClubCharts/1.0 (+https://vrc-club-charts.vercel.app/about.html)"
ARTICLE_PATH = re.compile(r"^/vrchat-world-\d+/?$")
WORLD_PATH = re.compile(r"^/home/world/(wrld_[0-9a-fA-F-]{36})(?:/info)?/?$")
PAGE_LIMIT = 2


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._in_h1 = 0
        self._title: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self._in_h1 += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = max(0, self._in_h1 - 1)

    def handle_data(self, data):
        if self._in_h1:
            self._title.append(data)

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._title)).strip()[:120]


def article_urls(page_html: str) -> list[str]:
    parsed = LinkParser()
    parsed.feed(page_html)
    result, seen = [], set()
    for href in parsed.links:
        u = urllib.parse.urlparse(urllib.parse.urljoin(BASE, href))
        url = BASE + u.path.rstrip("/")
        if u.scheme != "https" or u.netloc not in {"sia-vr.com", "www.sia-vr.com"}:
            continue
        if ARTICLE_PATH.fullmatch(u.path) and url not in seen:
            result.append(url)
            seen.add(url)
    return result


def extract_world_article(article_html: str) -> tuple[str, str] | None:
    parsed = LinkParser()
    parsed.feed(article_html)
    for href in parsed.links:
        u = urllib.parse.urlparse(href)
        if u.scheme != "https" or u.netloc not in {"vrchat.com", "www.vrchat.com"}:
            continue
        match = WORLD_PATH.fullmatch(u.path)
        if match and WORLD_ID.fullmatch(match.group(1)) and parsed.title:
            return match.group(1), parsed.title
    return None


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=16) as response:
        return response.read(1_000_000).decode("utf-8", errors="replace")


def robots_policy() -> urllib.robotparser.RobotFileParser:
    request = urllib.request.Request(BASE + "/robots.txt", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(200_000).decode("utf-8", errors="replace")
    parsed = urllib.robotparser.RobotFileParser()
    parsed.parse(raw.splitlines())
    return parsed


def collect_candidates(today: str | None = None) -> tuple[list[dict], dict]:
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    report: dict = {"lastAttemptAt": today, "status": "unavailable", "articlesChecked": 0, "leads": 0}
    try:
        policy = robots_policy()
    except Exception as exc:
        print(f"INFO: Sia VR robots policy unavailable; skipping source: {type(exc).__name__}")
        return [], report  # Fail closed, rather than assuming crawling is allowed.
    if not policy.can_fetch(UA, INDEX):
        report["status"] = "robots_disallowed"
        print("INFO: Sia VR category crawling disallowed by robots.txt")
        return [], report

    links: list[str] = []
    try:
        for page in range(1, PAGE_LIMIT + 1):
            url = INDEX if page == 1 else INDEX + f"/page/{page}"
            if not policy.can_fetch(UA, url):
                continue
            links.extend(article_urls(fetch_text(url)))
    except Exception as exc:
        print(f"INFO: Sia VR category unavailable; skipping source: {type(exc).__name__}")
        return [], report

    links = list(dict.fromkeys(links))
    if not links:
        report["status"] = "empty"
        return [], report

    state = read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    start = int(state.get("siaVrNextIndex", 0)) % len(links)
    cap = max(1, min(8, int(os.environ.get("VCC_SIA_VR_ARTICLES_PER_RUN", "5"))))
    chosen = (links[start:] + links[:start])[:cap]
    found: dict[str, dict] = {}
    for article in chosen:
        if not policy.can_fetch(UA, article):
            continue
        try:
            raw = fetch_text(article)
            report["articlesChecked"] += 1
            row = extract_world_article(raw)
            if not row:
                continue
            wid, title = row
            if BLOCKED_NAME.search(title):
                continue
            is_club_name = bool(CLUB_NAME.search(title))
            found[wid] = {
                "id": wid, "name": title, "authorHint": "",
                "source": article, "sourceCategories": ["sia_vr_club"],
                "confidenceScore": 88 if is_club_name else 72,
                "confidence": "awaiting-public-metadata",
                "reasons": ["source:sia-vr-club"] + (
                    ["+explicit-club-name"] if is_club_name else []),
                "firstDiscoveredAt": today, "lastSeenAt": today,
            }
        except Exception as exc:
            print(f"INFO: Sia VR article unavailable: {type(exc).__name__}")

    report["status"] = "ok"
    report["leads"] = len(found)
    report["articlesListed"] = len(links)
    if report["articlesChecked"]:
        state = read_json(STATE, {})
        state = state if isinstance(state, dict) else {}
        state["siaVrNextIndex"] = (start + len(chosen)) % len(links)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sia VR leads: {len(found)} from {report['articlesChecked']} permitted articles")
    return list(found.values()), report
