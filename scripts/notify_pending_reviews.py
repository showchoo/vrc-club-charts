#!/usr/bin/env python3
"""Notify the site owner once per actionable moderation task through GitHub Issues.

Assigned GitHub issues can generate Gmail notifications when GitHub email
notifications are enabled. Community review bodies, authors, database UUIDs
and other private fields NEVER leave Supabase.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
API = "https://api.github.com"
ADMIN = "https://vrc-club-charts.vercel.app/reviewer-admin.html"
SIGNALS = "https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/pending-review-signals"
MODERATION = "https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-candidate-status"
MARKER = re.compile(r"<!-- vcc-review-alert:([a-z0-9_:-]{8,130}) -->")
WORLD_ID = re.compile(r"^wrld_[0-9a-f-]{36}$")
TOKEN = re.compile(r"^[0-9a-f]{40}$")
PENDING = {"needs_review", "verification_unavailable", "classification_unavailable"}
LABEL = "vcc-needs-attention"


def read_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array: {path}")
    return data


def request_json(url: str, *, method: str = "GET", payload=None, token: str = ""):
    headers = {
        "Accept": "application/vnd.github+json" if url.startswith(API) else "application/json",
        "User-Agent": "VRCClubCharts-ActionNotifications/1.0",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(
        urllib.request.Request(url, data=body, method=method, headers=headers), timeout=25
    ) as response:
        raw = response.read(1_000_000)
    return json.loads(raw) if raw else {}


def public_statuses():
    response = request_json(MODERATION)
    if not isinstance(response, dict) or response.get("complete") is not True:
        raise ValueError("Moderation status endpoint returned incomplete data")
    records = response.get("decisions")
    if not isinstance(records, list):
        raise ValueError("Moderation decisions are not an array")
    decided = set()
    for row in records:
        if not isinstance(row, dict) or not WORLD_ID.fullmatch(str(row.get("world_id") or "")):
            raise ValueError("Malformed moderation record")
        if row.get("status") not in {"approved", "rejected"}:
            raise ValueError("Unknown moderation status")
        decided.add(row["world_id"])
    return decided


def pending_review_tokens():
    response = request_json(SIGNALS)
    if not isinstance(response, dict) or response.get("complete") is not True:
        raise ValueError("Pending review status is unavailable or incomplete")
    tokens = response.get("pending")
    if not isinstance(tokens, list) or any(not TOKEN.fullmatch(str(t)) for t in tokens):
        raise ValueError("Pending review tokens invalid")
    return set(tokens)


def clean_label(value):
    return re.sub(r"[\n\r<>\x60\[\]]", " ", str(value or "")).strip()[:85]


def desired_alerts(*, decided, tokens):
    """Map durable idempotency keys to titles and public-safe issue bodies."""
    candidate_rows = read_json(DATA / "world-candidates.json")
    ai_rows = read_json(DATA / "world-candidate-ai-decisions.json")
    submission_rows = read_json(DATA / "world-submission-decisions.json")
    by_world = {row["id"]: row for row in ai_rows
                if isinstance(row, dict) and WORLD_ID.fullmatch(str(row.get("id") or ""))}
    pending = {}
    for item in candidate_rows:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or "")
        if not WORLD_ID.fullmatch(wid) or wid in decided:
            continue
        record = by_world.get(wid, {})
        state = record.get("status")
        if state not in PENDING:
            continue  # Give AI time to screen newly discovered leads automatically.
        name = clean_label(item.get("name") or record.get("name") or wid)
        key = "candidate:" + wid
        category = "AI判定が未確定" if state == "needs_review" else "公開情報・AI確認にエラー"
        description = (
            f"**対象World:** {name}\n\n"
            f"**World ID:** {wid}\n\n"
            f"**判断待ち:** {category}\n\n"
            "管理者による確認が必要です。承認または除外を判断してください。\n\n"
            f"[VCC管理画面を開く]({ADMIN})"
        )
        pending[key] = (f"[VCC] World判断待ち：{name}", description)
    for record in submission_rows:
        if not isinstance(record, dict):
            continue
        wid = str(record.get("id") or "")
        if not WORLD_ID.fullmatch(wid) or record.get("status") not in PENDING or wid in decided:
            continue
        name = clean_label(record.get("name") or wid)
        key = "submission:" + wid
        pending[key] = (
            f"[VCC] 投稿World確認待ち：{name}",
            f"**投稿されたWorld:** {name}\n\n**ID:** {wid}\n\n"
            "AIが自動掲載できませんでした。管理者による確認が必要です。\n\n"
            f"[VCC管理画面を開く]({ADMIN})"
        )
    for opaque in tokens:
        key = "review:" + opaque
        pending[key] = (
            "[VCC] 新しいユーザーレビューの公開判断待ち",
            "新しいユーザーレビューが届き、公開・却下の判断待ちです。\n\n"
            "レビュー本文や投稿者情報はGitHubには保存していません。\n\n"
            f"[VCC管理画面で確認する]({ADMIN})"
        )
    return pending


def existing_alert_issues(*, repository, token):
    """Query open AND closed issues to prevent repeat notifications."""
    found = {}
    for page in range(1, 31):
        query = urllib.parse.urlencode({
            "state": "all", "labels": LABEL, "per_page": 100, "page": page
        })
        result = request_json(f"{API}/repos/{repository}/issues?{query}", token=token)
        if not isinstance(result, list):
            raise ValueError("Invalid GitHub issues response; refusing duplicates")
        for issue in result:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            match = MARKER.search(str(issue.get("body") or ""))
            if match:
                found[match.group(1)] = issue
        if len(result) < 100:
            return found
    raise RuntimeError("Issue history exceeded safe pagination limit")


def ensure_label(*, repository, token):
    try:
        request_json(f"{API}/repos/{repository}/labels", method="POST", token=token,
            payload={"name": LABEL, "color": "D5AB5B",
                     "description": "VRC Club Charts action-needed moderation notifications"})
    except urllib.error.HTTPError as exc:
        if exc.code != 422:  # Label already exists
            raise


def sync_alerts(*, repository, owner, token, desired, existing, max_new=15):
    new_count = closed_count = 0
    for key in sorted(desired):
        if key in existing:
            continue
        if new_count >= max_new:
            break
        title, description = desired[key]
        marker = f"<!-- vcc-review-alert:{key} -->"
        request_json(f"{API}/repos/{repository}/issues", method="POST", token=token,
            payload={
                "title": title[:180], "body": description + "\n\n" + marker,
                "assignees": [owner], "labels": [LABEL],
            })
        new_count += 1
        print(f"CREATED {key.split(':', 1)[0]} alert")
    for key, issue in existing.items():
        if key in desired or issue.get("state") != "open":
            continue
        number = int(issue["number"])
        request_json(f"{API}/repos/{repository}/issues/{number}", method="PATCH",
                     token=token, payload={"state": "closed", "state_reason": "completed"})
        closed_count += 1
        print(f"RESOLVED issue #{number}")
    return {"created": new_count, "resolved": closed_count, "active": len(desired)}


def main():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "showchoo/vrc-club-charts")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "showchoo")
    if not token or repo != "showchoo/vrc-club-charts" or owner != "showchoo":
        raise RuntimeError("GitHub Actions token or expected repository is missing")
    # Fail closed: do not alter issues if either status source is unavailable.
    decided = public_statuses()
    tokens = pending_review_tokens()
    wanted = desired_alerts(decided=decided, tokens=tokens)
    ensure_label(repository=repo, token=token)
    issues = existing_alert_issues(repository=repo, token=token)
    result = sync_alerts(repository=repo, owner=owner, token=token,
                         desired=wanted, existing=issues)
    print("VCC GitHub-to-Gmail notification bridge: " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
