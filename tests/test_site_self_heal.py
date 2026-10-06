"""Offline regression tests for unattended health monitoring and the Gemini safety boundary."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import gemini_site_repair as repair
from scripts import monitor_site_health as monitor
from scripts import notify_site_health as notify

WORLD = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
FIXABLE = [{"code": "home_worlds_link", "category": "home",
            "detail": "Homepage has no Worlds link", "auto_fixable": True}]


def fake_site(path_status=None, world_thumb=True):
    path_status = path_status or {}
    responses = {}
    for name, (path, marker) in monitor.PAGES.items():
        text = f'<!doctype html><html><body>{marker}</body></html>'
        if name == "home":
            text += '<a href="worlds/">Worlds</a><script src="i18n.js?v=1"></script>focusWorldGrid'
        if name == "worlds":
            text += (
                '<script src="../i18n.js"></script>'
                f'<a class="world-catalog-row"><img src="world-thumb?id={WORLD}"></a>'
                f'<a class="world-catalog-row"><img src="world-thumb?id={WORLD}"></a>'
            )
        responses[monitor.SITE + path] = (200, "text/html", text.encode())
    for name in monitor.SCRIPTS:
        body = ("vccLanguageToggle" if name == "i18n.js" else
                "world-thumb" if name == "app.js" else "ok")
        responses[monitor.SITE + "/" + name] = (200, "application/javascript", body.encode())
    responses[monitor.SITE + "/data/weekly-ranking.json"] = (
        200, "application/json", json.dumps({"worlds": [{"id": WORLD}]}).encode()
    )
    responses[monitor.SITE + "/data/ai-scout.json"] = (
        200, "application/json", b'{"scored":[]}'
    )
    responses[monitor.SITE + "/worlds/" + WORLD + ".html"] = (
        200, "text/html", ("world-thumb?id=" + WORLD).encode()
    )
    responses[monitor.THUMB + "?id=" + WORLD] = (
        200 if world_thumb else 502, "image/jpeg" if world_thumb else "text/plain",
        b"\xff\xd8" + b"x" * 110 if world_thumb else b""
    )
    responses.update(path_status)
    return lambda url: responses.get(url, (404, "text/plain", b""))


class SiteMonitoringTests(unittest.TestCase):
    def test_healthy_route_and_thumbnail_feed(self):
        report = monitor.validate_site(fake_site())
        self.assertTrue(report["healthy"], report["issues"])
        self.assertEqual(report["checks"]["world_catalog"]["rows"], 2)
        self.assertEqual(report["checks"]["thumbnail_proxy"]["status"], 200)

    def test_missing_world_directory_is_actionable(self):
        fetch = fake_site({monitor.SITE + "/worlds/": (404, "text/plain", b"")})
        report = monitor.validate_site(fetch)
        problems = {x["code"]: x for x in report["issues"]}
        self.assertIn("worlds_http", problems)
        self.assertTrue(problems["worlds_http"]["auto_fixable"])

    def test_thumbnail_cdn_outage_is_not_an_auto_fix(self):
        report = monitor.validate_site(fake_site(world_thumb=False))
        problem = next(x for x in report["issues"] if x["code"] == "thumbnail_delivery")
        self.assertFalse(problem["auto_fixable"])

    def test_unapproved_http_request_rejected(self):
        with self.assertRaises(ValueError):
            monitor.fetch("https://evil.example/steal")


class GeminiBoundariesTests(unittest.TestCase):
    def test_only_one_plain_relative_href_can_auto_merge(self):
        self.assertTrue(repair.safe_auto_merge([{
            "path": "index.html", "old": 'href="worlds"',
            "new": 'href="worlds/"'
        }]))
        for edits in [
            [{"path":"app.js","old":'href="worlds"',"new":'href="worlds/"'}],
            [{"path":"index.html","old":'href="worlds"',"new":'href="https://evil.example"'}],
            [{"path":"index.html","old":'src="broken"', "new":'src="okay"'}],
        ]:
            self.assertFalse(repair.safe_auto_merge(edits))

    def test_allowed_small_patch_and_failed_suspicious_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "index.html").write_text('<a href="worlds">Worlds</a>')
            with patch.object(repair, "ROOT", root):
                ok = {"confidence": 0.98, "edits": [{
                    "path": "index.html", "old": 'href="worlds"', "new": 'href="worlds/"'
                }]}
                edits, auto = repair.validate_edits(ok, FIXABLE)
                self.assertTrue(auto)
                repair.apply_edits(edits)
                self.assertIn('href="worlds/"', (root / "index.html").read_text())
                for malformed in [
                    {"confidence": 0.99, "edits": [{
                        "path":".github/workflows/site-self-heal.yml", "old":"x", "new":"y"}]},
                    {"confidence": 0.99, "edits": [{
                        "path":"index.html", "old":'href="worlds/"', "new":"GITHUB_TOKEN"}]},
                    {"confidence": 0.4, "edits": [{
                        "path":"index.html", "old":'href="worlds/"', "new":'href="worlds/index.html"'}]},
                ]:
                    if malformed["confidence"] < 0.84:
                        self.assertEqual(repair.validate_edits(malformed, FIXABLE), ([], False))
                    else:
                        with self.assertRaises(ValueError):
                            repair.validate_edits(malformed, FIXABLE)

    def test_no_code_edits_for_external_only_issue(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "index.html").write_text('<a href="worlds">Worlds</a>')
            with patch.object(repair, "ROOT", root):
                proposal = {"confidence": 1.0, "edits": [{
                    "path": "index.html", "old": 'href="worlds"', "new": 'href="worlds/"'
                }]}
                self.assertEqual(repair.validate_edits(proposal, [
                    {"code": "thumbnail_delivery", "auto_fixable": False}
                ]), ([], False))


class HealthAlertTests(unittest.TestCase):
    def test_alert_displays_only_monitor_summary_and_optional_pr(self):
        text = notify.format_incident(
            {"issues": FIXABLE}, {"status": "no_safe_patch"},
            "https://github.com/showchoo/vrc-club-charts/pull/123"
        )
        self.assertIn("home_worlds_link", text)
        self.assertIn("pull/123", text)
        self.assertIn("requires human approval", text)

    def test_green_monitor_resolves_open_issue(self):
        operations = []

        def fake_api(method, path, token, payload=None):
            operations.append((method, path, payload))
            if method == "GET":
                return [{"number": 23, "body": "issue"}]
            return {}

        with patch.object(notify, "api", side_effect=fake_api):
            status = notify.sync({"healthy": True}, {}, "token",
                                 "showchoo/vrc-club-charts", "showchoo")
        self.assertEqual(status, "healthy")
        self.assertTrue(any(method == "PATCH" and data.get("state") == "closed"
                            for method, _, data in operations))


if __name__ == "__main__":
    unittest.main()
