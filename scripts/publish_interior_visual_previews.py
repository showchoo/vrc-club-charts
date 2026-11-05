#!/usr/bin/env python3
"""Explicitly opt-in to publish numeric interior-video visual previews.

No raw videos, screenshots, free-form observations, personal information or
Craftsmanship claims are sent to GitHub. Deployment is handled by existing
Vercel Git integration after a normal authenticated git push.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import atomic_json, ROOT
    from scripts.compile_interior_visual_estimates import compile_feed, eligible_catalog_ids
except ModuleNotFoundError:
    from auto_process_interior_queue import atomic_json, ROOT
    from compile_interior_visual_estimates import compile_feed, eligible_catalog_ids

OUTPUT = ROOT / "data" / "interior-visual-estimates.json"


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=check, timeout=60)


def check_git_safety() -> None:
    branch = git("branch", "--show-current").stdout.strip()
    if branch != "main":
        raise ValueError("Automatic publishing only runs from the local main branch")
    upstream = git("remote", "get-url", "origin").stdout.strip()
    root_url = upstream.removesuffix(".git")
    if root_url not in {
        "https://github.com/showchoo/vrc-club-charts",
        "git@github.com:showchoo/vrc-club-charts",
    }:
        raise ValueError("Unexpected Git remote")
    if git("status", "--porcelain").stdout.strip():
        raise ValueError("Working tree must be clean to avoid touching other work")
    git("fetch", "--quiet", "origin", "main")
    local = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", "origin/main").stdout.strip()
    if local != remote:
        raise ValueError("Local checkout must be up-to-date with origin/main")


def release(draft_dir: Path, *, publish_and_push: bool,
            copyright_clearance_confirmed: bool = False) -> dict:
    draft_dir = draft_dir.expanduser().resolve(strict=True)
    if draft_dir.is_relative_to(ROOT):
        raise ValueError("Private draft reports cannot be in the repository")
    feed = compile_feed(draft_dir, eligible_ids=eligible_catalog_ids())
    count = len(feed["worlds"])
    if not publish_and_push:
        return {"status": "preview", "eligibleVisualPreviews": count,
                "published": False}
    if not copyright_clearance_confirmed:
        raise ValueError("Confirm permission to publish the numeric visual previews")
    # A nonempty draft directory with all permission flags revoked must
    # remove previously published visual entries; an empty directory should
    # not silently erase public data during a temporary disk/mount failure.
    if not count and not any(draft_dir.glob("*.draft.json")):
        return {"status": "no-eligible-records", "published": False}
    check_git_safety()
    current = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    if current.get("worlds") == feed["worlds"]:
        return {"status": "unchanged", "published": False, "worlds": count}
    atomic_json(OUTPUT, feed)
    try:
        git("add", "--", str(OUTPUT.relative_to(ROOT)))
        git("commit", "-m", "data: update consented interior video visual previews")
        git("push", "origin", "main")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Do not force-push. The user can resolve standard Git conflicts.
        raise RuntimeError("Git commit/push failed; inspect local repo before retrying")
    return {"status": "pushed", "published": True, "worlds": count,
            "output": str(OUTPUT.relative_to(ROOT))}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft-dir", type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--publish-and-push", action="store_true")
    p.add_argument("--confirm-publishing-rights", action="store_true",
                   help="Confirm authority to publish the numeric visual estimates")
    args = p.parse_args(argv)
    try:
        summary = release(
            args.draft_dir, publish_and_push=args.publish_and_push,
            copyright_clearance_confirmed=args.confirm_publishing_rights,
        )
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        p.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
