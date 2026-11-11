"""Cross-platform simulated Win32 HWND regression tests.

Never opens Windows, VRChat or OSC. Simulates >32-bit HWND values and
validates ctypes declares pointer-width WinAPI signatures before callbacks.
"""
from __future__ import annotations

from contextlib import redirect_stderr
import ctypes
from ctypes import wintypes
import io
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import windows_vrchat_inspector as inspector

LARGE_HWND = 0x1_0000_F00D
OTHER_HWND = 1234


class FakeFunction:
    def __init__(self, implementation):
        self.implementation = implementation
        self.argtypes = None
        self.restype = ctypes.c_int  # ctypes WinDLL's unsafe default
    def __call__(self, *args):
        return self.implementation(*args)


class FakeUser32:
    def __init__(self):
        self.foreground = LARGE_HWND
        self.raise_in_callback = False
        self.SetProcessDPIAware = FakeFunction(lambda: 1)
        self.EnumWindows = FakeFunction(self.enumerate)
        self.IsWindowVisible = FakeFunction(self.visible)
        self.GetWindowTextLengthW = FakeFunction(self.title_length)
        self.GetWindowTextW = FakeFunction(self.title)
        self.GetClientRect = FakeFunction(self.client_rect)
        self.ClientToScreen = FakeFunction(self.client_to_screen)
        self.GetForegroundWindow = FakeFunction(lambda: self.foreground)

    def enumerate(self, callback, context):
        self.last_callback = callback
        assert self.EnumWindows.argtypes[1] == wintypes.LPARAM
        for hwnd in (OTHER_HWND, LARGE_HWND):
            if not callback(hwnd, context):
                break
        return 1

    def visible(self, hwnd):
        # Regression for missing argtypes: WinDLL otherwise assumes c_int.
        if self.IsWindowVisible.argtypes != [wintypes.HWND] and hwnd > 0x7FFFFFFF:
            raise OverflowError("32-bit c_int would overflow for this HWND")
        if self.raise_in_callback:
            raise RuntimeError(r"SECRET: C:\Users\private_user")
        return 1

    def title_length(self, hwnd):
        return 6 if hwnd == LARGE_HWND else 5

    def title(self, hwnd, buffer, size):
        buffer.value = "VRChat" if hwnd == LARGE_HWND else "other"
        return len(buffer.value)

    def client_rect(self, hwnd, ptr):
        ptr._obj.left = 0
        ptr._obj.top = 0
        ptr._obj.right = 1578
        ptr._obj.bottom = 864
        return 1

    def client_to_screen(self, hwnd, ptr):
        ptr._obj.x = 10
        ptr._obj.y = 20
        return 1


class WindowHandleTests(unittest.TestCase):
    def run_simulated(self, fake, callable_fn):
        # WINFUNCTYPE and windll are only defined on Windows; CFUNCTYPE
        # simulates the same callback pointer-width semantics on CI/Linux.
        with (patch.object(inspector.sys, "platform", "win32"),
              patch.object(inspector.ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
              patch.object(inspector.ctypes, "windll",
                           SimpleNamespace(user32=fake), create=True)):
            return callable_fn()

    def test_high_bit_hwnd_enumeration_and_rect(self):
        fake = FakeUser32()
        actual = self.run_simulated(fake, lambda: inspector.get_window("VRChat"))
        self.assertEqual(actual, (LARGE_HWND, {
            "left": 10, "top": 20, "width": 1578, "height": 864,
        }))
        self.assertEqual(fake.IsWindowVisible.argtypes, [wintypes.HWND])
        self.assertEqual(fake.GetWindowTextLengthW.argtypes, [wintypes.HWND])
        self.assertEqual(fake.GetWindowTextW.argtypes,
                         [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int])
        self.assertEqual(fake.GetClientRect.argtypes,
                         [wintypes.HWND, ctypes.POINTER(wintypes.RECT)])
        self.assertEqual(fake.ClientToScreen.argtypes,
                         [wintypes.HWND, ctypes.POINTER(wintypes.POINT)])
        self.assertEqual(fake.GetForegroundWindow.restype, wintypes.HWND)

    def test_foreground_high_bit_handle_is_not_truncated(self):
        fake = FakeUser32()
        self.assertTrue(self.run_simulated(
            fake, lambda: inspector.is_active(LARGE_HWND)))
        self.assertEqual(fake.GetForegroundWindow.argtypes, [])
        self.assertEqual(fake.GetForegroundWindow.restype, wintypes.HWND)
        fake.foreground = OTHER_HWND
        self.assertFalse(self.run_simulated(
            fake, lambda: inspector.is_active(LARGE_HWND)))

    def test_callback_failure_exits_safely_without_leaking_window_data(self):
        fake = FakeUser32()
        fake.raise_in_callback = True
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaisesRegex(
                RuntimeError, "WinAPI callback"):
            self.run_simulated(fake, lambda: inspector.get_window("VRChat"))
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("private_user", stderr.getvalue())

    def test_wrong_title_and_non_windows_are_rejected(self):
        fake = FakeUser32()
        with self.assertRaises(ValueError):
            self.run_simulated(fake, lambda: inspector.get_window("Chrome"))
        self.assertFalse(inspector.is_active(0))
        self.assertFalse(inspector.is_active(-1))
        self.assertFalse(inspector.is_active(True))


if __name__ == "__main__":
    unittest.main()
