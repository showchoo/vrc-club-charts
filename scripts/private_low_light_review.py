#!/usr/bin/env python3
"""Create a local, private original/shadow-lift image comparison from one VRChat capture.

This tool NEVER controls or launches VRChat/Steam, calls Gemini, sends network
traffic, alters the source screenshot, or verifies DJ equipment functionality.
It is a review aid for operator-authorized, previously captured low-light PNGs.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    from scripts.diagnose_light_cycle_report import read_report, DiagnosticError
    from scripts.inspection_light_cycle import sample_lighting
    from scripts.auto_process_interior_queue import ROOT, atomic_json
except ModuleNotFoundError:
    from diagnose_light_cycle_report import read_report, DiagnosticError
    from inspection_light_cycle import sample_lighting
    from auto_process_interior_queue import ROOT, atomic_json

PRIVATE_ROOT = Path.home() / "Videos" / "VRCClubCharts" / "private-light-recovery"
REVIEW_FOLDER = "private-visibility-review"
SOURCE_NAME = "low-light-review.png"
ORIGINAL_NAME = "original.png"
ENHANCED_NAME = "shadow-lift.png"
MANIFEST_NAME = "review.json"
INDEX_NAME = "index.html"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REPORT_BYTES = 128 * 1024
MAX_CANDIDATE_FOLDERS = 5000
SHADOW_PIVOT = 112
SHADOW_GAMMA = 0.56
RUN_FOLDER_RE = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}_\d{8}T\d{6}Z_[0-9a-f]{10}\Z")


class PrivateReviewError(ValueError):
    """Unsafe, unverified, or incomplete private capture."""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _no_symlinks(path: Path) -> None:
    """Reject symlink components, including a linked parent directory."""
    for segment in (path, *path.parents):
        if segment.is_symlink():
            raise PrivateReviewError("symlink-path-rejected")


def _read_bounded(path: Path, maximum: int) -> bytes:
    _no_symlinks(path)
    if not path.is_file():
        raise PrivateReviewError("private-file-missing")
    size = path.stat().st_size
    if not 0 < size <= maximum:
        raise PrivateReviewError("private-file-size-invalid")
    data = path.read_bytes()
    if len(data) != size:
        raise PrivateReviewError("private-file-changed-while-reading")
    return data


def latest_private_report(root: Path = PRIVATE_ROOT) -> Path:
    """Discover the newest locally saved eligible low-light report only."""
    _no_symlinks(root)
    if not root.is_dir():
        raise PrivateReviewError("no-private-capture-folder")
    folders = list(root.iterdir())
    if len(folders) > MAX_CANDIDATE_FOLDERS:
        raise PrivateReviewError("too-many-private-capture-folders")
    for folder in sorted(folders, key=lambda p: p.name, reverse=True):
        if not RUN_FOLDER_RE.fullmatch(folder.name):
            continue
        _no_symlinks(folder)
        if not folder.is_dir():
            continue
        report = folder / "lighting-cycle.json"
        if not report.is_file():
            continue
        raw = _read_bounded(report, MAX_REPORT_BYTES)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PrivateReviewError("invalid-private-report-json") from exc
        if data.get("status") == "low-light-visibility-needs-review":
            return report
    raise PrivateReviewError("no-low-light-review-report-found")


def _verified_source(report_path: Path) -> tuple[dict, bytes, str]:
    _no_symlinks(report_path)
    if report_path.name != "lighting-cycle.json":
        raise PrivateReviewError("expected-private-lighting-report")
    if report_path.resolve().is_relative_to(ROOT):
        raise PrivateReviewError("do-not-process-files-inside-repository")
    report_bytes = _read_bounded(report_path, MAX_REPORT_BYTES)
    try:
        report = json.loads(report_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PrivateReviewError("invalid-private-report-json") from exc
    try:
        verified = read_report(report_path)
    except (DiagnosticError, OSError, ValueError, KeyError, TypeError) as exc:
        raise PrivateReviewError("private-lighting-report-unverified") from exc
    if verified.get("sourceStatus") != "low-light-visibility-needs-review":
        raise PrivateReviewError("not-a-low-light-capture")
    shot = report.get("screenshot")
    if not isinstance(shot, dict) or shot.get("file") != SOURCE_NAME:
        raise PrivateReviewError("low-light-screenshot-reference-missing")
    expected_hash = shot.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise PrivateReviewError("invalid-original-image-digest")
    source_bytes = _read_bounded(report_path.parent / SOURCE_NAME, MAX_IMAGE_BYTES)
    if _hash(source_bytes) != expected_hash:
        raise PrivateReviewError("original-image-sha256-mismatch")
    return report, source_bytes, expected_hash


def shadow_curve() -> list[int]:
    """Monotone shadow lift with unchanged pixels >=112 and black unchanged.

    Not an exposure measurement: it only changes pixels for local review.
    """
    return [
        value if value >= SHADOW_PIVOT else
        int(round(SHADOW_PIVOT * (value / SHADOW_PIVOT) ** SHADOW_GAMMA))
        for value in range(256)
    ]


def enhance_png(original: bytes, capture_region: dict) -> bytes:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise PrivateReviewError("install-pillow-for-local-review") from exc
    try:
        with Image.open(io.BytesIO(original)) as opened:
            if opened.format != "PNG":
                raise PrivateReviewError("expected-original-png")
            width, height = opened.size
            if not (320 <= width <= 3840 and 240 <= height <= 2160):
                raise PrivateReviewError("private-image-dimensions-invalid")
            if (not isinstance(capture_region, dict) or
                    capture_region.get("width") != width or
                    capture_region.get("height") != height):
                raise PrivateReviewError("capture-region-does-not-match-image")
            # Luminance-only edit preserves screen highlights and reduces
            # the odds of drastically overexposing bright stage panels.
            y, cb, cr = opened.convert("YCbCr").split()
            enhanced = Image.merge("YCbCr", (y.point(shadow_curve()), cb, cr))
            transformed = enhanced.convert("RGB")
            out = io.BytesIO()
            transformed.save(out, format="PNG", optimize=True)
            result = out.getvalue()
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        if isinstance(exc, PrivateReviewError):
            raise
        raise PrivateReviewError("private-image-decode-or-enhancement-failed") from exc
    if len(result) > MAX_IMAGE_BYTES:
        raise PrivateReviewError("enhanced-private-image-too-large")
    return result


def _render_html(world_id: str) -> str:
    wid = html.escape(world_id)
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'img-src &#39;self&#39; file:; style-src &#39;unsafe-inline&#39;">'
        '<title>非公開・低照度DJクラブ画像比較</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:1500px;'
        'margin:1.2rem auto;padding:0 1rem;color:#eee;background:#15181c}'
        'main{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}'
        'figure{margin:0;background:#272c30;padding:0.7rem;border-radius:12px}'
        'img{width:100%;height:auto;object-fit:contain}'
        'figcaption{margin:0.5rem 0}p{line-height:1.6}</style></head><body>'
        '<h1>非公開：低照度ワールドの原画・補正版</h1>'
        '<p>World: '+wid+'</p>'
        '<p>表示画像はローカルのみ。元画像を改変せず、補正版は暗部の輝度を数学的に'
        '持ち上げた参考画像です。見えない設備を創作しませんが、'
        '色・陰影・ノイズが本来の見た目と異なる場合があります。'
        'DJブース、DJデッキ、ライブ配信機能・音声再生の存在／動作は未確認です。'
        '画像に第三者や個人情報がある場合は外部共有しないでください。</p>'
        '<main><figure><img src="original.png" alt="元の撮影フレーム">'
        '<figcaption>元の撮影フレーム（ハッシュ検証済み）</figcaption></figure>'
        '<figure><img src="shadow-lift.png" alt="暗部補正した参考画像">'
        '<figcaption>暗部のみ明るくした参考画像（非証拠・AI未評価）'
        '</figcaption></figure></main></body></html>'
    )


def _verify_existing(folder: Path, expected_source_sha: str, world_id: str) -> dict:
    _no_symlinks(folder)
    if not folder.is_dir():
        raise PrivateReviewError("existing-review-folder-is-invalid")
    raw = _read_bounded(folder / MANIFEST_NAME, MAX_REPORT_BYTES)
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PrivateReviewError("existing-review-json-invalid") from exc
    if (manifest.get("schemaVersion") != 1 or
            manifest.get("status") != "private-shadow-review-unverified" or
            manifest.get("worldId") != world_id or
            manifest.get("originalSha256") != expected_source_sha or
            manifest.get("equipmentFunctionalityVerified") is not False or
            manifest.get("rankingEligible") is not False or
            manifest.get("publiclyShareable") is not False):
        raise PrivateReviewError("existing-review-provenance-mismatch")
    for name, digest in (
        (ORIGINAL_NAME, expected_source_sha),
        (ENHANCED_NAME, manifest.get("enhancedSha256")),
    ):
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PrivateReviewError("existing-review-image-digest-invalid")
        if _hash(_read_bounded(folder / name, MAX_IMAGE_BYTES)) != digest:
            raise PrivateReviewError("existing-review-image-changed")
    _read_bounded(folder / INDEX_NAME, MAX_REPORT_BYTES)
    return {
        "status": "existing-private-review",
        "index": str(folder / INDEX_NAME),
        "original": str(folder / ORIGINAL_NAME),
        "enhanced": str(folder / ENHANCED_NAME),
        "worldId": world_id,
        "equipmentFunctionalityVerified": False,
        "publiclyShareable": False,
        "vrchatLaunched": False,
        "externalUploads": False,
    }


def produce_private_review(report_path: Path) -> dict:
    report_path = Path(report_path).expanduser()
    report, original, digest = _verified_source(report_path)
    folder = report_path.parent / REVIEW_FOLDER
    world_id = report["worldId"]
    if folder.exists() or folder.is_symlink():
        return _verify_existing(folder, digest, world_id)
    enhanced = enhance_png(original, report.get("captureRegion"))
    # Only numeric pixel distribution is disclosed. Neither set of metrics
    # can prove an object identity, camera movement, or an operable DJ player.
    original_metrics = sample_lighting(original)
    enhanced_metrics = sample_lighting(enhanced)
    manifest = {
        "schemaVersion": 1,
        "status": "private-shadow-review-unverified",
        "worldId": world_id,
        "sourceFile": SOURCE_NAME,
        "originalSha256": digest,
        "enhancedSha256": _hash(enhanced),
        "transform": {
            "kind": "local-YCbCr-luma-shadow-power-curve",
            "pivot": SHADOW_PIVOT,
            "exponent": SHADOW_GAMMA,
            "abovePivotUnchangedInLumaDomain": True,
            "syntheticDetailAdded": False,
            "trueLightingRecovered": False,
        },
        "originalMetrics": original_metrics,
        "enhancedMetrics": enhanced_metrics,
        "humanReviewRequired": True,
        "djBoothLocated": False,
        "equipmentFunctionalityVerified": False,
        "lightingCycleVerified": False,
        "navigationSafe": False,
        "rankingEligible": False,
        "publiclyShareable": False,
        "vrchatLaunched": False,
        "externalUploads": False,
    }
    # Stage within the same private parent. Never overwrite a completed or
    # incomplete review, and remove temporary files if interrupted.
    stage = Path(tempfile.mkdtemp(prefix=".shadow-review-", dir=report_path.parent))
    try:
        (stage / ORIGINAL_NAME).write_bytes(original)
        (stage / ENHANCED_NAME).write_bytes(enhanced)
        (stage / INDEX_NAME).write_text(_render_html(world_id), encoding="utf-8")
        atomic_json(stage / MANIFEST_NAME, manifest)
        if folder.exists() or folder.is_symlink():
            raise PrivateReviewError("concurrent-review-already-exists")
        stage.rename(folder)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {
        "status": manifest["status"],
        "index": str(folder / INDEX_NAME),
        "original": str(folder / ORIGINAL_NAME),
        "enhanced": str(folder / ENHANCED_NAME),
        "worldId": world_id,
        "originalMetrics": original_metrics,
        "enhancedMetrics": enhanced_metrics,
        "equipmentFunctionalityVerified": False,
        "publiclyShareable": False,
        "vrchatLaunched": False,
        "externalUploads": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--report", type=Path, help="A validated local lighting-cycle.json")
    group.add_argument("--root", type=Path, help="Find newest low-light capture here")
    parser.add_argument("--open", action="store_true",
                        help="Open the resulting private HTML in the local browser")
    args = parser.parse_args(argv)
    try:
        report_path = args.report if args.report else latest_private_report(
            args.root if args.root else PRIVATE_ROOT)
        result = produce_private_review(report_path)
        if args.open:
            if sys.platform != "win32":
                raise PrivateReviewError("open-available-on-windows-only")
            os.startfile(result["index"])  # explicit local user opt-in
    except (PrivateReviewError, OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
