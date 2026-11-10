#!/usr/bin/env python3
"""Offline integrity attestations for local VRChat inspection recordings.

Never uploads or edits media. Stores only the expected local MP4 filename,
byte count and SHA-256 digest in private queue state. This is *file integrity*
(not proof of successful client capture, people absent, or DJ functionality).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat

WORLD_ID_RE = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA_VERSION = 1


class CaptureIntegrityError(ValueError):
    """An allowlisted reason code, never a filesystem path or exception text."""


def capture_path(capture_dir: Path, world_id: str, filename: str) -> Path:
    """Accept only the bounded filename emitted by the local capture script."""
    if not isinstance(world_id, str) or not WORLD_ID_RE.fullmatch(world_id):
        raise CaptureIntegrityError("invalid-world-id")
    if (not isinstance(filename, str) or
            re.fullmatch(
                re.escape(world_id) + r"_[0-9]{8}T[0-9]{6}Z\.mp4",
                filename,
            ) is None):
        raise CaptureIntegrityError("invalid-capture-filename")
    root = capture_dir.expanduser().resolve()
    path = root / filename
    if path.is_symlink() or path.resolve().parent != root:
        raise CaptureIntegrityError("unsafe-capture-path")
    return path


def capture_integrity(capture_dir: Path, world_id: str, filename: str) -> dict:
    """Stream SHA-256 without reading the MP4 into memory or exposing its path."""
    path = capture_path(capture_dir, world_id, filename)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
                raise CaptureIntegrityError("capture-missing-or-empty")
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
    except FileNotFoundError:
        raise CaptureIntegrityError("capture-missing-or-empty") from None
    except CaptureIntegrityError:
        raise
    except OSError:
        raise CaptureIntegrityError("capture-unreadable") from None

    if ((before.st_size, before.st_mtime_ns, before.st_ino) !=
            (after.st_size, after.st_mtime_ns, after.st_ino)):
        raise CaptureIntegrityError("capture-changed-during-hash")
    if path.is_symlink() or path.resolve().parent != capture_dir.expanduser().resolve():
        raise CaptureIntegrityError("unsafe-capture-path")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "filename": filename,
        "bytes": before.st_size,
        "sha256": digest.hexdigest(),
    }


def verify_capture_integrity(capture_dir: Path, world_id: str, evidence: object) -> dict:
    """Fail closed on missing, legacy, tampered or insufficient evidence."""
    if not isinstance(evidence, dict) or evidence.get("schemaVersion") != SCHEMA_VERSION:
        raise CaptureIntegrityError("capture-attestation-missing")
    filename = evidence.get("filename")
    digest = evidence.get("sha256")
    size = evidence.get("bytes")
    if (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)
            or type(size) is not int or size <= 0):
        raise CaptureIntegrityError("capture-attestation-invalid")
    found = capture_integrity(capture_dir, world_id, filename)
    if found["bytes"] != size or found["sha256"] != digest:
        raise CaptureIntegrityError("capture-digest-mismatch")
    return found
