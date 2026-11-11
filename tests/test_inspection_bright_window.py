"""Offline tests for private, unverified bright-window suggestions."""
import unittest

from scripts.inspection_bright_window import BriefBrightWindow


def metrics(median, black=0.2):
    return {"medianLuma": median, "nearBlackFraction": black}


class BrightWindowTests(unittest.TestCase):
    def test_two_consecutive_bright_after_dark_yield_one_candidate(self):
        window = BriefBrightWindow()
        for level, image in zip([5, 8, 60, 100, 10, 75, 110, 4],
                                [bytes([i]) for i in range(8)]):
            window.observe(metrics(level), image)
        result = window.summary()
        self.assertEqual(result["status"], "brief-brightness-opportunity")
        self.assertEqual(result["eligibleBrightPairsSeen"], 2)
        self.assertEqual(result["candidate"]["candidateSample"], 7)
        self.assertEqual(result["candidate"]["medianLuma"], 110)
        self.assertEqual(window.best_image, bytes([6]))
        self.assertFalse(result["lightingCycleVerified"])
        self.assertFalse(result["safeToMoveOrResumeAutomation"])
        self.assertFalse(result["djEquipmentVerified"])
        self.assertTrue(result["strobeOrOverexposureNotExcluded"])

    def test_single_bright_strobes_never_qualify(self):
        window = BriefBrightWindow()
        for level in [5, 170, 5, 160, 5, 186, 5]:
            window.observe(metrics(level), b"frame")
        self.assertIsNone(window.best_image)
        self.assertIsNone(window.summary()["candidate"])
        self.assertEqual(window.summary()["eligibleBrightPairsSeen"], 0)

    def test_stable_always_bright_does_not_claim_dark_recovery(self):
        window = BriefBrightWindow()
        for _ in range(30):
            window.observe(metrics(110), b"frame")
        self.assertIsNone(window.summary()["candidate"])
        self.assertEqual(window.summary()["eligibleBrightPairsSeen"], 0)

    def test_dark_overlay_cannot_qualify_as_bright(self):
        window = BriefBrightWindow()
        for value, black in [(5, 0.8), (170, 0.96), (180, 0.98), (60, .2), (5, .8)]:
            window.observe(metrics(value, black), b"frame")
        self.assertIsNone(window.summary()["candidate"])

    def test_offline_metric_only_analysis_never_creates_image(self):
        window = BriefBrightWindow()
        for level in [5, 60, 90, 7]:
            window.observe(metrics(level))
        self.assertIsNotNone(window.summary()["candidate"])
        self.assertIsNone(window.best_image)


    def test_longer_bright_run_beats_two_frame_186_peak(self):
        window = BriefBrightWindow()
        levels = [5, 100, 186, 9, 65, 75, 68, 71, 8]
        for i, level in enumerate(levels):
            window.observe(metrics(level), bytes([i]))
        candidate = window.summary()["candidate"]
        self.assertEqual(candidate["brightRunSamples"], [5, 8])
        self.assertEqual(candidate["brightRunLength"], 4)
        self.assertEqual(candidate["candidateSample"], 8)
        self.assertEqual(candidate["medianLuma"], 71)
        self.assertEqual(window.best_image, bytes([7]))
        self.assertEqual(window.summary()["eligibleBrightPairsSeen"], 4)
        self.assertFalse(window.summary()["safeToMoveOrResumeAutomation"])

    def test_equal_length_run_prefers_lower_brightness_spread(self):
        window = BriefBrightWindow()
        for level in [8, 65, 120, 10, 55, 59, 9]:
            window.observe(metrics(level), b"local")
        candidate = window.summary()["candidate"]
        self.assertEqual(candidate["brightRunSamples"], [5, 6])
        self.assertEqual(candidate["brightRunLumaSpread"], 4)

    def test_later_longer_run_updates_representative(self):
        window = BriefBrightWindow()
        for i, level in enumerate([10, 60, 85, 15, 55, 65, 60, 12]):
            window.observe(metrics(level), bytes([i]))
        self.assertEqual(window.summary()["candidate"]["brightRunLength"], 3)
        self.assertEqual(window.summary()["candidate"]["candidateSample"], 7)
        self.assertEqual(window.best_image, bytes([6]))

    def test_held_frame_history_bounded_to_six(self):
        window = BriefBrightWindow()
        for i, level in enumerate([8] + [60] * 30):
            window.observe(metrics(level), bytes([i]))
        self.assertEqual(len(window._recent_frames), 6)
        self.assertEqual(window.summary()["candidate"]["brightRunLength"], 30)
        self.assertEqual(window.summary()["candidate"]["representativeFrameLimitedToLastSamples"], 6)
        self.assertFalse(window.summary()["lightingCycleVerified"])

    def test_missing_png_offline_still_computes_candidate(self):
        window = BriefBrightWindow()
        for level in [9, 56, 62, 65, 8]:
            window.observe(metrics(level))
        self.assertEqual(window.summary()["candidate"]["brightRunLength"], 3)
        self.assertIsNone(window.best_image)

    def test_invalid_values_fail_closed(self):
        for value in [None, {}, metrics(float("nan")), metrics(True), metrics(-5)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                BriefBrightWindow().observe(value)


if __name__ == "__main__":
    unittest.main()
