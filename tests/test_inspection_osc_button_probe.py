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
