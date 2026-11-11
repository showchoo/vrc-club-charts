"""No live client, network, recorder or GPU is used by these tests."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import inspection_sweep as sweep
from scripts import windows_vrchat_inspector as windows
from scripts import run_one_world_inspection as pipeline

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


class FakeController:
    def __init__(self):
        self.actions = []
        self.closed = False

    def neutral(self):
        self.actions.append(("neutral", 0.0))

    def act(self, action, still_safe, duration=None):
        if not still_safe():
            raise RuntimeError("Lost focus")
        self.actions.append((action, duration))

    def close(self):
        self.closed = True
        self.neutral()


class BoundedSweepTests(unittest.TestCase):
    def test_plan_is_short_and_deterministic(self):
        self.assertEqual(
            sweep.sweep_plan(2),
            ("observe", "turn_right", "observe", "turn_right", "observe"))
        self.assertEqual(sweep.sweep_plan().count("turn_right"), 4)
        for turns in (0, -1, 5, 1.5, True, None):
            with self.subTest(turns=turns), self.assertRaises(ValueError):
                sweep.sweep_plan(turns)

    def run_sweep(self, samples, **kwargs):
        controller = FakeController()
        records = []
        obs = iter(samples)
        with patch.object(sweep, "signature", side_effect=lambda value: (value[0],) * 9):
            report = sweep.run_sweep(
                controller=controller, capture_png=lambda: next(obs),
                still_safe=kwargs.get("safe", lambda: True),
                seconds_left=kwargs.get("remaining", lambda: 60),
                log_action=records.append, turns=kwargs.get("turns", 3))
        return report, controller, records

    def test_changed_views_complete_four_bounded_turns(self):
        report, ctl, records = self.run_sweep(
            [bytes([10]), bytes([60]), bytes([100]), bytes([160]), bytes([220])], turns=4)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["executedTurns"], 4)
        self.assertEqual(report["observations"], 5)
        self.assertEqual(report["viewChangesObserved"], 4)
        self.assertEqual(sum(a == "turn_right" for a, _ in ctl.actions), 4)
        self.assertEqual(sum(a == "observe" for a, _ in ctl.actions), 5)
        self.assertTrue(all(seconds <= .5 for _, seconds in ctl.actions))
        self.assertEqual(len(records), 9)
        for field in ("reliablePositionOrCoverageVerified",
                      "peopleAbsentIndependentlyVerified",
                      "djEquipmentFunctionalityVerified"):
            self.assertFalse(report[field])

    def test_unchanged_view_stops_after_two_turns(self):
        report, ctl, records = self.run_sweep(
            [bytes([10]), bytes([10]), bytes([10]), bytes([100])], turns=4)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["reason"], "no_visible_change_after_two_turns")
        self.assertEqual(report["executedTurns"], 2)
        self.assertEqual(report["observations"], 3)
        self.assertEqual(records[-1]["action"], "stop")

    def test_dark_real_png_signature_stops_before_any_camera_turn(self):
        original = b"\x89PNG\r\n\x1a\nsynthetic-content"
        ctl, logs = FakeController(), []
        with patch.object(sweep, "one_frame_low_light", return_value={
            "status": "low-visibility", "visualNavigationShouldPause": True
        }):
            result = sweep.run_sweep(
                controller=ctl, capture_png=lambda: original,
                still_safe=lambda: True, seconds_left=lambda: 40,
                log_action=logs.append, turns=4)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "low_visibility_or_invalid_image")
        self.assertEqual(result["executedTurns"], 0)
        self.assertEqual(ctl.actions, [])
        self.assertEqual(logs[-1]["safetyDecision"], "low_visibility_or_invalid_image")

    def test_lighting_transition_stops_before_second_turn(self):
        samples = iter([
            b"\x89PNG\r\n\x1a\nbefore",
            b"\x89PNG\r\n\x1a\nafter",
        ])
        controller, logs = FakeController(), []
        with (
            patch.object(sweep, "one_frame_low_light", return_value={
                "status": "not-near-black", "visualNavigationShouldPause": False
            }),
            patch.object(sweep, "analyze_png_pair", return_value={
                "status": "suspected-lighting-transition",
                "visualNavigationShouldPause": True,
            }),
            patch.object(sweep, "signature", side_effect=[(80,)*9, (120,)*9]),
        ):
            result = sweep.run_sweep(
                controller=controller, capture_png=lambda: next(samples),
                still_safe=lambda: True, seconds_left=lambda: 40,
                log_action=logs.append, turns=4)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "lighting_transition_or_low_visibility")
        self.assertEqual(result["executedTurns"], 1)
        self.assertEqual(sum(action == "turn_right" for action, _ in controller.actions), 1)
        self.assertEqual(logs[-1]["action"], "stop")
        self.assertEqual(result["viewChangesObserved"], 0)

    def test_focus_loss_never_sends_an_action(self):
        report, ctl, records = self.run_sweep([], safe=lambda: False)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(ctl.actions, [])
        self.assertEqual(records, [])

    def test_time_budget_stops_before_any_action(self):
        report, ctl, records = self.run_sweep([], remaining=lambda: 0.8)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["reason"], "recording_time_exhausted")
        self.assertEqual(ctl.actions, [])

    def test_sweep_requires_explicit_authorization_before_windows_access(self):
        kwargs = dict(
            world_id=WORLD, out_dir=Path(tempfile.gettempdir()), seconds=15,
            ai=False, sweep=True, evaluate=False, confirm_private=True,
            accept_risk=True, confirm_upload=False, model="test",
        )
        with patch.object(windows, "get_window",
                          side_effect=AssertionError("client unexpectedly accessed")):
            with self.assertRaisesRegex(ValueError, "platform authorization"):
                windows.inspect(**kwargs)
            kwargs["platform_authorization_confirmed"] = True
            kwargs["accept_risk"] = False
            with self.assertRaisesRegex(ValueError, "operator acknowledgement"):
                windows.inspect(**kwargs)
            kwargs["accept_risk"] = True
            kwargs["ai"] = True
            with self.assertRaisesRegex(ValueError, "either AI motion"):
                windows.inspect(**kwargs)

    def test_explicit_sweep_run_needs_no_cloud_key(self):
        class FakeRecorder:
            FPS = 4
            instance = None
            def __init__(self, hwnd, area, output, ffmpeg):
                FakeRecorder.instance = self
                self.output = output
                self.stop_event = threading.Event()
                self.frames = 22
                self.failed = None
            def start(self):
                self.output.write_bytes(b"local-fake-capture-for-test")
            def close(self):
                pass

        ctl = FakeController()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(windows, "get_window", return_value=(
                    1234, {"left": 0, "top": 0, "width": 640, "height": 480})),
                patch.object(windows, "is_active", return_value=True),
                patch.object(windows, "WindowRecorder", FakeRecorder),
                patch.object(windows, "OscMovement", return_value=ctl),
                patch.object(windows, "screenshot_png", return_value=b"synthetic"),
                patch.object(windows, "run_sweep") as fake_sweep,
                patch.dict(windows.os.environ, {"GEMINI_API_KEY": ""}),
                patch.object(windows, "choose_action",
                             side_effect=AssertionError("Cloud model called")),
            ):
                def finished(**kwargs):
                    kwargs["log_action"]({"action": "observe", "safetyDecision": "test"})
                    FakeRecorder.instance.stop_event.set()
                    return {"status": "completed", "reason": "bounded_sequence_finished",
                            "reliablePositionOrCoverageVerified": False}
                fake_sweep.side_effect = finished
                report = windows.inspect(
                    world_id=WORLD, out_dir=Path(directory), seconds=15,
                    ai=False, sweep=True, evaluate=False, confirm_private=True,
                    accept_risk=True, confirm_upload=False, model="test",
                    platform_authorization_confirmed=True,
                )
                self.assertTrue(fake_sweep.called)
            self.assertEqual(report["mode"], "local_windows_bounded_sweep")
            self.assertEqual(report["sweep"]["status"], "completed")
            self.assertFalse(report["rankingEligible"])
            self.assertFalse(report["equipmentFunctionalityVerified"])
            self.assertTrue(ctl.closed)
            self.assertEqual(len(list(Path(directory).glob("*.inspection.json"))), 1)
            disk=json.loads(next(Path(directory).glob("*.inspection.json")).read_text())
            self.assertEqual(disk["mode"], "local_windows_bounded_sweep")

    def test_incomplete_sweep_prevents_cloud_analysis_or_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            opts = dict(world_id=WORLD, captures=Path(directory), seconds=15,
                        sweep_motion=True, private_confirmed=True,
                        automation_risk_confirmed=True,
                        platform_authorization_confirmed=True,
                        analyze_video=True, recording_rights_confirmed=True,
                        gemini_upload_confirmed=True)
            def incomplete(**kwargs):
                return {
                    "worldId": WORLD,
                    "sweep": {"status": "stopped", "reason": "no_visible_change_after_two_turns"},
                    "recording": {"filename": "mock.mp4", "frames": 40, "bytes": 3000}
                }
            with (
                patch.object(pipeline, "preflight", return_value={"ready": True}),
                patch.object(pipeline, "inspect", side_effect=incomplete),
                patch.object(pipeline, "process_queue",
                             side_effect=AssertionError("Cloud upload attempted")),
                patch.object(pipeline, "release",
                             side_effect=AssertionError("Publication attempted")),
            ):
                result = pipeline.run_inspection(**opts)
            self.assertEqual(result["status"], "capture-incomplete")
            self.assertFalse(result["rankingsChanged"])

    def test_missing_authorization_rejected_before_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pipeline, "preflight",
                              side_effect=AssertionError("Preflight invoked early")):
                with self.assertRaisesRegex(ValueError, "platform authorization"):
                    pipeline.run_inspection(
                        world_id=WORLD, captures=Path(directory),
                        sweep_motion=True, private_confirmed=True,
                        automation_risk_confirmed=True)


if __name__ == "__main__":
    unittest.main()
