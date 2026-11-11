#!/usr/bin/env python3
"""Observe a private VRChat club's dimming -> stable brightening without OSC.

Dry-run is inert. Live observation needs an operator, a manually joined
private World, rights confirmation, live World log guard and emergency hotkey.
Only one private recovered screenshot and numeric illumination data are saved.
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
    from scripts.inspection_world_log import corroborate_world, MAX_ACTIVE_SESSION_AGE_SECONDS
    from scripts.inspection_session_guard import WorldSessionGuard
    from scripts.inspection_emergency_stop import EmergencyStop
    from scripts.windows_vrchat_inspector import get_window, is_active, screenshot_png
    from scripts.auto_process_interior_queue import ROOT, atomic_json
except ModuleNotFoundError:
    from inspection_light_cycle import LightCycleTracker, sample_lighting
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


def observe_cycle(*, capture_png, still_safe, wait, max_samples: int) -> dict:
    """One-second spaced observations; still_safe must enforce focus+guards.

    No OSC input ever. Return screenshot bytes ONLY after a full stable
    dark-to-recovered cycle. Light changes never verify walkable geometry.
    """
    if type(max_samples) is not int or not 1 <= max_samples <= MAX_SECONDS:
        raise ValueError("invalid-observation-count")
    tracker = LightCycleTracker()
    samples = []
    recovered_png = None
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
        result = tracker.observe(metrics)
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
    }


def run_live(*, world_id: str, seconds: int, out_dir: Path,
             focus_seconds: float = FOCUS_SECONDS) -> dict:
    dest = validate_request(world_id, seconds, out_dir)
    if sys.platform != "win32":
        raise ValueError("windows-required")
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
        observation = observe_cycle(
            capture_png=lambda: screenshot_png(hwnd, area),
            still_safe=safe, wait=stop.wait, max_samples=seconds)
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
    data = {
        "schemaVersion": 1,
        "status": "recovered-stable-light-observed" if stable else "lighting-cycle-not-confirmed",
        "worldId": world_id,
        "source": "local-supervised-stationary-light-cycle",
        "completedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "observationSecondsMaximum": seconds,
        "lightingCycle": observation["state"],
        "luminanceSamples": observation["samples"],
        "screenshot": (
            {"file": "recovery.png",
             "sha256": hashlib.sha256(recovered).hexdigest()}
            if stable else None),
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
        if stable:
            (output / "recovery.png").write_bytes(recovered)
        atomic_json(output / "lighting-cycle.json", data)
    except OSError:
        return {"status": "stopped", "reason": "local-output-failed",
                "screenshotsSaved": 0, "movementCommandsSent": 0,
                "autonomousMovementRestarted": False}
    return {
        "status": data["status"], "lightCycle": observation["state"],
        "reportFile": str(output / "lighting-cycle.json"),
        "recoveryImage": str(output / "recovery.png") if stable else None,
        "screenshotsSaved": 1 if stable else 0,
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
            }, ensure_ascii=False, indent=2))
            return 0
        if not all((
            args.confirm_private_instance, args.confirm_recording_rights,
            args.confirm_platform_authorization, args.acknowledge_automation_risk,
        )):
            raise ValueError("live-requires-private-rights-authorization-and-risk-ack")
        output = run_live(world_id=args.world_id, seconds=args.seconds,
                          out_dir=destination)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["status"] in (
        "recovered-stable-light-observed", "lighting-cycle-not-confirmed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
