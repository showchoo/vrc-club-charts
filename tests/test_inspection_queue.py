"""Offline tests: no VRChat client, OSC, Gemini, or GitHub writes."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import inspection_queue as q

A = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
B = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"


def plan():
    return {"schemaVersion": 1, "worlds": [
        {"worldId": A, "name": "A DJ World"},
        {"worldId": B, "name": "B DJ World"},
    ]}


class InspectionQueueTests(unittest.TestCase):
    def test_catalog_only_public_eligible_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = Path(folder) / "worlds.json"
            catalog.write_text(json.dumps([
                {"id": A, "name": "A", "chartEligible": True, "releaseStatus": "public"},
                {"id": B, "name": "B", "chartEligible": True, "releaseStatus": "private"},
                {"id": B, "name": "B", "chartEligible": True, "releaseStatus": "public"},
                {"id": B, "name": "duplicate", "chartEligible": True, "releaseStatus": "public"},
                {"id": "junk", "name": "fake", "chartEligible": True, "releaseStatus": "public"},
            ]), encoding="utf-8")
            result = q.plan_from_catalog(catalog, limit=10)
            self.assertEqual([w["worldId"] for w in result["worlds"]], [A, B])
            with self.assertRaisesRegex(ValueError, "1 and 25"):
                q.plan_from_catalog(catalog, limit=26)

    def test_invalid_and_duplicate_ids_rejected(self):
        for altered in ("oops", A.upper(), "wrld_" + "a" * 100):
            bad = plan()
            bad["worlds"][0]["worldId"] = altered
            with self.assertRaises(ValueError):
                q.validate_plan(bad)
        dup = plan()
        dup["worlds"][1]["worldId"] = A
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            q.validate_plan(dup)

    def test_cannot_run_inside_repository(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            q.outside_repository(q.REPO_ROOT / "tmp")

    def test_wrong_acknowledgement_stops_before_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            result = q.run_queue(plan(), capture_dir=Path(folder),
                                 inspection_fn=lambda **kw: self.fail("inspector called"),
                                 input_fn=lambda prompt: "q")
            self.assertEqual(result["status"], "paused")
            self.assertFalse((Path(folder) / "inspection-queue-state.json").exists())

    def test_resume_skips_completed_only(self):
        calls = []
        def inspect(**kw):
            calls.append(kw)
            return {"worldId": kw["world_id"], "status": "capture-complete",
                    "captureStopReason": "completed"}
        with tempfile.TemporaryDirectory() as folder:
            first = iter([A, "q"])
            r1 = q.run_queue(plan(), capture_dir=Path(folder), inspection_fn=inspect,
                             input_fn=lambda _: next(first))
            self.assertEqual(r1["status"], "paused")
            self.assertEqual(len(calls), 1)
            self.assertFalse(calls[0]["publish_visual"])
            self.assertFalse(calls[0]["use_ai_motion"])
            r2 = q.run_queue(plan(), capture_dir=Path(folder), inspection_fn=inspect,
                             input_fn=lambda _: B)
            self.assertEqual(r2["status"], "completed")
            self.assertEqual([x["world_id"] for x in calls], [A, B])
            state = json.loads((Path(folder) / "inspection-queue-state.json").read_text())
            self.assertEqual(state["worlds"][A]["status"], "completed")
            self.assertEqual(state["worlds"][B]["status"], "completed")

    def test_failing_world_stops_and_requires_new_ack(self):
        calls = []
        def fail(**kw):
            calls.append(kw["world_id"])
            return {"worldId": kw["world_id"], "status": "capture-unusable"}
        with tempfile.TemporaryDirectory() as folder:
            r = q.run_queue(plan(), capture_dir=Path(folder), inspection_fn=fail,
                            input_fn=lambda _: A)
            self.assertEqual(r["status"], "failed")
            self.assertEqual(calls, [A])
            changed = plan()
            changed["worlds"].reverse()
            with self.assertRaisesRegex(ValueError, "different plan"):
                q.run_queue(changed, capture_dir=Path(folder), inspection_fn=fail,
                            input_fn=lambda _: A)

    def test_launch_url_is_official_and_strict(self):
        self.assertEqual(q.world_launch_url(A),
                         "https://vrchat.com/home/launch?worldId=" + A)
        for bad in ("https://attacker.example", A + "&instanceId=public", "wrld_invalid"):
            with self.assertRaises(ValueError):
                q.world_launch_url(bad)

    def test_opt_in_browser_handoff_still_requires_manual_ack(self):
        urls = []
        with tempfile.TemporaryDirectory() as folder:
            result = q.run_queue(
                plan(), capture_dir=Path(folder), open_world_page=True,
                open_url_fn=lambda url: urls.append(url) or True,
                inspection_fn=lambda **kw: self.fail("Should never record before acknowledgement"),
                input_fn=lambda _: "q")
        self.assertEqual(result["status"], "paused")
        self.assertEqual(urls, [q.world_launch_url(A)])

    def test_failed_browser_open_does_not_prompt_or_record(self):
        with tempfile.TemporaryDirectory() as folder:
            r = q.run_queue(plan(), capture_dir=Path(folder), open_world_page=True,
                            open_url_fn=lambda url: False,
                            input_fn=lambda _: self.fail("No prompt after failed browser"),
                            inspection_fn=lambda **kw: self.fail("No recording"))
            self.assertEqual(r["status"], "paused")

    def test_incomplete_capture_is_not_marked_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = q.run_queue(
                plan(), capture_dir=Path(folder), input_fn=lambda _: A,
                inspection_fn=lambda **kw: {
                    "worldId": kw["world_id"], "status": "capture-complete",
                    "captureStopReason": "user_ctrl_c",
                })
            self.assertEqual(result["status"], "failed")
            state = json.loads((Path(folder) / "inspection-queue-state.json").read_text())
            self.assertEqual(state["worlds"][A]["status"], "failed")
            self.assertNotIn(B, state["worlds"])

    def test_consent_enforced_before_any_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            def should_not_prompt(_):
                self.fail("prompt called")
            for options in ({"sweep": True}, {"analyze_video": True}):
                with self.assertRaises(ValueError):
                    q.run_queue(plan(), capture_dir=Path(folder), **options,
                                inspection_fn=lambda **kw: self.fail("capture"),
                                input_fn=should_not_prompt)

    def test_mismatched_inspector_result_never_completes(self):
        with tempfile.TemporaryDirectory() as folder:
            r = q.run_queue(plan(), capture_dir=Path(folder), input_fn=lambda _: A,
                            inspection_fn=lambda **kw: {"worldId": B, "status": "capture-complete"})
            self.assertEqual(r["status"], "failed")


if __name__ == "__main__":
    unittest.main()
