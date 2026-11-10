"""Offline emergency hotkey tests: no real keyboard, VRChat or OSC calls."""
from __future__ import annotations

import json
import threading
import unittest
from unittest.mock import patch, MagicMock

from scripts import inspection_emergency_stop as hotkey


class EmergencyStopTests(unittest.TestCase):
    def test_offline_default_does_not_read_real_keyboard(self):
        with patch.object(hotkey.sys, "platform", "linux"):
            self.assertFalse(hotkey.windows_chord_pressed())

    def test_exact_three_key_chord_and_high_bit_are_required(self):
        windows = MagicMock()
        with (patch.object(hotkey.sys, "platform", "win32"),
              patch.object(hotkey.ctypes, "windll", windows, create=True)):
            for down in (
                set(),
                {hotkey.VK_F12},
                {hotkey.VK_SHIFT, hotkey.VK_F12},
                {hotkey.VK_CONTROL, hotkey.VK_SHIFT},
            ):
                with self.subTest(down=down):
                    windows.user32.GetAsyncKeyState.side_effect = (
                        lambda vk: 0x8001 if vk in down else 0x0001
                    )
                    self.assertFalse(hotkey.windows_chord_pressed())
            windows.user32.GetAsyncKeyState.side_effect = (
                lambda vk: 0x8000 if vk in {
                    hotkey.VK_CONTROL, hotkey.VK_SHIFT, hotkey.VK_F12
                } else 0
            )
            self.assertTrue(hotkey.windows_chord_pressed())

    def test_initial_pressed_hotkey_stops_before_recorder_start(self):
        event = threading.Event()
        monitor = hotkey.EmergencyStop(event, is_pressed=lambda: True)
        self.assertFalse(monitor.start())
        self.assertTrue(event.is_set())
        self.assertEqual(monitor.close()["reason"], "operator-emergency-hotkey")

    def test_hotkey_detected_while_running_stops_and_reports_redacted_status(self):
        event = threading.Event()
        checks = []
        def pressed():
            checks.append(1)
            return len(checks) >= 2
        monitor = hotkey.EmergencyStop(
            event, is_pressed=pressed, interval_seconds=0.01
        )
        self.assertTrue(monitor.start())
        self.assertTrue(event.wait(timeout=2))
        state = monitor.close()
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["chord"], "Ctrl+Shift+F12")
        self.assertEqual(state["reason"], "operator-emergency-hotkey")
        self.assertFalse(state["keyLogging"])
        self.assertGreaterEqual(state["checks"], 2)

    def test_monitor_error_trips_fail_closed_without_leaking_exception(self):
        event = threading.Event()
        def raise_private():
            raise RuntimeError("secret private key and username")
        monitor = hotkey.EmergencyStop(event, is_pressed=raise_private)
        self.assertFalse(monitor.start())
        self.assertTrue(event.is_set())
        self.assertEqual(monitor.close()["reason"], "hotkey-monitor-error")
        self.assertNotIn("secret", json.dumps(monitor.summary()))

    def test_safe_idle_close_and_idempotence(self):
        event = threading.Event()
        monitor = hotkey.EmergencyStop(
            event, is_pressed=lambda: False, interval_seconds=0.05
        )
        self.assertTrue(monitor.start())
        result = monitor.close()
        self.assertEqual(result, monitor.close())
        self.assertFalse(event.is_set())
        with self.assertRaises(RuntimeError):
            monitor.start()

    def test_poll_interval_cannot_be_disabled_or_unbounded(self):
        for value in (True, 0, -1, 0.001, 1.0, "0.1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hotkey.EmergencyStop(threading.Event(), interval_seconds=value)


if __name__ == "__main__":
    unittest.main()
