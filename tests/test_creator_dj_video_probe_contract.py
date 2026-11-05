"""Static contract of the creator-owned Udon probe (no Unity SDK in CI).

This is not compilation or a VRChat runtime test. It prevents accidentally
removing safety gates, introducing network calls or claims of audio verification.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "unity" / "CreatorOwnedDJProbe" / "VCCDJVideoProbe.cs"


class CreatorOwnedProbeTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_video_events_are_explicit(self):
        for event in (
            "OnVideoReady()", "OnVideoStart()", "OnVideoPlay()",
            "OnVideoPause()", "OnVideoEnd()", "OnVideoError(VideoError videoError)",
        ):
            with self.subTest(event=event):
                self.assertIn(event, self.source)

    def test_probe_can_only_start_with_one_participant(self):
        self.assertIn("VRCPlayerApi.GetPlayerCount() != 1", self.source)
        self.assertIn('Emit("privacy_stop", -1, 0)', self.source)
        self.assertIn("public void BeginProbe()", self.source)
        self.assertIn("public void EndProbe()", self.source)

    def test_local_logging_only_with_bounded_samples(self):
        self.assertIn("private const int MaxSamples = 20;", self.source)
        self.assertIn("Time.realtimeSinceStartup - beganAt > 60f", self.source)
        self.assertIn("Debug.Log(", self.source)
        self.assertIn("VCCDJPROBE|v=1|session=", self.source)
        self.assertIn("|vms=", self.source)
        self.assertNotIn("HttpClient", self.source)
        self.assertNotIn("UnityWebRequest", self.source)
        self.assertNotIn("OnVideoPlayURL", self.source)

    def test_no_fake_verified_ranking_markers(self):
        self.assertNotIn("CraftsmanshipScore =", self.source)
        self.assertNotIn("rankingEligible = true", self.source)
        self.assertNotIn("audioOutputVerified = true", self.source)

    def test_sdk_components_are_expected(self):
        self.assertIn("BaseVRCVideoPlayer", self.source)
        self.assertIn("UdonSharpBehaviour", self.source)
        self.assertIn("public override void Interact()", self.source)


if __name__ == "__main__":
    unittest.main()
