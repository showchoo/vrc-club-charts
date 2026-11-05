"""Offline checker for an owner-installed Udon video-player probe.

Only examines explicitly supplied LOCAL logs. Never operates VRChat, reads
accounts, uploads telemetry, or asserts audible / live DJ playback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import ROOT, atomic_json
    from scripts.evaluate_interior_video import WORLD_ID
except ModuleNotFoundError:
    from auto_process_interior_queue import ROOT, atomic_json
    from evaluate_interior_video import WORLD_ID

TOKEN = re.compile(r"[A-Za-z0-9_-]{8,32}\Z")
COMPONENT = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
EVENTS = frozenset(("begin", "ready", "start", "play", "pause",
                    "sample", "error", "end", "stop", "privacy_stop"))
PATTERN = re.compile(
    r"VCCDJPROBE\|v=1\|session=([A-Za-z0-9_-]+)"
    r"\|world=(wrld_[0-9a-fA-F-]+)\|component=([A-Za-z0-9_-]+)"
    r"\|event=([a-z_]+)\|ms=(\d+)\|vms=(-?\d+)"
    r"\|players=(\d+)\|code=(-?\d+)(?!\w)"
)


def extract(path: Path, *, session: str, world: str, component: str) -> tuple[list[dict], str]:
    if not TOKEN.fullmatch(session) or not COMPONENT.fullmatch(component):
        raise ValueError("Invalid owner test session or component identifier")
    if not WORLD_ID.fullmatch(world):
        raise ValueError("Invalid World ID")
    path = path.expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 50_000_000:
        raise ValueError("Expected local output log under 50 MB")
    hash_value = hashlib.sha256()
    events = []
    with path.open("rb") as stream:
        for line in stream:
            hash_value.update(line)
            if b"VCCDJPROBE|" not in line:
                continue
            match = PATTERN.search(line.decode("utf-8", errors="replace"))
            if not match:
                continue
            token, wid, cid, event, ms, vms, players, code = match.groups()
            if (token, wid, cid) != (session, world, component):
                continue
            if event not in EVENTS or len(events) >= 100:
                raise ValueError("Unknown or excessive player events")
            elapsed, playback, count, err = map(int, (ms, vms, players, code))
            if not (0 <= elapsed <= 65_000 and -1 <= playback <= 36_000_000
                    and 0 <= count <= 100 and -1000 <= err <= 1000):
                raise ValueError("Invalid player event values")
            events.append({"event": event, "ms": elapsed,
                           "vms": playback, "players": count, "code": err})
    return events, hash_value.hexdigest()


def assess(events: list[dict]) -> dict:
    labels = [e["event"] for e in events]
    defects = []
    if not events or labels.count("begin") != 1 or labels[0] != "begin":
        defects.append("missing_or_multiple_begin")
    if any(b["ms"] < a["ms"] for a, b in zip(events, events[1:])):
        defects.append("clock_reversal")
    if any(e["players"] != 1 for e in events) or "privacy_stop" in labels:
        defects.append("participant_count_mismatch")
    if "error" in labels:
        defects.append("video_error")
    if "pause" in labels:
        defects.append("playback_interrupted")
    if not all(x in labels for x in ("ready", "start", "play")):
        defects.append("player_events_incomplete")
    end_count = labels.count("stop") + labels.count("end")
    if end_count != 1 or labels[-1] not in ("stop", "end"):
        defects.append("invalid_test_end")
    samples = [(i, e) for i, e in enumerate(events)
               if e["event"] == "sample" and e["vms"] >= 0]
    progress = False
    if len(samples) >= 3:
        before, after = samples[0][1], samples[-1][1]
        elapsed = after["ms"] - before["ms"]
        distance = after["vms"] - before["vms"]
        monotonic = all(
            b["vms"] + 200 >= a["vms"]
            for (_, a), (_, b) in zip(samples, samples[1:])
        )
        progress = elapsed >= 1500 and distance >= 2000 and monotonic and (
            0.45 <= distance / elapsed <= 1.5
        )
        first_index = samples[0][0]
        if not all(x in labels[:first_index] for x in ("ready", "start", "play")):
            progress = False
    if not progress:
        defects.append("playback_clock_not_verified")
    complete = not defects
    return {
        "schemaVersion": 1,
        "status": "local_player_clock_observed" if complete else "inconclusive",
        "reasonCodes": defects,
        "eventCount": len(events), "clockSamples": len(samples),
        "eventSequenceObserved": complete,
        "playbackClockAdvanced": complete and progress,
        "creatorInstrumented": True,
        "independentlyAuthenticated": False,
        "videoPixelsVerified": False, "audioVerified": False,
        "liveStreamVerified": False, "controlsVerified": False,
        "equipmentFunctionalityVerified": False, "rankingEligible": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--component", default="screen01")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        out = args.out.expanduser().resolve()
        if out.is_relative_to(ROOT) or out.exists():
            raise ValueError("Use a new private output path outside the Git repository")
        events, digest = extract(args.log, session=args.session,
                                 world=args.world, component=args.component)
        result = assess(events)
        result.update(worldId=args.world, componentId=args.component,
                      session=args.session, logSha256=digest)
        atomic_json(out, result)
        print(json.dumps({"status": result["status"], "report": str(out),
                          "equipmentFunctionalityVerified": False}))
        return 0 if result["status"] == "local_player_clock_observed" else 1
    except (ValueError, OSError) as exc:
        parser.exit(2, "ERROR: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
