#!/usr/bin/env python3
"""Conservative offline quality gate for consented, silent interior video.

Analyze downsampled GRAYSCALE frames with locally installed FFmpeg. This does
not identify people, call an AI, interact with VRChat, or upload footage.
It identifies all-black or unchanged footage that should never be mistaken
for a successfully surveyed interior. Dark but detailed DJ Worlds remain OK.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

try:
    from scripts.inspection_media_verify import verify_mp4
except ModuleNotFoundError:
    from inspection_media_verify import verify_mp4

FRAME_W = 32
FRAME_H = 18
FRAME_BYTES = FRAME_W * FRAME_H
SAMPLE_FPS = 1
MAX_SAMPLES = 125
# Up to 1% genuinely visible pixels can be isolated overlay text rather than a room.
BLACK_VALUE = 10
MAX_BLACK_FRACTION = 0.99
MIN_FRAME_DELTA = 1.8
MIN_VARIATION_PIXELS = 0.025
MIN_SAMPLES_FOR_PROGRESS = 8


class VisualQualityError(ValueError):
    """Video has no useful room content or is not inspectable."""


def _samples(raw: bytes) -> list[bytes]:
    if not raw or len(raw) % FRAME_BYTES or len(raw) > FRAME_BYTES * MAX_SAMPLES:
        raise VisualQualityError("Invalid decoded video frame stream")
    frames = [raw[n:n + FRAME_BYTES] for n in range(0, len(raw), FRAME_BYTES)]
    if len(frames) < 2:
        raise VisualQualityError("Too few frames to assess visual quality")
    return frames


def analyze_gray_frames(raw: bytes) -> dict:
    """Pure function that cannot inspect source pixels beyond small gray samples."""
    frames = _samples(raw)
    darkness = [sum(px <= BLACK_VALUE for px in frame) / FRAME_BYTES for frame in frames]
    black_frames = sum(v >= MAX_BLACK_FRACTION for v in darkness)
    differences = []
    for earlier, later in zip(frames, frames[1:]):
        differences.append(sum(abs(a-b) for a, b in zip(earlier, later)) / FRAME_BYTES)
    novel_steps = sum(d >= MIN_FRAME_DELTA for d in differences)
    visible_detail = []
    for frame in frames:
        mean = sum(frame) / FRAME_BYTES
        visible_detail.append(sum(abs(px - mean) >= 8 for px in frame) / FRAME_BYTES)
    # All-black clips are unusable; some club lighting is dark but has detail.
    nearly_black = black_frames >= math.ceil(len(frames) * .9)
    unchanged = len(frames) >= MIN_SAMPLES_FOR_PROGRESS and novel_steps == 0
    weak_detail = sum(d >= MIN_VARIATION_PIXELS for d in visible_detail) < 2
    status = "unusable" if nearly_black or unchanged or weak_detail else "ok"
    reasons = []
    if nearly_black:
        reasons.append("almost_all_frames_black")
    if unchanged:
        reasons.append("no_visual_change_in_extended_clip")
    if weak_detail:
        reasons.append("insufficient_visible_scene_detail")
    return {
        "status": status,
        "sampledFrames": len(frames),
        "nearBlackFrames": black_frames,
        "visualChangeIntervals": novel_steps,
        "averageFrameChange": round(sum(differences) / len(differences), 3),
        "framesWithDetail": sum(d >= MIN_VARIATION_PIXELS for d in visible_detail),
        "reasons": reasons,
        "method": "ffmpeg_1fps_32x18_grayscale_luma_difference_v1",
        "limitations": "Heuristic: cannot verify VRChat world identity, room coverage, privacy or DJ equipment.",
    }


def assess_video_quality(video: Path, *, metadata: dict | None = None) -> dict:
    """Local FFmpeg subprocess; only ~72KB raw monochrome sampling at most."""
    video = Path(video).expanduser().resolve(strict=True)
    if metadata is None:
        metadata = verify_mp4(video)
    if metadata.get("metadataVerified") is not True:
        raise VisualQualityError("Video metadata has not been verified")
    tool = shutil.which("ffmpeg")
    if not tool:
        raise VisualQualityError("FFmpeg not available for local visual quality check")
    command = [
        tool, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-map", "0:v:0", "-an",
        "-vf", f"fps={SAMPLE_FPS},scale={FRAME_W}:{FRAME_H},format=gray",
        "-frames:v", str(MAX_SAMPLES),
        "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1",
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=35, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VisualQualityError("FFmpeg could not decode representative frames") from exc
    if result.returncode or len(result.stdout) > MAX_SAMPLES * FRAME_BYTES:
        raise VisualQualityError("FFmpeg failed to decode representative frames")
    return analyze_gray_frames(result.stdout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        info = verify_mp4(args.video)
        quality = assess_video_quality(args.video, metadata=info)
        print(json.dumps(quality, ensure_ascii=False, indent=2))
        return 0 if quality["status"] == "ok" else 2
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
