#!/usr/bin/env python3
"""Opt-in, local-only VRChat OSC button and analog-turn probes.

Runs only against a manually joined private World, after local join-log
corroboration and explicit authorization acknowledgements. Uses a few short
button pulses; cannot verify whether the VRChat camera actually moved.
No recording, screenshots, Gemini API, web requests, or publishing.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import struct
import sys
import threading
import time

try:
    from scripts.inspection_world_log import corroborate_world
    from scripts.inspection_session_guard import WorldSessionGuard
    from scripts.inspection_emergency_stop import EmergencyStop
    from scripts.windows_vrchat_inspector import get_window, is_active, osc_packet
except ModuleNotFoundError:
    from inspection_world_log import corroborate_world
    from inspection_session_guard import WorldSessionGuard
    from inspection_emergency_stop import EmergencyStop
    from windows_vrchat_inspector import get_window, is_active, osc_packet

WORLD_RE = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
LOOK_RIGHT = "/input/LookRight"
LOOK_HORIZONTAL = "/input/LookHorizontal"
PULSES = 3
HOLD_SECONDS = 0.65
GAP_SECONDS = 0.55
FOCUS_SECONDS = 8
ANALOG_PULSES = 2
ANALOG_VALUE = 0.80
ANALOG_HOLD_SECONDS = 0.40


def _pad(value: str) -> bytes:
    raw = value.encode("ascii") + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


def look_right_packet(pressed: int) -> bytes:
    """Send only the official LookRight button, as OSC int 1 or 0."""
    if type(pressed) is not int or pressed not in (0, 1):
        raise ValueError("LookRight must be integer 1 or 0")
    return _pad(LOOK_RIGHT) + _pad(",i") + struct.pack(">i", pressed)


def look_horizontal_probe_packet(active: bool) -> bytes:
    """Only 0.80 or 0.00 on the documented LookHorizontal axis.

    This deliberately avoids changing production sweep amplitude until the
    operator confirms actual camera movement on the target client.
    """
    if type(active) is not bool:
        raise ValueError("Analog probe requires an explicit boolean state")
    return osc_packet(LOOK_HORIZONTAL, ANALOG_VALUE if active else 0.0)


class ProbeStopped(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def run_probe(world_id: str, *, focus_seconds: float = FOCUS_SECONDS,
              mode: str = "button") -> dict:
    """Observe focus, World log and emergency stop throughout short pulses."""
    if mode not in ("button", "analog") or not isinstance(mode, str):
        raise ValueError("invalid-probe-mode")
    if sys.platform != "win32":
        raise ValueError("windows-required")
    if not isinstance(world_id, str) or not WORLD_RE.fullmatch(world_id):
        raise ValueError("invalid-world-id")
    if isinstance(focus_seconds, bool) or not isinstance(focus_seconds, (int, float)) or not 0 <= focus_seconds <= FOCUS_SECONDS:
        raise ValueError("invalid-focus-delay")
    pulses_planned = ANALOG_PULSES if mode == "analog" else PULSES
    hold_seconds = ANALOG_HOLD_SECONDS if mode == "analog" else HOLD_SECONDS
    packet = look_horizontal_probe_packet if mode == "analog" else look_right_packet
    joined = corroborate_world(world_id, max_age_seconds=180)
    if joined.get("status") != "corroborated":
        return {"status": "blocked", "reason": "world-log-unconfirmed",
                "pulsesSent": 0, "cameraMotionVerified": False}

    hwnd, _ = get_window("VRChat")
    stop_event = threading.Event()
    world_guard = WorldSessionGuard(
        world_id=world_id, join_fingerprint=joined["joinFingerprint"],
        capture_stop_event=stop_event,
    )
    hotkey = EmergencyStop(stop_event)
    sock = None
    pulses = 0
    reason = None

    def safe() -> bool:
        return not stop_event.is_set() and is_active(hwnd)

    def rest(seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not safe():
                raise ProbeStopped("focus-or-safety-stop")
            stop_event.wait(min(0.05, max(0, deadline - time.monotonic())))

    try:
        if not world_guard.start():
            raise ProbeStopped("world-log-unconfirmed")
        if not hotkey.start():
            raise ProbeStopped("hotkey-monitor-unavailable")
        print("Focus the VRChat window now. The probe starts in 8 seconds.",
              flush=True)
        # The probe is non-invasive until the VRChat window is foreground.
        if stop_event.wait(focus_seconds):
            raise ProbeStopped("focus-or-safety-stop")
        if not safe():
            raise ProbeStopped("vrchat-not-foreground")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for index in range(pulses_planned):
            if not safe():
                raise ProbeStopped("focus-or-safety-stop")
            try:
                sock.sendto(packet(True if mode == "analog" else 1), ("127.0.0.1", 9000))
                rest(hold_seconds)
                pulses += 1
            finally:
                # Release even if focus, hotkey or the log monitor interrupts us.
                sock.sendto(packet(False if mode == "analog" else 0), ("127.0.0.1", 9000))
            if index < pulses_planned - 1:
                rest(GAP_SECONDS)
    except ProbeStopped as exc:
        reason = exc.reason
    except (OSError, RuntimeError, ValueError):
        # Never print WinAPI/UDP exception text, usernames or log data.
        reason = "local-probe-error"
    finally:
        if sock is not None:
            try:
                sock.sendto(packet(False if mode == "analog" else 0), ("127.0.0.1", 9000))
            except OSError:
                reason = reason or "button-release-failed"
            sock.close()
        world_guard.close()
        hotkey.close()

    if world_guard.reason:
        reason = "world-log-monitor-stopped"
    if hotkey.reason:
        reason = ("operator-emergency-hotkey" if hotkey.reason == "operator-emergency-hotkey"
                  else "hotkey-monitor-stopped")
    return {
        "status": "stopped" if reason else "sent-unverified",
        "reason": reason,
        "mode": mode,
        "oscAddress": LOOK_HORIZONTAL if mode == "analog" else LOOK_RIGHT,
        "analogValue": ANALOG_VALUE if mode == "analog" else None,
        "pulsesSent": pulses,
        "cameraMotionVerified": False,
        "oscDeliveryAcknowledged": False,
        "recordedOrUploaded": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-id", required=True)
    parser.add_argument("--live", action="store_true",
                        help="Actually send short, bounded right-turn pulses to local VRChat")
    parser.add_argument("--mode", choices=("button", "analog"), default="button",
                        help="button=LookRight int 1/0; analog=LookHorizontal float 0.8/0")
    parser.add_argument("--confirm-private-instance", action="store_true")
    parser.add_argument("--confirm-platform-authorization", action="store_true")
    parser.add_argument("--acknowledge-automation-risk", action="store_true")
    args = parser.parse_args(argv)
    if not isinstance(args.world_id, str) or not WORLD_RE.fullmatch(args.world_id):
        parser.error("Provide a valid VRChat World ID")
    if not args.live:
        print(json.dumps({
            "status": "dry-run",
            "wouldSend": LOOK_HORIZONTAL if args.mode == "analog" else LOOK_RIGHT,
            "mode": args.mode,
            "value": ANALOG_VALUE if args.mode == "analog" else 1,
            "pulses": ANALOG_PULSES if args.mode == "analog" else PULSES,
            "recordedOrUploaded": False,
        }, indent=2))
        return 0
    if not (args.confirm_private_instance and args.confirm_platform_authorization
            and args.acknowledge_automation_risk):
        parser.error("Live probe requires all three explicit authorization flags")
    try:
        result = run_probe(args.world_id, mode=args.mode)
    except (ValueError, OSError, RuntimeError):
        result = {"status": "blocked", "reason": "local-preflight-error",
                  "pulsesSent": 0, "cameraMotionVerified": False}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["status"] == "sent-unverified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
