"""Offline regression tests; never launch VRChat, record the desktop or call Gemini."""
from __future__ import annotations

import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import windows_vrchat_inspector as m

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


class InspectionTests(unittest.TestCase):
    def test_model_actions_must_be_allowlisted(self):
        self.assertEqual(m.parse_decision({"action": "forward", "reason": "Door ahead"}), ("forward", "Door ahead"))
        for decision in (None, [], {"action": "open-url", "reason": "click"},
                         {"action": "/input/Jump", "reason": "go"},
                         {"action": "forward", "reason": ["wrong type"]}):
            with self.subTest(decision=decision), self.assertRaises(ValueError):
                m.parse_decision(decision)

    def test_osc_packet_only_local_input_axes_and_bounded_values(self):
        packet = m.osc_packet("/input/Vertical", 0.45)
        self.assertEqual(packet[:16], b"/input/Vertical\0")
        self.assertEqual(packet[16:20], b",f\0\0")
        self.assertAlmostEqual(struct.unpack(">f", packet[-4:])[0], .45, places=5)
        for path in ("/avatar/parameters/x", "/input/Jump", "/input/UseAxisRight", "/input/Vertical\0extra"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.osc_packet(path, 0.2)
        for value in (2, -2, True, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.osc_packet("/input/Vertical", value)

    def test_live_verified_right_turn_amplitude_is_bounded_and_released(self):
        # 0.80 Right LookHorizontal was confirmed by the Windows operator.
        # Never infer that the left-turn amplitude was also confirmed.
        self.assertEqual(m.OscMovement.AXES["turn_right"],
                         ("/input/LookHorizontal", 0.80))
        self.assertEqual(m.OscMovement.AXES["turn_left"],
                         ("/input/LookHorizontal", -0.35))
        with (patch.object(m.socket, "socket") as fake_socket,
              patch.object(m.time, "monotonic", side_effect=[0.0, 0.5])):
            controller = m.OscMovement()
            controller.act("turn_right", lambda: True, duration=0.4)
            calls = fake_socket.return_value.sendto.call_args_list
            self.assertTrue(all(c.args[1] == ("127.0.0.1", 9000) for c in calls))
            turning = [c.args[0] for c in calls
                       if c.args[0].startswith(b"/input/LookHorizontal\0")
                       and struct.unpack(">f", c.args[0][-4:])[0] > 0]
            self.assertEqual(len(turning), 1)
            self.assertAlmostEqual(struct.unpack(">f", turning[0][-4:])[0], .8, places=5)
            final = calls[-len(controller.ALL):]
            self.assertEqual(len(final), 3)
            self.assertTrue(all(struct.unpack(">f", c.args[0][-4:])[0] == 0 for c in final))
            controller.close()

    def test_right_turn_emergency_stop_also_releases_high_amplitude(self):
        stop = m.threading.Event()
        checks = []
        def still_safe():
            checks.append(1)
            if len(checks) >= 3:
                stop.set()
            return not stop.is_set()
        with patch.object(m.socket, "socket") as fake_socket:
            controller = m.OscMovement()
            with self.assertRaises(RuntimeError):
                controller.act("turn_right", still_safe, duration=0.4)
            packets = [c.args[0] for c in fake_socket.return_value.sendto.call_args_list]
            self.assertTrue(any(p.startswith(b"/input/LookHorizontal\0")
                                and abs(struct.unpack(">f", p[-4:])[0] - .8) < .00001
                                for p in packets))
            self.assertTrue(all(struct.unpack(">f", p[-4:])[0] == 0
                                for p in packets[-len(controller.ALL):]))
            controller.close()

    def test_actions_bounded_and_inert_default(self):
        self.assertEqual(m.clamp_duration("stop"), 0)
        self.assertLessEqual(m.clamp_duration("forward"), .65)
        for bad in ("interact", "jump", "teleport", "click", "open_url"):
            with self.assertRaises(ValueError):
                m.clamp_duration(bad)

    def test_movement_always_releases_axes_even_when_safety_fails(self):
        with patch.object(m.socket, "socket") as fake_socket:
            ctl = m.OscMovement()
            fake_socket.return_value.sendto.reset_mock()
            with self.assertRaises(RuntimeError):
                ctl.act("forward", lambda: False)
            packets = [a.args[0] for a in fake_socket.return_value.sendto.call_args_list]
            self.assertGreaterEqual(len(packets), 6)
            self.assertTrue(all(struct.unpack(">f", p[-4:])[0] == 0 for p in packets))
            self.assertTrue(packets[-1].startswith(b"/input/LookHorizontal\0"))
            self.assertEqual(struct.unpack(">f", packets[-1][-4:])[0], 0)
            hosts = [a.args[1] for a in fake_socket.return_value.sendto.call_args_list]
            self.assertEqual(set(hosts), {("127.0.0.1", 9000)})
            ctl.close()

    def test_emergency_stop_event_releases_active_osc_input(self):
        event = m.threading.Event()
        checks = []
        def still_safe():
            checks.append(1)
            if len(checks) >= 3:
                event.set()  # Pretend the Ctrl+Shift+F12 monitor tripped.
            return not event.is_set()
        with patch.object(m.socket, "socket") as fake_socket:
            ctl = m.OscMovement()
            fake_socket.return_value.sendto.reset_mock()
            with self.assertRaises(RuntimeError):
                ctl.act("forward", still_safe)
            packets = [call.args[0] for call in fake_socket.return_value.sendto.call_args_list]
            self.assertTrue(any(struct.unpack(">f", p[-4:])[0] > 0 for p in packets))
            tail = packets[-len(ctl.ALL):]
            self.assertEqual(len(tail), len(ctl.ALL))
            self.assertTrue(all(struct.unpack(">f", p[-4:])[0] == 0 for p in tail))
            self.assertEqual({c.args[1] for c in fake_socket.return_value.sendto.call_args_list},
                             {("127.0.0.1", 9000)})
            ctl.close()

    def test_h264_recorder_normalizes_odd_window_dimensions(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn("scale=trunc(iw/2)*2:trunc(ih/2)*2", source)

    def test_requires_private_instance_and_risk_ack_for_ai(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(m.os.environ, {"GEMINI_API_KEY": "test"}, clear=False):
            base = dict(world_id=WORLD, out_dir=Path(d), seconds=5, ai=True, evaluate=False,
                        confirm_private=True, accept_risk=False, confirm_upload=True,
                        model="gemini-3.5-flash-lite")
            with self.assertRaisesRegex(ValueError, "acknowledge risk"):
                m.inspect(**base)
            base["accept_risk"] = True
            base["confirm_upload"] = False
            with self.assertRaisesRegex(ValueError, "consent"):
                m.inspect(**base)
            base["confirm_private"] = False
            with self.assertRaisesRegex(ValueError, "private"):
                m.inspect(**base)
            base["confirm_private"] = True
            base["seconds"] = 121
            with self.assertRaisesRegex(ValueError, "120"):
                m.inspect(**base)

    def test_focus_handshake_is_bounded_before_start(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn("focus_deadline = time.monotonic() + 15", source)
        self.assertIn("if not is_active(hwnd):", source)

    def test_local_ai_inspection_generates_draft_without_ranking_changes(self):
        class FakeRecorder:
            FPS = 4
            def __init__(self, hwnd, area, output, ffmpeg):
                self.output = output
                self.stop_event = m.threading.Event()
                self.frames = 8
                self.failed = None
            def start(self):
                self.output.write_bytes(b"mock-opaque-local-clip")
            def close(self):
                pass

        class FakeController:
            def __init__(self):
                self.closed = False
            def neutral(self):
                pass
            def close(self):
                self.closed = True

        class FakeGuard:
            def decide(self, png, suggestion):
                return suggestion, "normal"
            def metrics(self):
                return {"observedFrames": 1, "recoveryTurns": 0}

        with tempfile.TemporaryDirectory() as d, patch.dict(m.os.environ, {"GEMINI_API_KEY": "test"}, clear=False):
            with (patch.object(m, "get_window", return_value=(1234, {"left": 0, "top": 0, "width": 640, "height": 480})),
                  patch.object(m, "is_active", return_value=True),
                  patch.object(m, "WindowRecorder", FakeRecorder),
                  patch.object(m, "OscMovement", FakeController),
                  patch.object(m, "NavigationGuard", FakeGuard),
                  patch.object(m, "screenshot_png", return_value=b"safe_mock"),
                  patch.object(m, "one_frame_low_light", return_value={
                      "status": "not-near-black", "visualNavigationShouldPause": False}),
                  patch.object(m, "choose_action", return_value=("stop", "End observation"))):
                report = m.inspect(world_id=WORLD, out_dir=Path(d), seconds=5,
                    ai=True, evaluate=False, confirm_private=True,
                    accept_risk=True, confirm_upload=True, model="gemini-3.5-flash-lite")
            self.assertFalse(report["rankingEligible"])
            self.assertFalse(report["equipmentFunctionalityVerified"])
            self.assertFalse(report["independentlyVerifiedDJPlayback"])
            self.assertEqual(report["actions"][0]["action"], "stop")
            records = list(Path(d).glob("*.inspection.json"))
            self.assertEqual(len(records), 1)
            written = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(written["mode"], "local_windows_ai_osc")
            self.assertEqual(len(list(Path(d).glob("*.mp4"))), 1)

    def test_local_world_guard_stop_disables_direct_gemini_and_releases_osc(self):
        class FakeRecorder:
            FPS = 4
            def __init__(self, hwnd, area, output, ffmpeg):
                self.output = output
                self.stop_event = m.threading.Event()
                self.frames = 30
                self.failed = None
            def start(self):
                self.output.write_bytes(b"synthetic-local-only-test")
                self.stop_event.set()
            def close(self):
                self.stop_event.set()

        class FakeController:
            closed = False
            def neutral(self):
                pass
            def close(self):
                self.closed = True

        class FakeWorldGuard:
            def __init__(self, **kwargs):
                self.reason = None
                self.stop = kwargs["capture_stop_event"]
            def start(self):
                return True
            def close(self):
                self.stop.set()
                self.reason = "local-world-or-instance-changed"
                return {"status": "stopped", "reason": self.reason, "checks": 2}

        class FakeNavigationGuard:
            def metrics(self):
                return {"observedFrames": 0, "recoveryTurns": 0}

        from scripts import evaluate_interior_video as evaluation
        with tempfile.TemporaryDirectory() as d, patch.dict(m.os.environ, {"GEMINI_API_KEY": "test"}):
            with (patch.object(m, "get_window", return_value=(123, {
                        "left": 0, "top": 0, "width": 640, "height": 480})),
                  patch.object(m, "is_active", return_value=True),
                  patch.object(m, "WindowRecorder", FakeRecorder),
                  patch.object(m, "WorldSessionGuard", FakeWorldGuard),
                  patch.object(m, "OscMovement", FakeController),
                  patch.object(m, "NavigationGuard", FakeNavigationGuard),
                  patch.object(evaluation, "ask_gemini",
                               side_effect=AssertionError("Gemini must not run after World guard stop"))):
                report = m.inspect(
                    world_id=WORLD, out_dir=Path(d), seconds=5,
                    ai=True, evaluate=True, confirm_private=True,
                    accept_risk=True, confirm_upload=True,
                    model="gemini-3.5-flash-lite",
                    expected_join_fingerprint="a" * 64)
            self.assertEqual(report["stopReason"], "world_log_guard_stopped")
            self.assertEqual(report["localWorldGuard"]["status"], "stopped")
            self.assertFalse(report["rankingEligible"])
            self.assertFalse(list(Path(d).glob("*.evaluation-draft.json")))

    def test_operator_emergency_hotkey_stops_capture_and_never_uploads(self):
        class FakeRecorder:
            FPS = 4
            def __init__(self, hwnd, area, output, ffmpeg):
                self.output = output
                self.stop_event = m.threading.Event()
                self.frames = 18
                self.failed = None
            def start(self):
                self.output.write_bytes(b"synthetic-clip-only")
            def close(self):
                self.stop_event.set()

        class FakeEmergencyStop:
            def __init__(self, stop_event):
                self.stop = stop_event
                self.reason = None
            def start(self):
                self.reason = "operator-emergency-hotkey"
                self.stop.set()
                return True
            def close(self):
                return {"status": "stopped", "reason": self.reason, "keyLogging": False}

        from scripts import evaluate_interior_video as evaluation
        with tempfile.TemporaryDirectory() as d, patch.dict(m.os.environ, {"GEMINI_API_KEY": "mock"}, clear=False):
            with (patch.object(m, "get_window", return_value=(123, {
                       "left": 0, "top": 0, "width": 640, "height": 480})),
                  patch.object(m, "is_active", return_value=True),
                  patch.object(m, "WindowRecorder", FakeRecorder),
                  patch.object(m, "EmergencyStop", FakeEmergencyStop),
                  patch.object(evaluation, "ask_gemini",
                               side_effect=AssertionError("Interrupted capture must not be uploaded"))):
                report = m.inspect(
                    world_id=WORLD, out_dir=Path(d), seconds=5, ai=False,
                    evaluate=True, confirm_private=True, accept_risk=False,
                    confirm_upload=True, model="gemini-3.5-flash-lite")
            self.assertEqual(report["stopReason"], "operator_emergency_stop")
            self.assertFalse(report["emergencyStop"]["keyLogging"])
            self.assertFalse(list(Path(d).glob("*.evaluation-draft.json")))

    def test_operator_hotkey_monitor_failure_blocks_capture_and_ai(self):
        class FakeRecorder:
            FPS = 4
            def __init__(self, hwnd, area, output, ffmpeg):
                self.stop_event = m.threading.Event()
                self.output = output
                self.frames = 0
                self.failed = None
            def start(self):
                raise AssertionError("Must not record with failed monitor")
            def close(self):
                pass

        class FakeEmergencyStop:
            def __init__(self, stop_event):
                self.reason = "hotkey-monitor-error"
                stop_event.set()
            def start(self):
                return False
            def close(self):
                return {"status": "stopped", "reason": self.reason}

        with tempfile.TemporaryDirectory() as d:
            with (patch.object(m, "get_window", return_value=(123, {
                       "left": 0, "top": 0, "width": 640, "height": 480})),
                  patch.object(m, "is_active", return_value=True),
                  patch.object(m, "WindowRecorder", FakeRecorder),
                  patch.object(m, "EmergencyStop", FakeEmergencyStop)):
                report = m.inspect(
                    world_id=WORLD, out_dir=Path(d), seconds=5, ai=False,
                    evaluate=False, confirm_private=True, accept_risk=False,
                    confirm_upload=False, model="gemini-3.5-flash-lite")
            self.assertEqual(report["stopReason"], "emergency_stop_monitor_failed")
            self.assertFalse(report["rankingEligible"])

    def test_direct_inspector_reports_nonzero_exit_for_operator_stop(self):
        example = {
            "stopReason": "operator_emergency_stop",
            "mode": "local_windows_capture_only",
            "recording": {"filename": "aborted.mp4", "frames": 18},
            "actions": [],
            "rankingEligible": False,
        }
        stdout = io.StringIO()
        with patch.object(m, "inspect", return_value=example), redirect_stdout(stdout):
            rc = m.main([
                "--world-id", WORLD, "--seconds", "5",
                "--private-instance-confirmed",
            ])
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "operator_emergency_stop")

    def test_direct_inspector_reports_zero_only_for_completed_capture(self):
        example = {
            "stopReason": "completed",
            "mode": "local_windows_capture_only",
            "recording": {"filename": "complete.mp4", "frames": 20},
            "actions": [],
            "rankingEligible": False,
        }
        with patch.object(m, "inspect", return_value=example), redirect_stdout(io.StringIO()):
            rc = m.main(["--world-id", WORLD, "--seconds", "5", "--private-instance-confirmed"])
        self.assertEqual(rc, 0)

    def test_source_never_launches_or_logs_in_or_uploads_automatically(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("vrchat.com/api", source)
        self.assertNotIn("OpenProcess(", source)
        self.assertNotIn("CreateRemoteThread(", source)
        self.assertNotIn("requests.post(", source)
        self.assertNotIn("subprocess.Popen(['VRChat", source)
        self.assertIn("127.0.0.1", source)
        self.assertIn("confirm_upload", source)
        self.assertIn("rankingEligible", source)


if __name__ == "__main__":
    unittest.main()
