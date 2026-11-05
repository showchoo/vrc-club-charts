"""No unconsented local capture enters the cloud evaluation queue."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import auto_evaluate_local_captures as auto
from scripts import auto_process_interior_queue as queue

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def local_capture(folder, *, frames=20, private=True, audio=False, filename=None):
    filename = filename or WORLD + "_20261106T020000Z.mp4"
    (folder / filename).write_bytes(b"mock video file, not a VRChat recording")
    item = {
        "schemaVersion": 1, "worldId": WORLD,
        "instanceAccess": ("owner_attested_private_no_other_participants"
                           if private else "public"),
        "stopReason": "completed",
        "recording": {"filename": filename, "audio": audio, "frames": frames},
    }
    (folder / "capture.inspection.json").write_text(json.dumps(item), encoding="utf-8")


class AutoCaptureQueueTests(unittest.TestCase):
    def test_dry_run_counts_only_safe_private_capture(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            local_capture(folder)
            result = auto.build_and_process(folder, folder / "out", dry_run=True,
                                            attest_all=False, upload_allowed=False,
                                            max_videos=1, model="gemini-3.5-flash-lite")
            self.assertEqual(result["eligibleLocalCaptures"], 1)
            self.assertFalse((folder / "out").exists())

    def test_public_or_audio_or_too_short_are_excluded(self):
        for opts in [{"private": False}, {"audio": True}, {"frames": 3}]:
            with self.subTest(opts=opts), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                local_capture(folder, **opts)
                self.assertEqual(auto.discover_captures(folder), [])

    def test_requires_attestation_and_provider_permission(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            local_capture(folder)
            with self.assertRaisesRegex(ValueError, "consent"):
                auto.build_and_process(folder, folder / "out", dry_run=False,
                    attest_all=False, upload_allowed=True, max_videos=1,
                    model="gemini-3.5-flash-lite")
            with self.assertRaisesRegex(ValueError, "authorized"):
                auto.build_and_process(folder, folder / "out", dry_run=False,
                    attest_all=True, upload_allowed=False, max_videos=1,
                    model="gemini-3.5-flash-lite")

    def test_never_auto_publishes_or_bypasses_private_queue(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            local_capture(folder)
            with patch.object(auto, "process_queue", return_value={"succeeded": 1}) as batch:
                result = auto.build_and_process(folder, folder / "out", dry_run=False,
                    attest_all=True, upload_allowed=True, max_videos=2,
                    model="gemini-3.5-flash-lite")
                self.assertEqual(result["succeeded"], 1)
                args, kw = batch.call_args
                manifest = json.loads(args[0].read_text(encoding="utf-8"))
                self.assertFalse(manifest["videos"][0]["permissionToPublish"])
                self.assertTrue(kw["allow_upload"])
                self.assertEqual(kw["max_items"], 2)

    def test_rejects_filename_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            local_capture(folder)
            log = folder / "capture.inspection.json"
            record = json.loads(log.read_text(encoding="utf-8"))
            record["recording"]["filename"] = "../" + WORLD + "_20261106T020000Z.mp4"
            log.write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(auto.discover_captures(folder), [])


if __name__ == "__main__":
    unittest.main()
