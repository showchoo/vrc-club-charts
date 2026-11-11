#!/usr/bin/env python3
"""Read-only lighting calibration diagnostics from an existing private run.

Never opens VRChat, captures a screen, makes OSC packets, calls Gemini, sends
data or alters the original evidence. Reports WHY a three-frame bright
baseline was not established; does not retroactively claim full light-cycle
recovery, path clearance or DJ equipment operation.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import re
from pathlib import Path

try:
    from scripts.inspection_light_cycle import (
        BASELINE_MAX_SPREAD, BASELINE_MIN_MEDIAN, CALIBRATION_SAMPLES,
        MAX_VALID_NEAR_BLACK,
    )
    from scripts.inspection_bright_window import BriefBrightWindow
    from scripts.auto_process_interior_queue import ROOT
except ModuleNotFoundError:
    from inspection_light_cycle import (
        BASELINE_MAX_SPREAD, BASELINE_MIN_MEDIAN, CALIBRATION_SAMPLES,
        MAX_VALID_NEAR_BLACK,
    )
    from inspection_bright_window import BriefBrightWindow
    from auto_process_interior_queue import ROOT

MAX_INPUT_BYTES = 128 * 1024
STATES = frozenset((
    "calibrating", "watching-for-dim", "waiting-for-recovery",
    "recovered-stable-light",
))
SOURCE = "local-supervised-stationary-light-cycle"
WORLD_ID = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")


class DiagnosticError(ValueError):
    """Local report was not a trusted private stationary lighting observation."""


def _safe_number(value: object, lower: float, upper: float) -> float:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not lower <= value <= upper):
        raise DiagnosticError("Malformed or out-of-range luminance sample")
    return float(value)


def analyze_samples(samples: list[dict]) -> dict:
    """Explain baseline failure without weakening any active safety threshold."""
    if not isinstance(samples, list) or not 1 <= len(samples) <= 120:
        raise DiagnosticError("Expected 1-120 local observations")
    medians = []
    black_fractions = []
    states = []
    for index, sample in enumerate(samples, 1):
        if (not isinstance(sample, dict) or
                type(sample.get("sample")) is not int or sample["sample"] != index
                or sample.get("state") not in STATES):
            raise DiagnosticError("Invalid sample index or state")
        medians.append(_safe_number(sample.get("medianLuma"), 0, 255))
        black_fractions.append(_safe_number(sample.get("nearBlackFraction"), 0, 1))
        states.append(sample["state"])
    bright = [v >= BASELINE_MIN_MEDIAN for v in medians]
    visible = [v < MAX_VALID_NEAR_BLACK for v in black_fractions]
    eligible = [a and b for a, b in zip(bright, visible)]
    max_run = run = 0
    for allowed in eligible:
        run = run + 1 if allowed else 0
        max_run = max(max_run, run)
    stable_windows = []
    stable_below_threshold = []
    all_visible_stable_windows = []
    for start in range(len(samples) - CALIBRATION_SAMPLES + 1):
        group = medians[start:start + CALIBRATION_SAMPLES]
        low_black = black_fractions[start:start + CALIBRATION_SAMPLES]
        if (max(group) - min(group) <= BASELINE_MAX_SPREAD and
                all(f < MAX_VALID_NEAR_BLACK for f in low_black)):
            all_visible_stable_windows.append(start + 1)
            if all(v >= BASELINE_MIN_MEDIAN for v in group):
                stable_windows.append(start + 1)
            if all(v < BASELINE_MIN_MEDIAN for v in group):
                stable_below_threshold.append(start + 1)
    baseline_problem = "none-identified"
    if "watching-for-dim" not in states and "waiting-for-recovery" not in states and "recovered-stable-light" not in states:
        if not any(bright):
            baseline_problem = "no-samples-above-minimum-luminance"
        elif not any(visible):
            baseline_problem = "all-samples-near-black"
        elif not any(eligible):
            baseline_problem = "bright-frames-excluded-by-near-black-fraction"
        elif not stable_windows:
            baseline_problem = "no-three-consecutive-eligible-stable-frames"
        else:
            baseline_problem = "state-trace-inconsistent-with-calibration"
    elif "waiting-for-recovery" in states and "recovered-stable-light" not in states:
        baseline_problem = "baseline-acquired-but-full-recovery-unconfirmed"
    elif "watching-for-dim" in states and "waiting-for-recovery" not in states:
        baseline_problem = "baseline-acquired-but-dimming-unconfirmed"
    elif "recovered-stable-light" in states:
        baseline_problem = "lighting-recovery-marked-in-original"

    bright_windows = BriefBrightWindow()
    for original_sample in samples:
        bright_windows.observe(original_sample)

    return {
        "status": "read-only-calibration-diagnostics",
        "briefBrightWindow": bright_windows.summary(),
        "samplesAnalyzed": len(samples),
        "firstSampleState": states[0],
        "lastSampleState": states[-1],
        "originalMinimumMedianLuma": BASELINE_MIN_MEDIAN,
        "originalMaxNearBlackFraction": MAX_VALID_NEAR_BLACK,
        "originalStableFrameRequirement": CALIBRATION_SAMPLES,
        "originalMaxStableLumaSpread": BASELINE_MAX_SPREAD,
        "medianLumaMin": round(min(medians), 3),
        "medianLumaMax": round(max(medians), 3),
        "medianLumaTypical": round(float(statistics.median(medians)), 3),
        "nearBlackFractionMin": round(min(black_fractions), 4),
        "nearBlackFractionMax": round(max(black_fractions), 4),
        "framesAboveCurrentLumaThreshold": sum(bright),
        "framesPassingNearBlackLimit": sum(visible),
        "framesPassingBothConditions": sum(eligible),
        "longestRunPassingBothConditions": max_run,
        "stableThreeFrameWindowsPassingAllConditions": len(stable_windows),
        "stableVisibleWindowsEntirelyBelowLumaThreshold": len(stable_below_threshold),
        "stableVisibleWindowsIgnoringAbsoluteLumaThreshold": len(all_visible_stable_windows),
        "firstStableEligibleWindowStart": stable_windows[0] if stable_windows else None,
        "primaryDiagnostic": baseline_problem,
        "originalReportModified": False,
        "brightnessThresholdsAutomaticallyChanged": False,
        "lightingCycleRetroactivelyVerified": False,
        "cameraMotionOrPathSafetyVerified": False,
        "djBoothOrFunctionalityVerified": False,
        "externalUploads": False,
    }


def read_report(path: Path) -> dict:
    path = path.expanduser()
    if path.is_symlink() or path.name != "lighting-cycle.json":
        raise DiagnosticError("Expected original non-symlink lighting-cycle.json")
    path = path.resolve(strict=True)
    if path.is_relative_to(ROOT) or path.stat().st_size > MAX_INPUT_BYTES:
        raise DiagnosticError("Only bounded private reports outside repository are supported")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(report, dict) or report.get("schemaVersion") != 1 or
            report.get("source") != SOURCE or
            report.get("status") not in ("lighting-cycle-not-confirmed",
                                         "recovered-stable-light-observed",
                                         "brief-brightness-opportunity-observed") or
            report.get("privateLocalOnly") is not True or
            report.get("publiclyShareable") is not False or
            report.get("rankingEligible") is not False or
            report.get("movementCommandsSent") != 0 or
            report.get("autonomousMovementRestarted") is not False or
            report.get("externalUploads") is not False):
        raise DiagnosticError("Report must be an existing private stationary observation")
    world = report.get("worldId")
    if not isinstance(world, str) or WORLD_ID.fullmatch(world) is None:
        raise DiagnosticError("Invalid World identity in lighting report")
    if not path.parent.name.startswith(world + "_"):
        raise DiagnosticError("Lighting report folder does not match World identity")
    if report["status"] == "brief-brightness-opportunity-observed":
        screenshot = report.get("screenshot")
        bright_window = report.get("briefBrightWindow")
        if (not isinstance(screenshot, dict) or
                screenshot.get("file") != "bright-window-candidate.png" or
                screenshot.get("stableLightingRecoveryConfirmed") is not False or
                screenshot.get("humanReviewRequired") is not True or
                not isinstance(bright_window, dict) or
                bright_window.get("status") != "brief-brightness-opportunity" or
                bright_window.get("lightingCycleVerified") is not False or
                bright_window.get("safeToMoveOrResumeAutomation") is not False):
            raise DiagnosticError("Unverified bright frame needs restricted provenance")
        state = report.get("lightingCycle")
    if (not isinstance(state, dict) or
            state.get("status") not in STATES or
            type(state.get("samples")) is not int):
        raise DiagnosticError("Missing original lighting state machine result")
    samples = report.get("luminanceSamples")
    result = analyze_samples(samples)
    if result["samplesAnalyzed"] != state["samples"] or result["lastSampleState"] != state["status"]:
        raise DiagnosticError("Lighting samples are inconsistent with original state")
    return {
        "worldId": world,
        "sourceStatus": report["status"],
        "sourceLightCycleState": state["status"],
        **result,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = read_report(args.report)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
