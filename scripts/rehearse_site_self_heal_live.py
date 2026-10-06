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
            if edit.get("path") != "index.html":
                print("FAIL: Gemini proposed an edit outside the isolated homepage")
                return 1
            repair.apply_edits(edits)
            after = (root / "index.html").read_text(encoding="utf-8")
            # The model may choose either a directory URL or an explicit index
            # file. Accept a demonstrably working fix, not one exact JSON shape.
            if 'href="wrolds/"' in after or not (
                'href="worlds/"' in after or 'href="worlds/index.html"' in after
            ):
                print("FAIL: Gemini proposal did not repair the broken fixture link")
                print("Proposed edit path:", edit.get("path"))
                print("Proposed replacement length:", len(edit.get("new", "")))
                return 1
            if syntactically_safe and not repair.verified_built_link_fix(edits, root):
                print("FAIL: target not verified in isolated published fixture")
                return 1
            if not syntactically_safe:
                print("PASS: Gemini produced a working repair requiring human review")
            else:
                print("PASS: Gemini produced a working repair eligible for built-link verification")
            print("PASS: Gemini API key and model connectivity verified")
            print("PASS: no production site file or credential was changed")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
