#!/usr/bin/env python3
"""One guarded, operator-supervised OSC *position* step in an already joined VRChat World.

Dry-run by default. Live opt-in makes ONE 0.20-second, low-amplitude movement
and captures two local/private frames for visual comparison. It is NOT
autonomous path planning, obstacle avoidance, stairs traversal, or proof of
movement. Does not join worlds, click objects, contact Gemini, or publish.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import threading
import time
import uuid
from pathlib import Path

try:
    from scripts.inspection_world_log import corroborate_world, MAX_ACTIVE_SESSION_AGE_SECONDS
    from scripts.inspection_session_guard import WorldSessionGuard
    from scripts.inspection_emergency_stop import EmergencyStop
    from scripts.inspection_navigation_guard import signature, distance, DISTANCE_THRESHOLD
    from scripts.windows_vrchat_inspector import (
        OscMovement, get_window, is_active, screenshot_png,
    )
    from scripts.auto_process_interior_queue import atomic_json, ROOT
except ModuleNotFoundError:
    from inspection_world_log import corroborate_world, MAX_ACTIVE_SESSION_AGE_SECONDS
    from inspection_session_guard import WorldSessionGuard
    from inspection_emergency_stop import EmergencyStop
    from inspection_navigation_guard import signature, distance, DISTANCE_THRESHOLD
    from windows_vrchat_inspector import OscMovement, get_window, is_active, screenshot_png
    from auto_process_interior_queue import atomic_json, ROOT

STEP_SECONDS = 0.20
SETTLE_SECONDS = 0.30
FOCUS_SECONDS = 8.0
DIRECTIONS = ("forward", "backward", "strafe_left", "strafe_right")
MAX_LOCAL_FRAME_BYTES = 10 * 1024 * 1024


class StepStopped(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def validate_request(world_id: str, direction: str, out_dir: Path) -> Path:
    from re import fullmatch
    if not isinstance(world_id, str) or not fullmatch(
        r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", world_id
    ):
        raise ValueError("invalid-world-id")
    if direction not in DIRECTIONS:
        raise ValueError("invalid-direction")
    if out_dir.is_symlink():
        raise ValueError("output-dir-symlink-not-allowed")
    dest = out_dir.expanduser().resolve()
    if dest.is_relative_to(ROOT):
        raise ValueError("output-must-be-outside-repository")
    return dest


def execute_one_step(*, controller, capture_png, still_safe, wait,
                     direction: str) -> dict:
    """One non-repeating movement pulse with before/after private screenshots.

    The underlying controller clamps the pulse and neutralizes axes in a
    finally block. A change in pixels is NOT proof of distance traveled.
    """
    if direction not in DIRECTIONS:
        raise ValueError("invalid-direction")
    if not still_safe():
        raise StepStopped("unsafe-before-observation")
    before = capture_png()
    if not isinstance(before, bytes) or not 8 <= len(before) <= MAX_LOCAL_FRAME_BYTES:
        raise StepStopped("invalid-before-image")
    if not still_safe():
        raise StepStopped("unsafe-before-movement")
    controller.act(direction, still_safe, duration=STEP_SECONDS)
    if not still_safe() or wait(SETTLE_SECONDS):
        raise StepStopped("unsafe-after-movement")
    after = capture_png()
    if not isinstance(after, bytes) or not 8 <= len(after) <= MAX_LOCAL_FRAME_BYTES:
        raise StepStopped("invalid-after-image")
    if not still_safe():
        raise StepStopped("unsafe-after-observation")
    before_signature, after_signature = signature(before), signature(after)
    delta = distance(before_signature, after_signature)
    if not isinstance(delta, (int, float)) or not math.isfinite(delta):
        raise StepStopped("invalid-visual-comparison")
    return {
        "beforePng": before, "afterPng": after,
        "visualChangeDetected": bool(delta > DISTANCE_THRESHOLD),
        "visualDifferenceScore": round(delta, 5),
    }


def run_live(*, world_id: str, direction: str, out_dir: Path,
             focus_seconds: float = FOCUS_SECONDS) -> dict:
    out_dir = validate_request(world_id, direction, out_dir)
    if sys.platform != "win32":
        raise ValueError("windows-required")
    if (isinstance(focus_seconds, bool) or not isinstance(focus_seconds, (int, float))
            or not math.isfinite(focus_seconds) or not 0 <= focus_seconds <= FOCUS_SECONDS):
        raise ValueError("invalid-focus-delay")
    joined = corroborate_world(world_id, max_age_seconds=MAX_ACTIVE_SESSION_AGE_SECONDS)
    if not isinstance(joined, dict) or joined.get("status") != "corroborated":
        return {"status": "blocked", "reason": "local-private-world-log-unconfirmed",
                "stepsAttempted": 0, "positionVerified": False}
    hwnd, area = get_window("VRChat")
    stop = threading.Event()
    world_guard = WorldSessionGuard(
        world_id=world_id, join_fingerprint=joined["joinFingerprint"],
        capture_stop_event=stop)
    emergency = EmergencyStop(stop)
    controller = None
    attempted = 0
    outcome = None
    reason = None
    release_failed = False

    def safe() -> bool:
        return not stop.is_set() and is_active(hwnd)

    try:
        if not world_guard.start():
            raise StepStopped("local-world-log-monitor-unconfirmed")
        if not emergency.start():
            raise StepStopped("emergency-hotkey-monitor-unavailable")
        print("Switch to the manually joined private VRChat World now (8 seconds).",
              flush=True)
        if stop.wait(focus_seconds):
            raise StepStopped("focus-or-safety-stop")
        if not safe():
            raise StepStopped("vrchat-not-foreground")
        controller = OscMovement()
        controller.neutral()
        # Never retry a step: a screenshot cannot establish collision or pose.
        attempted = 1
        outcome = execute_one_step(
            controller=controller,
            capture_png=lambda: screenshot_png(hwnd, area),
            still_safe=safe, wait=stop.wait, direction=direction)
        if not safe():
            raise StepStopped("focus-or-safety-stop")
    except StepStopped as exc:
        reason = exc.reason
    except KeyboardInterrupt:
        reason = "operator-ctrl-c"
    except Exception:
        # Never display window titles, image bytes, OSC payloads, or local
        # client-log error text in output.
        reason = "guarded-position-step-failed"
    finally:
        if controller is not None:
            try:
                controller.close()  # Neutralizes all three OSC axes.
            except Exception:
                release_failed = True
        try:
            world_guard.close()  # Final World log check.
        finally:
            emergency.close()

    if release_failed:
        reason = "osc-neutral-release-failed"
    elif emergency.reason:
        reason = ("operator-emergency-hotkey" if
                  emergency.reason == "operator-emergency-hotkey" else
                  "emergency-monitor-stopped")
    elif world_guard.reason:
        reason = "world-log-monitor-stopped"

    base = {
        "schemaVersion": 1, "worldId": world_id, "direction": direction,
        "stepSeconds": STEP_SECONDS, "stepCountMax": 1,
        "stepsAttempted": attempted,
        "source": "local-osc-private-single-position-step",
        "positionVerified": False, "distanceMeters": None,
        "collisionSafetyVerified": False, "stairsTraversed": False,
        "djBoothLocated": False, "equipmentFunctionalityVerified": False,
        "noPublicRankingChanges": True, "noNetworkOrCloudUploads": True,
    }
    if reason is not None or outcome is None:
        return {**base, "status": "stopped", "reason": reason or "incomplete"}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = out_dir / (world_id + "_" + stamp + "_" + uuid.uuid4().hex[:10])
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        folder.mkdir(exist_ok=False)
        before_file, after_file = folder / "before.png", folder / "after.png"
        before_file.write_bytes(outcome["beforePng"])
        after_file.write_bytes(outcome["afterPng"])
        report = {**base, "status": "sent-unverified",
                  "visualChangeDetected": outcome["visualChangeDetected"],
                  "visualDifferenceScore": outcome["visualDifferenceScore"],
                  "frames": [
                      {"file": "before.png",
                       "sha256": hashlib.sha256(outcome["beforePng"]).hexdigest()},
                      {"file": "after.png",
                       "sha256": hashlib.sha256(outcome["afterPng"]).hexdigest()},
                  ],
                  "privateLocalOnly": True}
        atomic_json(folder / "position-step.json", report)
    except (OSError, ValueError):
        return {**base, "status": "stopped", "reason": "local-evidence-write-failed"}
    # Return only ordinary local paths, never image contents.
    return {**report, "reportFile": str(folder / "position-step.json"),
            "before": str(before_file), "after": str(after_file)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-id", required=True)
    parser.add_argument("--direction", choices=DIRECTIONS, default="forward")
    parser.add_argument("--out-dir", type=Path,
                        default=Path.home() / "Videos" / "VRCClubCharts"
                        / "private-position-probes")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-private-instance", action="store_true")
    parser.add_argument("--confirm-recording-rights", action="store_true")
    parser.add_argument("--confirm-flat-clear-path", action="store_true")
    parser.add_argument("--confirm-platform-authorization", action="store_true")
    parser.add_argument("--acknowledge-automation-risk", action="store_true")
    args = parser.parse_args(argv)
    try:
        dest = validate_request(args.world_id, args.direction, args.out_dir)
        if not args.live:
            print(json.dumps({
                "status": "dry-run", "networkRequestsMade": 0,
                "oscPacketsSent": 0, "framesRecorded": 0,
                "worldId": args.world_id, "direction": args.direction,
                "stepSeconds": STEP_SECONDS,
                "requiresOperatorSupervision": True,
                "stairOrObstacleNavigation": False,
            }, indent=2))
            return 0
        if not all((
            args.confirm_private_instance, args.confirm_recording_rights,
            args.confirm_flat_clear_path, args.confirm_platform_authorization,
            args.acknowledge_automation_risk,
        )):
            raise ValueError("live-requires-private-rights-clear-flat-path-platform-authorization-and-risk-ack")
        result = run_live(world_id=args.world_id, direction=args.direction, out_dir=dest)
    except (ValueError, OSError) as exc:
        parser.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "sent-unverified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
