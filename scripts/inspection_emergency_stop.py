#!/usr/bin/env python3
"""Windows-only emergency stop for local, operator-supervised VRChat captures.

Hold Ctrl+Shift+F12 while the official client is foreground. This module
reads only those three key states; it never installs a hook, stores keystrokes,
sends input, uploads anything or touches the VRChat process.

The stop_event is shared with video capture and bounded OSC movement. Polling
is best effort and not a substitute for unplugging the controller or closing
the client in an emergency.
"""
from __future__ import annotations

import ctypes
import sys
import threading
from typing import Callable

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_F12 = 0x7B
MAX_POLL_INTERVAL_SECONDS = 0.5


def windows_chord_pressed() -> bool:
    """Poll a single explicit stop chord; no keyboard capture or global hook."""
    if sys.platform != "win32":
        return False
    get_state = ctypes.windll.user32.GetAsyncKeyState
    return all(get_state(vk) & 0x8000 for vk in (VK_CONTROL, VK_SHIFT, VK_F12))


class EmergencyStop:
    """Stop recorder/OSC when the operator presses the hotkey or polling fails."""

    def __init__(self, capture_stop_event: threading.Event, *,
                 is_pressed: Callable[[], bool] | None = None,
                 interval_seconds: float = 0.05):
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float)):
            raise ValueError("Invalid emergency stop polling interval")
        if not 0.01 <= interval_seconds <= MAX_POLL_INTERVAL_SECONDS:
            raise ValueError("Emergency stop polling interval out of bounds")
        self.capture_stop_event = capture_stop_event
        self.is_pressed = is_pressed if is_pressed is not None else windows_chord_pressed
        self.interval_seconds = interval_seconds
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._closed = False
        self.reason: str | None = None
        self.checks = 0

    def _trip(self, reason: str) -> None:
        # Never print exception text: it can include private window details.
        if self.reason is None:
            self.reason = reason
        self.capture_stop_event.set()

    def check(self) -> bool:
        if self.reason is not None:
            return False
        try:
            pressed = self.is_pressed()
        except Exception:
            self._trip("hotkey-monitor-error")
            return False
        self.checks += 1
        if pressed:
            self._trip("operator-emergency-hotkey")
            return False
        return True

    def _watch(self) -> None:
        while not self._shutdown.wait(self.interval_seconds):
            if self.capture_stop_event.is_set():
                return
            if not self.check():
                return

    def start(self) -> bool:
        if self._closed or self._thread is not None:
            raise RuntimeError("Emergency stop monitor may only start once")
        if not self.check():
            return False
        self._thread = threading.Thread(
            target=self._watch, name="vcc-operator-emergency-stop", daemon=True
        )
        self._thread.start()
        return True

    def close(self) -> dict:
        if self._closed:
            return self.summary()
        self._closed = True
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                self._trip("hotkey-monitor-timeout")
        return self.summary()

    def summary(self) -> dict:
        return {
            "status": "stopped" if self.reason is not None else "clear",
            "reason": self.reason,
            "checks": self.checks,
            "chord": "Ctrl+Shift+F12",
            "keyLogging": False,
        }
