"""Visual novelty guard for an opt-in, local VRChat camera navigation pilot.

This detects near-identical frames and suggests a bounded recovery turn.
It is not a collision sensor, pose tracker, path planner, or proof of world coverage.
"""
from __future__ import annotations

import hashlib
import io

MAX_STALE_STEPS = 2
MAX_RECOVERIES = 2
DISTANCE_THRESHOLD = 0.018


def signature(png: bytes) -> tuple[int, ...]:
    if not isinstance(png, bytes) or not png:
        raise ValueError("Invalid screenshot bytes")
    try:
        from PIL import Image
    except ImportError:
        # No third-party packages are required by offline unit tests.
        # Exact duplicate frames can still be detected without Pillow.
        return tuple(hashlib.sha256(png).digest())
    try:
        with Image.open(io.BytesIO(png)) as img:
            gray = img.convert("L").resize((16, 9))
            return tuple(gray.getdata())
    except (OSError, ValueError) as exc:
        raise ValueError("Screenshot could not be decoded") from exc


def distance(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    if len(a) != len(b) or not a:
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / (len(a) * 255)


class NavigationGuard:
    """Stop if movement appears stuck despite a small recovery turn."""
    def __init__(self, *, stale_limit=MAX_STALE_STEPS,
                 max_recoveries=MAX_RECOVERIES):
        self.last_signature = None
        self.last_action = None
        self.stale_count = 0
        self.recoveries = 0
        self.sampling_count = 0
        self.total_novel_changes = 0
        self.stale_limit = stale_limit
        self.max_recoveries = max_recoveries

    def decide(self, png: bytes, suggested_action: str) -> tuple[str, str]:
        valid = {"forward", "backward", "turn_left", "turn_right",
                 "strafe_left", "strafe_right", "observe", "stop"}
        if suggested_action not in valid:
            raise ValueError("Invalid movement suggestion")
        now = signature(png)
        self.sampling_count += 1
        if self.last_signature is not None:
            novel = distance(self.last_signature, now) > DISTANCE_THRESHOLD
            if novel:
                self.total_novel_changes += 1
                self.stale_count = 0
                self.recoveries = 0
            elif self.last_action in valid - {"observe", "stop"}:
                self.stale_count += 1
        self.last_signature = now
        if suggested_action == "stop":
            self.last_action = "stop"
            return "stop", "model_requested_stop"
        if self.stale_count >= self.stale_limit:
            self.stale_count = 0
            if self.recoveries >= self.max_recoveries:
                self.last_action = "stop"
                return "stop", "no_visual_progress_after_recovery"
            action = "turn_right" if self.recoveries % 2 == 0 else "turn_left"
            self.recoveries += 1
            self.last_action = action
            return action, "bounded_recovery_turn"
        self.last_action = suggested_action
        return suggested_action, "normal"

    def metrics(self) -> dict:
        return {
            "observedFrames": self.sampling_count,
            "visualChanges": self.total_novel_changes,
            "recoveryTurns": self.recoveries,
            "reliableCollisionDetection": False,
            "independentWorldCoverageVerified": False,
        }
