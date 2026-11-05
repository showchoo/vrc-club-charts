#!/usr/bin/env python3
"""Join operator-attested, LOCAL DJ player event and audio test observations.

This cannot authenticate the actual VRChat recording source, time-align an
arbitrary audio file with Udon events, or establish live-stream functionality.
It NEVER controls VRChat, sends network traffic, or changes public rankings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.analyze_creator_dj_probe import extract, assess
    from scripts.dj_audio_playback_test import (digest, read_tone_pattern,
                                                MAX_CAPTURE_SIZE)
    from scripts.auto_process_interior_queue import ROOT
except ModuleNotFoundError:
    from analyze_creator_dj_probe import extract, assess
    from dj_audio_playback_test import digest, read_tone_pattern, MAX_CAPTURE_SIZE
    from auto_process_interior_queue import ROOT


class InspectionEvidenceError(ValueError):
    """A private test is missing rights, provenance, or valid evidence."""


def _existing_local_file(path: Path, max_bytes: int) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink():
        raise InspectionEvidenceError("Input cannot be a symlink")
    source = path.resolve(strict=True)
    if not source.is_file() or not 0 < source.stat().st_size <= max_bytes:
        raise InspectionEvidenceError("Invalid or oversized local input file")
    return source


def evaluate_session(*, log: Path, session: str, world: str, component: str,
                     reference: Path, capture: Path,
                     recording_rights_confirmed: bool,
                     same_session_attested: bool) -> dict:
    if not recording_rights_confirmed:
        raise InspectionEvidenceError("Consent for the private recording is required")
    if not same_session_attested:
        raise InspectionEvidenceError("Operator must link this capture to the test session")

    log_path = _existing_local_file(log, 50_000_000)
    original = _existing_local_file(reference, MAX_CAPTURE_SIZE)
    recorded = _existing_local_file(capture, MAX_CAPTURE_SIZE)
    if original == recorded:
        raise InspectionEvidenceError("Reference and recording must be separate files")

    log_events, log_sha = extract(log_path, session=session, world=world,
                                  component=component)
    player = assess(log_events)
    source_sha = digest(original)
    capture_sha = digest(recorded)
    if source_sha == capture_sha:
        raise InspectionEvidenceError("Recording cannot be a byte-identical source copy")

    # The reference is explicitly verified before interpreting the capture.
    source_audio = read_tone_pattern(original)
    if not source_audio["matched"]:
        raise InspectionEvidenceError("Reference has no valid original four-tone test audio")
    recorded_audio = read_tone_pattern(recorded)
    observed_player = player["status"] == "local_player_clock_observed"
    observed_audio = recorded_audio["matched"]

    # Even both positive signals do not independently establish that the
    # matching sound arose from this VRChat World or the same test session.
    return {
        "schemaVersion": 1,
        "status": ("operator_linked_local_observations"
                   if observed_player and observed_audio else "inconclusive"),
        "worldId": world,
        "componentId": component,
        "sessionToken": session,
        "sourceHashes": {
            "vrchatOutputLogSha256": log_sha,
            "referenceVideoSha256": source_sha,
            "operatorSuppliedRecordingSha256": capture_sha,
        },
        "observations": {
            "playerEventSequenceAndClockObserved": observed_player,
            "fourToneAudioPatternInSeparateRecording": observed_audio,
            "playerEventCount": player["eventCount"],
            "playerClockSampleCount": player["clockSamples"],
            "playerReasonCodes": player["reasonCodes"],
            "recordedToneFrequenciesHz": recorded_audio["frequenciesDetected"],
        },
        "attestations": {
            "privateRecordingRightsAndParticipantConsent": True,
            "recordingBelongsToSameTestSession": True,
        },
        "proofLimitations": [
            "Session association is operator-attested, not cryptographically authenticated",
            "Separate matching audio could have originated outside VRChat",
            "Udon video player clock is not proof of rendered video or audible output",
            "Neither signal measures real-time DJ livestream or control operations",
        ],
        "vrchatClientOriginIndependentlyAuthenticated": False,
        "audioOutputIndependentlyVerified": False,
        "videoPixelsVerified": False,
        "liveDjStreamingVerified": False,
        "controlsVerified": False,
        "equipmentFunctionalityVerified": False,
        "rankingEligible": False,
        "publicSiteChanged": False,
        "networkUsed": False,
    }


def private_report(path: Path, result: dict) -> Path:
    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise InspectionEvidenceError("Report destination cannot be a symlink")
    target = raw.resolve()
    if target.is_relative_to(ROOT):
        raise InspectionEvidenceError("Private reports must stay outside repository")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids clobbering a prior human-approved report.
    with target.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--component", default="screen01")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--recording", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--confirm-private-recording-rights", action="store_true")
    parser.add_argument("--attest-recording-from-session", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = evaluate_session(
            log=args.log, session=args.session, world=args.world,
            component=args.component, reference=args.reference,
            capture=args.recording,
            recording_rights_confirmed=args.confirm_private_recording_rights,
            same_session_attested=args.attest_recording_from_session,
        )
        destination = private_report(args.out, result)
    except (OSError, ValueError) as exc:
        parser.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps({
        "status": result["status"], "report": str(destination),
        "equipmentFunctionalityVerified": False, "rankingEligible": False,
    }, ensure_ascii=False))
    return 0 if result["status"] == "operator_linked_local_observations" else 1


if __name__ == "__main__":
    raise SystemExit(main())
