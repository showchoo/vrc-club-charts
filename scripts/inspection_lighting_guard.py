"""Conservative lighting-transition and low-visibility hints for private VRChat frames.

The heuristics identify strong image-wide brightness swings and near-black
frames; they CANNOT determine whether camera motion happened. Moving club
lights, projection screens, bloom, avatars and global day/night cycles can
confound any two-frame visual test. Ambiguity must never certify movement,
clearance, DJ equipment or independent World coverage.
"""
from __future__ import annotations

import io
import statistics

SAMPLE_W = 192
SAMPLE_H = 108
NEAR_BLACK_VALUE = 18
NEAR_BLACK_FRACTION = .96
GLOBAL_MEDIAN_DELTA = 12
GLOBAL_SAME_DIRECTION_FRACTION = .55
GLOBAL_MIN_PER_PIXEL_DELTA = 8


def analyze_luma_pair(before: bytes, after: bytes) -> dict:
    """Pure 8-bit grayscale metric: input arrays must have equal pixel counts."""
    if (not isinstance(before, bytes) or not isinstance(after, bytes) or
            len(before) != len(after) or not 16 <= len(before) <= 50000):
        raise ValueError("Invalid same-size grayscale samples")
    n = len(before)
    dark_before = sum(x <= NEAR_BLACK_VALUE for x in before) / n
    dark_after = sum(x <= NEAR_BLACK_VALUE for x in after) / n
    delta = [int(b) - int(a) for a, b in zip(before, after)]
    median_delta = statistics.median(delta)
    down = sum(x <= -GLOBAL_MIN_PER_PIXEL_DELTA for x in delta) / n
    up = sum(x >= GLOBAL_MIN_PER_PIXEL_DELTA for x in delta) / n
    global_swing = (
        (median_delta <= -GLOBAL_MEDIAN_DELTA and down >= GLOBAL_SAME_DIRECTION_FRACTION)
        or (median_delta >= GLOBAL_MEDIAN_DELTA and up >= GLOBAL_SAME_DIRECTION_FRACTION)
    )
    low_visibility = dark_before >= NEAR_BLACK_FRACTION or dark_after >= NEAR_BLACK_FRACTION
    status = ("low-visibility" if low_visibility else
              "suspected-lighting-transition" if global_swing else
              "no-major-global-lighting-change-detected")
    return {
        "status": status,
        "lightingTransitionSuspected": bool(global_swing),
        "lowVisibilityObserved": bool(low_visibility),
        "medianSignedLumaChange": round(median_delta, 3),
        "fractionPixelsDarkBefore": round(dark_before, 4),
        "fractionPixelsDarkAfter": round(dark_after, 4),
        "fractionPixelsBrightened": round(up, 4),
        "fractionPixelsDimmed": round(down, 4),
        "visualNavigationShouldPause": bool(global_swing or low_visibility),
        "positionOrClearanceVerified": False,
        "lightingHeuristicNotProof": True,
    }


def analyze_png_pair(before_png: bytes, after_png: bytes) -> dict:
    """Private local PNGs only, without uploading or retaining image pixels."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return {"status": "pillow-unavailable",
                "visualNavigationShouldPause": True,
                "positionOrClearanceVerified": False}
    try:
        with Image.open(io.BytesIO(before_png)) as before, Image.open(io.BytesIO(after_png)) as after:
            if (before.size != after.size or
                    not 320 <= before.width <= 3840 or
                    not 240 <= before.height <= 2160):
                return {"status": "mismatched-or-invalid-image-dimensions",
                        "visualNavigationShouldPause": True,
                        "positionOrClearanceVerified": False}
            interp = Image.Resampling.BILINEAR
            a = before.convert("L").resize((SAMPLE_W, SAMPLE_H), interp).tobytes()
            b = after.convert("L").resize((SAMPLE_W, SAMPLE_H), interp).tobytes()
        return analyze_luma_pair(a, b)
    except (OSError, ValueError, UnidentifiedImageError):
        return {"status": "invalid-or-undecodable-image",
                "visualNavigationShouldPause": True,
                "positionOrClearanceVerified": False}


def one_frame_low_light(png: bytes) -> dict:
    """Fail closed on too-dark frames before attempting new AI OSC movement."""
    try:
        from PIL import Image, UnidentifiedImageError
        with Image.open(io.BytesIO(png)) as source:
            if not 320 <= source.width <= 3840 or not 240 <= source.height <= 2160:
                raise ValueError("Invalid screenshot")
            gray = source.convert("L").resize((SAMPLE_W, SAMPLE_H),
                                              Image.Resampling.BILINEAR).tobytes()
        darkness = sum(v <= NEAR_BLACK_VALUE for v in gray) / len(gray)
        return {"status": "low-visibility" if darkness >= NEAR_BLACK_FRACTION else "not-near-black",
                "nearBlackFraction": round(darkness, 4),
                "visualNavigationShouldPause": darkness >= NEAR_BLACK_FRACTION}
    except (ImportError, OSError, ValueError, UnidentifiedImageError):
        return {"status": "image-visibility-unavailable",
                "visualNavigationShouldPause": True}
