#!/usr/bin/env python3
"""Read-only, fail-closed Google Calendar workday gate for a future LOCAL patrol.

Only checks the current Asia/Tokyo date against confirmed shift events in
the primary calendar. No Steam, VRChat, OSC, ranking, or scheduling actions.
Keep OAuth credentials and token on the Windows PC, NEVER in this public repo.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

TIMEZONE = dt.timezone(dt.timedelta(hours=9), "Asia/Tokyo")
SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]
# A standalone "仕事" shift or "仕事　会計なし" / "仕事 明け..." variant.
# Do not match "仕事なし", "仕事ズボン縫う", or other unrelated phrases.
SHIFT_TITLE = re.compile(r"^仕事(?:$|[\u0020\u3000\t])")
MAX_PAGES = 10
PAGE_SIZE = 250


class CalendarGateError(RuntimeError):
    """No verified workday decision can be made: refuse to launch patrol."""


def local_auth_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "VRCClubCharts" / "calendar-auth"
    return Path.home() / ".config" / "VRCClubCharts" / "calendar-auth"


def _read_event_time(raw: object) -> dt.datetime:
    if not isinstance(raw, dict):
        raise CalendarGateError("invalid-calendar-event-time")
    if isinstance(raw.get("date"), str):
        try:
            return dt.datetime.combine(
                dt.date.fromisoformat(raw["date"]), dt.time.min, TIMEZONE)
        except ValueError as exc:
            raise CalendarGateError("invalid-calendar-event-date") from exc
    stamp = raw.get("dateTime")
    if not isinstance(stamp, str):
        raise CalendarGateError("calendar-event-has-no-time")
    try:
        instant = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarGateError("invalid-calendar-event-timestamp") from exc
    if instant.tzinfo is None:
        # Google normally returns timezone-aware dateTime. A naive value
        # cannot be trusted for a safety gate, so fail closed.
        raise CalendarGateError("calendar-event-timestamp-missing-timezone")
    return instant.astimezone(TIMEZONE)


def workday_event(event: object, target: dt.date) -> bool:
    """Accept only confirmed title-bounded shifts intersecting JST day."""
    if not isinstance(event, dict):
        raise CalendarGateError("invalid-calendar-event")
    if event.get("status") != "confirmed":
        return False
    title = event.get("summary")
    if not isinstance(title, str) or SHIFT_TITLE.match(title) is None:
        return False
    start = _read_event_time(event.get("start"))
    end = _read_event_time(event.get("end"))
    if end <= start:
        raise CalendarGateError("invalid-calendar-event-range")
    day_start = dt.datetime.combine(target, dt.time.min, TIMEZONE)
    day_end = day_start + dt.timedelta(days=1)
    return start < day_end and end > day_start


def decide_from_events(events: list[dict], target: dt.date) -> dict:
    """Return only a boolean decision, never private event titles or IDs."""
    if not isinstance(events, list) or type(target) is not dt.date:
        raise CalendarGateError("invalid-calendar-input")
    count = sum(1 for event in events if workday_event(event, target))
    return {
        "schemaVersion": 1,
        "dateJst": target.isoformat(),
        "timeZone": "Asia/Tokyo",
        "status": "workday-eligible" if count else "non-workday-skip",
        "workday": bool(count),
        "matchingConfirmedWorkEvents": count,
        "calendarReadOnly": True,
        "vrchatLaunched": False,
        "steamLaunched": False,
        "automaticPatrolImplemented": False,
        "publicScheduleStored": False,
    }


def calendar_events(service: object, target: dt.date) -> list[dict]:
    """Query ALL matching-day events, paging so no truncated result is trusted.

    Google Calendar events.list timeMin is exclusive on event.end and
    timeMax is exclusive on event.start. Query only this JST day.
    """
    if type(target) is not dt.date:
        raise CalendarGateError("invalid-date")
    start = dt.datetime.combine(target, dt.time.min, TIMEZONE)
    end = start + dt.timedelta(days=1)
    args = {
        "calendarId": "primary",
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": "Asia/Tokyo",
        "singleEvents": True,
        "showDeleted": False,
        "maxResults": PAGE_SIZE,
        "fields": "items(status,summary,start,end),nextPageToken",
    }
    events: list[dict] = []
    pages_seen: set[str] = set()
    for _ in range(MAX_PAGES):
        try:
            result = service.events().list(**args).execute()
        except Exception as exc:
            raise CalendarGateError("calendar-api-unavailable") from exc
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise CalendarGateError("invalid-calendar-api-response")
        events.extend(result["items"])
        page = result.get("nextPageToken")
        if not page:
            return events
        if not isinstance(page, str) or page in pages_seen:
            raise CalendarGateError("invalid-calendar-pagination")
        pages_seen.add(page)
        args["pageToken"] = page
    raise CalendarGateError("calendar-pagination-limit-exceeded")


def authenticate(auth_dir: Path, *, allow_browser: bool = False):
    """Google desktop OAuth. Browser interaction is allowed ONLY on setup."""
    token_path = auth_dir / "token.json"
    client_path = auth_dir / "oauth-client.json"
    if not token_path.exists() and not allow_browser:
        raise CalendarGateError("calendar-authorization-required")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise CalendarGateError("install-google-calendar-python-dependencies") from exc
    creds = None
    try:
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif allow_browser:
            if not client_path.is_file():
                raise CalendarGateError("oauth-client-json-missing")
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_path), SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            raise CalendarGateError("calendar-reauthorization-required")
        if not creds or not creds.valid:
            raise CalendarGateError("calendar-authorization-failed")
        auth_dir.mkdir(parents=True, exist_ok=True)
        temp = token_path.with_name("token.json.tmp")
        try:
            temp.write_text(creds.to_json(), encoding="utf-8")
            os.replace(temp, token_path)
            if os.name != "nt":
                token_path.chmod(0o600)
        finally:
            temp.unlink(missing_ok=True)
        return creds
    except CalendarGateError:
        raise
    except Exception as exc:
        raise CalendarGateError("calendar-credentials-invalid-or-expired") from exc


def read_google_events(target: dt.date, *, allow_browser: bool = False) -> list[dict]:
    creds = authenticate(local_auth_dir(), allow_browser=allow_browser)
    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise CalendarGateError("calendar-client-unavailable") from exc
    return calendar_events(service, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="JST date YYYY-MM-DD; default today")
    parser.add_argument("--authorize", action="store_true",
                        help="Allow one interactive OAuth login on this PC")
    args = parser.parse_args(argv)
    try:
        target = (dt.date.fromisoformat(args.date) if args.date else
                  dt.datetime.now(TIMEZONE).date())
        events = read_google_events(target, allow_browser=args.authorize)
        result = decide_from_events(events, target)
    except (CalendarGateError, ValueError) as exc:
        print(json.dumps({
            "status": "calendar-unavailable-skip",
            "reason": str(exc),
            "workday": False, "vrchatLaunched": False,
            "automaticPatrolImplemented": False,
        }, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 0 eligible; 3 verified non-workday; 2 API/auth/error (never eligible).
    return 0 if result["workday"] else 3


if __name__ == "__main__":
    sys.exit(main())
