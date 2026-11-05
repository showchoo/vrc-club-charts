"""Strict local FFprobe validation without launching FFmpeg or any cloud client."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts import inspection_media_verify as media


def sample_metadata(*, duration="3.25", streams=None):
    return {
        "format": {"duration": duration, "size": "1048576"},
        "streams": streams if streams is not None else [
            {"index": 0, "codec_type": "video", "codec_name": "h264",
             "width": 1280, "height": 720, "nb_frames": "13"},
        ],
    }


class MediaValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.video = Path(self.temp.name) / "capture.mp4"
        self.video.write_bytes(b"fake-ffprobe-test" * 200)
        which = patch.object(media.shutil, "which", return_value="/fake/ffprobe")
        self.which = which.start()
        self.addCleanup(which.stop)

    def mock_probe(self, metadata):
        return patch.object(media.subprocess, "run", return_value=CompletedProcess(
            args=["ffprobe"], returncode=0, stdout=json.dumps(metadata), stderr=""))

    def test_valid_silent_h264_video_reports_safe_metadata(self):
        with self.mock_probe(sample_metadata()) as proc:
            result = media.verify_mp4(self.video, max_seconds=45)
        self.assertEqual(result["codec"], "h264")
        self.assertEqual(result["width"], 1280)
        self.assertEqual(result["durationSeconds"], 3.25)
        self.assertEqual(result["audioTracks"], 0)
        self.assertTrue(result["metadataVerified"])
        self.assertFalse(result["fullFrameDecodeVerified"])
        self.assertIn("-show_entries", proc.call_args.args[0])

    def test_empty_and_small_mp4_rejected_before_probe(self):
        self.video.write_bytes(b"tiny")
        with patch.object(media.subprocess, "run", side_effect=AssertionError("No subprocess should run")):
            with self.assertRaisesRegex(media.MediaVerificationError, "too small"):
                media.verify_mp4(self.video)

    def test_audio_stream_rejected_to_prevent_unintentional_upload(self):
        streams = sample_metadata()["streams"] + [
            {"index": 1, "codec_type": "audio", "codec_name": "aac"}
        ]
        with self.mock_probe(sample_metadata(streams=streams)):
            with self.assertRaisesRegex(media.MediaVerificationError, "audio"):
                media.verify_mp4(self.video)

    def test_invalid_codec_and_frame_count_rejected(self):
        for change, message in [
            ({"codec_name": "vp9"}, "H.264"),
            ({"width": 721}, "dimensions"),
            ({"nb_frames": "3"}, "too few"),
            ({"height": 0}, "dimensions"),
        ]:
            data = sample_metadata()
            data["streams"][0].update(change)
            with self.subTest(change=change), self.mock_probe(data):
                with self.assertRaisesRegex(media.MediaVerificationError, message):
                    media.verify_mp4(self.video)

    def test_wrong_or_extreme_duration_rejected(self):
        for duration in ("0", "-3", "nan", "inf", "1.0", "200"):
            with self.subTest(duration=duration), self.mock_probe(sample_metadata(duration=duration)):
                with self.assertRaises(media.MediaVerificationError):
                    media.verify_mp4(self.video, max_seconds=45)

    def test_no_ffprobe_and_failed_probe_rejected(self):
        with patch.object(media.shutil, "which", return_value=None):
            with self.assertRaisesRegex(media.MediaVerificationError, "not found"):
                media.verify_mp4(self.video)
        with patch.object(media.subprocess, "run", return_value=CompletedProcess(
            ["ffprobe"], 1, stdout="", stderr="Could not open")):
            with self.assertRaisesRegex(media.MediaVerificationError, "could not read"):
                media.verify_mp4(self.video)

    def test_cannot_probe_url_or_non_mp4_path(self):
        sample = Path(self.temp.name) / "test.txt"
        sample.write_bytes(b"x" * 2000)
        with self.assertRaisesRegex(media.MediaVerificationError, "local MP4"):
            media.verify_mp4(sample)

    def test_probe_does_not_mutate_source_video(self):
        original = self.video.read_bytes()
        with self.mock_probe(sample_metadata()):
            media.verify_mp4(self.video)
        self.assertEqual(self.video.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
