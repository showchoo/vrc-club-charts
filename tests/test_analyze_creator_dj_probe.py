"""Unit tests for private, creator-installed Udon video player telemetry."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import analyze_creator_dj_probe as probe

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
SESSION = "CreatorTest01"


def event(kind, elapsed, clock=-1, players=1, code=0):
    return (
        f"2026.11.06 17:00:00 Debug - VCCDJPROBE|v=1"
        f"|session={SESSION}|world={WORLD}|component=screen01"
        f"|event={kind}|ms={elapsed}|vms={clock}"
        f"|players={players}|code={code}\n"
    )


def happy_log():
    return "".join([
        event("begin", 0),
        event("ready", 90),
        event("start", 130),
        event("play", 140),
        event("sample", 1000, 1000),
        event("sample", 2000, 2000),
        event("sample", 3000, 3000),
        event("stop", 3200),
    ])


class LocalPlayerProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / "output_log.txt"

    def load(self, text):
        self.log.write_text(text, encoding="utf-8")
        events, sha = probe.extract(self.log, session=SESSION, world=WORLD,
                                    component="screen01")
        self.assertEqual(len(sha), 64)
        return events

    def test_positive_means_only_clock_and_events_not_dj_stream(self):
        items = self.load(happy_log())
        result = probe.assess(items)
        self.assertEqual(result["status"], "local_player_clock_observed")
        self.assertTrue(result["playbackClockAdvanced"])
        self.assertTrue(result["eventSequenceObserved"])
        for field in ("equipmentFunctionalityVerified", "audioVerified",
                      "liveStreamVerified", "controlsVerified",
                      "videoPixelsVerified", "independentlyAuthenticated",
                      "rankingEligible"):
            with self.subTest(field=field):
                self.assertFalse(result[field])

    def test_errors_pauses_and_extra_participants_are_inconclusive(self):
        alterations = [
            happy_log().replace(event("stop", 3200), event("error", 3200, code=4)),
            happy_log().replace(event("stop", 3200), event("pause", 3001) +
                                event("stop", 3200)),
            happy_log().replace(event("sample", 2000, 2000),
                                event("sample", 2000, 2000, players=2)),
            happy_log().replace(event("stop", 3200),
                                event("privacy_stop", 3200)),
        ]
        for text in alterations:
            with self.subTest(text=text[-85:]):
                result = probe.assess(self.load(text))
                self.assertEqual(result["status"], "inconclusive")
                self.assertFalse(result["equipmentFunctionalityVerified"])

    def test_missing_play_and_no_progress_never_pass(self):
        for text in [
            happy_log().replace(event("play", 140), ""),
            happy_log().replace(event("sample", 3000, 3000),
                                event("sample", 3000, 1000)),
            happy_log().replace(event("start", 130), ""),
            happy_log().replace(event("stop", 3200), ""),
            happy_log().replace(event("stop", 3200), event("begin", 3200)),
        ]:
            with self.subTest(text=text[-85:]):
                self.assertEqual(probe.assess(self.load(text))["status"],
                                 "inconclusive")

    def test_other_test_sessions_and_private_log_lines_not_included(self):
        log_text = (
            "username=someone confidential_secret=VERY_PRIVATE\n" +
            happy_log() +
            happy_log().replace(SESSION, "OtherSession99")
        )
        items = self.load(log_text)
        self.assertEqual(len(items), 8)
        result = probe.assess(items)
        self.assertNotIn("VERY_PRIVATE", json.dumps(result))
        self.assertEqual(result["status"], "local_player_clock_observed")

    def test_invalid_tokens_or_video_session_refused(self):
        self.log.write_text(happy_log(), encoding="utf-8")
        for token in ("too", "../../x", "white space", "a" * 80):
            with self.subTest(token=token), self.assertRaises(ValueError):
                probe.extract(self.log, session=token, world=WORLD,
                              component="screen01")
        with self.assertRaises(ValueError):
            probe.extract(self.log, session=SESSION, world="not-a-world",
                          component="screen01")

    def test_bad_log_event_value_rejected(self):
        wrong = happy_log().replace(event("sample", 2000, 2000),
                                    event("sample", 2000, 2000, players=999))
        with self.assertRaisesRegex(ValueError, "Invalid player event"):
            self.load(wrong)

    def test_empty_log_yields_unknown_not_positive(self):
        result = probe.assess(self.load("2026.11.06 normal log\n"))
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("missing_or_multiple_begin", result["reasonCodes"])

    def test_stored_report_is_local_and_never_overwritten(self):
        self.log.write_text(happy_log(), encoding="utf-8")
        out = self.root / "private-verification.json"
        argv = ["--log", str(self.log), "--session", SESSION,
                "--world", WORLD, "--component", "screen01",
                "--out", str(out)]
        self.assertEqual(probe.main(argv), 0)
        recorded = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(recorded["status"], "local_player_clock_observed")
        self.assertFalse(recorded["equipmentFunctionalityVerified"])
        with self.assertRaises(SystemExit):
            probe.main(argv)


if __name__ == "__main__":
    unittest.main()
