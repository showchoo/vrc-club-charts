#!/usr/bin/env python3
"""One-off, isolated GitHub Actions rehearsal of the production Gemini repair path.

Run ONLY on the disposable proof branch. Mutates the Actions checkout (never main).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import gemini_site_repair as repair
from scripts import monitor_site_health as monitor

ROOT = Path(__file__).resolve().parents[1]
RESULT = Path("/tmp/vcc-gemini-e2e-result.json")


def main() -> int:
    # The test branch contains one deliberately broken homepage navigation link.
    homepage = ROOT / "index.html"
    text = homepage.read_text(encoding="utf-8")
    if text.count('href="wrolds/"') != 1:
        raise SystemExit("FAIL: isolated fixture is not broken exactly once")

    # Reuse the existing offline monitor fixture, but replace its homepage
    # response with the same typo that exists in this temporary checkout.
    spec = importlib.util.spec_from_file_location(
        "vcc_test_selfheal", ROOT / "tests" / "test_site_self_heal.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("FAIL: monitor fixture unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    healthy_fetcher = module.fake_site()

    def broken_fetcher(url: str):
        status, mime, body = healthy_fetcher(url)
        if url == monitor.SITE + "/" and status == 200:
            body = body.replace(b'href="worlds/"', b'href="wrolds/"', 1)
        return status, mime, body

    report = monitor.validate_site(broken_fetcher)
    found = {x["code"] for x in report["issues"]}
    assert not report["healthy"] and "home_worlds_link" in found, found
    assert len(report["issues"]) == 1, found
    report_file = Path("/tmp/vcc-gemini-e2e-health.json")
    report_file.write_text(json.dumps(report), encoding="utf-8")
    print("PASS: existing monitor detected controlled link regression")

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("FAIL: Gemini key missing")
    # Call the unchanged, production Gemini entry point with its real
    # credentials, source context, allowlist and patch application.
    with patch.object(sys, "argv", [
        "gemini_site_repair", "--report", str(report_file),
        "--result", str(RESULT),
    ]):
        exit_code = repair.main()
    if exit_code:
        raise SystemExit("FAIL: Gemini repair entry point failed")
    plan = json.loads(RESULT.read_text(encoding="utf-8"))
    if plan["status"] != "patch_proposed":
        raise SystemExit("FAIL: Gemini did not propose an allowed patch (" + plan["status"] + ")")
    edits = plan.get("proposed_edits") or []
    if plan["edits"] != ["index.html"] or not 1 <= len(edits) <= 2:
        raise SystemExit("FAIL: Gemini changed more than the test homepage")
    revised = homepage.read_text(encoding="utf-8")
    if 'href="wrolds/"' in revised or not (
        'href="worlds/"' in revised or 'href="worlds/index.html"' in revised
    ):
        raise SystemExit("FAIL: proposed patch does not repair link")
    changed = set(subprocess.check_output(
        ["git", "diff", "--name-only"], text=True, cwd=ROOT
    ).splitlines())
    if changed != {"index.html"}:
        raise SystemExit("FAIL: changed unexpected paths " + repr(sorted(changed)))
    print("PASS: real Gemini-generated edit corrected the temporary checkout")
    print("PATCH_KIND:", "eligible" if plan["auto_merge"] else "review_required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
