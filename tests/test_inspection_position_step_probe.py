"""Offline-only tests for guarded VRChat single-position-step pilot."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import inspection_position_step_probe as probe


WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
FINGERPRINT = "a" * 64


class FakeWorldGuard:
    instance = None

    def __init__(self, *, world_id, join_fingerprint, capture_stop_event):
        assert world_id == WORLD
        assert join_fingerprint == FINGERPRINT
        self.stop_event = capture_stop_event
        self.reason = None
        self.starts = 0
        self.closes = 0
        FakeWorldGuard.instance = self

    def start(self):
        self.starts += 1
        return True

    def close(self):
        self.closes += 1
        return {"status": "corroborated"}


class FakeEmergency:
    instance = None

    def __init__(self, capture_stop_event):
        self.stop_event = capture_stop_event
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


class FakeController:
    instance = None

    def __init__(self):
        self.actions = []
        self.closed = False
        FakeController.instance = self

    def neutral(self):
        self.actions.append(("neutral", 0))

    def act(self, action, still_safe, duration=None):
        assert still_safe()
        assert action in probe.DIRECTIONS
        assert duration == probe.STEP_SECONDS
        self.actions.append((action, duration))
        # This fake does not implement a real UDP send. Production OscMovement
        # independently neutralizes its three axes within a finally block.

    def close(self):
        self.closed = True
        self.neutral()


class PositionStepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "private"
        self.patches = [
            patch.object(probe.sys, "platform", "win32"),
            patch.object(probe, "corroborate_world", return_value={
                "status": "corroborated", "worldId": WORLD,
                "joinFingerprint": FINGERPRINT}),
            patch.object(probe, "get_window", return_value=(
                123, {"left": 0, "top": 0, "width": 640, "height": 480})),
            patch.object(probe, "is_active", return_value=True),
            patch.object(probe, "WorldSessionGuard", FakeWorldGuard),
            patch.object(probe, "EmergencyStop", FakeEmergency),
            patch.object(probe, "OscMovement", FakeController),
            patch.object(probe, "screenshot_png", side_effect=[
                b"PRIVATE_BEFORE_FRAME_BYTES", b"PRIVATE_AFTER_FRAME_BYTES"]),
            patch.object(probe, "signature", side_effect=[
                (0,) * 16, (200,) * 16]),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_dry_run_never_probes_windows_or_network_or_stores_frames(self):
        with (patch.object(probe, "run_live", side_effect=AssertionError("Live called")),
              patch.object(probe, "corroborate_world", side_effect=AssertionError("log check")),
              patch("builtins.print") as printed):
            result = probe.main(["--world-id", WORLD])
        self.assertEqual(result, 0)
        report = json.loads(printed.call_args.args[0])
        self.assertEqual(report["status"], "dry-run")
        self.assertEqual(report["oscPacketsSent"], 0)
        self.assertEqual(report["framesRecorded"], 0)
        self.assertFalse(self.out.exists())

    def test_one_realistic_supervised_step_yields_two_local_frames(self):
        result = probe.run_live(
            world_id=WORLD, direction="forward", out_dir=self.out,
            focus_seconds=0)
        self.assertEqual(result["status"], "sent-unverified")
        self.assertEqual(result["stepsAttempted"], 1)
        self.assertTrue(result["visualChangeDetected"])
        self.assertFalse(result["positionVerified"])
        self.assertFalse(result["collisionSafetyVerified"])
        self.assertFalse(result["stairsTraversed"])
        self.assertFalse(result["djBoothLocated"])
        self.assertFalse(result["equipmentFunctionalityVerified"])
        self.assertTrue(result["noPublicRankingChanges"])
        self.assertEqual([x[0] for x in FakeController.instance.actions],
                         ["neutral", "forward", "neutral"])
        self.assertTrue(FakeController.instance.closed)
        self.assertEqual(FakeWorldGuard.instance.closes, 1)
        self.assertTrue(FakeEmergency.instance.closed)
        before, after = Path(result["before"]), Path(result["after"])
        self.assertEqual(before.read_bytes(), b"PRIVATE_BEFORE_FRAME_BYTES")
        self.assertEqual(after.read_bytes(), b"PRIVATE_AFTER_FRAME_BYTES")
        disk = json.loads(Path(result["reportFile"]).read_text(encoding="utf-8"))
        self.assertEqual(disk["source"], "local-osc-private-single-position-step")
        self.assertEqual(disk["frames"][0]["file"], "before.png")
        self.assertEqual(len(disk["frames"][0]["sha256"]), 64)
        self.assertNotIn("PRIVATE_BEFORE", json.dumps(disk))
        self.assertNotIn(str(self.out), json.dumps(disk))
        self.assertEqual(len(list(self.out.rglob("position-step.json"))), 1)

    def test_unfocused_vrchat_rejects_before_controller_or_screenshots(self):
        with (patch.object(probe, "is_active", return_value=False),
              patch.object(probe, "OscMovement",
                           side_effect=AssertionError("No controller")),
              patch.object(probe, "screenshot_png",
                           side_effect=AssertionError("No screenshot"))):
            result = probe.run_live(
                world_id=WORLD, direction="forward", out_dir=self.out,
                focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "vrchat-not-foreground")
        self.assertEqual(result["stepsAttempted"], 0)
        self.assertFalse(self.out.exists())
        self.assertEqual(FakeWorldGuard.instance.closes, 1)
        self.assertTrue(FakeEmergency.instance.closed)

    def test_uncorroborated_world_never_touches_window_or_controller(self):
        with (patch.object(probe, "corroborate_world", return_value={"status": "stale"}),
              patch.object(probe, "get_window", side_effect=AssertionError("No window"))):
            result = probe.run_live(
                world_id=WORLD, direction="forward", out_dir=self.out,
                focus_seconds=0)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stepsAttempted"], 0)
        self.assertFalse(self.out.exists())

    def test_missing_any_rights_gate_prevents_live_action(self):
        flags = [
            "--confirm-private-instance", "--confirm-recording-rights",
            "--confirm-flat-clear-path", "--confirm-platform-authorization",
            "--acknowledge-automation-risk",
        ]
        for flag in flags:
            with self.subTest(missing=flag), patch.object(
                probe, "run_live", side_effect=AssertionError("MUST NOT call live")
            ):
                with self.assertRaises(SystemExit) as caught:
                    probe.main(["--world-id", WORLD, "--live"] +
                               [f for f in flags if f != flag])
                self.assertEqual(caught.exception.code, 2)

    def test_missing_after_frame_neutralizes_and_does_not_store_evidence(self):
        with patch.object(probe, "screenshot_png", side_effect=[
            b"PRIVATE_BEFORE_FRAME_BYTES", ValueError("internal-screen-details")]):
            result = probe.run_live(
                world_id=WORLD, direction="forward", out_dir=self.out,
                focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "guarded-position-step-failed")
        self.assertEqual(result["stepsAttempted"], 1)
        self.assertTrue(FakeController.instance.closed)
        self.assertFalse(self.out.exists())
        self.assertNotIn("internal-screen-details", json.dumps(result))

    def test_world_guard_final_stop_overrides_success(self):
        original = FakeWorldGuard.close
        def changed(self):
            self.reason = "local-world-or-instance-changed"
            return original(self)
        with patch.object(FakeWorldGuard, "close", changed):
            result = probe.run_live(
                world_id=WORLD, direction="forward", out_dir=self.out,
                focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "world-log-monitor-stopped")
        self.assertFalse(self.out.exists())
        self.assertTrue(FakeController.instance.closed)

    def test_probe_only_allows_simple_locomotion_no_stairs_or_jumps(self):
        for unsafe in ("jump", "turn_right", "stair_climb", "go_to_player", "stop"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                probe.validate_request(WORLD, unsafe, self.out)
        for world in (WORLD.upper(), "junk", "wrld_bad"):
            with self.subTest(world=world), self.assertRaises(ValueError):
                probe.validate_request(world, "forward", self.out)
        with self.assertRaises(ValueError):
            probe.validate_request(WORLD, "forward", probe.ROOT / "screens")

    def test_core_rechecks_focus_before_movement_and_after_step(self):
        ctl = FakeController()
        samples = [b"before-private", b"after-private"]
        safe_states = iter([True, True, True, False])
        with self.assertRaisesRegex(probe.StepStopped, "unsafe-after-movement"):
            probe.execute_one_step(
                controller=ctl,
                capture_png=lambda: samples.pop(0),
                still_safe=lambda: next(safe_states),
                wait=lambda _: False, direction="forward")
        self.assertEqual(ctl.actions[0][0], "forward")
        self.assertEqual(samples, [b"after-private"])


if __name__ == "__main__":
    unittest.main()
