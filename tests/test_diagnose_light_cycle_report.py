"""Retrospective diagnostics from saved luminance metadata; no screen capture or OSC."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import diagnose_light_cycle_report as diag

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"


def samples(levels, *, black=0.2, state="calibrating"):
    return [
        {"sample": i + 1, "medianLuma": v,
         "nearBlackFraction": black if type(black) in (int, float) else black[i],
         "state": state}
        for i, v in enumerate(levels)
    ]


def fixture(folder: Path, values):
    folder.mkdir(parents=True)
    raw = {
        "schemaVersion": 1, "status": "lighting-cycle-not-confirmed",
        "worldId": WORLD, "source": "local-supervised-stationary-light-cycle",
        "lightingCycle": {"status": values[-1]["state"], "samples": len(values)},
        "luminanceSamples": values,
        "privateLocalOnly": True, "publiclyShareable": False,
        "rankingEligible": False, "movementCommandsSent": 0,
        "autonomousMovementRestarted": False, "externalUploads": False,
    }
    path = folder / "lighting-cycle.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name) / (WORLD + "_20261111T062458Z_0f2ebe8795")

    def test_full_90_second_baseline_failure_from_dark_but_visible_frames(self):
        path = fixture(self.folder, samples([20.0] * 90, black=.5))
        before = path.read_bytes()
        data = diag.read_report(path)
        self.assertEqual(data["samplesAnalyzed"], 90)
        self.assertEqual(data["sourceLightCycleState"], "calibrating")
        self.assertEqual(data["primaryDiagnostic"], "no-samples-above-minimum-luminance")
        self.assertEqual(data["framesAboveCurrentLumaThreshold"], 0)
        self.assertEqual(data["framesPassingNearBlackLimit"], 90)
        self.assertEqual(data["stableVisibleWindowsEntirelyBelowLumaThreshold"], 88)
        self.assertEqual(data["stableVisibleWindowsIgnoringAbsoluteLumaThreshold"], 88)
        self.assertFalse(data["brightnessThresholdsAutomaticallyChanged"])
        self.assertFalse(data["lightingCycleRetroactivelyVerified"])
        self.assertFalse(data["cameraMotionOrPathSafetyVerified"])
        self.assertFalse(data["djBoothOrFunctionalityVerified"])
        self.assertFalse(data["externalUploads"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.folder.iterdir()), [path])


    def test_variable_bright_pairs_are_relevant_but_never_recovered(self):
        levels = [5, 7, 70, 186, 10, 8, 60, 100, 11, 10]
        result = diag.analyze_samples(samples(levels, black=.3))
        self.assertEqual(result["primaryDiagnostic"],
                         "no-three-consecutive-eligible-stable-frames")
        opportunity = result["briefBrightWindow"]
        self.assertEqual(opportunity["status"], "brief-brightness-opportunity")
        self.assertEqual(opportunity["candidate"]["candidateSample"], 4)
        self.assertEqual(opportunity["candidate"]["medianLuma"], 186)
        self.assertFalse(opportunity["lightingCycleVerified"])
        self.assertFalse(opportunity["safeToMoveOrResumeAutomation"])
        self.assertFalse(result["originalReportModified"])


    def test_longer_bright_window_outweighs_shorter_brighter_peak(self):
        values = samples([6, 105, 186, 8, 63, 72, 68, 70, 5], black=.25)
        analysis = diag.analyze_samples(values)
        candidate = analysis["briefBrightWindow"]["candidate"]
        self.assertEqual(candidate["brightRunLength"], 4)
        self.assertEqual(candidate["brightRunSamples"], [5, 8])
        self.assertEqual(candidate["candidateSample"], 7)
        self.assertEqual(candidate["medianLuma"], 68)
        self.assertEqual(candidate["selectionPolicy"],
                         "longest-bright-run-then-lowest-luma-spread")
        self.assertEqual(analysis["primaryDiagnostic"],
                         "no-three-consecutive-eligible-stable-frames")
        self.assertFalse(analysis["originalReportModified"])
        self.assertFalse(analysis["lightingCycleRetroactivelyVerified"])

    def test_new_private_bright_candidate_report_can_be_reanalyzed(self):
        values = samples([5, 7, 70, 120, 9, 10, 60, 90, 7, 8],
                         black=.2)
        path = fixture(self.folder, values)
        report = json.loads(path.read_text(encoding="utf-8"))
        report["status"] = "brief-brightness-opportunity-observed"
        report["briefBrightWindow"] = diag.analyze_samples(values)["briefBrightWindow"]
        report["screenshot"] = {
            "file": "bright-window-candidate.png",
            "sha256": "a" * 64,
            "humanReviewRequired": True,
            "stableLightingRecoveryConfirmed": False,
        }
        path.write_text(json.dumps(report), encoding="utf-8")
        before = path.read_bytes()
        analyzed = diag.read_report(path)
        self.assertEqual(analyzed["sourceStatus"], report["status"])
        self.assertEqual(analyzed["briefBrightWindow"]["status"],
                         "brief-brightness-opportunity")
        self.assertEqual(path.read_bytes(), before)
        report["screenshot"]["stableLightingRecoveryConfirmed"] = True
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(diag.DiagnosticError, "restricted provenance"):
            diag.read_report(path)

    def test_high_but_unstable_lighting_fails_three_frame_baseline(self):
        values = samples([60, 80] * 45, black=.2)
        data = diag.analyze_samples(values)
        self.assertEqual(data["primaryDiagnostic"], "no-three-consecutive-eligible-stable-frames")
        self.assertEqual(data["framesPassingBothConditions"], 90)
        self.assertEqual(data["longestRunPassingBothConditions"], 90)
        self.assertEqual(data["stableThreeFrameWindowsPassingAllConditions"], 0)

    def test_near_black_pixels_exclude_bright_overlay(self):
        data = diag.analyze_samples(samples([70] * 20, black=.96))
        self.assertEqual(data["primaryDiagnostic"], "all-samples-near-black")
        self.assertEqual(data["framesAboveCurrentLumaThreshold"], 20)
        self.assertEqual(data["framesPassingNearBlackLimit"], 0)

    def test_bright_frames_and_black_rejects_on_the_same_frames(self):
        values = samples([20, 70] * 15, black=[.2, .95] * 15)
        data = diag.analyze_samples(values)
        self.assertEqual(data["primaryDiagnostic"], "bright-frames-excluded-by-near-black-fraction")
        self.assertEqual(data["framesPassingBothConditions"], 0)

    def test_prior_tracker_states_do_not_misidentify_baseline_problem(self):
        values = samples([65] * 15, black=.2, state="watching-for-dim")
        data = diag.analyze_samples(values)
        self.assertEqual(data["primaryDiagnostic"], "baseline-acquired-but-dimming-unconfirmed")
        self.assertEqual(data["stableThreeFrameWindowsPassingAllConditions"], 13)

    def test_reject_tampered_or_public_report(self):
        p = fixture(self.folder, samples([20] * 10))
        raw = json.loads(p.read_text())
        raw["publiclyShareable"] = True
        p.write_text(json.dumps(raw))
        with self.assertRaisesRegex(diag.DiagnosticError, "private stationary"):
            diag.read_report(p)
        raw["publiclyShareable"] = False
        raw["lightingCycle"]["samples"] = 12
        p.write_text(json.dumps(raw))
        with self.assertRaisesRegex(diag.DiagnosticError, "inconsistent"):
            diag.read_report(p)

    def test_reject_malicious_samples_nan_and_wrong_index(self):
        for data in (
            samples([float("nan")] * 10),
            samples([float("inf")] * 10),
            samples([-1] * 10),
            samples([30] * 10, black=1.5),
            samples([22] * 10)[:2] + [{"sample": 100, "medianLuma": 20, "nearBlackFraction": .3, "state": "calibrating"}],
        ):
            with self.subTest(data=data), self.assertRaises(diag.DiagnosticError):
                diag.analyze_samples(data)

    def test_never_calls_vrchat_or_writes_when_cli_runs(self):
        p = fixture(self.folder, samples([20] * 90, black=.4))
        with patch("builtins.print") as output:
            code = diag.main(["--report", str(p)])
        result = json.loads(output.call_args.args[0])
        self.assertEqual(code, 0)
        self.assertEqual(result["primaryDiagnostic"], "no-samples-above-minimum-luminance")
        self.assertEqual(len(list(self.folder.iterdir())), 1)
        self.assertEqual(result["originalReportModified"], False)

    def test_rejects_report_inside_source_repository(self):
        with self.assertRaises((OSError, ValueError)):
            diag.read_report(diag.ROOT / "scripts" / "lighting-cycle.json")


if __name__ == "__main__":
    unittest.main()
