#!/usr/bin/env python3
"""Read-only Windows readiness checks for the opt-in VRChat inspection pilot.

No account access, OSC traffic, capture, model API calls or remote requests.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys


def dependency_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def preflight(*, wants_ai: bool = False, wants_video_ai: bool = False,
              check_window: bool = True, wants_sweep: bool = False) -> dict:
    checks: list[dict] = []
    def add(name: str, ok: bool, detail: str, essential: bool = True):
        checks.append({"check": name, "ok": bool(ok), "required": essential,
                       "detail": detail})

    windows = platform.system() == "Windows"
    add("windows", windows, "Windows desktop 10/11 required")
    add("python", sys.version_info >= (3, 10), "Python 3.10 or later required")
    ffmpeg = shutil.which("ffmpeg")
    add("ffmpeg", bool(ffmpeg), "FFmpeg must be installed and available on PATH")
    ffprobe = shutil.which("ffprobe")
    add("ffprobe", bool(ffprobe), "FFprobe is required to validate video output before any AI upload")
    if ffmpeg:
        try:
            proc = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                                  capture_output=True, text=True, timeout=8, check=False)
            add("h264", proc.returncode == 0 and "libx264" in proc.stdout,
                "FFmpeg needs the libx264 encoder for MP4 output")
        except (OSError, subprocess.TimeoutExpired):
            add("h264", False, "Unable to verify FFmpeg libx264 encoder")
    add("mss", dependency_exists("mss"), "Install the mss screenshot library")
    if wants_ai or wants_video_ai:
        add("google-genai", dependency_exists("google.genai"),
            "Install google-genai; video/frames may be uploaded to Gemini")
        add("gemini-key", bool(os.environ.get("GEMINI_API_KEY")),
            "Set GEMINI_API_KEY privately in the Windows environment (value is never printed)")
    if wants_ai or wants_sweep:
        add("pillow", dependency_exists("PIL"),
            "Install Pillow for real frame novelty/loop detection")
        add("osc", True,
            "Enable OSC in VRChat's Action Menu; OSC write-only status cannot be verified here",
            essential=False)
    if check_window and windows:
        try:
            try:
                from scripts.windows_vrchat_inspector import get_window
            except ModuleNotFoundError:
                from windows_vrchat_inspector import get_window
            hwnd, dimensions = get_window("VRChat")
            add("vrchat-window", bool(hwnd and dimensions.get("width", 0) >= 320),
                "Exactly one visible official VRChat window must be open; the World must be entered manually")
        except Exception:
            add("vrchat-window", False,
                "VRChat window not detected. Open the client and enter a private instance first.")
    add("privacy", True,
        "Private instance and recording/participant permission must be confirmed by the operator",
        essential=False)
    ok = all(c["ok"] for c in checks if c["required"])
    return {"schemaVersion": 1, "ready": ok, "checks": checks,
            "doesNotAccessVRChatOrCloud": True,
            "note": "A successful preflight does not establish permission for autonomous VRChat use."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai-explore", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--analyze-video", action="store_true")
    parser.add_argument("--no-window-check", action="store_true")
    args = parser.parse_args(argv)
    result = preflight(wants_ai=args.ai_explore, wants_video_ai=args.analyze_video,
                       check_window=not args.no_window_check, wants_sweep=args.sweep)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
