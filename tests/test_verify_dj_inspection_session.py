"""Tests for private combined DJ player/audio evidence, not VRChat operation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_dj_inspection_session as combined

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
SESSION = "CreatorTest01"


def event(kind, ms, vms=-1, players=1):
    return (
        "2026.11.06 Debug: VCCDJPROBE|v=1|session=" + SESSION
        + "|world=" + WORLD + "|component=screen01|event=" + kind
        + "|ms=" + str(ms) + "|vms=" + str(vms)
        + "|players=" + str(players) + "|code=0\n"
    )


def log_text():
    return "".join([
        event("begin", 0), event("ready", 80),
        event("start", 120), event("play", 150),
        event("sample", 1000, 1000),
        event("sample", 2000, 2000),
        event("sample", 3000, 3000), event("stop", 3250),
    ])


class CombinedEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.log = self.base / "output_log.txt"
        self.reference = self.base / "reference.mp4"
        self.capture = self.base / "capture.mp4"
        self.destination = self.base / "private-combined.json"
        self.log.write_text(log_text() + "private message PASSWORD_DO_NOT_COPY\n")
        self.reference.write_bytes(b"source data test fixture")
        self.capture.write_bytes(b"separate recording test fixture")

    def evaluate(self, *, rights=True, same=True):
        return combined.evaluate_session(
            log=self.log, session=SESSION, world=WORLD, component="screen01",
            reference=self.reference, capture=self.capture,
            recording_rights_confirmed=rights, same_session_attested=same,
        )

    @staticmethod
    def tones(matched):
        return {"matched": matched, "frequenciesDetected":
                [523, 659, 784, 1046] if matched else []}

    def test_both_signals_generate_unverified_aggregate_only(self):
        with patch.object(combined, "read_tone_pattern", return_value=self.tones(True)):
            result = self.evaluate()
        self.assertEqual(result["status"], "operator_linked_local_observations")
        self.assertTrue(result["observations"]["playerEventSequenceAndClockObserved"])
        self.assertTrue(result["observations"]["fourToneAudioPatternInSeparateRecording"])
        self.assertEqual(len(result["sourceHashes"]), 3)
        for field in ("equipmentFunctionalityVerified", "rankingEligible",
                      "audioOutputIndependentlyVerified", "videoPixelsVerified",
                      "liveDjStreamingVerified", "controlsVerified",
                      "vrchatClientOriginIndependentlyAuthenticated",
                      "publicSiteChanged", "networkUsed"):
            with self.subTest(field=field):
                self.assertFalse(result[field])
        encoded = json.dumps(result)
        self.assertNotIn("PASSWORD_DO_NOT_COPY", encoded)
        self.assertNotIn(str(self.capture), encoded)

    def test_only_audio_positive_is_inconclusive(self):
        self.log.write_text(log_text().replace(event("play", 150), ""))
        with patch.object(combined, "read_tone_pattern", return_value=self.tones(True)):
            result = self.evaluate()
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["observations"]["playerEventSequenceAndClockObserved"])

    def test_only_player_positive_is_inconclusive(self):
        with patch.object(combined, "read_tone_pattern",
                          side_effect=[self.tones(True), self.tones(False)]):
            result = self.evaluate()
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["observations"]["fourToneAudioPatternInSeparateRecording"])

    def test_bad_reference_rejected(self):
        with patch.object(combined, "read_tone_pattern",
                          return_value=self.tones(False)):
            with self.assertRaisesRegex(ValueError, "Reference"):
                self.evaluate()

    def test_consent_and_same_session_attestations_required(self):
        for rights, same in ((False, True), (True, False), (False, False)):
            with self.subTest(rights=rights, same=same), self.assertRaises(ValueError):
                self.evaluate(rights=rights, same=same)

    def test_copied_reference_rejected(self):
        self.capture.write_bytes(self.reference.read_bytes())
        with self.assertRaisesRegex(ValueError, "byte-identical"):
            self.evaluate()

    def test_private_report_does_not_overwrite(self):
        with patch.object(combined, "read_tone_pattern", return_value=self.tones(True)):
            result = self.evaluate()
        target = combined.private_report(self.destination, result)
        self.assertTrue(target.is_file())
        self.assertEqual(json.loads(target.read_text())["status"],
                         "operator_linked_local_observations")
        with self.assertRaises(FileExistsError):
            combined.private_report(self.destination, result)

    def test_out_of_order_events_are_not_positive(self):
        broken = log_text().replace(event("ready", 80), "").replace(
            event("play", 150), event("play", 80) + event("ready", 150))
        self.log.write_text(broken)
        with patch.object(combined, "read_tone_pattern", return_value=self.tones(True)):
            result = self.evaluate()
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("player_events_out_of_order",
                      result["observations"]["playerReasonCodes"])

    def test_symlink_inputs_rejected(self):
        fake = self.base / "alias.mp4"
        try:
            fake.symlink_to(self.capture)
        except (OSError, NotImplementedError):
            self.skipTest("Cannot create symlink on this platform")
        self.capture = fake
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.evaluate()

    def test_wrong_world_never_correlates(self):
        with patch.object(combined, "read_tone_pattern", return_value=self.tones(True)):
            result = combined.evaluate_session(
                log=self.log, session=SESSION,
                world="wrld_12345678-1234-1234-1234-123456789012",
                component="screen01", reference=self.reference,
                capture=self.capture, recording_rights_confirmed=True,
                same_session_attested=True)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["observations"]["playerEventCount"], 0)


if __name__ == "__main__":
    unittest.main()
