#!/usr/bin/env python3
"""Extract PRIVATE, source-verified DJ facility keyframes for local inspection.

Input: an owner-authorized local MP4 plus its private *.draft.json. Outputs
a small folder of JPEG frames, a machine-readable audit and local HTML index.
Never contacts VRChat, Gemini, Vercel, GitHub, or any network. No proof of
working DJ equipment is inferred from the appearance of an object.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

try:
    from scripts.evaluate_interior_video import media_sha256, validate_media, WORLD_ID
    from scripts.inspection_evidence_timeline import audit_timeline, attach_verified_timeline
    from scripts.inspection_visual_quality import assess_video_quality
    from scripts.inspection_facility_inventory import (
        LABELS_JA, public_facility_observations,
    )
    from scripts.inspection_media_verify import verify_mp4
    from scripts.auto_process_interior_queue import atomic_json, ROOT
except ModuleNotFoundError:
    from evaluate_interior_video import media_sha256, validate_media, WORLD_ID
    from inspection_evidence_timeline import audit_timeline, attach_verified_timeline
    from inspection_visual_quality import assess_video_quality
    from inspection_facility_inventory import LABELS_JA, public_facility_observations
    from inspection_media_verify import verify_mp4
    from auto_process_interior_queue import atomic_json, ROOT

FRAME_LIMIT = 6
MAX_REPORT_BYTES = 1024 * 1024


class FrameEvidenceError(ValueError):
    """Cannot safely extract an evidence frame from this particular recording."""



def _authorize_direct_cli_draft_for_local_frames(report: dict, video: Path) -> dict:
    """Locally reverify an older single-video CLI draft, with explicit CLI rights.

    Direct evaluate_interior_video.py --analyze --confirm-sharing initially saved
    provenance and AI findings but omitted the queue's consent/timeline metadata.
    We may derive a PRIVATE, in-memory equivalent ONLY for this local extraction
    and ONLY when the operator used --confirm-recording-rights. Never rewrite the
    original draft, upload media, or imply permission to publish/stream.
    """
    if not isinstance(report, dict) or "consent" in report:
        raise FrameEvidenceError("Cannot upgrade a draft with existing consent metadata")
    if (report.get("status") != "draft_video_assessment" or
            report.get("rankingEligible") is not False or
            report.get("livePlaybackIndependentlyVerified") is not False):
        raise FrameEvidenceError("Only private, unranked direct video drafts can be locally verified")
    method = report.get("method")
    if (not isinstance(method, dict) or
            method.get("kind") != "gemini_video_analysis" or
            method.get("independentInWorldInspection") is not False):
        raise FrameEvidenceError("Only a direct video-analysis draft is eligible for local recovery")
    evidence = report.get("evidence")
    if (not isinstance(evidence, dict) or
            evidence.get("type") != "interior_video" or
            evidence.get("source") not in {"owner-recorded", "creator-provided"} or
            evidence.get("timestampBasis") != "video_seconds_model_estimated"):
        raise FrameEvidenceError("Unsupported direct draft video provenance")
    digest = evidence.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise FrameEvidenceError("Missing full media SHA-256")
    size = validate_media(video)
    if evidence.get("bytes") != size or media_sha256(video) != digest:
        raise FrameEvidenceError("Recorded video SHA-256 or size differs from the draft")
    metadata = verify_mp4(video)
    quality = assess_video_quality(video, metadata=metadata)
    if quality.get("status") != "ok":
        raise FrameEvidenceError("Original footage failed local visual-quality verification")
    enriched = attach_verified_timeline(report, metadata=metadata, visual_quality=quality)
    # This is NOT saved to the user's original draft; the current explicit
    # --confirm-recording-rights acknowledges local extraction only.
    enriched["consent"] = {
        "recordingConsentConfirmed": True,
        "aiAnalysisConsentConfirmed": False,
        "permissionToPublishVisualEstimate": False,
    }
    return enriched


def _check_document(report: dict, video: Path) -> tuple[str, str, float, list[dict]]:
    if not isinstance(report, dict) or report.get("schemaVersion") != 1:
        raise FrameEvidenceError("Unknown draft report schema")
    if report.get("status") != "draft_video_assessment" or report.get("rankingEligible") is not False:
        raise FrameEvidenceError("Only private, unranked drafts can supply frame evidence")
    wid = report.get("worldId")
    if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid):
        raise FrameEvidenceError("Invalid World ID")
    consent = report.get("consent")
    if not isinstance(consent, dict) or consent.get("recordingConsentConfirmed") is not True:
        raise FrameEvidenceError("Recording/participant permission must be attested")
    evidence = report.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("type") != "interior_video":
        raise FrameEvidenceError("Missing video provenance")
    digest = evidence.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise FrameEvidenceError("Missing full media SHA-256")
    validate_media(video)
    actual_hash = media_sha256(video)
    if actual_hash != digest:
        raise FrameEvidenceError("Recorded video SHA-256 differs from the draft")
    parsed = verify_mp4(video)
    # FFprobe metadata must match the report's previously verified clip length.
    actual_duration = parsed["durationSeconds"]
    audit = audit_timeline(report)
    if abs(audit["durationSeconds"] - actual_duration) > 0.15:
        raise FrameEvidenceError("The report cites a different video duration")
    analysis = report.get("analysis")
    sightings = public_facility_observations(
        analysis.get("facilities") if isinstance(analysis, dict) else None,
        duration_seconds=actual_duration,
    )
    return wid, digest, actual_duration, sightings[:FRAME_LIMIT]


def _render_index(world_id: str, rows: list[dict]) -> str:
    cards = []
    for row in rows:
        title = html.escape(LABELS_JA[row["kind"]])
        src = html.escape(row["file"], quote=True)
        time_text = f'{row["timestampSeconds"]:.2f}'
        confidence = f'{row["confidence"]:.0%}'
        cards.append(
            '<article><h2>' + title + '</h2>'
            '<img src="' + src + '" alt="' + title + 'の候補フレーム" loading="lazy">'
            '<p>映像内の時刻: ' + time_text + '秒／AI推定信頼度: ' +
            confidence + '</p><p>確認状態: 未確認（外観のみ）</p></article>'
        )
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<title>非公開・DJ設備映像証拠</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:1100px;'
        'margin:2rem auto;padding:0 1rem;background:#17181a;color:#f0f1f2}'
        'article{border:1px solid #555;border-radius:12px;padding:1rem;'
        'margin:1rem 0}img{max-width:100%;height:auto}h1{font-size:1.5rem}'
        'h2{font-size:1.2rem}p{line-height:1.5}</style></head><body>'
        '<h1>非公開・DJ設備候補の映像証拠</h1>'
        '<p>World ID: ' + html.escape(world_id) + '</p>'
        '<p>これはモデルが指定した時刻の元動画フレームです。'
        '設備が存在・機能する証明ではなく、DJ配信や再生、音声・操作の'
        '動作確認も行っていません。画像に個人情報が含まれる可能性があるため、'
        '公開・共有せずローカルで取り扱ってください。</p>'
        + "".join(cards) + '</body></html>'
    )


def export_frame_evidence(report: dict, video: Path, out_root: Path, *,
                          authorize_direct_draft: bool = False) -> dict:
    """One immutable local folder per (World ID, full source-video digest).

    A failure cannot leave a completed manifest. Existing folders cannot be
    silently overwritten or followed through a symlink. An incomplete folder
    is left in place as an explicit failure marker for operator inspection.
    """
    video = Path(video).expanduser().resolve(strict=True)
    out_root = Path(out_root).expanduser().resolve()
    if out_root.is_relative_to(ROOT):
        raise FrameEvidenceError("Private screenshots cannot be stored in source repository")
    if not video.is_file():
        raise FrameEvidenceError("Local source video not found")
    if authorize_direct_draft and isinstance(report, dict) and "consent" not in report:
        report = _authorize_direct_cli_draft_for_local_frames(report, video)
    wid, digest, duration, sightings = _check_document(report, video)
    if not sightings:
        return {"status": "no-high-confidence-facilities",
                "worldId": wid, "frameCount": 0,
                "functionalityVerified": False}
    out_root.mkdir(parents=True, exist_ok=True)
    folder = out_root / f"{wid}_{digest}"
    if folder.is_symlink():
        raise FrameEvidenceError("Existing evidence folder cannot be a symlink")
    if folder.exists():
        manifest_file = folder / "frames.json"
        index_file = folder / "index.html"
        if not manifest_file.is_file() or manifest_file.is_symlink() or not index_file.is_file():
            raise FrameEvidenceError("Existing evidence folder is incomplete; refusing to overwrite")
        previous = json.loads(manifest_file.read_text(encoding="utf-8"))
        items = previous.get("items")
        if (previous.get("schemaVersion") != 1 or
            previous.get("status") != "local-private-unreviewed" or
            previous.get("worldId") != wid or previous.get("mediaSha256") != digest or
            previous.get("equipmentFunctionalityVerified") is not False or
            not isinstance(items, list) or len(items) != len(sightings)):
            raise FrameEvidenceError("Existing evidence folder does not match this exact video")
        for item in items:
            if not isinstance(item, dict) or item.get("kind") not in LABELS_JA:
                raise FrameEvidenceError("Existing evidence records are invalid")
            filename = item.get("file")
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise FrameEvidenceError("Existing evidence filename is invalid")
            still = folder / filename
            if still.is_symlink() or not still.is_file() or still.stat().st_size < 300:
                raise FrameEvidenceError("Previously extracted frame is missing")
        return {
            "status": "existing-private-evidence", "worldId": wid,
            "frameCount": len(items), "index": str(index_file),
            "functionalityVerified": False,
        }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FrameEvidenceError("FFmpeg required for local frame extraction")
    folder.mkdir()
    rows = []
    for observation in sightings:
        kind = observation["kind"]  # strictly allowlisted by serializer
        timestamp = min(float(observation["timestampSeconds"]), max(0, duration - 0.10))
        image = f"{kind}_{round(timestamp * 1000):06d}ms.jpg"
        target = folder / image
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-ss", f"{timestamp:.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", "scale=640:-2",
            "-q:v", "4", str(target),
        ]
        try:
            output = subprocess.run(cmd, capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FrameEvidenceError("Could not decode cited private frame") from exc
        if output.returncode != 0 or not target.is_file() or target.stat().st_size < 300:
            raise FrameEvidenceError("FFmpeg failed to extract a cited frame")
        rows.append({
            "kind": kind, "file": image,
            "timestampSeconds": round(timestamp, 3),
            "confidence": observation["confidence"],
            "humanReviewed": False, "equipmentFunctionalityVerified": False,
        })
    # Detect source-video changes during the extraction run, even if the
    # replacement kept the same duration and filename.
    if media_sha256(video) != digest:
        raise FrameEvidenceError("Source video changed while extracting evidence")
    index = folder / "index.html"
    # Absolute paths, arbitrary model observations and remote links are
    # deliberately omitted from the local HTML and JSON outputs.
    manifest = {
        "schemaVersion": 1, "status": "local-private-unreviewed",
        "worldId": wid, "mediaSha256": digest,
        "frameCount": len(rows), "items": rows,
        "equipmentFunctionalityVerified": False,
        "publiclyShareable": False,
    }
    index.write_text(_render_index(wid, rows), encoding="utf-8")
    atomic_json(folder / "frames.json", manifest)
    return {
        "status": manifest["status"], "worldId": wid,
        "frameCount": len(rows), "index": str(index),
        "functionalityVerified": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--out-dir", type=Path,
                   default=Path.home() / "Videos" / "VRCClubCharts" / "private-keyframes")
    p.add_argument("--confirm-recording-rights", action="store_true",
                   help="Confirm private source-video recording and participant permissions")
    args = p.parse_args(argv)
    try:
        if not args.confirm_recording_rights:
            raise FrameEvidenceError("Confirm recording rights before generating private keyframes")
        draft_file = args.draft.expanduser().resolve(strict=True)
        if draft_file.stat().st_size > MAX_REPORT_BYTES:
            raise FrameEvidenceError("Draft report exceeds size limit")
        report = json.loads(draft_file.read_text(encoding="utf-8"))
        outcome = export_frame_evidence(
            report, args.video, args.out_dir,
            authorize_direct_draft=args.confirm_recording_rights,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
