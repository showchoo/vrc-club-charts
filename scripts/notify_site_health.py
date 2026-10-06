#!/usr/bin/env python3
"""One GitHub Issue per production incident, assigned to the owner for email alerts."""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LABEL = "vcc-site-health"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def api(method: str, path: str, token: str, payload=None):
    if not path.startswith("/repos/"):
        raise ValueError("Unexpected GitHub API path")
    url = "https://api.github.com" + path
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "VCC-Autonomous-Health/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(1_000_000)
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # Do not print API response bodies; they may contain private data.
        raise RuntimeError(f"GitHub REST {method} {path.split('?')[0]}: HTTP {exc.code}") from None


def format_incident(report: dict, repair: dict, pr_url="") -> str:
    issues = report.get("issues") or []
    rows = []
    for item in issues[:12]:
        code = re.sub(r"[^a-z0-9_]", "", str(item.get("code", "")).lower())[:60]
        detail = re.sub(r"[\r\n\[\]<>]", " ", str(item.get("detail", "")))[:220]
        rows.append(f"- **{code}**: {detail}")
    status = re.sub(r"[^a-z0-9_]", "", str(repair.get("status", "not_attempted")))[:60]
    description = [
        "The automated production monitor detected a reproducible issue.",
        "",
        "**URL:** https://vrc-club-charts.vercel.app/",
        "**Health checks:**",
        *rows,
        "",
        f"**Gemini repair status:** {status}",
        "**Safety policy:** AI-generated code is confined to a small allowlist, "
        "must pass repository validation, and requires human approval unless it is "
        "a single verified internal-link edit.",
    ]
    if pr_url and re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+", pr_url):
        description += ["", f"**Proposed repair:** {pr_url}"]
    else:
        description += ["", "Check the GitHub Actions run and the repository for next steps."]
    description += [
        "",
        "A new incident is reported once; repeated checks do not send duplicate alerts. "
        "This Issue closes automatically when the monitor reports recovery.",
    ]
    return "\n".join(description)


def sync(report: dict, repair: dict, token: str, repo: str, owner: str, pr_url=""):
    base = "/repos/" + repo
    issues = api("GET", base + "/issues?state=open&labels=" + LABEL + "&per_page=50", token)
    existing = [x for x in issues if isinstance(x, dict) and "pull_request" not in x]
    if report.get("healthy") is True:
        for issue in existing:
            api("PATCH", base + f"/issues/{issue['number']}", token,
                {"state": "closed", "state_reason": "completed"})
        print(f"Health incidents resolved: {len(existing)}")
        return "healthy"

    body = format_incident(report, repair, pr_url)
    if existing:
        # Avoid repeated comments and notification email storms on every hourly run.
        current = existing[0]
        if pr_url and pr_url not in str(current.get("body", "")):
            api("PATCH", base + f"/issues/{current['number']}", token, {"body": body})
        print(f"Reusing open health incident #{current['number']}")
        return "existing"

    # If a previous incident was manually closed while still broken, respect that
    # decision rather than recreating the same notification every hour.
    recent = api("GET", base + "/issues?state=closed&labels=" + LABEL + "&per_page=20", token)
    codes = {str(x.get("code")) for x in report.get("issues") or []}
    for issue in recent:
        old = set(re.findall(r"\*\*([a-z0-9_]+)\*\*:", str(issue.get("body", ""))))
        if codes and codes == old:
            print("Incident already acknowledged by owner; not reopening an identical alert")
            return "acknowledged"

    try:
        api("POST", base + "/labels", token,
            {"name": LABEL, "color": "CF222E",
             "description": "Automated VCC production outage / Gemini repair alert"})
    except RuntimeError as exc:
        if "HTTP 422" not in str(exc):
            raise

    created = api("POST", base + "/issues", token, {
        "title": "[VCC] Site health incident — automated repair status",
        "body": body,
        "labels": [LABEL],
        "assignees": [owner] if owner else [],
    })
    print("Created new health alert Issue #" + str(created.get("number")))
    return "created"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="/tmp/vcc-site-health.json")
    parser.add_argument("--repair", default="/tmp/vcc-repair-result.json")
    parser.add_argument("--pr-url-file", default="/tmp/vcc-repair-pr.txt")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not token or not REPOSITORY_PATTERN.fullmatch(repo):
        raise SystemExit("Missing GitHub Actions notification environment")
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    repair = (json.loads(Path(args.repair).read_text(encoding="utf-8"))
              if Path(args.repair).exists() else {"status": "not_attempted"})
    pr_url = Path(args.pr_url_file).read_text(encoding="utf-8").strip() if Path(args.pr_url_file).exists() else ""
    sync(report, repair, token, repo, owner, pr_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
