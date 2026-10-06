#!/usr/bin/env python3
"""Manual, one-call Gemini rehearsal on isolated local HTML. Never touches production."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts import gemini_site_repair as repair


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise SystemExit("FAIL: GEMINI_API_KEY is not exposed to this workflow")
    issue = {
        "code": "home_worlds_link",
        "category": "home",
        "detail": (
            "In the isolated test fixture only, the Worlds nav uses the typo "
            "href=\"wrolds/\". The existing destination is worlds/. "
            "Correct this one internal link without changing any other code."
        ),
        "auto_fixable": True,
    }
    html = (
        '<!doctype html><nav>'
        '<a href="wrolds/">Worlds</a>'
        '<a href="events.html">Events</a>'
        '</nav>'
    )
    with tempfile.TemporaryDirectory(prefix="vcc-gemini-rehearsal-") as temp:
        root = Path(temp)
        (root / "index.html").write_text(html, encoding="utf-8")
        (root / "worlds").mkdir()
        (root / "worlds" / "index.html").write_text("<h1>Worlds</h1>")
        with patch.object(repair, "ROOT", root):
            try:
                proposal = repair.query_gemini(
                    [issue], {"index.html": html}, key
                )
                edits, syntactically_safe = repair.validate_edits(proposal, [issue])
            except Exception as exc:
                # Never print the API key or raw API responses.
                print("FAIL: Gemini API request/validation:", type(exc).__name__)
                return 1
            if len(edits) != 1:
                print("FAIL: Gemini returned no allowable single-link repair")
                return 1
            edit = edits[0]
            expected = {
                "path": "index.html",
                "old": 'href="wrolds/"',
                "new": 'href="worlds/"',
            }
            if edit != expected:
                print("FAIL: Gemini returned a different repair; do not trust it")
                return 1
            if not syntactically_safe:
                print("FAIL: expected single-link syntactic safety")
                return 1
            repair.apply_edits(edits)
            if not repair.verified_built_link_fix(edits, root):
                print("FAIL: target not verified on the isolated built fixture")
                return 1
            if (root / "index.html").read_text() != html.replace(
                    'href="wrolds/"', 'href="worlds/"'):
                print("FAIL: unexpected fixture edit")
                return 1
            print("PASS: Gemini API responded; exact bounded fix applied;")
            print("PASS: old route absent and new published target verified")
            print("PASS: no production site file or credential was changed")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
