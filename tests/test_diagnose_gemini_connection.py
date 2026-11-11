"""Offline tests for tiny redacted Gemini REST diagnostics (no network)."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from scripts import diagnose_gemini_connection as diag


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, value):
        self.data = json.dumps(value).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.data[:size]


class GeminiRestDiagnosticTests(unittest.TestCase):
    def test_successful_get_and_tiny_post_never_include_key_in_url(self):
        seen = []
        key = "AIza_TEST_SECRET_must_not_be_printed"
        def send(request, timeout):
            seen.append(request)
            self.assertEqual(request.get_header("X-goog-api-key"), key)
            self.assertNotIn(key, request.full_url)
            self.assertEqual(timeout, diag.TIMEOUT_SECONDS)
            return FakeResponse({"models": []} if request.get_method() == "GET" else {"candidates": []})
        def probe(url, provided, *, payload=None):
            return diag.probe(url, provided, payload=payload, urlopen=send)
        report = diag.diagnostics(key, probe_fn=probe, environ={})
        self.assertEqual(report["status"], "rest-text-ok")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0].get_method(), "GET")
        self.assertEqual(seen[1].get_method(), "POST")
        self.assertIn(b"Reply with OK only", seen[1].data)
        self.assertNotIn(key, json.dumps(report))
        self.assertNotIn("candidates", json.dumps(report))

    def test_html_400_does_not_echo_key_or_body_and_skips_post(self):
        key = "AIza_SECRET"
        requests = []
        def sender(request, timeout):
            requests.append(request)
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request",
                {"Content-Type": "text/html"},
                io.BytesIO(b'<html><title>Error 400 Bad Request SECRET_BODY</title></html>'))
        result = diag.diagnostics(key, probe_fn=lambda url, api_key, **kw:
                                  diag.probe(url, api_key, urlopen=sender, **kw),
                                  environ={"HTTPS_PROXY": "http://user:secret@proxy"})
        self.assertEqual(result["status"], "rest-list-failed")
        self.assertEqual(result["modelList"]["httpStatus"], 400)
        self.assertEqual(result["modelList"]["responseKind"], "html")
        self.assertEqual(len(requests), 1)
        self.assertTrue(result["proxyEnvironmentPresent"])
        self.assertNotIn(key, json.dumps(result))
        self.assertNotIn("SECRET_BODY", json.dumps(result))
        self.assertNotIn("user:", json.dumps(result))

    def test_google_json_error_status_is_only_structured_detail(self):
        def sender(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden",
                {"Content-Type": "application/json"},
                io.BytesIO(b'{"error": {"status":"PERMISSION_DENIED","message":"SECRET"}}'))
        report = diag.probe(diag.MODEL_LIST_URL, "AIza_SECRET", urlopen=sender)
        self.assertEqual(report["apiErrorStatus"], "PERMISSION_DENIED")
        self.assertNotIn("SECRET", json.dumps(report))

    def test_missing_key_fails_without_network(self):
        def invalid(*args, **kwargs):
            raise AssertionError("must not send")
        report = diag.diagnostics("", probe_fn=invalid, environ={})
        self.assertEqual(report["status"], "missing-api-key")
        self.assertNotIn("modelList", report)

    def test_model_list_failure_must_not_call_text_generation(self):
        seen = []
        def fail(url, key, **kw):
            seen.append(url)
            return {"outcome": "http-error", "httpStatus": 400}
        report = diag.diagnostics("AIza_TEST", probe_fn=fail, environ={})
        self.assertEqual(len(seen), 1)
        self.assertEqual(report["status"], "rest-list-failed")

    def test_safe_key_character_flags(self):
        r = diag.diagnostics(" \"AIza_test\" ", probe_fn=lambda *a, **k: {
            "outcome": "http-error", "httpStatus": 400}, environ={"GOOGLE_API_KEY": "another-secret"})
        self.assertTrue(r["keyHasOuterWhitespace"])
        self.assertTrue(r["keyHasQuoteCharacters"])
        self.assertEqual(r["keyFamily"], "unrecognized")
        self.assertTrue(r["googleApiKeyAlsoSet"])
        self.assertNotIn("AIza_test", json.dumps(r))
        self.assertNotIn("another-secret", json.dumps(r))

    def test_new_aq_authorization_key_is_normal_not_invalid(self):
        secret = "AQ.fake_new_auth_key_secret"
        captured = []
        def no_success(url, key, **kwargs):
            captured.append((url, key))
            return {"outcome": "http-error", "httpStatus": 400, "responseKind": "html"}
        r = diag.diagnostics(secret, probe_fn=no_success, environ={})
        self.assertEqual(r["keyFamily"], "authorization")
        self.assertEqual(r["modelList"]["httpStatus"], 400)
        self.assertEqual(r["status"], "rest-list-failed")
        self.assertEqual(len(captured), 1)
        self.assertNotIn(secret, json.dumps(r))
        self.assertNotIn("fake_new_auth", json.dumps(r))

    def test_legacy_standard_key_is_classified_without_validation_claim(self):
        r = diag.diagnostics("AIza_LegacySecret", probe_fn=lambda *a, **kwargs: {
            "outcome": "http-error", "httpStatus": 400}, environ={})
        self.assertEqual(r["keyFamily"], "legacy-standard")
        self.assertNotIn("AIza_LegacySecret", json.dumps(r))

    def test_dry_run_is_inert(self):
        with patch.object(diag, "diagnostics", side_effect=AssertionError("network")):
            self.assertEqual(diag.main([]), 0)


if __name__ == "__main__":
    unittest.main()
