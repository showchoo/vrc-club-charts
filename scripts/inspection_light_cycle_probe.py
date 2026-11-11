#!/usr/bin/env python3
"""Observe a private VRChat club's dimming -> stable brightening without OSC.

Dry-run is inert. Live observation needs an operator, a manually joined
private World, rights confirmation, live World log guard and emergency hotkey.
At most one private PNG (recovery, bright candidate or dark diagnostic)
and numeric illumination data are saved.
No player movement, Gemini, public ranking or automatic locomotion restart.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
import threading
import uuid
from pathlib import Path

try:
    from scripts.inspection_light_cycle import LightCycleTracker, sample_lighting
    from scripts.diagnose_light_cycle_report import (analyze_samples,
        is_near_black_capture_sample)
    from scripts.inspection_bright_window import BriefBrightWindow
    from scripts.inspection_world_log import corroborate_world, MAX_ACTIVE_SESSION_AGE_SECONDS
    from scripts.inspection_session_guard import WorldSessionGuard
    from scripts.inspection_emergency_stop import EmergencyStop
    from scripts.windows_vrchat_inspector import get_window, is_active, screenshot_png
    from scripts.auto_process_interior_queue import ROOT, atomic_json
except ModuleNotFoundError:
    from inspection_light_cycle import LightCycleTracker, sample_lighting
    from diagnose_light_cycle_report import (analyze_samples,
        is_near_black_capture_sample)
    from inspection_bright_window import BriefBrightWindow
    from inspection_world_log import corroborate_world, MAX_ACTIVE_SESSION_AGE_SECONDS
    from inspection_session_guard import WorldSessionGuard
    from inspection_emergency_stop import EmergencyStop
    from windows_vrchat_inspector import get_window, is_active, screenshot_png
    from auto_process_interior_queue import ROOT, atomic_json

WORLD_ID = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
MIN_SECONDS = 10
MAX_SECONDS = 120
FOCUS_SECONDS = 8
OBSERVE_INTERVAL_SECONDS = 1.0
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class ObservationStopped(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def validate_request(world_id: str, seconds: int, out_dir: Path) -> Path:
    if not isinstance(world_id, str) or not WORLD_ID.fullmatch(world_id):
        raise ValueError("invalid-world-id")
    if type(seconds) is not int or not MIN_SECONDS <= seconds <= MAX_SECONDS:
        raise ValueError("observation-seconds-must-be-10-to-120")
    out_dir = out_dir.expanduser()
    if out_dir.is_symlink():
        raise ValueError("output-symlinks-not-allowed")
    path = out_dir.resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("private-output-must-be-outside-repository")
    return path


def observe_cycle(*, capture_png, still_safe, wait, max_samples: int,
                  capture_brief_window: bool = False,
                  capture_dark_diagnostic: bool = False) -> dict:
    """One-second spaced observations; still_safe must enforce focus+guards.

    No OSC input ever. Return screenshot bytes ONLY after a full stable
    dark-to-recovered cycle. Light changes never verify walkable geometry.
    """
    if type(max_samples) is not int or not 1 <= max_samples <= MAX_SECONDS:
        raise ValueError("invalid-observation-count")
    tracker = LightCycleTracker()
    window = BriefBrightWindow() if capture_brief_window else None
    samples = []
    recovered_png = None
    all_near_black = True
    dark_diagnostic_png = None
    for index in range(max_samples):
        if not still_safe():
            raise ObservationStopped("world-focus-or-emergency-stop")
        png = capture_png()
        if (not isinstance(png, bytes) or
                not 100 <= len(png) <= MAX_IMAGE_BYTES):
            raise ObservationStopped("invalid-private-frame")
        if not still_safe():
            raise ObservationStopped("world-focus-or-emergency-stop")
        metrics = sample_lighting(png)
        if capture_dark_diagnostic:
            if is_near_black_capture_sample(metrics) and all_near_black:
                dark_diagnostic_png = png
            else:
                all_near_black = False
                dark_diagnostic_png = None
        result = tracker.observe(metrics)
        if window is not None:
            window.observe(metrics, png)
        samples.append({
            "sample": index + 1,
            "medianLuma": metrics["medianLuma"],
            "nearBlackFraction": metrics["nearBlackFraction"],
            "state": result["status"],
        })
        if result["status"] == "recovered-stable-light":
            if not still_safe():
                raise ObservationStopped("world-focus-or-emergency-stop")
            recovered_png = png
            break
        if index + 1 < max_samples and wait(OBSERVE_INTERVAL_SECONDS):
            raise ObservationStopped("world-focus-or-emergency-stop")
    return {
        "state": tracker.summary(),
        "samples": samples,
        "recoveredPng": recovered_png,
        "briefBrightWindow": window.summary() if window is not None else None,
        "briefBrightPng": window.best_image if window is not None else None,
        "darkDiagnosticPng": (dark_diagnostic_png
                              if capture_dark_diagnostic and all_near_black
                              and len(samples) >= 3 else None),
    }


def run_live(*, world_id: str, seconds: int, out_dir: Path,
             focus_seconds: float = FOCUS_SECONDS,
             capture_brief_window: bool = False,
             capture_dark_diagnostic: bool = False) -> dict:
    dest = validate_request(world_id, seconds, out_dir)
    if sys.platform != "win32":
        raise ValueError("windows-required")
    if type(capture_brief_window) is not bool:
        raise ValueError("invalid-brief-window-opt-in")
    if type(capture_dark_diagnostic) is not bool:
        raise ValueError("invalid-dark-diagnostic-opt-in")
    if (isinstance(focus_seconds, bool) or
            not isinstance(focus_seconds, (int, float)) or
            not math.isfinite(focus_seconds) or
            not 0 <= focus_seconds <= FOCUS_SECONDS):
        raise ValueError("invalid-focus-delay")
    joined = corroborate_world(world_id, max_age_seconds=MAX_ACTIVE_SESSION_AGE_SECONDS)
    if not isinstance(joined, dict) or joined.get("status") != "corroborated":
        return {"status": "blocked", "reason": "local-world-log-unconfirmed",
                "screenshotsSaved": 0, "movementCommandsSent": 0}
    hwnd, area = get_window("VRChat")
    stop = threading.Event()
    world_guard = WorldSessionGuard(
        world_id=world_id, join_fingerprint=joined["joinFingerprint"],
        capture_stop_event=stop)
    emergency = EmergencyStop(stop)
    observation = None
    reason = None

    def safe():
        return not stop.is_set() and is_active(hwnd)

    try:
        if not world_guard.start():
            raise ObservationStopped("world-session-guard-refused")
        if not emergency.start():
            raise ObservationStopped("emergency-stop-unavailable")
        print("Focus the manually joined private VRChat World within 8 seconds.",
              flush=True)
        if stop.wait(focus_seconds) or not safe():
            raise ObservationStopped("world-focus-or-emergency-stop")
        # Window geometry may change while the operator focuses VRChat.
        # Re-read the foreground target before capturing any private pixels.
        focused_hwnd, focused_area = get_window("VRChat")
        if focused_hwnd != hwnd or not safe():
            raise ObservationStopped("world-window-changed-before-capture")
        area = focused_area
        observation = observe_cycle(
            capture_png=lambda: screenshot_png(hwnd, area),
            still_safe=safe, wait=stop.wait, max_samples=seconds,
            capture_brief_window=capture_brief_window,
            capture_dark_diagnostic=capture_dark_diagnostic)
    except ObservationStopped as exc:
        reason = exc.reason
    except KeyboardInterrupt:
        reason = "operator-ctrl-c"
    except Exception:
        # Do not leak window titles, usernames, log contents or image bytes.
        reason = "local-light-observation-error"
    finally:
        try:
            world_guard.close()
        finally:
            emergency.close()

    if emergency.reason:
        reason = ("operator-emergency-hotkey"
                  if emergency.reason == "operator-emergency-hotkey"
                  else "emergency-monitor-stopped")
    elif world_guard.reason:
        reason = "world-log-monitor-stopped"

    if reason is not None:
        return {"status": "stopped", "reason": reason,
                "screenshotsSaved": 0, "movementCommandsSent": 0,
                "autonomousMovementRestarted": False}
    if observation is None:
        return {"status": "stopped", "reason": "observation-incomplete",
                "screenshotsSaved": 0, "movementCommandsSent": 0,
                "autonomousMovementRestarted": False}

    recovered = observation["recoveredPng"]
    stable = observation["state"]["status"] == "recovered-stable-light"
    candidate = observation["briefBrightPng"] if not stable else None
    candidate_found = candidate is not None
    dark_diagnostic = (observation["darkDiagnosticPng"]
                       if not stable and not candidate_found else None)
    dark_diagnostic_found = dark_diagnostic is not None
    image_file = ("recovery.png" if stable else
                  "bright-window-candidate.png" if candidate_found else
                  "dark-capture-diagnostic.png")
    saved_png = recovered if stable else candidate if candidate_found else dark_diagnostic
    final_status = ("recovered-stable-light-observed" if stable else
                    "brief-brightness-opportunity-observed" if candidate_found else
                    "capture-visibility-needs-review" if dark_diagnostic_found else
                    "lighting-cycle-not-confirmed")
    diagnostics = analyze_samples(observation["samples"])
    data = {
        "schemaVersion": 1,
        "status": final_status,
        "worldId": world_id,
        "source": "local-supervised-stationary-light-cycle",
        "completedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "observationSecondsMaximum": seconds,
        "captureRegion": {k: area[k] for k in ("left", "top", "width", "height")},
        "lightingCycle": observation["state"],
        "luminanceSamples": observation["samples"],
        "calibrationDiagnostics": diagnostics,
        "captureVisibilityDiagnostic": diagnostics["captureVisibilityDiagnostic"],
        "briefBrightWindow": observation["briefBrightWindow"],
        "screenshot": (
            {"file": image_file, "sha256": hashlib.sha256(saved_png).hexdigest(),
             "humanReviewRequired": True,
             "stableLightingRecoveryConfirmed": stable,
             "captureVisibilityVerified": False}
            if saved_png is not None else None),
        "privateLocalOnly": True,
        "recordingAndParticipantRightsOperatorAttested": True,
        "movementCommandsSent": 0,
        "autonomousMovementRestarted": False,
        "collisionSafetyVerified": False,
        "independentPositionVerified": False,
        "djBoothLocated": False,
        "equipmentFunctionalityVerified": False,
        "publiclyShareable": False,
        "rankingEligible": False,
        "externalUploads": False,
    }
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = dest / f"{world_id}_{stamp}_{uuid.uuid4().hex[:10]}"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        output.mkdir(exist_ok=False)
        if saved_png is not None:
            (output / image_file).write_bytes(saved_png)
        atomic_json(output / "lighting-cycle.json", data)
    except OSError:
        return {"status": "stopped", "reason": "local-output-failed",
                "screenshotsSaved": 0, "movementCommandsSent": 0,
                "autonomousMovementRestarted": False}
    return {
        "status": data["status"], "lightCycle": observation["state"],
        "calibrationDiagnostics": data["calibrationDiagnostics"],
        "briefBrightWindow": data["briefBrightWindow"],
        "captureVisibilityDiagnostic": data["captureVisibilityDiagnostic"],
        "captureRegion": data["captureRegion"],
        "reportFile": str(output / "lighting-cycle.json"),
        "recoveryImage": str(output / "recovery.png") if stable else None,
        "brightWindowImage": str(output / image_file) if candidate_found else None,
        "captureDiagnosticImage": (str(output / "dark-capture-diagnostic.png")
                                   if dark_diagnostic_found else None),
        "screenshotsSaved": 1 if saved_png is not None else 0,
        "movementCommandsSent": 0, "autonomousMovementRestarted": False,
        "rankingEligible": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-id", required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--out-dir", type=Path,
                        default=Path.home() / "Videos" / "VRCClubCharts"
                        / "private-light-recovery")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--capture-bright-window", action="store_true",
                        help="Explicitly opt in to one local unverified bright candidate PNG")
    parser.add_argument("--capture-dark-diagnostic", action="store_true",
                        help="Opt in to one private near-black capture for human comparison")
    parser.add_argument("--confirm-private-instance", action="store_true")
    parser.add_argument("--confirm-recording-rights", action="store_true")
    parser.add_argument("--confirm-platform-authorization", action="store_true")
    parser.add_argument("--acknowledge-automation-risk", action="store_true")
    args = parser.parse_args(argv)
    try:
        destination = validate_request(args.world_id, args.seconds, args.out_dir)
        if not args.live:
            print(json.dumps({
                "status": "dry-run", "worldId": args.world_id,
                "maximumObservationSeconds": args.seconds,
                "screenCaptures": 0, "oscCommandsSent": 0,
                "requiresPrivateWorldAndRightsForLive": True,
                "autonomousMovementRestarted": False,
                "externalNetworkRequests": 0,
                "briefWindowCaptureEnabled": False,
                "darkDiagnosticCaptureEnabled": False,
            }, ensure_ascii=False, indent=2))
            return 0
        if not all((
            args.confirm_private_instance, args.confirm_recording_rights,
            args.confirm_platform_authorization, args.acknowledge_automation_risk,
        )):
            raise ValueError("live-requires-private-rights-authorization-and-risk-ack")
        output = run_live(world_id=args.world_id, seconds=args.seconds,
                          out_dir=destination,
                          capture_brief_window=args.capture_bright_window,
                          capture_dark_diagnostic=args.capture_dark_diagnostic)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] in (
        "recovered-stable-light-observed", "lighting-cycle-not-confirmed",
        "brief-brightness-opportunity-observed",
        "capture-visibility-needs-review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
