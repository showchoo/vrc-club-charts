#!/usr/bin/env python3
"""Local, operator-gated multi-World inspection queue.

This does not launch/join VRChat Worlds, use VRChat APIs, or publish scores.
Each World is entered manually and explicitly acknowledged before recording.
State and media stay outside the repository; there is no unattended loop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Callable

try:
    from scripts.inspection_capture_integrity import (
        CaptureIntegrityError, capture_integrity, verify_capture_integrity,
    )
except ModuleNotFoundError:
    from inspection_capture_integrity import (
        CaptureIntegrityError, capture_integrity, verify_capture_integrity,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
WORLD_ID_RE = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
MAX_WORLDS = 25
SUCCESS = {"capture-complete", "private-analysis-complete"}


def world_launch_url(world_id: str) -> str:
    """Return only VRChat's public web launch page, never a client-protocol jump."""
    if not isinstance(world_id, str) or not WORLD_ID_RE.fullmatch(world_id):
        raise ValueError("Invalid World ID for launch page")
    return "https://vrchat.com/home/launch?worldId=" + world_id


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(REPO_ROOT):
        raise ValueError("Private plans, state and captures must be outside the Git repository")
    return resolved


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".vcc-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(payload, writer, ensure_ascii=False, indent=2)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def validate_plan(data: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("Unsupported inspection plan schema")
    rows = data.get("worlds")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_WORLDS:
        raise ValueError("Plan must contain 1 to 25 Worlds")
    seen = set()
    clean = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid World entry")
        world_id = row.get("worldId")
        if not isinstance(world_id, str) or not WORLD_ID_RE.fullmatch(world_id):
            raise ValueError("Invalid World ID in plan")
        if world_id in seen:
            raise ValueError("Duplicate World ID in plan")
        seen.add(world_id)
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Invalid World display name")
        clean.append({"worldId": world_id, "name": name.strip()})
    return clean


def plan_from_catalog(catalog_path: Path, limit: int = 5) -> dict:
    if type(limit) is not int or not 1 <= limit <= MAX_WORLDS:
        raise ValueError("--limit must be between 1 and 25")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError("World catalog must be a list")
    worlds, seen = [], set()
    for item in catalog:
        if not isinstance(item, dict):
            continue
        wid = item.get("id")
        if (not isinstance(wid, str) or not WORLD_ID_RE.fullmatch(wid)
                or item.get("releaseStatus") != "public"
                or item.get("chartEligible") is not True or wid in seen):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        seen.add(wid)
        worlds.append({"worldId": wid, "name": name.strip()[:200]})
        if len(worlds) == limit:
            break
    if not worlds:
        raise ValueError("No eligible public Worlds found in catalog")
    plan = {"schemaVersion": 1, "generatedAt": utc_now(), "worlds": worlds}
    validate_plan(plan)
    return plan


def plan_digest(worlds: list[dict]) -> str:
    ids = [row["worldId"] for row in worlds]
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_completed_entry(captures: Path, world_id: str, entry: dict) -> dict:
    """Require a consistent success result plus matching, intact local media."""
    result = entry.get("result")
    evidence = entry.get("captureIntegrity")
    if not isinstance(evidence, dict):
        raise CaptureIntegrityError("capture-attestation-missing")
    if (not isinstance(result, dict)
            or result.get("worldId") != world_id
            or result.get("status") not in SUCCESS
            or result.get("captureStopReason") != "completed"
            or not isinstance(evidence, dict)
            or result.get("recording") != evidence.get("filename")):
        raise CaptureIntegrityError("completed-result-mismatch")
    return verify_capture_integrity(captures, world_id, evidence)


def audit_queue(plan: dict, *, capture_dir: Path) -> dict:
    """Offline, read-only audit of completed World's MP4 integrity.

    This does not read client logs, send OSC, access VRChat or call Gemini.
    Pending/failed entries are not represented as completed evidence.
    """
    worlds = validate_plan(plan)
    captures = outside_repository(capture_dir)
    path = captures / "inspection-queue-state.json"
    if not path.is_file():
        return {"status": "blocked", "reason": "queue-state-missing",
                "auditedCompleted": 0, "problems": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "blocked", "reason": "queue-state-unreadable",
                "auditedCompleted": 0, "problems": []}
    if (not isinstance(state, dict) or state.get("schemaVersion") != 1
            or state.get("planDigest") != plan_digest(worlds)
            or not isinstance(state.get("worlds"), dict)):
        return {"status": "blocked", "reason": "queue-state-plan-mismatch",
                "auditedCompleted": 0, "problems": []}
    checked, problems = 0, []
    for item in worlds:
        wid = item["worldId"]
        entry = state["worlds"].get(wid, {})
        if not isinstance(entry, dict):
            problems.append({"worldId": wid, "reason": "invalid-queue-entry"})
            continue
        if entry.get("status") != "completed":
            continue
        try:
            verify_completed_entry(captures, wid, entry)
            checked += 1
        except (CaptureIntegrityError, OSError) as exc:
            reason = (str(exc) if isinstance(exc, CaptureIntegrityError)
                      else "capture-unreadable")
            problems.append({"worldId": wid, "reason": reason})
    return {"status": "blocked" if problems else "ok",
            "auditedCompleted": checked, "problems": problems}


def run_queue(plan: dict, *, capture_dir: Path, seconds: int = 45,
              sweep: bool = False, analyze_video: bool = False,
              platform_authorized: bool = False,
              automation_risk_acknowledged: bool = False,
              recording_rights_confirmed: bool = False,
              gemini_upload_confirmed: bool = False,
              inspection_fn: Callable | None = None,
              input_fn: Callable[[str], str] = input,
              open_world_page: bool = False,
              open_url_fn: Callable[[str], bool] | None = None,
              verify_world_log: bool = False) -> dict:
    worlds = validate_plan(plan)
    captures = outside_repository(capture_dir)
    if not 5 <= seconds <= 120:
        raise ValueError("Capture duration must be 5–120 seconds")
    if sweep and not (platform_authorized and automation_risk_acknowledged):
        raise ValueError("Sweep requires platform authorization and risk acknowledgement")
    if analyze_video and not (recording_rights_confirmed and gemini_upload_confirmed):
        raise ValueError("Gemini requires recording rights and explicit cloud upload consent")
    if open_world_page and open_url_fn is None:
        import webbrowser
        open_url_fn = webbrowser.open
    captures.mkdir(parents=True, exist_ok=True)
    state_path = captures / "inspection-queue-state.json"
    digest = plan_digest(worlds)
    state = {"schemaVersion": 1, "planDigest": digest, "updatedAt": utc_now(), "worlds": {}}
    if state_path.exists():
        existing = json.loads(state_path.read_text(encoding="utf-8"))
        if (not isinstance(existing, dict) or existing.get("schemaVersion") != 1
                or existing.get("planDigest") != digest
                or not isinstance(existing.get("worlds"), dict)):
            raise ValueError("Existing queue state belongs to a different plan; use a separate capture directory")
        state = existing
    if inspection_fn is None:
        try:
            from scripts.run_one_world_inspection import run_inspection
        except ModuleNotFoundError:
            from run_one_world_inspection import run_inspection
        inspection_fn = run_inspection

    def save(world_id: str, status: str, result: dict | None = None,
             media_evidence: dict | None = None):
        entry = {"status": status, "updatedAt": utc_now()}
        if result is not None:
            # Existing single-World result is already restricted to local audit metadata.
            entry["result"] = result
        if media_evidence is not None:
            entry["captureIntegrity"] = media_evidence
        state["worlds"][world_id] = entry
        state["updatedAt"] = utc_now()
        atomic_json(state_path, state)

    for number, item in enumerate(worlds, 1):
        wid = item["worldId"]
        existing_entry = state["worlds"].get(wid, {})
        if not isinstance(existing_entry, dict):
            return {"status": "blocked", "reason": "invalid-queue-entry",
                    "worldId": wid, "statePath": str(state_path)}
        if existing_entry.get("status") == "completed":
            try:
                verify_completed_entry(captures, wid, existing_entry)
            except (CaptureIntegrityError, OSError) as exc:
                reason = (str(exc) if isinstance(exc, CaptureIntegrityError)
                          else "capture-unreadable")
                print("Previous completed recording could not be verified: " + reason)
                return {"status": "blocked", "reason": reason,
                        "worldId": wid, "statePath": str(state_path)}
            continue
        print(f"\n[{number}/{len(worlds)}] {item['name']} ({wid})")
        page = world_launch_url(wid)
        print("Official World launch page: " + page)
        if open_world_page:
            try:
                if not open_url_fn(page):
                    print("Browser could not open the official World page. No capture attempted.")
                    return {"status": "paused", "worldId": wid, "statePath": str(state_path)}
            except Exception as exc:
                print("World page launch failed (" + type(exc).__name__ + "). No capture attempted.")
                return {"status": "paused", "worldId": wid, "statePath": str(state_path)}
        print("Open THIS World manually in a private, empty VRChat instance.")
        print("Verify World identity, permission and recording rights; the tool cannot verify them.")
        answer = input_fn("Type the entire World ID to begin recording (or q to stop): ").strip()
        if answer != wid:
            print("Stopped without recording: World ID not acknowledged.")
            return {"status": "paused", "worldId": wid, "statePath": str(state_path)}
        save(wid, "running")
        try:
            result = inspection_fn(
                world_id=wid, captures=captures, seconds=seconds,
                use_ai_motion=False, analyze_video=analyze_video, publish_visual=False,
                private_confirmed=True,
                automation_risk_confirmed=automation_risk_acknowledged,
                recording_rights_confirmed=recording_rights_confirmed,
                gemini_upload_confirmed=gemini_upload_confirmed,
                publishing_rights_confirmed=False,
                sweep_motion=sweep,
                platform_authorization_confirmed=platform_authorized,
                verify_world_log=verify_world_log,
            )
            if not isinstance(result, dict) or result.get("worldId") != wid:
                raise RuntimeError("Inspector result World ID mismatch")
        except (OSError, RuntimeError, ValueError) as exc:
            # Exception text can contain a Windows username, path or API data.
            save(wid, "failed", {"errorType": type(exc).__name__,
                                 "message": "Inspection failed before verified completion"})
            return {"status": "failed", "worldId": wid, "statePath": str(state_path)}
        status = result.get("status")
        if status not in SUCCESS or result.get("captureStopReason") != "completed":
            save(wid, "failed", result)
            return {"status": "failed", "worldId": wid, "statePath": str(state_path)}
        try:
            # A completed World must have an immutable local file attestation;
            # otherwise the next run must not silently skip the World.
            media_evidence = capture_integrity(captures, wid, result.get("recording"))
        except (CaptureIntegrityError, OSError) as exc:
            reason = (str(exc) if isinstance(exc, CaptureIntegrityError)
                      else "capture-unreadable")
            save(wid, "failed", {"status": "capture-integrity-failed", "reason": reason})
            return {"status": "failed", "worldId": wid,
                    "reason": reason, "statePath": str(state_path)}
        save(wid, "completed", result, media_evidence=media_evidence)
    return {"status": "completed", "completed": len(worlds), "statePath": str(state_path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prepare", action="store_true", help="Save an offline World plan, no client access")
    group.add_argument("--run", action="store_true", help="Run with manual confirmation at every World")
    group.add_argument("--audit-state", action="store_true",
                       help="Read-only audit of previously completed MP4s; no client/OSC/Gemini")
    parser.add_argument("--catalog", type=Path, default=REPO_ROOT / "data" / "worlds.json")
    parser.add_argument("--capture-dir", type=Path, default=Path.home() / "Videos" / "VRCClubCharts")
    parser.add_argument("--plan-file", type=Path, help="Private JSON plan; defaults to capture folder")
    parser.add_argument("--limit", type=int, default=5, help="Number of public Worlds, maximum 25")
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--verify-local-log", action="store_true",
                        help="Before/after local VRChat output log corroboration; no uploads")
    parser.add_argument("--open-world-page", action="store_true",
                        help="Open each official VRChat World launch web page, not the client")
    parser.add_argument("--analyze-video", action="store_true")
    parser.add_argument("--confirm-platform-authorization", action="store_true")
    parser.add_argument("--acknowledge-automation-risk", action="store_true")
    parser.add_argument("--confirm-recording-rights", action="store_true")
    parser.add_argument("--confirm-gemini-upload", action="store_true")
    args = parser.parse_args(argv)
    try:
        captures = outside_repository(args.capture_dir)
        plan_path = outside_repository(args.plan_file or (captures / "inspection-queue-plan.json"))
        if args.audit_state:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            result = audit_queue(plan, capture_dir=captures)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "ok" else 1
        if args.run:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            result = run_queue(
                plan, capture_dir=captures, seconds=args.seconds, sweep=args.sweep,
                analyze_video=args.analyze_video,
                platform_authorized=args.confirm_platform_authorization,
                automation_risk_acknowledged=args.acknowledge_automation_risk,
                recording_rights_confirmed=args.confirm_recording_rights,
                gemini_upload_confirmed=args.confirm_gemini_upload,
                open_world_page=args.open_world_page,
                verify_world_log=args.verify_local_log,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "completed" else 1
        plan = plan_from_catalog(args.catalog, args.limit)
        if args.prepare:
            atomic_json(plan_path, plan)
            print(f"Prepared private inspection plan: {plan_path}")
        else:
            print("Dry run only. No plan saved, client accessed, or Gemini called.")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    except (KeyboardInterrupt, EOFError):
        print("Stopped by operator. Completed Worlds remain in local queue state.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
