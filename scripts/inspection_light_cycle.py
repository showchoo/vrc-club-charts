"""Lighting fade -> stable recovery observation; never a movement or safety sensor.

A stationary, supervised camera can detect a relative illumination cycle.
No image-only method proves that a path is safe, the camera actually moved,
or DJ equipment is present. Thresholds are provisional and local-only.
"""
from __future__ import annotations

import io
import math
import statistics

CALIBRATION_SAMPLES = 3
DIM_SAMPLES = 2
RECOVERY_SAMPLES = 3
BASELINE_MIN_MEDIAN = 45.0
BASELINE_MAX_SPREAD = 6.0
DIM_RATIO = 0.72
DIM_MIN_ABSOLUTE_DROP = 15.0
RECOVER_RATIO = 0.86
RECOVERY_MAX_SPREAD = 4.0
LOW_VISIBILITY_FRACTION = 0.96
MAX_VALID_NEAR_BLACK = 0.92
WIDTH = 192
HEIGHT = 108


def sample_lighting(png: bytes) -> dict:
    """Read one private screenshot; only numeric luminance metrics leave here."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required for local lighting observation") from exc
    if not isinstance(png, bytes) or not 100 <= len(png) <= 10 * 1024 * 1024:
        raise ValueError("Invalid screenshot bytes")
    try:
        with Image.open(io.BytesIO(png)) as image:
            if image.format != "PNG" or not 320 <= image.width <= 3840 or not 240 <= image.height <= 2160:
                raise ValueError("Not a bounded VRChat PNG frame")
            raw = image.convert("L").resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR).tobytes()
    except (OSError, ValueError) as exc:
        raise ValueError("Local screenshot cannot be inspected") from exc
    median = statistics.median(raw)
    near_black = sum(x <= 18 for x in raw) / len(raw)
    return {
        "medianLuma": round(float(median), 3),
        "meanLuma": round(sum(raw) / len(raw), 3),
        "nearBlackFraction": round(near_black, 4),
    }


def _check_sample(value: dict) -> tuple[float, float]:
    if not isinstance(value, dict):
        raise ValueError("Invalid lighting observation")
    median = value.get("medianLuma")
    near_black = value.get("nearBlackFraction")
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or
           not math.isfinite(x) for x in (median, near_black)):
        raise ValueError("Invalid illumination metrics")
    if not 0 <= median <= 255 or not 0 <= near_black <= 1:
        raise ValueError("Out-of-range illumination metrics")
    return float(median), float(near_black)


class LightCycleTracker:
    """Relative brightness cycle; insufficient evidence always remains unknown."""

    def __init__(self):
        self.status = "calibrating"
        self.baseline = None
        self.samples = 0
        self.calibration = []
        self.dim_streak = 0
        self.stable_recovery = []
        self.darkness_seen = False
        self.recovery_seen = False
        self.dim_confirmed_at = None
        self.recovered_at = None

    def observe(self, metrics: dict) -> dict:
        median, near_black = _check_sample(metrics)
        if self.status == "recovered-stable-light":
            raise ValueError("Light cycle already completed")
        self.samples += 1
        if self.status == "calibrating":
            # Require a stable *lit* baseline; do not pretend a dark starting
            # scene is a verified bright reference.
            if median >= BASELINE_MIN_MEDIAN and near_black < MAX_VALID_NEAR_BLACK:
                self.calibration = (self.calibration + [median])[-CALIBRATION_SAMPLES:]
                if (len(self.calibration) == CALIBRATION_SAMPLES and
                        max(self.calibration) - min(self.calibration) <= BASELINE_MAX_SPREAD):
                    self.baseline = round(float(statistics.median(self.calibration)), 3)
                    self.status = "watching-for-dim"
            else:
                self.calibration = []
        elif self.status == "watching-for-dim":
            enough_dim = (median <= min(self.baseline * DIM_RATIO,
                                       self.baseline - DIM_MIN_ABSOLUTE_DROP)
                          or near_black >= LOW_VISIBILITY_FRACTION)
            self.dim_streak = self.dim_streak + 1 if enough_dim else 0
            if self.dim_streak >= DIM_SAMPLES:
                self.darkness_seen = True
                self.dim_confirmed_at = self.samples
                self.status = "waiting-for-recovery"
                self.stable_recovery = []
        elif self.status == "waiting-for-recovery":
            # Must return near the *original* illuminated baseline, be
            # sufficiently visible, and stay stable over several samples.
            recovered = (median >= max(BASELINE_MIN_MEDIAN,
                                       self.baseline * RECOVER_RATIO)
                         and near_black < MAX_VALID_NEAR_BLACK)
            if recovered:
                self.stable_recovery = (
                    self.stable_recovery + [median])[-RECOVERY_SAMPLES:]
            else:
                self.stable_recovery = []
            if (len(self.stable_recovery) == RECOVERY_SAMPLES and
                    max(self.stable_recovery) - min(self.stable_recovery)
                    <= RECOVERY_MAX_SPREAD):
                self.recovery_seen = True
                self.recovered_at = self.samples
                self.status = "recovered-stable-light"
        return self.summary()

    def summary(self) -> dict:
        return {
            "status": self.status, "samples": self.samples,
            "referenceMedianLuma": self.baseline,
            "dimSeen": self.darkness_seen,
            "dimConfirmedSample": self.dim_confirmed_at,
            "recoverySeen": self.recovery_seen,
            "recoveryConfirmedSample": self.recovered_at,
            "stableRecoverySamples": len(self.stable_recovery),
            "lightingOnly": True,
            "positionOrPathSafetyVerified": False,
            "lightingThresholdsFieldValidated": False,
        }
