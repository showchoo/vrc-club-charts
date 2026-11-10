"""Offline safety-integration drills for a resumable VRChat inspection batch.

Covers successful synthetic captures, operator abort, a changed World-log
result, exceptions, missing/tampered MP4s, and read-only audit. Does not
start the client, capture a window, send OSC, upload or call cloud models.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts import inspection_queue as q

A = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
B = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"


def plan():
    return {"schemaVersion": 1, "worlds": [
        {"worldId": A, "name": "Private synthetic DJ World A"},
        {"worldId": B, "name": "Private synthetic DJ World B"},
    ]}


def synthetic_recording(**kwargs):
    world = kwargs["world_id"]
    name = world + "_20261111T120000Z.mp4"
    (kwargs["captures"] / name).write_bytes(b"synthetic clip without any recorded people: " + world.encode())
    return {"worldId": world, "status": "capture-complete",
            "captureStopReason": "completed", "recording": name}


class QueueIntegrityAndAbortDrills(unittest.TestCase):
    def run_success(self, folder):
        with contextlib.redirect_stdout(io.StringIO()):
            output = q.run_queue(
                plan(), capture_dir=Path(folder),
                inspection_fn=synthetic_recording,
                input_fn=lambda message: A if A in message else B,
            )
        self.assertEqual(output["status"], "completed")
        return output

    def test_successful_batch_records_and_audits_two_local_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_success(folder)
            result = q.audit_queue(plan(), capture_dir=Path(folder))
            self.assertEqual(result, {
                "status": "ok", "auditedCompleted": 2, "problems": [],
            })
            state = json.loads((Path(folder) / "inspection-queue-state.json").read_text())
            self.assertEqual(len(state["worlds"][A]["captureIntegrity"]["sha256"]), 64)
            self.assertNotIn("Private synthetic", json.dumps(state))

    def test_tampered_recording_blocks_next_run_before_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_success(folder)
            clip = Path(folder) / (A + "_20261111T120000Z.mp4")
            clip.write_bytes(b"tampered-but-not-empty")
            audit = q.audit_queue(plan(), capture_dir=Path(folder))
            self.assertEqual(audit["status"], "blocked")
            self.assertEqual(audit["problems"], [
                {"worldId": A, "reason": "capture-digest-mismatch"},
            ])
            result = q.run_queue(
                plan(), capture_dir=Path(folder),
                inspection_fn=lambda **kw: self.fail("No re-recording allowed"),
                input_fn=lambda _: self.fail("Must stop before prompt"),
            )
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "capture-digest-mismatch")
            self.assertEqual(result["worldId"], A)

    def test_deleted_recording_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_success(folder)
            (Path(folder) / (B + "_20261111T120000Z.mp4")).unlink()
            audit = q.audit_queue(plan(), capture_dir=Path(folder))
            self.assertEqual(audit["status"], "blocked")
            self.assertEqual(audit["auditedCompleted"], 1)
            self.assertEqual(audit["problems"][0]["reason"], "capture-missing-or-empty")

    def test_legacy_completed_without_hash_must_not_be_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_success(folder)
            state_path = Path(folder) / "inspection-queue-state.json"
            state = json.loads(state_path.read_text())
            state["worlds"][A].pop("captureIntegrity")
            state_path.write_text(json.dumps(state), encoding="utf-8")
            audit = q.audit_queue(plan(), capture_dir=Path(folder))
            self.assertEqual(audit["problems"][0]["reason"], "capture-attestation-missing")
            result = q.run_queue(
                plan(), capture_dir=Path(folder),
                inspection_fn=lambda **kw: self.fail("No recording before audit"),
                input_fn=lambda _: self.fail("No prompt before audit"),
            )
            self.assertEqual(result["status"], "blocked")

    def test_claimed_capture_success_without_mp4_is_failed_not_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = q.run_queue(
                plan(), capture_dir=Path(folder), input_fn=lambda _: A,
                inspection_fn=lambda **kw: {
                    "worldId": kw["world_id"], "status": "capture-complete",
                    "captureStopReason": "completed",
                    "recording": kw["world_id"] + "_20261111T120000Z.mp4",
                },
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "capture-missing-or-empty")
            state = json.loads((Path(folder) / "inspection-queue-state.json").read_text())
            self.assertEqual(state["worlds"][A]["status"], "failed")
            self.assertNotIn(B, state["worlds"])

    def test_operator_hotkey_and_world_log_switch_never_complete_or_advance(self):
        for reason in ("operator_emergency_stop", "world_log_guard_stopped",
                       "emergency_stop_monitor_failed", "window_unfocused"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as folder:
                calls = []
                def stopped(**kwargs):
                    calls.append(kwargs["world_id"])
                    result = synthetic_recording(**kwargs)
                    result["captureStopReason"] = reason
                    return result
                r = q.run_queue(
                    plan(), capture_dir=Path(folder), input_fn=lambda _: A,
                    inspection_fn=stopped,
                )
                self.assertEqual(r["status"], "failed")
                self.assertEqual(calls, [A])
                self.assertEqual(q.audit_queue(plan(), capture_dir=Path(folder))["auditedCompleted"], 0)

    def test_log_mismatch_status_never_marks_completed_even_if_mp4_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            def mismatched(**kwargs):
                result = synthetic_recording(**kwargs)
                result["status"] = "world-log-changed"
                return result
            r = q.run_queue(
                plan(), capture_dir=Path(folder),
                input_fn=lambda _: A, inspection_fn=mismatched,
            )
            self.assertEqual(r["status"], "failed")
            state = json.loads((Path(folder) / "inspection-queue-state.json").read_text())
            self.assertEqual(state["worlds"][A]["status"], "failed")

    def test_private_exception_details_are_redacted_in_queue_state(self):
        with tempfile.TemporaryDirectory() as folder:
            def broken(**kwargs):
                raise RuntimeError(r"C:\Users\PrivateName\secret_user_id")
            r = q.run_queue(
                plan(), capture_dir=Path(folder),
                inspection_fn=broken, input_fn=lambda _: A,
            )
            self.assertEqual(r["status"], "failed")
            state_path = Path(folder) / "inspection-queue-state.json"
            text = state_path.read_text(encoding="utf-8")
            self.assertNotIn("PrivateName", text)
            self.assertNotIn("secret_user_id", text)
            self.assertEqual(json.loads(text)["worlds"][A]["result"]["errorType"], "RuntimeError")

    def test_audit_is_read_only_and_never_calls_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_success(folder)
            state_path = Path(folder) / "inspection-queue-state.json"
            before = state_path.read_bytes()
            result = q.audit_queue(plan(), capture_dir=Path(folder))
            after = state_path.read_bytes()
            self.assertEqual(result["status"], "ok")
            self.assertEqual(before, after)

    def test_audit_wrong_plan_or_missing_state_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(q.audit_queue(plan(), capture_dir=Path(folder))["reason"],
                             "queue-state-missing")
            self.run_success(folder)
            swapped = plan()
            swapped["worlds"].reverse()
            self.assertEqual(q.audit_queue(swapped, capture_dir=Path(folder))["reason"],
                             "queue-state-plan-mismatch")


if __name__ == "__main__":
    unittest.main()
