#!/usr/bin/env python3
"""Redacted, opt-in Gemini REST connectivity checks using Python stdlib only.

No local video, VRChat, source code or model output is uploaded. A GET to the
model listing and, only after that succeeds, one tiny POST are sent to the
official Gemini API. Credential, response body, proxy URLs and user paths are
never printed. No automatic retries. Report is safe to paste in a support chat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request

MODEL = "gemini-3.5-flash-lite"
MODEL_LIST_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODEL + ":generateContent"
)
MAX_ERROR_BYTES = 4096
TIMEOUT_SECONDS = 20


def _response_kind(content_type: str, body: bytes) -> str:
    if isinstance(content_type, str) and "json" in content_type.lower():
        return "json"
    if isinstance(content_type, str) and "html" in content_type.lower():
        return "html"
    if body.lstrip()[:10].lower().startswith((b"<!doctype", b"<html")):
        return "html"
    try:
        if isinstance(json.loads(body), dict):
            return "json"
    except (ValueError, UnicodeDecodeError):
        pass
    return "other"


def _safe_error_status(body: bytes) -> str | None:
    try:
        raw = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("error"), dict):
        return None
    status = raw["error"].get("status")
    return status if isinstance(status, str) and re.fullmatch(r"[A-Z_]{3,50}", status) else None


def probe(url: str, key: str, *, payload: bytes | None = None,
          urlopen=None) -> dict:
    """Never put the API key in the URL or the returned report."""
    method = "POST" if payload is not None else "GET"
    headers = {"x-goog-api-key": key, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, headers=headers, method=method, data=payload)
    sender = urlopen if urlopen is not None else urllib.request.urlopen
    try:
        with sender(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_ERROR_BYTES)
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get("Content-Type", "") if error.headers is not None else ""
        body = error.read(MAX_ERROR_BYTES)
    except (OSError, urllib.error.URLError, TimeoutError, ConnectionError) as error:
        return {"outcome": "connection-error", "errorType": type(error).__name__}

    kind = _response_kind(content_type, body)
    result = {
        "outcome": "ok" if 200 <= status <= 299 else "http-error",
        "httpStatus": status,
        "responseKind": kind,
    }
    safe_status = _safe_error_status(body)
    if safe_status:
        result["apiErrorStatus"] = safe_status
    return result


def diagnostics(key: str, *, probe_fn=probe, environ=None) -> dict:
    env = os.environ if environ is None else environ
    # Flag likely copy/paste problems without printing any key information.
    result = {
        "schemaVersion": 1,
        "apiKeyPresent": bool(key),
        "keyLooksTruncated": bool(key and len(key) < 20),
        "keyHasOuterWhitespace": bool(key and key != key.strip()),
        "keyHasQuoteCharacters": bool(key and ('"' in key or "'" in key)),
        # Google AI Studio began issuing AQ.-prefixed authorization keys by
        # default in May 2026. A non-AIza prefix is not evidence of a bad key.
        # Only report the public key *family*, never any prefix/characters.
        "keyFamily": (
            "authorization" if key.startswith("AQ.")
            else "legacy-standard" if key.startswith("AIza")
            else "missing" if not key
            else "unrecognized"
        ),
        "googleApiKeyAlsoSet": bool(env.get("GOOGLE_API_KEY")),
        "proxyEnvironmentPresent": any(
            bool(env.get(name)) for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                                            "http_proxy", "https_proxy", "all_proxy")
        ),
        "testsSentNoUserMedia": True,
    }
    if not key:
        result["status"] = "missing-api-key"
        return result
    if len(key) < 20:
        result["status"] = "invalid-key-input-length"
        return result
    first = probe_fn(MODEL_LIST_URL, key)
    result["modelList"] = first
    if first.get("outcome") != "ok":
        result["status"] = "rest-list-failed"
        return result
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Reply with OK only"}]}]
    }).encode("utf-8")
    second = probe_fn(GENERATE_URL, key, payload=payload)
    result["textGeneration"] = second
    result["status"] = "rest-text-ok" if second.get("outcome") == "ok" else "rest-generate-failed"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true",
                        help="Opt in to a Google API key check and one tiny text-only request")
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"status": "dry-run", "networkRequestsMade": 0}, indent=2))
        return 0
    result = diagnostics(os.environ.get("GEMINI_API_KEY", ""))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["status"] == "rest-text-ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
