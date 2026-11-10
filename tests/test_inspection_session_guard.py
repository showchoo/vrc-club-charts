"""Offline coverage for World log guard: never opens VRChat, OSC or files."""
from __future__ import annotations

import json
import threading
import unittest

from scripts.inspection_session_guard import WorldSessionGuard

A = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
B = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
HASH = "a" * 64
NEXT = "b" * 64


def same(world_id=A, digest=HASH):
    return {"status": "corroborated", "worldId": world_id, "joinFingerprint": digest}


class WorldSessionGuardTests(unittest.TestCase):
    def test_correct_world_is_checked_before_start_and_on_close(self):
        event = threading.Event()
        seen = []
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH, capture_stop_event=event,
            interval_seconds=5.0,
            check_fn=lambda world, **kwargs: seen.append((world, kwargs)) or same())
        self.assertTrue(guard.start())
        summary = guard.close()
        self.assertEqual(summary["status"], "corroborated")
        self.assertEqual(summary["checks"], 2)
        self.assertEqual([x[0] for x in seen], [A, A])
        self.assertFalse(event.is_set())
        self.assertFalse(summary["participantsIndependentlyVerified"])
        self.assertNotIn(HASH, json.dumps(summary))

    def test_initial_unconfirmed_event_prevents_capture(self):
        event = threading.Event()
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH, capture_stop_event=event,
            check_fn=lambda *a, **kw: {"status": "unconfirmed", "reason": "logs-unavailable"})
        self.assertFalse(guard.start())
        self.assertTrue(event.is_set())
        self.assertEqual(guard.close()["reason"], "local-log-unconfirmed")
        self.assertEqual(guard.checks, 1)

    def test_live_world_switch_signals_stop(self):
        event = threading.Event()
        calls = []
        def changing(world, **kwargs):
            calls.append(world)
            return same() if len(calls) == 1 else same(B, NEXT)
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH, capture_stop_event=event,
            check_fn=changing, interval_seconds=0.01)
        self.assertTrue(guard.start())
        self.assertTrue(event.wait(timeout=2.0))
        summary = guard.close()
        self.assertEqual(summary["reason"], "local-world-or-instance-changed")
        self.assertGreaterEqual(summary["checks"], 2)

    def test_final_check_catches_switch_before_periodic_tick(self):
        event = threading.Event()
        seen = []
        def changing(*args, **kwargs):
            seen.append(1)
            return same() if len(seen) == 1 else same(A, NEXT)
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH, capture_stop_event=event,
            check_fn=changing, interval_seconds=5.0)
        self.assertTrue(guard.start())
        result = guard.close()
        self.assertTrue(event.is_set())
        self.assertEqual(result["reason"], "local-world-or-instance-changed")

    def test_read_error_never_leaks_private_text(self):
        event = threading.Event()
        def failure(*args, **kwargs):
            raise RuntimeError("private username and password should not be printed")
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH, capture_stop_event=event,
            check_fn=failure)
        self.assertFalse(guard.start())
        summary = guard.close()
        self.assertTrue(event.is_set())
        self.assertEqual(summary["reason"], "local-log-read-error")
        self.assertNotIn("private username", json.dumps(summary))

    def test_invalid_or_wrong_world_fails_closed(self):
        for result in (None, {}, same(B), {"status": "corroborated", "worldId": A}):
            with self.subTest(result=result):
                event = threading.Event()
                guard = WorldSessionGuard(
                    world_id=A, join_fingerprint=HASH, capture_stop_event=event,
                    check_fn=lambda *a, **kw: result)
                self.assertFalse(guard.start())
                self.assertTrue(event.is_set())

    def test_invalid_fingerprint_and_interval_rejected(self):
        for bad in ("hi", "G" * 64, "", None):
            with self.subTest(fingerprint=bad), self.assertRaises(ValueError):
                WorldSessionGuard(world_id=A, join_fingerprint=bad,
                                  capture_stop_event=threading.Event())
        with self.assertRaises(ValueError):
            WorldSessionGuard(world_id=A, join_fingerprint=HASH,
                              capture_stop_event=threading.Event(),
                              interval_seconds=0)

    def test_close_is_idempotent_and_guard_cannot_restart(self):
        guard = WorldSessionGuard(
            world_id=A, join_fingerprint=HASH,
            capture_stop_event=threading.Event(),
            check_fn=lambda *a, **kw: same())
        self.assertTrue(guard.start())
        self.assertEqual(guard.close(), guard.close())
        with self.assertRaises(RuntimeError):
            guard.start()


if __name__ == "__main__":
    unittest.main()
