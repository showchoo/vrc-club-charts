"""Offline workday gate tests. No Google network, OAuth browser, or VRChat."""
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

from scripts import workday_patrol_gate as gate

DAY = dt.date(2026, 11, 12)


def event(summary="仕事", start="2026-11-12T00:00:00+09:00",
          end="2026-11-13T00:00:00+09:00", status="confirmed"):
    return {
        "summary": summary, "start": {"dateTime": start},
        "end": {"dateTime": end}, "status": status,
    }


class GateDecisionTests(unittest.TestCase):
    def test_shift_title_variants_are_eligible(self):
        for title in ["仕事", "仕事 会計なし", "仕事　明けで滝田バスケ",
                      "仕事\t締め", "仕事　締め+有給"]:
            with self.subTest(title=title):
                result = gate.decide_from_events([event(summary=title)], DAY)
                self.assertTrue(result["workday"])
                self.assertEqual(result["status"], "workday-eligible")
                self.assertEqual(result["matchingConfirmedWorkEvents"], 1)
                self.assertFalse(result["vrchatLaunched"])
                self.assertFalse(result["automaticPatrolImplemented"])

    def test_similar_personal_tasks_and_no_work_are_excluded(self):
        for title in ["仕事なし", "仕事ズボン縫う", "仕事の準備", "仕事予定",
                      "仕事関連", "仕事?", "残業", "NBA 仕事", "明日は仕事"]:
            with self.subTest(title=title):
                result = gate.decide_from_events([event(summary=title)], DAY)
                self.assertFalse(result["workday"])
                self.assertEqual(result["status"], "non-workday-skip")

    def test_cancelled_and_tentative_events_do_not_authorize(self):
        for status in ["cancelled", "tentative", None]:
            with self.subTest(status=status):
                self.assertFalse(gate.decide_from_events([
                    event(status=status)], DAY)["workday"])

    def test_event_in_adjacent_jst_day_is_excluded(self):
        prior = event(start="2026-11-11T00:00:00+09:00",
                      end="2026-11-12T00:00:00+09:00")
        after = event(start="2026-11-13T00:00:00+09:00",
                      end="2026-11-14T00:00:00+09:00")
        self.assertFalse(gate.decide_from_events([prior, after], DAY)["workday"])

    def test_timezone_offset_is_converted_to_japan(self):
        utc = event(start="2026-11-11T15:00:00Z",
                    end="2026-11-12T15:00:00Z")
        self.assertTrue(gate.decide_from_events([utc], DAY)["workday"])
        self.assertFalse(gate.decide_from_events([utc], dt.date(2026, 11, 11))["workday"])

    def test_all_day_google_date_event_is_supported(self):
        all_day = {
            "summary": "仕事", "status": "confirmed",
            "start": {"date": "2026-11-12"},
            "end": {"date": "2026-11-13"},
        }
        self.assertTrue(gate.decide_from_events([all_day], DAY)["workday"])

    def test_bad_shift_data_must_fail_closed(self):
        variants = [
            event(start="2026-11-12T00:00:00"),
            event(end="2026-11-12T00:00:00+09:00"),
            event(start="bad timestamp"),
            {"summary": "仕事", "status": "confirmed", "start": {}},
            None,
        ]
        for broken in variants:
            with self.subTest(broken=broken), self.assertRaises(gate.CalendarGateError):
                gate.decide_from_events([broken], DAY)

    def test_does_not_expose_private_event_titles_in_decision(self):
        result = gate.decide_from_events([
            event(summary="仕事　明けで体育館バスケ"),
            event(summary="仕事", status="cancelled")], DAY)
        dumped = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("体育館", dumped)
        self.assertNotIn("仕事", dumped)
        self.assertEqual(result["matchingConfirmedWorkEvents"], 1)


class MockRequest:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def execute(self):
        if not self.pages:
            raise AssertionError("Unexpected extra API request")
        item = self.pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class MockService:
    def __init__(self, pages):
        self.req = MockRequest(pages)

    def events(self):
        return self.req


class CalendarReaderTests(unittest.TestCase):
    def test_reads_all_pages_without_title_query_and_jst_bounds(self):
        service = MockService([
            {"items": [event("仕事なし")], "nextPageToken": "p2"},
            {"items": [event("仕事　会計なし")]},
        ])
        events = gate.calendar_events(service, DAY)
        self.assertEqual(len(events), 2)
        self.assertTrue(gate.decide_from_events(events, DAY)["workday"])
        self.assertEqual(service.req.calls[0]["calendarId"], "primary")
        self.assertEqual(service.req.calls[0]["timeMin"],
                         "2026-11-12T00:00:00+09:00")
        self.assertEqual(service.req.calls[0]["timeMax"],
                         "2026-11-13T00:00:00+09:00")
        self.assertEqual(service.req.calls[0]["timeZone"], "Asia/Tokyo")
        self.assertNotIn("q", service.req.calls[0])
        self.assertEqual(service.req.calls[1]["pageToken"], "p2")
        self.assertEqual(service.req.calls[0]["singleEvents"], True)

    def test_empty_authoritative_response_means_no_work(self):
        service = MockService([{"items": []}])
        self.assertFalse(gate.decide_from_events(
            gate.calendar_events(service, DAY), DAY)["workday"])

    def test_api_failure_fails_closed(self):
        service = MockService([RuntimeError("private details")])
        with self.assertRaisesRegex(gate.CalendarGateError, "api-unavailable"):
            gate.calendar_events(service, DAY)

    def test_malformed_or_cyclic_pagination_fails_closed(self):
        for pages in [[{}], [{"items": [event()], "nextPageToken": "x"},
                             {"items": [event()], "nextPageToken": "x"}]]:
            with self.subTest(pages=pages), self.assertRaises(gate.CalendarGateError):
                gate.calendar_events(MockService(pages), DAY)

    def test_missing_credentials_never_opens_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(
                    gate.CalendarGateError, "authorization-required"):
                gate.authenticate(Path(folder), allow_browser=False)


class CommandLineTests(unittest.TestCase):
    def test_eligible_returns_zero_without_launch(self):
        out = io.StringIO()
        with (patch.object(gate, "read_google_events",
                           return_value=[event("仕事　会計なし")]) as read,
              redirect_stdout(out)):
            code = gate.main(["--date", "2026-11-12"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["vrchatLaunched"])
        read.assert_called_once_with(DAY, allow_browser=False)

    def test_nonworkday_returns_three(self):
        out = io.StringIO()
        with (patch.object(gate, "read_google_events", return_value=[]),
              redirect_stdout(out)):
            code = gate.main(["--date", "2026-11-12"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out.getvalue())["status"], "non-workday-skip")

    def test_api_failure_returns_two_and_skips(self):
        out = io.StringIO()
        with (patch.object(gate, "read_google_events",
                           side_effect=gate.CalendarGateError("calendar-api-unavailable")),
              redirect_stdout(out)):
            code = gate.main(["--date", "2026-11-12"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(out.getvalue())["workday"])


if __name__ == "__main__":
    unittest.main()
