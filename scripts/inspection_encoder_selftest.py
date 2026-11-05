#!/usr/bin/env python3
"""Safe local encoder self-test: synthetic FFmpeg color input, no desktop recording.

Creates a temporary silent video, verifies it with FFprobe, and deletes it.
Does not contact VRChat, Gemini, GitHub or the network. Never takes screenshots.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from scripts.inspection_media_verify import verify_mp4, MediaVerificationError
except ModuleNotFoundError:
    from inspection_media_verify import verify_mp4, MediaVerificationError


def run_encoder_selftest() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found in PATH")
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe not found in PATH")
    with tempfile.TemporaryDirectory(prefix="vcc-encoder-test-") as folder:
        output = Path(folder) / "synthetic-test.mp4"
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=640x360:r=4:d=3",
            "-an", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output),
        ]
        try:
            encoded = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=25, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Synthetic encoder test failed or timed out") from exc
        if encoded.returncode != 0 or not output.exists():
            raise RuntimeError("FFmpeg failed to create synthetic MP4 (check libx264)")
        try:
            video = verify_mp4(output, max_seconds=10)
        except MediaVerificationError as exc:
            raise RuntimeError("Generated synthetic video did not pass FFprobe validation") from exc
        return {
            "status": "success", "test": "synthetic_ffmpeg_h264_roundtrip",
            "video": video, "temporaryFileDeletedAfterTest": True,
            "recordsVRChat": False, "usesNetwork": False, "hasAudio": False,
        }


if __name__ == "__main__":
    try:
        print(json.dumps(run_encoder_selftest(), ensure_ascii=False, indent=2))
    except RuntimeError as exc:
        raise SystemExit("ERROR: " + str(exc)) from exc
