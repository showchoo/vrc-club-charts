"""No-network tests for dynamic club lighting safety heuristics."""
from __future__ import annotations

import io
import unittest

from scripts import inspection_lighting_guard as light


class LightingGuardTests(unittest.TestCase):
    def test_uniform_stage_dimming_is_not_scene_motion_evidence(self):
        before = bytes([140]) * (192 * 108)
        after = bytes([78]) * (192 * 108)
        result = light.analyze_luma_pair(before, after)
        self.assertEqual(result["status"], "suspected-lighting-transition")
        self.assertTrue(result["lightingTransitionSuspected"])
        self.assertTrue(result["visualNavigationShouldPause"])
        self.assertFalse(result["positionOrClearanceVerified"])
        self.assertFalse(result["lowVisibilityObserved"])
        self.assertLess(result["medianSignedLumaChange"], -50)

    def test_club_brightening_also_pauses(self):
        r = light.analyze_luma_pair(bytes([30]) * 2000, bytes([100]) * 2000)
        self.assertTrue(r["lightingTransitionSuspected"])
        self.assertGreater(r["medianSignedLumaChange"], 0)
        self.assertTrue(r["visualNavigationShouldPause"])

    def test_sudden_near_black_frame_is_low_visibility(self):
        before = bytes([130]) * 2000
        after = bytes([3]) * 2000
        r = light.analyze_luma_pair(before, after)
        self.assertEqual(r["status"], "low-visibility")
        self.assertTrue(r["lowVisibilityObserved"])
        self.assertTrue(r["visualNavigationShouldPause"])
        self.assertGreater(r["fractionPixelsDarkAfter"], .96)

    def test_dark_but_detailed_club_not_automatically_blocked(self):
        # 50% illuminated decor + 50% black background is not all-black.
        scene = bytes([5, 48] * 1000)
        r = light.analyze_luma_pair(scene, scene)
        self.assertEqual(r["status"], "no-major-global-lighting-change-detected")
        self.assertFalse(r["lowVisibilityObserved"])
        self.assertFalse(r["visualNavigationShouldPause"])
        self.assertFalse(r["positionOrClearanceVerified"])

    def test_local_object_difference_not_assumed_global_light_change(self):
        source = bytes([90]) * 2000
        changed = bytes([110]) * 200 + bytes([90]) * 1800
        r = light.analyze_luma_pair(source, changed)
        self.assertEqual(r["status"], "no-major-global-lighting-change-detected")
        self.assertFalse(r["lightingTransitionSuspected"])
        self.assertFalse(r["positionOrClearanceVerified"])

    def test_invalid_samples_fail_closed(self):
        for a, b in ((b"", b""), (b"\x00"*16, b"\x00"*15),
                     (b"invalid", b"invalid")):
            with self.subTest(length=(len(a), len(b))):
                with self.assertRaises(ValueError):
                    light.analyze_luma_pair(a, b)

    def test_low_light_single_frame_with_real_png(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed on CI; pure grayscale tests still run")
        dark = Image.new("RGB", (384, 240), (2, 2, 2))
        bright = Image.new("RGB", (384, 240), (60, 60, 60))
        a, b = io.BytesIO(), io.BytesIO()
        dark.save(a, "PNG")
        bright.save(b, "PNG")
        self.assertTrue(light.one_frame_low_light(a.getvalue())["visualNavigationShouldPause"])
        self.assertFalse(light.one_frame_low_light(b.getvalue())["visualNavigationShouldPause"])
        self.assertTrue(light.analyze_png_pair(a.getvalue(), b.getvalue())[
            "visualNavigationShouldPause"])

    def test_invalid_png_never_claims_clear_view(self):
        outcome = light.one_frame_low_light(b"not an image")
        self.assertTrue(outcome["visualNavigationShouldPause"])
        outcome = light.analyze_png_pair(b"not an image", b"also not an image")
        self.assertTrue(outcome["visualNavigationShouldPause"])


if __name__ == "__main__":
    unittest.main()
