"""Offline deterministic video quality checks; no VRChat or Gemini calls."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts import inspection_visual_quality as q


def frame(t=0, kind="dynamic"):
    if kind == "black":
        return bytes([0] * q.FRAME_BYTES)
    if kind == "static":
        return bytes(((j * 13 + 65) % 210 for j in range(q.FRAME_BYTES)))
    if kind == "dim":
        return bytes((4 if ((j + t) % 2) else 42
                     for j in range(q.FRAME_BYTES)))
    return bytes((60 + ((j * 11 + t * 17) % 130)
                  for j in range(q.FRAME_BYTES)))


class QualityTests(unittest.TestCase):
    def test_synthetic_moving_scene_is_usable(self):
        raw = b"".join(frame(i) for i in range(12))
        report = q.analyze_gray_frames(raw)
        self.assertEqual(report["status"], "ok")
        self.assertGreater(report["visualChangeIntervals"], 1)
        self.assertEqual(report["sampledFrames"], 12)

    def test_black_even_with_valid_h264_wrapper_is_rejected(self):
        report = q.analyze_gray_frames(frame(kind="black") * 12)
        self.assertEqual(report["status"], "unusable")
        self.assertIn("almost_all_frames_black", report["reasons"])

    def test_unchanged_detailed_room_is_flagged_as_insufficient_coverage(self):
        report = q.analyze_gray_frames(frame(kind="static") * 12)
        self.assertEqual(report["status"], "unusable")
        self.assertIn("no_visual_change_in_extended_clip", report["reasons"])
        self.assertNotIn("almost_all_frames_black", report["reasons"])

    def test_dark_but_detailed_changing_room_is_not_automatically_rejected(self):
        report = q.analyze_gray_frames(b"".join(frame(i, "dim") for i in range(12)))
        self.assertEqual(report["status"], "ok")
        self.assertGreater(report["framesWithDetail"], 2)

    def test_invalid_sample_buffer_is_rejected(self):
        for raw in (b"", b"1", b"x" * (q.FRAME_BYTES + 10),
                    b"x" * (q.FRAME_BYTES * (q.MAX_SAMPLES + 1))):
            with self.subTest(size=len(raw)), self.assertRaises(q.VisualQualityError):
                q.analyze_gray_frames(raw)

    def test_decoding_is_local_downsampled_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.mp4"
            path.write_bytes(b"x" * 2048)
            payload = b"".join(frame(t) for t in range(10))
            fake = CompletedProcess([], 0, stdout=payload, stderr=b"")
            with (patch.object(q.shutil, "which", return_value="/opt/ffmpeg"),
                  patch.object(q.subprocess, "run", return_value=fake) as process):
                report = q.assess_video_quality(path,
                    metadata={"metadataVerified": True})
            self.assertEqual(report["status"], "ok")
            command = process.call_args.args[0]
            self.assertIn("fps=1,scale=32:18,format=gray", command)
            self.assertIn("pipe:1", command)
            self.assertIn("-nostdin", command)
            self.assertEqual(process.call_args.kwargs["timeout"], 35)

    def test_decode_error_is_not_mislabeled_as_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.mp4"
            path.write_bytes(b"x" * 2048)
            for returned in (CompletedProcess([], 1, stdout=b"", stderr=b"bad"),
                             CompletedProcess([], 0, stdout=b"x", stderr=b"")):
                with (patch.object(q.shutil, "which", return_value="/opt/ffmpeg"),
                      patch.object(q.subprocess, "run", return_value=returned)):
                    with self.assertRaises(q.VisualQualityError):
                        q.assess_video_quality(path, metadata={"metadataVerified": True})

    def test_unverified_metadata_blocks_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.mp4"
            path.write_bytes(b"x" * 2048)
            with patch.object(q.subprocess, "run", side_effect=AssertionError("must not decode")):
                with self.assertRaisesRegex(q.VisualQualityError, "metadata"):
                    q.assess_video_quality(path, metadata={"metadataVerified": False})


if __name__ == "__main__":
    unittest.main()
