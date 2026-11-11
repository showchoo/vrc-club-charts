"""Offline tests for local-only OSC LookRight diagnostic and safe button release."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import itertools
import json
import struct
import unittest
from unittest.mock import Mock, patch

from scripts import inspection_osc_button_probe as p

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"


class FakeWorldGuard:
    reason = None
    instances = []
    def __init__(self, **kwargs):
        self.stop = kwargs["capture_stop_event"]
        FakeWorldGuard.instances.append(self)
    def start(self):
        return True
    def close(self):
        return {"status": "corroborated"}


class FakeHotkey:
    reason = None
    def __init__(self, stop_event):
        self.stop = stop_event
    def start(self):
        return True
    def close(self):
        return {"status": "clear"}


class ButtonProbeTests(unittest.TestCase):
    def test_only_button_integer_packets_are_emitted(self):
        pressed = p.look_right_packet(1)
        released = p.look_right_packet(0)
        self.assertTrue(pressed.startswith(b"/input/LookRight\0"))
        self.assertIn(b",i\0\0", pressed)
        self.assertEqual(struct.unpack(">i", pressed[-4:]), (1,))
        self.assertEqual(struct.unpack(">i", released[-4:]), (0,))
        for wrong in (-1, 2, True, 1.0, "1", None):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                p.look_right_packet(wrong)

    def test_analog_packet_uses_full_bounded_axis_and_zero_release(self):
        packet = p.look_horizontal_probe_packet(True)
        released = p.look_horizontal_probe_packet(False)
        self.assertTrue(packet.startswith(b"/input/LookHorizontal\0"))
        self.assertEqual(struct.unpack(">f", packet[-4:])[0],
                         struct.unpack(">f", p.osc_packet("/input/LookHorizontal", 0.80)[-4:])[0])
        self.assertEqual(struct.unpack(">f", released[-4:])[0], 0.0)
        self.assertEqual(p.ANALOG_PULSES, 2)
        self.assertLessEqual(p.ANALOG_HOLD_SECONDS, 0.5)
        for bad in (1, 0, "True", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.look_horizontal_probe_packet(bad)

    def test_analog_dry_run_is_inert_and_exposes_test_value(self):
        output = io.StringIO()
        with (patch.object(p, "run_probe", side_effect=AssertionError("No live probe")),
              redirect_stdout(output)):
            code = p.main(["--world-id", WORLD, "--mode", "analog"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "dry-run")
        self.assertEqual(result["mode"], "analog")
        self.assertEqual(result["wouldSend"], "/input/LookHorizontal")
        self.assertEqual(result["value"], 0.8)
        self.assertFalse(result["recordedOrUploaded"])

    def test_analog_live_probe_sends_two_short_pulses_and_three_zeroes(self):
        sock = Mock()
        clock = itertools.count()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=True),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              patch.object(p.time, "monotonic", side_effect=lambda: next(clock)),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0, mode="analog")
        self.assertEqual(result["status"], "sent-unverified")
        self.assertEqual(result["mode"], "analog")
        self.assertEqual(result["oscAddress"], "/input/LookHorizontal")
        self.assertEqual(result["pulsesSent"], 2)
        self.assertFalse(result["cameraMotionVerified"])
        packets = [c.args[0] for c in sock.sendto.call_args_list]
        self.assertEqual(len(packets), 5)
        values = [round(struct.unpack(">f", x[-4:])[0], 2) for x in packets]
        self.assertEqual(values, [0.8, 0.0, 0.8, 0.0, 0.0])
        self.assertEqual({c.args[1] for c in sock.sendto.call_args_list},
                         {("127.0.0.1", 9000)})
        sock.close.assert_called_once()

    def test_analog_focus_loss_prevents_turning(self):
        sock = Mock()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=False),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0, mode="analog")
        self.assertEqual(result["status"], "stopped")
        sock.sendto.assert_not_called()

    def test_quick_menu_packet_only_int_1_and_0(self):
        pressed = p.quick_menu_packet(1)
        released = p.quick_menu_packet(0)
        self.assertTrue(pressed.startswith(b"/input/QuickMenuToggleRight\0"))
        self.assertIn(b",i\0\0", pressed)
        self.assertEqual(struct.unpack(">i", pressed[-4:])[0], 1)
        self.assertEqual(struct.unpack(">i", released[-4:])[0], 0)
        self.assertEqual(p.UI_HOLD_SECONDS, 0.12)
        for wrong in (True, False, -1, 2, 1.0, "1"):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                p.quick_menu_packet(wrong)

    def test_quick_menu_default_dry_run_does_not_access_client(self):
        output = io.StringIO()
        with (patch.object(p, "run_probe", side_effect=AssertionError("No live OSC")),
              redirect_stdout(output)):
            code = p.main(["--world-id", WORLD, "--mode", "ui"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "dry-run")
        self.assertEqual(report["wouldSend"], "/input/QuickMenuToggleRight")
        self.assertEqual(report["pulses"], 1)
        self.assertFalse(report["recordedOrUploaded"])

    def test_quick_menu_live_sends_single_press_and_releases_even_on_cleanup(self):
        sock = Mock()
        clock = itertools.count()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=True),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              patch.object(p.time, "monotonic", side_effect=lambda: next(clock)),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0, mode="ui")
        self.assertEqual(result["status"], "sent-unverified")
        self.assertEqual(result["pulsesSent"], 1)
        self.assertEqual(result["mode"], "ui")
        self.assertEqual(result["oscAddress"], "/input/QuickMenuToggleRight")
        self.assertFalse(result["cameraMotionVerified"])
        packets = [call.args[0] for call in sock.sendto.call_args_list]
        self.assertEqual([struct.unpack(">i", q[-4:])[0] for q in packets], [1, 0, 0])
        self.assertTrue(all(q.startswith(b"/input/QuickMenuToggleRight\0") for q in packets))
        self.assertEqual({call.args[1] for call in sock.sendto.call_args_list},
                         {("127.0.0.1", 9000)})
        sock.close.assert_called_once()

    def test_quick_menu_focus_loss_blocks_all_live_input(self):
        sock = Mock()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=False),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0, mode="ui")
        self.assertEqual(result["status"], "stopped")
        sock.sendto.assert_not_called()

    def test_default_cli_never_contacts_client_or_sends_osc(self):
        output = io.StringIO()
        with (patch.object(p, "run_probe", side_effect=AssertionError("Must be inert")),
              redirect_stdout(output)):
            result = p.main(["--world-id", WORLD])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "dry-run")

    def test_live_cli_requires_all_user_acknowledgements(self):
        with self.assertRaises(SystemExit) as outcome:
            p.main(["--world-id", WORLD, "--live"])
        self.assertEqual(outcome.exception.code, 2)

    def test_wrong_log_blocks_before_any_socket_or_window_access(self):
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "unconfirmed", "reason": "wrong-world"}),
              patch.object(p, "get_window", side_effect=AssertionError("No window access")),
              patch.object(p.socket, "socket", side_effect=AssertionError("No packets"))):
            result = p.run_probe(WORLD, focus_seconds=0)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["pulsesSent"], 0)

    def test_live_probe_releases_lookright_after_every_pulse(self):
        sock = Mock()
        clock = itertools.count()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=True),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              patch.object(p.time, "monotonic", side_effect=lambda: next(clock)),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0)
        self.assertEqual(result["status"], "sent-unverified")
        self.assertEqual(result["pulsesSent"], 3)
        self.assertFalse(result["cameraMotionVerified"])
        self.assertFalse(result["oscDeliveryAcknowledged"])
        packets = [c.args[0] for c in sock.sendto.call_args_list]
        self.assertEqual([struct.unpack(">i", x[-4:])[0] for x in packets],
                         [1, 0, 1, 0, 1, 0, 0])
        self.assertEqual({c.args[1] for c in sock.sendto.call_args_list},
                         {("127.0.0.1", 9000)})
        sock.close.assert_called_once()

    def test_window_unfocused_prevents_nonzero_packets(self):
        sock = Mock()
        with (patch.object(p.sys, "platform", "win32"),
              patch.object(p, "corroborate_world", return_value={
                  "status": "corroborated", "worldId": WORLD,
                  "joinFingerprint": "a" * 64}),
              patch.object(p, "get_window", return_value=(42, {})),
              patch.object(p, "is_active", return_value=False),
              patch.object(p, "WorldSessionGuard", FakeWorldGuard),
              patch.object(p, "EmergencyStop", FakeHotkey),
              patch.object(p.socket, "socket", return_value=sock),
              redirect_stdout(io.StringIO())):
            result = p.run_probe(WORLD, focus_seconds=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "vrchat-not-foreground")
        sock.sendto.assert_not_called()

    def test_invalid_world_and_non_windows_cannot_probe(self):
        with patch.object(p.sys, "platform", "linux"):
            with self.assertRaisesRegex(ValueError, "windows-required"):
                p.run_probe(WORLD, focus_seconds=0)
        with patch.object(p.sys, "platform", "win32"):
            with self.assertRaisesRegex(ValueError, "invalid-world-id"):
                p.run_probe("private_instance_secret", focus_seconds=0)


if __name__ == "__main__":
    unittest.main()
