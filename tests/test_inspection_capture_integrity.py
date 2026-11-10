"""Offline MP4 integrity tests: synthetic bytes only, no FFmpeg or VRChat."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import inspection_capture_integrity as m

A = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
B = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
FILENAME = A + "_20261111T120000Z.mp4"


def fail(code, fn):
    try:
        fn()
    except m.CaptureIntegrityError as exc:
        if str(exc) != code:
            raise AssertionError(f"Expected {code}, got {exc}") from exc
    else:
        raise AssertionError(f"Expected {code}")


class CaptureIntegrityTests(unittest.TestCase):
    def test_synthetic_capture_has_deterministic_hash_and_length(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = b"synthetic MP4 placeholder, not a real client capture"
            path = Path(folder) / FILENAME
            path.write_bytes(payload)
            evidence = m.capture_integrity(Path(folder), A, FILENAME)
            self.assertEqual(evidence["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(evidence["bytes"], len(payload))
            self.assertEqual(evidence["filename"], FILENAME)
            self.assertEqual(m.verify_capture_integrity(Path(folder), A, evidence), evidence)

    def test_missing_empty_and_changed_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            capture_dir = Path(folder)
            file = capture_dir / FILENAME
            fail("capture-missing-or-empty",
                 lambda: m.capture_integrity(capture_dir, A, FILENAME))
            file.write_bytes(b"")
            fail("capture-missing-or-empty",
                 lambda: m.capture_integrity(capture_dir, A, FILENAME))
            file.write_bytes(b"baseline")
            evidence = m.capture_integrity(capture_dir, A, FILENAME)
            file.write_bytes(b"modified")
            fail("capture-digest-mismatch",
                 lambda: m.verify_capture_integrity(capture_dir, A, evidence))
            file.unlink()
            fail("capture-missing-or-empty",
                 lambda: m.verify_capture_integrity(capture_dir, A, evidence))

    def test_invalid_names_cannot_escape_capture_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for bad in (
                "../" + FILENAME, "subfolder/" + FILENAME,
                "..\\" + FILENAME, "/tmp/" + FILENAME,
                B + "_20261111T120000Z.mp4",
                A + "_test.mp4", A + "_20261111T120000Z.mp4.exe", "",
                None,
            ):
                with self.subTest(bad=bad):
                    fail("invalid-capture-filename",
                         lambda: m.capture_integrity(root, A, bad))

    def test_symlink_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "unrelated.bin"
            original.write_bytes(b"sensitive-private-media")
            link = root / FILENAME
            try:
                link.symlink_to(original)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable in test environment")
            fail("unsafe-capture-path",
                 lambda: m.capture_integrity(root, A, FILENAME))

    def test_missing_legacy_and_malformed_evidence_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / FILENAME).write_bytes(b"synthetic")
            for bad in (None, {}, {"schemaVersion": 0}, "not a dict"):
                with self.subTest(bad=bad):
                    fail("capture-attestation-missing",
                         lambda: m.verify_capture_integrity(root, A, bad))
            current = m.capture_integrity(root, A, FILENAME)
            for bad in (
                {**current, "sha256": "INVALID"},
                {**current, "bytes": True},
                {**current, "bytes": -1},
            ):
                with self.subTest(bad=bad):
                    fail("capture-attestation-invalid",
                         lambda: m.verify_capture_integrity(root, A, bad))

    def test_wrong_world_never_uses_valid_file_attestation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / FILENAME).write_bytes(b"synthetic")
            current = m.capture_integrity(root, A, FILENAME)
            fail("invalid-capture-filename",
                 lambda: m.verify_capture_integrity(root, B, current))


if __name__ == "__main__":
    unittest.main()
