#!/usr/bin/env python3
"""Fail-closed local VRChat World-log guard for an opted-in recording.

Only reads local client log metadata via inspection_world_log. The guard can
stop local capture, but cannot prove participant absence, live client state,
or authorization for unattended world travel.
"""
from __future__ import annotations

import re
import threading
from typing import Callable

try:
    from scripts.inspection_world_log import corroborate_world
except ModuleNotFoundError:
    from inspection_world_log import corroborate_world

FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}\Z")


class WorldSessionGuard:
    """Periodically compare the latest local join against the expected hash.

    An independent thread polls while capture is running, and immediately
    requests capture shutdown on mismatch. OSC controller actions already
    observe the capture's stop_event and neutralize movement axes.
    """

    def __init__(self, *, world_id: str, join_fingerprint: str,
                 capture_stop_event: threading.Event,
                 check_fn: Callable | None = None, interval_seconds: float = 1.0):
        if not isinstance(join_fingerprint, str) or not FINGERPRINT_RE.fullmatch(join_fingerprint):
            raise ValueError("Expected local join fingerprint must be a SHA-256 hex digest")
        if isinstance(interval_seconds, bool) or not 0.01 <= interval_seconds <= 5:
            raise ValueError("Log poll interval must be between 0.01 and 5 seconds")
        self.world_id = world_id
        self.join_fingerprint = join_fingerprint
        self.capture_stop_event = capture_stop_event
        self.check_fn = check_fn if check_fn is not None else corroborate_world
        self.interval_seconds = interval_seconds
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self.reason: str | None = None
        self.checks = 0
        self._closed = False

    def _fail(self, reason: str) -> None:
        # Only emit known fixed reason codes; never log raw client data.
        if self.reason is None:
            self.reason = reason
        self.capture_stop_event.set()

    def check(self) -> bool:
        if self.reason is not None:
            return False
        try:
            result = self.check_fn(self.world_id, max_age_seconds=900)
        except Exception:
            self._fail("local-log-read-error")
            return False
        self.checks += 1
        if not isinstance(result, dict) or result.get("status") != "corroborated":
            self._fail("local-log-unconfirmed")
            return False
        if (result.get("worldId") != self.world_id
                or result.get("joinFingerprint") != self.join_fingerprint):
            self._fail("local-world-or-instance-changed")
            return False
        return True

    def _watch(self) -> None:
        while not self._shutdown.wait(self.interval_seconds):
            if self.capture_stop_event.is_set():
                return
            if not self.check():
                return

    def start(self) -> bool:
        if self._thread is not None or self._closed:
            raise RuntimeError("World guard may only be started once")
        # Synchronous gate before any recorder/OSC action starts.
        if not self.check():
            return False
        self._thread = threading.Thread(
            target=self._watch, name="vcc-local-world-guard", daemon=True
        )
        self._thread.start()
        return True

    def close(self) -> dict:
        if self._closed:
            return self.summary()
        self._closed = True
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                self._fail("local-log-monitor-timeout")
        if self.reason is None:
            # A final check immediately after stopping the background loop.
            self.check()
        return self.summary()

    def summary(self) -> dict:
        return {
            "status": "stopped" if self.reason is not None else "corroborated",
            "reason": self.reason,
            "checks": self.checks,
            "logBasedOnly": True,
            "participantsIndependentlyVerified": False,
            "equipmentFunctionalityVerified": False,
        }
