#!/usr/bin/env python3
"""Read-only, conservative corroboration of a manually entered VRChat World.

Output logs may contain private information. Read only the tail of the newest
local session file and return redacted status. A log is NOT proof of participant
absence, continued connection, or permission for automated movement.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
import re

WORLD_RE = re.compile(r"wrld_[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
EVENT_RE = re.compile(
    r"^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})\s+(?:Debug|Log|Info|Warning)\s+-\s+\[Behaviour\]\s+(.+)$"
)
JOIN_RE = re.compile(
    r"^Joining (wrld_[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}):(\S+)$"
)
SUCCESS = "Successfully joined room"
MAX_LOG_BYTES = 1024 * 1024


def default_log_dir() -> Path:
    """Official default location; never enumerate another profile."""
    base = Path(os.environ.get("USERPROFILE", str(Path.home())))
    return base / "AppData" / "LocalLow" / "VRChat" / "VRChat"


def newest_output_log(log_dir: Path) -> Path | None:
    """Choose latest modified session log, not arbitrary local text."""
    if not log_dir.is_dir():
        return None
    files = [p for p in log_dir.glob("output_log_*.txt") if p.is_file()]
    return max(files, key=lambda p: (p.stat().st_mtime_ns, p.name)) if files else None


def read_log_tail(file: Path, maximum: int = MAX_LOG_BYTES) -> str:
    """Bounded UTF-8-loss-tolerant read with no changes to original log."""
    if maximum < 1024 or maximum > MAX_LOG_BYTES:
        raise ValueError("Unbounded output log read denied")
    with file.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        truncated = size > maximum
        # Always reposition after measuring size; otherwise short logs read at EOF.
        stream.seek(size - maximum if truncated else 0)
        data = stream.read(maximum)
    if truncated:
        data = data.split(b"\n", 1)[-1]
    return data.decode("utf-8-sig", errors="replace")


def corroborate_world(world_id: str, *, log_dir: Path | None = None,
                      max_age_seconds: int = 180,
                      now: datetime | None = None) -> dict:
    """Corroborate the latest logged join, or fail closed.

    A positive result includes an ephemeral hashed join marker for before/after
    comparison, never instance/user IDs, the source log or raw line.
    """
    if not isinstance(world_id, str) or not WORLD_RE.fullmatch(world_id):
        raise ValueError("Invalid VRChat World ID")
    if not 30 <= max_age_seconds <= 900:
        raise ValueError("Join freshness window must be 30..900 seconds")
    moment = now if now is not None else datetime.now()
    if moment.tzinfo is not None:
        raise ValueError("Use local naive time for Unity local log timestamps")

    def reject(reason: str) -> dict:
        return {"status": "unconfirmed", "reason": reason}

    root = log_dir if log_dir is not None else default_log_dir()
    try:
        latest = newest_output_log(root)
        if latest is None:
            return reject("logs-unavailable")
        raw = read_log_tail(latest)
    except OSError:
        return reject("logs-unreadable")

    last = None
    for line in raw.splitlines():
        match = EVENT_RE.match(line)
        if not match:
            continue
        stamp, message = match.groups()
        if message.startswith("Joining wrld_"):
            joined = JOIN_RE.fullmatch(message)
            if not joined:
                last = {"invalid": True}
                continue
            try:
                timestamp = datetime.strptime(stamp, "%Y.%m.%d %H:%M:%S")
            except ValueError:
                last = {"invalid": True}
                continue
            last = {
                "worldId": joined.group(1).lower(),
                "private": "~private(" in joined.group(2),
                "timestamp": timestamp,
                "success": False,
                "left": False,
                "fingerprint": hashlib.sha256(
                    (latest.name + "\n" + line).encode("utf-8")
                ).hexdigest(),
            }
        elif last is not None and not last.get("invalid"):
            if message == SUCCESS:
                try:
                    success_time = datetime.strptime(stamp, "%Y.%m.%d %H:%M:%S")
                except ValueError:
                    continue
                delta = (success_time - last["timestamp"]).total_seconds()
                if 0 <= delta <= 180 and not last["left"]:
                    last["success"] = True
            elif (
                message.startswith("Leaving Room")
                or message.startswith("Leaving world")
                or message.startswith("OnDisconnected")
                or message.startswith("Disconnected from room")
            ):
                last["left"] = True

    if last is None or last.get("invalid"):
        return reject("join-not-found")
    if last["worldId"] != world_id.lower():
        return reject("wrong-world")
    if not last["private"]:
        return reject("not-private-instance")
    if last["left"]:
        return reject("left-room")
    if not last["success"]:
        return reject("join-not-confirmed")
    age = (moment - last["timestamp"]).total_seconds()
    if age < -5:
        return reject("join-in-future")
    if age > max_age_seconds:
        return reject("join-too-old")
    return {
        "status": "corroborated",
        "worldId": world_id,
        "joinFingerprint": last["fingerprint"],
        "logBasedOnly": True,
        "participantsIndependentlyVerified": False,
        "instanceAccessIndependentlyVerified": False,
    }
