#!/usr/bin/env python3
"""Read-only effect smoke test: re-submit an ALREADY LISTED World only.

The API must identify the existing World without charging a new submission or
reaching the Gemini queue. Never supply an unlisted World to this probe.
"""
from __future__ import annotations

import json
import urllib.request

BASE = "https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-submit"
EXISTING_WORLD = "wrld_6f6a12e4-9d48-4f89-b7fb-37e00df62be7"


def read(req: urllib.request.Request):
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.status, json.loads(response.read(100_000).decode("utf-8"))


def main():
    status, data = read(urllib.request.Request(BASE + "?queue=1&limit=1",
      headers={"Accept":"application/json", "User-Agent":"VCC-SubmissionSmoke/1.0"}))
    if status != 200 or not isinstance(data.get("worlds"), list):
        raise AssertionError("Submission read-only queue unavailable")
    payload = json.dumps({
        "url":"https://vrchat.com/home/world/"+EXISTING_WORLD+"/info",
        "visitorToken":"00000000-0000-4000-8000-000000000000",
    }).encode("utf-8")
    req = urllib.request.Request(BASE, payload, method="POST", headers={
        "Content-Type":"application/json",
        "Origin":"https://vrc-club-charts.vercel.app",
        "User-Agent":"VCC-SubmissionSmoke/1.0",
    })
    status, data = read(req)
    if status != 200 or data.get("status") != "already_listed" or data.get("worldId") != EXISTING_WORLD:
        raise AssertionError("Known published World was not deduplicated")
    print("World submission API: public queue readable; existing World safely deduplicated")


if __name__ == "__main__":
    main()
