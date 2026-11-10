"""Synthetic client-log tests; no VRChat, network, account or real log access."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts import inspection_world_log as logs

A = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
B = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
NOW = datetime(2026, 11, 10, 22, 30, 0)


def log_line(offset: int, text: str) -> str:
    stamp = (NOW + timedelta(seconds=offset)).strftime("%Y.%m.%d %H:%M:%S")
    return f"{stamp} Debug - [Behaviour] {text}\n"


def join(world_id: str = A, *, private: bool = True, offset: int = -10) -> str:
    suffix = "~private(usr_00000000-0000-4000-8000-000000000000)" if private else "~region(jp)"
    return log_line(offset, f"Joining {world_id}:12345{suffix}")


def succeeded(offset: int = -9) -> str:
    return log_line(offset, "Successfully joined room")


class LogCorroborationTests(unittest.TestCase):
    def check(self, content: str, *, id: str = A, age: int = 180):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "output_log_2026-11-10_22-20-00.txt"
            file.write_text(content, encoding="utf-8")
            result = logs.corroborate_world(
                id, log_dir=Path(folder), max_age_seconds=age, now=NOW
            )
            return result

    def test_recent_private_success_matches_and_redacts_sensitive_lines(self):
        result = self.check(join() + succeeded())
        self.assertEqual(result["status"], "corroborated")
        self.assertEqual(result["worldId"], A)
        self.assertEqual(len(result["joinFingerprint"]), 64)
        self.assertFalse(result["participantsIndependentlyVerified"])
        self.assertFalse(result["instanceAccessIndependentlyVerified"])
        self.assertNotIn("usr_00000000", json.dumps(result))
        self.assertNotIn("output_log", json.dumps(result))

    def test_latest_join_wins_even_if_older_join_successful(self):
        result = self.check(join() + succeeded() + join(B, offset=-3) + succeeded(-2))
        self.assertEqual(result, {"status": "unconfirmed", "reason": "wrong-world"})

    def test_success_before_join_is_not_valid(self):
        result = self.check(succeeded(-15) + join())
        self.assertEqual(result["reason"], "join-not-confirmed")

    def test_public_instance_rejected(self):
        result = self.check(join(private=False) + succeeded())
        self.assertEqual(result["reason"], "not-private-instance")

    def test_room_leave_after_success_rejected(self):
        result = self.check(join() + succeeded() + log_line(-1, "Leaving Room"))
        self.assertEqual(result["reason"], "left-room")

    def test_stale_join_and_future_join_rejected(self):
        self.assertEqual(self.check(join(offset=-600) + succeeded(-599))["reason"], "join-too-old")
        self.assertEqual(self.check(join(offset=20) + succeeded(21))["reason"], "join-in-future")

    def test_unsupported_join_format_invalidates_previous_result(self):
        result = self.check(join() + succeeded() + log_line(-2, "Joining wrld_something_unrecognized"))
        self.assertEqual(result["reason"], "join-not-found")

    def test_unreadable_and_missing_logs_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = logs.corroborate_world(A, log_dir=Path(folder), now=NOW)
            self.assertEqual(result["reason"], "logs-unavailable")

    def test_newest_file_is_used_and_not_older_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "output_log_2026-11-09_10-00-00.txt"
            new = root / "output_log_2026-11-10_22-20-00.txt"
            old.write_text(join() + succeeded())
            new.write_text(join(B) + succeeded())
            os.utime(old, (100, 100))
            os.utime(new, (200, 200))
            self.assertEqual(logs.corroborate_world(A, log_dir=root, now=NOW)["reason"], "wrong-world")

    def test_after_join_same_signature_changes_on_new_instance(self):
        first = self.check(join() + succeeded())
        second = self.check(join(offset=-5) + succeeded(-4))
        self.assertNotEqual(first["joinFingerprint"], second["joinFingerprint"])

    def test_tail_read_drops_partial_first_line(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "output_log_2026-11-10_22-20-00.txt"
            file.write_bytes(b"LONG PRIVATE START" + b"x" * 1600 + b"\n" + (join() + succeeded()).encode())
            tail = logs.read_log_tail(file, maximum=1024)
            self.assertTrue(tail.startswith(join().strip()))
            self.assertNotIn("LONG PRIVATE", tail)

    def test_validates_world_id_and_time_window(self):
        with self.assertRaises(ValueError):
            logs.corroborate_world(A + "&instance=foo", now=NOW)
        with self.assertRaises(ValueError):
            logs.corroborate_world(A, max_age_seconds=10000, now=NOW)


if __name__ == "__main__":
    unittest.main()
