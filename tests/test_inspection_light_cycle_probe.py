"""Stationary VRChat light-cycle recovery tests; no VRChat, OSC or network."""
from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import inspection_light_cycle as light
from scripts import inspection_light_cycle_probe as probe

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
JOIN = "a" * 64


def sample(level, dark=0.1):
    return {"medianLuma": level, "nearBlackFraction": dark}


def cycle_values():
    return [
        sample(120), sample(119), sample(121),  # 3 stable lit baseline
        sample(53), sample(52),                 # 2 consecutive dark
        sample(100), sample(106), sample(105), sample(104),
        # 100,106,105 is NOT stable enough (spread 6), but 106,105,104 is
    ]


class TrackerTests(unittest.TestCase):
    def test_fade_and_three_stable_recovered_frames(self):
        tracker = light.LightCycleTracker()
        states = [tracker.observe(data)["status"] for data in cycle_values()]
        self.assertEqual(states[2], "watching-for-dim")
        self.assertEqual(states[4], "waiting-for-recovery")
        self.assertEqual(states[-1], "recovered-stable-light")
        self.assertEqual(tracker.summary()["referenceMedianLuma"], 120.0)
        self.assertTrue(tracker.summary()["dimSeen"])
        self.assertTrue(tracker.summary()["recoverySeen"])
        self.assertEqual(tracker.summary()["dimConfirmedSample"], 5)
        self.assertEqual(tracker.summary()["recoveryConfirmedSample"], 9)
        self.assertFalse(tracker.summary()["positionOrPathSafetyVerified"])
        with self.assertRaisesRegex(ValueError, "already completed"):
            tracker.observe(sample(120))

    def test_always_bright_does_not_falsely_claim_recovery(self):
        tracker = light.LightCycleTracker()
        for level in [90, 90, 90] + [92, 88, 90] * 15:
            tracker.observe(sample(level))
        self.assertEqual(tracker.summary()["status"], "watching-for-dim")
        self.assertFalse(tracker.summary()["dimSeen"])
        self.assertFalse(tracker.summary()["recoverySeen"])

    def test_strobe_single_dark_sample_is_not_dim_cycle(self):
        tracker = light.LightCycleTracker()
        for level in [100, 101, 100, 30, 100, 101, 99, 30, 101]:
            tracker.observe(sample(level))
        self.assertEqual(tracker.summary()["status"], "watching-for-dim")
        self.assertFalse(tracker.summary()["dimSeen"])

    def test_dark_on_entry_does_not_create_bright_baseline(self):
        tracker = light.LightCycleTracker()
        for level in [5, 6, 5, 20, 20, 20, 70, 71, 70]:
            tracker.observe(sample(level, .98 if level < 30 else .1))
        self.assertEqual(tracker.summary()["status"], "watching-for-dim")
        self.assertEqual(tracker.summary()["referenceMedianLuma"], 70.0)
        self.assertFalse(tracker.summary()["dimSeen"])

    def test_dark_recovery_needs_near_original_brightness_and_stability(self):
        tracker = light.LightCycleTracker()
        for level in [120, 120, 120, 50, 50]:
            tracker.observe(sample(level))
        for level in [85, 105, 130, 107, 100, 106, 105]:
            tracker.observe(sample(level))
        self.assertEqual(tracker.summary()["status"], "waiting-for-recovery")
        self.assertFalse(tracker.summary()["recoverySeen"])
        tracker.observe(sample(104))
        self.assertEqual(tracker.summary()["status"], "recovered-stable-light")

    def test_out_of_range_or_missing_metrics_fail_closed(self):
        for bad in ({"medianLuma": "90", "nearBlackFraction": .1},
                    sample(float("nan")), sample(20, 2), {}, None,
                    sample(True), sample(-1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                light.LightCycleTracker().observe(bad)

    def test_real_png_luminance_sampling_if_pillow_installed(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow optional for CI, required in real Windows observation")
        image = Image.new("RGB", (384, 240), (75, 75, 75))
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        result = light.sample_lighting(raw.getvalue())
        self.assertEqual(result["medianLuma"], 75)
        self.assertLess(result["nearBlackFraction"], .1)
        with self.assertRaises(ValueError):
            light.sample_lighting(b"non-png" * 40)


class FakeWorldGuard:
    instance = None

    def __init__(self, *, world_id, join_fingerprint, capture_stop_event):
        assert world_id == WORLD
        assert join_fingerprint == JOIN
        self.reason = None
        self.started = False
        self.closed = False
        FakeWorldGuard.instance = self

    def start(self):
        self.started = True
        return True

    def close(self):
        self.closed = True
        return {"status": "corroborated"}


class FakeEmergency:
    instance = None

    def __init__(self, capture_stop_event):
        self.reason = None
        self.started = False
        self.closed = False
        FakeEmergency.instance = self

    def start(self):
        self.started = True
        return True

    def close(self):
        self.closed = True
        return {"status": "clear"}


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "private"
        patches = [
            patch.object(probe, "OBSERVE_INTERVAL_SECONDS", 0),
            patch.object(probe.sys, "platform", "win32"),
            patch.object(probe, "corroborate_world", return_value={
                "status": "corroborated", "joinFingerprint": JOIN, "worldId": WORLD}),
            patch.object(probe, "get_window", return_value=(
                333, {"left": 0, "top": 0, "width": 640, "height": 480})),
            patch.object(probe, "is_active", return_value=True),
            patch.object(probe, "WorldSessionGuard", FakeWorldGuard),
            patch.object(probe, "EmergencyStop", FakeEmergency),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_dry_run_no_ui_network_or_screenshots(self):
        with (patch.object(probe, "run_live",
                           side_effect=AssertionError("No live observation")),
              patch.object(probe, "get_window",
                           side_effect=AssertionError("No window")),
              patch("builtins.print") as print_mock):
            code = probe.main(["--world-id", WORLD])
        self.assertEqual(code, 0)
        output = json.loads(print_mock.call_args.args[0])
        self.assertEqual(output["status"], "dry-run")
        self.assertEqual(output["oscCommandsSent"], 0)
        self.assertEqual(output["screenCaptures"], 0)
        self.assertFalse(self.destination.exists())

    def test_completed_light_cycle_saves_one_private_frame_without_osc(self):
        values = cycle_values()
        snapshots = iter([b"\x89PNG\r\n\x1a\n" + b"x" * 300] * len(values))
        with (
            patch.object(probe, "screenshot_png", side_effect=lambda *a: next(snapshots)) as frames,
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=12, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "recovered-stable-light-observed")
        self.assertEqual(result["screenshotsSaved"], 1)
        self.assertEqual(result["movementCommandsSent"], 0)
        self.assertFalse(result["autonomousMovementRestarted"])
        self.assertFalse(result["rankingEligible"])
        self.assertEqual(frames.call_count, len(values))
        self.assertTrue(FakeWorldGuard.instance.closed)
        self.assertTrue(FakeEmergency.instance.closed)
        path = Path(result["reportFile"])
        stored = json.loads(path.read_text())
        self.assertTrue(stored["lightingCycle"]["dimSeen"])
        self.assertTrue(stored["lightingCycle"]["recoverySeen"])
        self.assertFalse(stored["collisionSafetyVerified"])
        self.assertFalse(stored["independentPositionVerified"])
        self.assertFalse(stored["djBoothLocated"])
        self.assertFalse(stored["publiclyShareable"])
        self.assertFalse(stored["externalUploads"])
        self.assertEqual(len(stored["luminanceSamples"]), len(values))
        self.assertTrue(Path(result["recoveryImage"]).is_file())
        self.assertEqual(len(list(self.destination.rglob("recovery.png"))), 1)

    def test_stays_bright_without_fade_never_claims_recovery(self):
        values = [sample(100)] * 10
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\x89PNG\r\n\x1a\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "lighting-cycle-not-confirmed")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertIsNone(result["recoveryImage"])
        self.assertFalse(result["lightCycle"]["dimSeen"])
        self.assertFalse(list(self.destination.rglob("recovery.png")))


    def test_dark_club_two_bright_frames_save_one_opt_in_candidate(self):
        # No three stable bright frames: original lighting-cycle algorithm fails.
        levels = [8, 10, 60, 120, 10, 11, 50, 100, 11, 10]
        values = [sample(x, .3 if x >= 45 else .8) for x in levels]
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_brief_window=True)
        self.assertEqual(result["status"], "brief-brightness-opportunity-observed")
        self.assertEqual(result["lightCycle"]["status"], "calibrating")
        self.assertEqual(result["screenshotsSaved"], 1)
        self.assertIsNone(result["recoveryImage"])
        self.assertTrue(Path(result["brightWindowImage"]).is_file())
        self.assertEqual(len(list(self.destination.rglob("*.png"))), 1)
        self.assertEqual(result["briefBrightWindow"]["candidate"]["medianLuma"], 100)
        self.assertEqual(result["briefBrightWindow"]["candidate"]["brightRunSamples"], [7, 8])
        self.assertEqual(result["briefBrightWindow"]["candidate"]["brightRunLength"], 2)
        self.assertEqual(result["movementCommandsSent"], 0)
        self.assertFalse(result["autonomousMovementRestarted"])
        self.assertFalse(result["rankingEligible"])
        report = json.loads(Path(result["reportFile"]).read_text())
        self.assertFalse(report["screenshot"]["stableLightingRecoveryConfirmed"])
        self.assertTrue(report["screenshot"]["humanReviewRequired"])
        self.assertFalse(report["publiclyShareable"])
        self.assertFalse(report["djBoothLocated"])
        self.assertFalse(report["externalUploads"])

    def test_dark_club_without_opt_in_still_saves_no_image(self):
        levels = [8, 10, 60, 120, 10, 11, 50, 100, 11, 10]
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting",
                         side_effect=[sample(x) for x in levels]),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "lighting-cycle-not-confirmed")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertFalse(list(self.destination.rglob("*.png")))

    def test_isolated_strobes_and_near_black_overlay_do_not_save_candidate(self):
        levels = [10, 186, 10, 90, 10, 100, 10, 170, 10, 60]
        samples = [sample(x, .97 if x == 186 else .2) for x in levels]
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=samples),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_brief_window=True)
        self.assertEqual(result["status"], "lighting-cycle-not-confirmed")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertIsNone(result["brightWindowImage"])

    def test_late_world_change_discards_brief_candidate(self):
        original_close = FakeWorldGuard.close

        def changed(self):
            self.reason = "local-world-or-instance-changed"
            return original_close(self)

        values = [sample(x) for x in [10, 12, 60, 100, 10, 9, 70, 90, 10, 11]]
        with (
            patch.object(FakeWorldGuard, "close", changed),
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_brief_window=True)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertFalse(self.destination.exists())


    def test_uniform_black_capture_saves_one_review_image_only_when_opted_in(self):
        values = [sample(1, .9602)] * 10
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_dark_diagnostic=True)
        self.assertEqual(result["status"], "capture-visibility-needs-review")
        self.assertEqual(result["screenshotsSaved"], 1)
        self.assertEqual(result["captureVisibilityDiagnostic"]["status"],
                         "near-black-throughout")
        self.assertIsNone(result["recoveryImage"])
        self.assertIsNone(result["brightWindowImage"])
        self.assertTrue(Path(result["captureDiagnosticImage"]).is_file())
        self.assertEqual(len(list(self.destination.rglob("*.png"))), 1)
        self.assertEqual(result["movementCommandsSent"], 0)
        self.assertFalse(result["autonomousMovementRestarted"])
        self.assertFalse(result["rankingEligible"])
        stored = json.loads(Path(result["reportFile"]).read_text())
        self.assertEqual(stored["screenshot"]["file"],
                         "dark-capture-diagnostic.png")
        self.assertTrue(stored["screenshot"]["humanReviewRequired"])
        self.assertFalse(stored["screenshot"]["captureVisibilityVerified"])
        self.assertFalse(stored["publiclyShareable"])
        self.assertFalse(stored["externalUploads"])

    def test_dark_without_diagnostic_opt_in_remains_numeric_only(self):
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting",
                         side_effect=[sample(1, .9602)] * 10),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "lighting-cycle-not-confirmed")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertIsNone(result["captureDiagnosticImage"])
        self.assertFalse(list(self.destination.rglob("*.png")))

    def test_interleaved_bright_prevents_dark_diagnostic_image(self):
        values = [sample(1, .96)] * 4 + [sample(10, .80)] + [sample(1, .96)] * 5
        with (
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=values),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_dark_diagnostic=True)
        self.assertEqual(result["status"], "lighting-cycle-not-confirmed")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertIsNone(result["captureDiagnosticImage"])

    def test_world_change_blocks_dark_capture_file(self):
        original_close = FakeWorldGuard.close

        def changed(self):
            self.reason = "local-world-or-instance-changed"
            return original_close(self)

        with (
            patch.object(FakeWorldGuard, "close", changed),
            patch.object(probe, "screenshot_png",
                         return_value=b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200),
            patch.object(probe, "sample_lighting",
                         side_effect=[sample(1, .96)] * 10),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_dark_diagnostic=True)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertFalse(self.destination.exists())

    def test_session_change_at_final_check_discards_recovery_image(self):
        original_close = FakeWorldGuard.close

        def changed(self):
            self.reason = "local-world-or-instance-changed"
            return original_close(self)

        with (
            patch.object(FakeWorldGuard, "close", changed),
            patch.object(probe, "screenshot_png",
                         return_value=b"\x89PNG\r\n\x1a\n" + b"x" * 200),
            patch.object(probe, "sample_lighting", side_effect=cycle_values()),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=12, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "world-log-monitor-stopped")
        self.assertEqual(result["screenshotsSaved"], 0)
        self.assertFalse(self.destination.exists())


    def test_focused_window_geometry_refreshed_before_capture(self):
        initial = {"left": 0, "top": 0, "width": 640, "height": 480}
        final = {"left": 120, "top": 60, "width": 800, "height": 600}
        areas = []
        with (
            patch.object(probe, "get_window",
                         side_effect=[(333, initial), (333, final)]),
            patch.object(probe, "screenshot_png",
                         side_effect=lambda hwnd, area:
                         (areas.append(dict(area)) or
                          b"\\x89PNG\\r\\n\\x1a\\n" + b"x" * 200)),
            patch.object(probe, "sample_lighting",
                         side_effect=[sample(1, .96)] * 10),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_dark_diagnostic=True)
        self.assertEqual(result["status"], "capture-visibility-needs-review")
        self.assertEqual(result["captureRegion"], final)
        self.assertEqual(areas, [final] * 10)

    def test_window_swap_before_capture_discards_all_evidence(self):
        with (
            patch.object(probe, "get_window", side_effect=[
                (333, {"left": 0, "top": 0, "width": 640, "height": 480}),
                (444, {"left": 0, "top": 0, "width": 640, "height": 480})]),
            patch.object(probe, "screenshot_png",
                         side_effect=AssertionError("No capture after HWND change")),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0, capture_dark_diagnostic=True)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "world-window-changed-before-capture")
        self.assertFalse(self.destination.exists())

    def test_lost_foreground_before_observation_creates_no_files(self):
        with (
            patch.object(probe, "is_active", return_value=False),
            patch.object(probe, "screenshot_png",
                         side_effect=AssertionError("No screenshots without focus")),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "world-focus-or-emergency-stop")
        self.assertFalse(self.destination.exists())

    def test_bad_world_log_stops_before_window_lookup(self):
        with (
            patch.object(probe, "corroborate_world", return_value={"status": "expired"}),
            patch.object(probe, "get_window", side_effect=AssertionError("No lookup")),
        ):
            result = probe.run_live(
                world_id=WORLD, seconds=10, out_dir=self.destination,
                focus_seconds=0)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.destination.exists())

    def test_recovery_sequence_stops_on_focus_loss(self):
        values = cycle_values()
        safety_calls = 0

        def still_safe():
            nonlocal safety_calls
            safety_calls += 1
            return safety_calls < 7

        with (
            patch.object(probe, "sample_lighting", side_effect=values),
            self.assertRaisesRegex(probe.ObservationStopped, "focus"),
        ):
            probe.observe_cycle(
                capture_png=lambda: b"\x89PNG\r\n\x1a\n" + b"x" * 200,
                still_safe=still_safe, wait=lambda _: False, max_samples=15)

    def test_rights_and_limits_gate_before_live(self):
        flags = [
            "--confirm-private-instance", "--confirm-recording-rights",
            "--confirm-platform-authorization", "--acknowledge-automation-risk",
        ]
        for skip in flags:
            with (self.subTest(missing=skip),
                  patch.object(probe, "run_live",
                               side_effect=AssertionError("Cannot run without consent")),
                  self.assertRaises(SystemExit) as failure):
                probe.main(["--world-id", WORLD, "--live"] +
                           [f for f in flags if f != skip])
            self.assertEqual(failure.exception.code, 2)
        for seconds in (0, 9, 121, 10.5):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                probe.validate_request(WORLD, seconds, self.destination)
        with self.assertRaises(ValueError):
            probe.validate_request(WORLD, 10, probe.ROOT / "private-data")


if __name__ == "__main__":
    unittest.main()
