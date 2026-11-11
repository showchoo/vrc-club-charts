#!/usr/bin/env python3
"""Offline visual diagnostics and operator feedback for ONE guarded OSC step.

Read-only verification of the original position-step.json and its two local
PNG files. Writes separate, private feedback JSON + HTML and an amplified
difference preview. No VRChat, Gemini, GitHub, external networking or ranking.
Human-observed movement is never represented as sensor-verified movement.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import io
import json
import math
import re
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import ROOT, atomic_json
    from scripts.inspection_lighting_guard import analyze_luma_pair
except ModuleNotFoundError:
    from auto_process_interior_queue import ROOT, atomic_json
    from inspection_lighting_guard import analyze_luma_pair

WORLD_RE = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
DIRECTIONS = {"forward", "backward", "strafe_left", "strafe_right"}
OBSERVATIONS = {"moved", "did-not-move", "uncertain"}
MAX_REPORT_BYTES = 32 * 1024
MAX_PNG_BYTES = 10 * 1024 * 1024
GRID_W = 192
GRID_H = 108


class PositionFeedbackError(ValueError):
    """Missing/untrusted provenance or conflicting operator review."""


def validate_original(report_file: Path) -> tuple[dict, bytes, bytes, Path]:
    """Every local screenshot must still hash to its original evidence record."""
    if report_file.is_symlink() or report_file.name != "position-step.json":
        raise PositionFeedbackError("Expected a non-symlink original position-step.json")
    report_file = report_file.expanduser().resolve(strict=True)
    directory = report_file.parent
    if directory.is_relative_to(ROOT) or directory.is_symlink():
        raise PositionFeedbackError("Private feedback must remain outside the source repository")
    if report_file.stat().st_size > MAX_REPORT_BYTES:
        raise PositionFeedbackError("Original step report too large")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if (not isinstance(report, dict) or report.get("schemaVersion") != 1 or
            report.get("status") != "sent-unverified" or
            report.get("source") != "local-osc-private-single-position-step" or
            report.get("stepCountMax") != 1 or report.get("stepsAttempted") != 1 or
            report.get("stepSeconds") != .2 or
            report.get("direction") not in DIRECTIONS or
            report.get("positionVerified") is not False or
            report.get("collisionSafetyVerified") is not False or
            report.get("equipmentFunctionalityVerified") is not False or
            report.get("noPublicRankingChanges") is not True or
            report.get("privateLocalOnly") is not True):
        raise PositionFeedbackError("Original report is not a verified private single-step attempt")
    world_id = report.get("worldId")
    if not isinstance(world_id, str) or not WORLD_RE.fullmatch(world_id):
        raise PositionFeedbackError("Invalid World ID")
    if not directory.name.startswith(world_id + "_"):
        raise PositionFeedbackError("Source folder and World ID mismatch")
    records = report.get("frames")
    if (not isinstance(records, list) or len(records) != 2 or
            not all(isinstance(r, dict) for r in records) or
            [r.get("file") for r in records] != ["before.png", "after.png"]):
        raise PositionFeedbackError("Missing expected before/after image provenance")
    contents = []
    for record in records:
        path = directory / record["file"]
        digest = record.get("sha256")
        if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
            raise PositionFeedbackError("Invalid screenshot checksum")
        if path.is_symlink() or not path.is_file() or not 8 <= path.stat().st_size <= MAX_PNG_BYTES:
            raise PositionFeedbackError("Missing or unsafe private screenshot")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise PositionFeedbackError("Original screenshot checksum mismatch")
        contents.append(data)
    return report, contents[0], contents[1], directory


def compare_frames(before: bytes, after: bytes, *, preview_file: Path) -> dict:
    """Sensitive *diagnostic* comparison, not position/flow verification.

    Old navigation guard reduces each picture to 16x9 grayscale. That loses
    short, low-amplitude motions. Inspect 192x108 grayscale, separately
    reporting the pixel-difference distribution and most changed tile.
    No threshold here declares that walking happened.
    """
    try:
        from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError
    except ImportError:
        return {"status": "unavailable-pillow-not-installed",
                "movementAutomaticallyVerified": False}
    try:
        with Image.open(io.BytesIO(before)) as first, Image.open(io.BytesIO(after)) as second:
            if first.size != second.size or not 320 <= first.width <= 3840 or not 240 <= first.height <= 2160:
                raise PositionFeedbackError("Invalid or mismatched screenshot dimensions")
            mode = Image.Resampling.BILINEAR
            a = first.convert("L").resize((GRID_W, GRID_H), mode)
            b = second.convert("L").resize((GRID_W, GRID_H), mode)
        lighting = analyze_luma_pair(a.tobytes(), b.tobytes())
        diff = ImageChops.difference(a, b)
        values = list(diff.getdata())
        count = len(values)
        total = sum(values)
        # This is an intentionally more sensitive diagnostic, not an
        # automatic movement decision. Moving lights can trigger it too.
        tiles = []
        stride_x, stride_y = GRID_W // 4, GRID_H // 4
        for tile_y in range(4):
            for tile_x in range(4):
                left, top = tile_x * stride_x, tile_y * stride_y
                box = (left, top, left + stride_x, top + stride_y)
                tile = diff.crop(box)
                tiles.append(sum(tile.getdata()) / (stride_x * stride_y * 255))
        amplified = ImageOps.autocontrast(diff)
        if preview_file.is_symlink() or preview_file.exists():
            raise PositionFeedbackError("Refusing to overwrite an existing diagnostic preview")
        amplified.save(preview_file, format="PNG")
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        if isinstance(exc, PositionFeedbackError):
            raise
        raise PositionFeedbackError("Could not inspect recorded local PNG files") from None
    return {
        "status": "computed",
        "method": "192x108-grayscale-absolute-difference-16-tiles-v1",
        "meanAbsPixelDifference": round(total / (count * 255), 6),
        "fractionPixelsDifferenceAbove3": round(sum(v > 3 for v in values) / count, 6),
        "fractionPixelsDifferenceAbove10": round(sum(v > 10 for v in values) / count, 6),
        "maxTileMeanDifference": round(max(tiles), 6),
        "lightingDiagnostics": lighting,
        "frameComparisonConfoundedByLighting": lighting["visualNavigationShouldPause"],
        "preview": preview_file.name,
        "imageDifferenceIsNotProofOfWalking": True,
        "movementAutomaticallyVerified": False,
    }


def render_page(report: dict, observation: str, metrics: dict) -> str:
    labels = {
        "moved": "操作者が目視で前進・移動を確認",
        "did-not-move": "操作者は移動を確認しなかった",
        "uncertain": "移動したか目視でも不明",
    }
    preview = ('<h2>差分を強調した画像（実際の移動を証明しません）</h2>'
               '<img src="difference-amplified.png" alt="コントラスト強調差分画像">'
               if metrics.get("preview") == "difference-amplified.png" else "")
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>非公開・移動テスト目視確認</title>'
        '<style>body{max-width:1100px;margin:2rem auto;padding:0 1rem;'
        'font:16px system-ui,sans-serif;background:#17181a;color:#eee}'
        'img{max-width:100%;height:auto;border:1px solid #555;border-radius:6px}'
        'section{margin:1.5rem 0}h1{font-size:1.5rem}h2{font-size:1.1rem}</style>'
        '</head><body><h1>非公開・移動テスト目視確認</h1>'
        '<p>World ID: ' + html.escape(report["worldId"]) + '</p>'
        '<p><strong>人手の結果：' + html.escape(labels[observation]) + '</strong></p>'
        '<p>照明・暗転の注意判定: '+html.escape(metrics.get("lightingDiagnostics", {}).get("status", "未測定"))+'。暗転や照明変化では、景色の差分から位置を判断できません。</p>'
        '<p>画像の差分が少なくてもOSC前進が実際に起きたことがあります。'
        'ただしこれは人手報告であり、画像による位置・移動距離・衝突の独立検証ではありません。'
        'スクリーン・ライト・アバターの変化も差分に含まれます。</p>'
        '<section><h2>移動前</h2><img src="before.png" alt="移動前のフレーム"></section>'
        '<section><h2>移動後</h2><img src="after.png" alt="移動後のフレーム"></section>'
        + preview + '</body></html>'
    )


def save_feedback(report_file: Path, *, observation: str) -> dict:
    if observation not in OBSERVATIONS:
        raise PositionFeedbackError("Invalid human movement observation")
    report, before, after, directory = validate_original(report_file)
    saved_path = directory / "position-step-feedback.json"
    page_path = directory / "position-step-feedback.html"
    preview = directory / "difference-amplified.png"
    if saved_path.exists():
        if saved_path.is_symlink() or saved_path.stat().st_size > MAX_REPORT_BYTES:
            raise PositionFeedbackError("Unsafe existing private feedback")
        existing = json.loads(saved_path.read_text(encoding="utf-8"))
        if (not isinstance(existing, dict) or existing.get("schemaVersion") != 1 or
                existing.get("worldId") != report["worldId"] or
                existing.get("sourceFrameHashes") != [r["sha256"] for r in report["frames"]] or
                existing.get("observedMovement") != observation or
                existing.get("independentPositionVerified") is not False or
                existing.get("publiclyShareable") is not False):
            raise PositionFeedbackError("Conflicting or unverifiable feedback already exists")
        if not page_path.is_file() or page_path.is_symlink():
            raise PositionFeedbackError("Existing private feedback HTML missing")
        return {"status": "existing-human-feedback", "observedMovement": observation,
                "reportFile": str(saved_path), "index": str(page_path)}
    if page_path.exists() or page_path.is_symlink() or preview.exists() or preview.is_symlink():
        raise PositionFeedbackError("Private feedback output already exists; refusing overwrite")
    metrics = compare_frames(before, after, preview_file=preview)
    review = {
        "schemaVersion": 1, "status": "private-human-movement-observation",
        "worldId": report["worldId"], "direction": report["direction"],
        "sourceFrameHashes": [r["sha256"] for r in report["frames"]],
        "sourceOriginalReportSha256": hashlib.sha256(
            Path(report_file).read_bytes()).hexdigest(),
        "observedMovement": observation,
        "humanObservedMovement": observation == "moved",
        "independentPositionVerified": False, "metersMoved": None,
        "collisionSafetyVerified": False, "stairsTraversed": False,
        "publiclyShareable": False, "equipmentFunctionalityVerified": False,
        "visualDiagnostics": metrics,
        "recordedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    # Original evidence and AI reports are immutable; feedback is a separate
    # local note. Do not write feedback until its HTML has been created.
    page_path.write_text(render_page(report, observation, metrics), encoding="utf-8")
    atomic_json(saved_path, review)
    return {"status": "private-human-movement-observation",
            "observedMovement": observation, "visualDiagnostics": metrics,
            "reportFile": str(saved_path), "index": str(page_path),
            "independentPositionVerified": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--observed", choices=sorted(OBSERVATIONS), required=True)
    p.add_argument("--confirm-human-observation", action="store_true")
    args = p.parse_args(argv)
    try:
        if not args.confirm_human_observation:
            raise PositionFeedbackError("Explicit operator observation confirmation required")
        result = save_feedback(args.report, observation=args.observed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        p.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
