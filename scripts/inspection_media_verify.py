#!/usr/bin/env python3
"""Validate that the local MP4 truly contains a decodable-looking video stream.

Read-only metadata inspection using FFprobe. No VRChat account access, recording,
AI inference, uploads or Git operations. This is not a full frame-by-frame decode.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path


class MediaVerificationError(ValueError):
    """Capture is incomplete, corrupted, unsuitable or uninspectable."""


def _positive_number(value) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise MediaVerificationError("Missing or nonnumeric video duration") from None
    if not math.isfinite(num) or num <= 0:
        raise MediaVerificationError("Invalid video duration")
    return num


def verify_mp4(path: Path, *, max_seconds: int = 120, min_seconds: float = 2.0) -> dict:
    video = Path(path).expanduser().resolve(strict=True)
    if not video.is_file() or video.suffix.casefold() != ".mp4":
        raise MediaVerificationError("Expected a local MP4 file")
    if video.stat().st_size < 1024:
        raise MediaVerificationError("Capture MP4 is too small to be a valid video")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise MediaVerificationError("FFprobe not found; install an FFmpeg package that includes ffprobe")
    try:
        response = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name,width,height,nb_frames,duration:"
             "format=duration,size", "-of", "json", str(video)],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaVerificationError("FFprobe failed or timed out") from exc
    if response.returncode != 0 or len(response.stdout) > 200000:
        raise MediaVerificationError("FFprobe could not read video metadata")
    try:
        data = json.loads(response.stdout)
    except json.JSONDecodeError as exc:
        raise MediaVerificationError("FFprobe returned invalid metadata") from exc
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise MediaVerificationError("FFprobe did not report video streams")
    streams = data["streams"]
    videos = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    audios = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise MediaVerificationError("Capture must contain exactly one video stream")
    if audios:
        raise MediaVerificationError("Capture unexpectedly contains audio; refusing AI upload")
    stream = videos[0]
    if stream.get("codec_name") != "h264":
        raise MediaVerificationError("Capture video is not H.264")
    width, height = stream.get("width"), stream.get("height")
    if (isinstance(width, bool) or isinstance(height, bool) or
        not isinstance(width, int) or not isinstance(height, int) or
        width < 320 or height < 240 or width > 8192 or height > 8192 or
        width % 2 or height % 2):
        raise MediaVerificationError("Capture has invalid dimensions")
    fmt = data.get("format")
    if not isinstance(fmt, dict):
        raise MediaVerificationError("FFprobe reported no format metadata")
    duration = _positive_number(fmt.get("duration", stream.get("duration")))
    if duration < min_seconds or duration > max_seconds + 5:
        raise MediaVerificationError("Capture duration is outside the allowed limits")
    frames = stream.get("nb_frames")
    if frames not in (None, "N/A"):
        try:
            frame_count = int(frames)
        except (ValueError, TypeError) as exc:
            raise MediaVerificationError("Invalid frame count") from exc
        if frame_count < 8:
            raise MediaVerificationError("Capture has too few encoded frames")
    else:
        frame_count = None
    return {
        "codec": "h264", "width": width, "height": height,
        "durationSeconds": round(duration, 3),
        "frames": frame_count, "audioTracks": 0,
        "container": "mp4", "metadataVerified": True,
        "fullFrameDecodeVerified": False,
    }
