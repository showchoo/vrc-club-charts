"""Conservative, *unverified* bright-view opportunity for dark VRChat clubs.

Never a lighting-recovery, path-safety, movement or DJ-equipment detector.
One or two strobe flashes can still fool this heuristic. No I/O or OSC here.
"""
from __future__ import annotations

try:
    from scripts.inspection_light_cycle import (
        BASELINE_MIN_MEDIAN, MAX_VALID_NEAR_BLACK, _check_sample,
    )
except ModuleNotFoundError:
    from inspection_light_cycle import (
        BASELINE_MIN_MEDIAN, MAX_VALID_NEAR_BLACK, _check_sample,
    )

DARK_CONTEXT_MAX_MEDIAN = 30.0
MIN_CONSECUTIVE_BRIGHT = 2


class BriefBrightWindow:
    """Select at most one locally held PNG after a dark->two-bright sequence.

    Unlike a stable lighting cycle, a pair can have arbitrary brightness spread.
    The saved candidate is for human visual review only, not safe auto-resume.
    """

    def __init__(self):
        self.samples = 0
        self.first_dark_sample = None
        self.previous_bright = None
        self.best_image = None
        self.best_candidate = None
        self.pairs_seen = 0

    def observe(self, metrics: dict, png: bytes | None = None) -> None:
        median, black = _check_sample(metrics)
        self.samples += 1
        if self.first_dark_sample is None and median <= DARK_CONTEXT_MAX_MEDIAN:
            self.first_dark_sample = self.samples
        bright = median >= BASELINE_MIN_MEDIAN and black < MAX_VALID_NEAR_BLACK
        if bright and self.previous_bright is not None and self.first_dark_sample is not None:
            self.pairs_seen += 1
            previous_index, previous_median, previous_black, previous_image = self.previous_bright
            # A brighter sample is a *review candidate*, not proof of visual
            # detail. Preserve it only in volatile memory until all guards pass.
            if previous_median >= median:
                selected = (previous_index, previous_median, previous_black, previous_image)
            else:
                selected = (self.samples, median, black, png)
            index, level, fraction, image = selected
            if self.best_candidate is None or level > self.best_candidate["medianLuma"]:
                self.best_candidate = {
                    "candidateSample": index,
                    "brightPairSamples": [previous_index, self.samples],
                    "precedingDarkSample": self.first_dark_sample,
                    "medianLuma": level,
                    "nearBlackFraction": fraction,
                }
                self.best_image = image
        self.previous_bright = (
            (self.samples, median, black, png) if bright else None
        )

    def summary(self) -> dict:
        return {
            "status": "brief-brightness-opportunity" if self.best_candidate
                      else "no-brief-brightness-opportunity",
            "samplesObserved": self.samples,
            "eligibleBrightPairsSeen": self.pairs_seen,
            "candidate": dict(self.best_candidate) if self.best_candidate else None,
            "requiresHumanVisualReview": True,
            "strobeOrOverexposureNotExcluded": True,
            "lightingCycleVerified": False,
            "safeToMoveOrResumeAutomation": False,
            "djEquipmentVerified": False,
        }
