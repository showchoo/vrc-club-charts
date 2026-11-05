"""Synthetic MP4 roundtrip invokes tools only on a disposable local file."""
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts import inspection_encoder_selftest as selftest


class EncoderSelfTests(unittest.TestCase):
    def test_writes_synthetic_video_and_runs_metadata_gate(self):
        def fake_ffmpeg(argv, **kwargs):
            self.assertIn("color=c=black:s=640x360:r=4:d=3", argv)
            self.assertIn("-nostdin", argv)
            self.assertIn("-an", argv)
            Path(argv[-1]).write_bytes(b"x" * 3000)
            return CompletedProcess(argv, 0, "", "")
        with (patch.object(selftest.shutil, "which", return_value="/mock/ffmpeg"),
              patch.object(selftest.subprocess, "run", side_effect=fake_ffmpeg),
              patch.object(selftest, "verify_mp4", return_value={
                  "metadataVerified": True, "audioTracks": 0, "durationSeconds": 3.0
              }) as probe):
            report = selftest.run_encoder_selftest()
        self.assertEqual(report["status"], "success")
        self.assertFalse(report["recordsVRChat"])
        self.assertFalse(report["usesNetwork"])
        self.assertFalse(report["hasAudio"])
        self.assertTrue(report["temporaryFileDeletedAfterTest"])
        self.assertFalse(probe.call_args.args[0].exists())

    def test_missing_ffprobe_fails_without_launching_ffmpeg(self):
        with (patch.object(selftest.shutil, "which",
                           side_effect=lambda app: "/fake/ffmpeg" if app == "ffmpeg" else None),
              patch.object(selftest.subprocess, "run", side_effect=AssertionError("Must not run"))):
            with self.assertRaisesRegex(RuntimeError, "FFprobe not found"):
                selftest.run_encoder_selftest()

    def test_encoder_failure_does_not_probe_or_leave_files(self):
        with (patch.object(selftest.shutil, "which", return_value="/fake/tool"),
              patch.object(selftest.subprocess, "run", return_value=CompletedProcess([], 1, "", "error")),
              patch.object(selftest, "verify_mp4", side_effect=AssertionError("Must not probe"))):
            with self.assertRaisesRegex(RuntimeError, "failed to create synthetic"):
                selftest.run_encoder_selftest()


if __name__ == "__main__":
    unittest.main()
