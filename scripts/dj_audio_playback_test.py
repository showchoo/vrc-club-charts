#!/usr/bin/env python3
"""Create a copyright-free DJ playback calibration clip and analyze local audio.

No live recording, remote uploads, VRChat control, URL handling or server.
A captured clip must be supplied separately by the authorized operator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import ROOT, atomic_json
    from scripts.dj_test_audio_signal import match_test_sequence
except ModuleNotFoundError:
    from auto_process_interior_queue import ROOT, atomic_json
    from dj_test_audio_signal import match_test_sequence

MAX_CAPTURE_SIZE = 250 * 1024 * 1024


def private_output(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_relative_to(ROOT) or path.exists():
        raise ValueError("Choose a new private output path outside the Git repository")
    return path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_ffmpeg(command: list[str], *, timeout=30) -> bytes:
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("FFmpeg unavailable or timed out") from exc
    if result.returncode:
        raise ValueError("FFmpeg failed to process local DJ test media")
    return result.stdout


def make_clip(path: Path) -> dict:
    target = private_output(path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("FFmpeg is required to generate the local test clip")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-f", "lavfi", "-i",
               "testsrc2=duration=8:size=640x360:rate=15"]
    for hz in (523, 659, 784, 1046):
        command.extend(["-f", "lavfi", "-i",
                        f"sine=frequency={hz}:duration=2:sample_rate=48000"])
    command += [
        "-filter_complex", "[1:a][2:a][3:a][4:a]concat=n=4:v=0:a=1[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", "-shortest", str(target),
    ]
    try:
        run_ffmpeg(command, timeout=45)
        if not target.is_file():
            raise ValueError("Test clip was not generated")
        matched = read_tone_pattern(target)
        if not matched["matched"]:
            raise ValueError("Generated video did not contain expected test tones")
        return {
            "status": "generated_original_test_clip",
            "path": str(target),
            "sha256": digest(target),
            "durationTargetSeconds": 8,
            "audioTestSequenceConfirmed": True,
            "isRealVRChatRecording": False,
            "equipmentFunctionalityVerified": False,
        }
    except Exception:
        if target.exists():
            target.unlink()
        raise


def read_tone_pattern(path: Path) -> dict:
    video = path.expanduser().resolve(strict=True)
    if video.is_symlink() or not video.is_file():
        raise ValueError("Expected a regular local test video file")
    if video.stat().st_size > MAX_CAPTURE_SIZE:
        raise ValueError("Local media too large for audio-only verification")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("FFmpeg is required")
    decoded = run_ffmpeg([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(video), "-map", "0:a:0", "-vn",
        "-t", "30", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "pipe:1",
    ])
    return match_test_sequence(decoded)


def verify(*, original: Path, recording: Path, out: Path,
           recording_rights_confirmed: bool) -> dict:
    if not recording_rights_confirmed:
        raise ValueError("Recording and participant consent must be confirmed")
    destination = private_output(out)
    source = original.expanduser().resolve(strict=True)
    captured = recording.expanduser().resolve(strict=True)
    original_digest, captured_digest = digest(source), digest(captured)
    if original_digest == captured_digest:
        raise ValueError("Source file and alleged independent capture are identical")
    source_signal = read_tone_pattern(source)
    if not source_signal["matched"]:
        raise ValueError("Expected test signal not found in reference clip")
    recorded_signal = read_tone_pattern(captured)
    report = {
        "schemaVersion": 1,
        "status": "test_audio_sequence_detected" if recorded_signal["matched"]
                  else "inconclusive",
        "originalSha256": original_digest,
        "recordingSha256": captured_digest,
        "referenceAudioPatternDetected": source_signal["matched"],
        "recordedAudioPatternDetected": recorded_signal["matched"],
        "recordedTonesHz": recorded_signal["frequenciesDetected"],
        "privacy": "creator_controlled_isolated_recording_attested_by_operator",
        "independentlyAuthenticatedVRChat": False,
        "actualSpeakerOrHeadsetOutputVerified": False,
        "liveDjStreamVerified": False,
        "equipmentFunctionalityVerified": False,
        "rankingEligible": False,
        "noRemoteUpload": True,
    }
    atomic_json(destination, report)
    return {"status": report["status"], "report": str(destination),
            "equipmentFunctionalityVerified": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("create")
    create.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--original", type=Path, required=True)
    check.add_argument("--recording", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    check.add_argument("--confirm-private-recording", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = (make_clip(args.out) if args.action == "create" else
                  verify(original=args.original, recording=args.recording,
                         out=args.out,
                         recording_rights_confirmed=args.confirm_private_recording))
    except (OSError, ValueError) as exc:
        parser.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "inconclusive" else 1


if __name__ == "__main__":
    raise SystemExit(main())
