"""Suggest a private, *unverified* bright-view frame after dark club lighting.

This is a luminance-only opportunity, never proof of visibility, a complete
light cycle, safe movement or DJ equipment. Strobes and overexposure remain
possible. No I/O, OSC, Gemini or uploads.
"""
from __future__ import annotations

import statistics

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
# PNGs can be up to 10 MB each. Never retain an unbounded live-video history.
MAX_HELD_FRAMES = 6
SELECTION_POLICY = "longest-bright-run-then-lowest-luma-spread"


class BriefBrightWindow:
    """Prefer sustained brightness over an isolated peak, review only.

    Eligibility: a frame <=30 preceded a run of at least two consecutive
    frames with median >=45 and near-black fraction <.92. Rank candidates
    first by consecutive run length, then by lower within-run luminance
    spread, then by run's median luminance. Choose an image nearest the
    run median from at most the last MAX_HELD_FRAMES candidate PNGs.
    Never infer what the image contains.
    """

    def __init__(self):
        self.samples = 0
        self.first_dark_sample = None
        self.best_image = None
        self.best_candidate = None
        self.pairs_seen = 0
        self._best_rank = None
        self._run_start = None
        self._run_luma = []
        self._recent_frames = []

    def observe(self, metrics: dict, png: bytes | None = None) -> None:
        median, black = _check_sample(metrics)
        self.samples += 1
        if self.first_dark_sample is None and median <= DARK_CONTEXT_MAX_MEDIAN:
            self.first_dark_sample = self.samples

        eligible = median >= BASELINE_MIN_MEDIAN and black < MAX_VALID_NEAR_BLACK
        if not eligible:
            self._run_start = None
            self._run_luma = []
            self._recent_frames = []
            return

        if self._run_start is None:
            self._run_start = self.samples
        self._run_luma.append(median)
        self._recent_frames.append((self.samples, median, black, png))
        if len(self._recent_frames) > MAX_HELD_FRAMES:
            self._recent_frames.pop(0)

        run_length = len(self._run_luma)
        if (run_length < MIN_CONSECUTIVE_BRIGHT or
                self.first_dark_sample is None or
                self.first_dark_sample >= self._run_start):
            return

        self.pairs_seen += 1
        spread = max(self._run_luma) - min(self._run_luma)
        run_median = float(statistics.median(self._run_luma))
        # Never rank an isolated 186-luma peak ahead of a longer lit window.
        rank = (run_length, -spread, run_median)
        if self._best_rank is not None and rank <= self._best_rank:
            return

        # Choose a representative, not necessarily the brightest, retained
        # frame; prefer the brighter frame only if equally close to median.
        selected = min(
            self._recent_frames,
            key=lambda frame: (abs(frame[1] - run_median), -frame[1], frame[0]),
        )
        index, level, fraction, image = selected
        self.best_candidate = {
            "candidateSample": index,
            "brightPairSamples": [self.samples - 1, self.samples],
            "precedingDarkSample": self.first_dark_sample,
            "medianLuma": level,
            "nearBlackFraction": fraction,
            "brightRunSamples": [self._run_start, self.samples],
            "brightRunLength": run_length,
            "brightRunMedianLuma": round(run_median, 3),
            "brightRunLumaSpread": round(spread, 3),
            "representativeFrameLimitedToLastSamples": MAX_HELD_FRAMES,
            "selectionPolicy": SELECTION_POLICY,
        }
        self._best_rank = rank
        self.best_image = image

    def summary(self) -> dict:
        return {
            "status": "brief-brightness-opportunity" if self.best_candidate
                      else "no-brief-brightness-opportunity",
            "samplesObserved": self.samples,
            "eligibleBrightPairsSeen": self.pairs_seen,
            "candidate": dict(self.best_candidate) if self.best_candidate else None,
            "selectionPolicy": SELECTION_POLICY,
            "requiresHumanVisualReview": True,
            "strobeOrOverexposureNotExcluded": True,
            "lightingCycleVerified": False,
            "safeToMoveOrResumeAutomation": False,
            "djEquipmentVerified": False,
        }
