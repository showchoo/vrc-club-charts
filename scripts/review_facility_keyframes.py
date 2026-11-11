#!/usr/bin/env python3
"""Private human correction for AI-suggested DJ facility keyframes.

Creates a separate local review record and reviewed HTML index; does not
overwrite original MP4, Gemini draft, extracted images, evidence manifest,
public rankings or any remote system. No network calls.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path

try:
    from scripts.evaluate_interior_video import WORLD_ID
    from scripts.inspection_facility_inventory import FACILITIES, LABELS_JA
    from scripts.auto_process_interior_queue import ROOT, atomic_json
except ModuleNotFoundError:
    from evaluate_interior_video import WORLD_ID
    from inspection_facility_inventory import FACILITIES, LABELS_JA
    from auto_process_interior_queue import ROOT, atomic_json


VERDICTS = {
    "not-visible-from-vantage": "この撮影位置から対象を確認できない（World内に存在しないという意味ではありません）",
    "visible-appearance-only": "外観を確認（機材の動作や配信機能は未検証）",
    "uncertain": "映像だけでは判別不能",
}
REASONS = {
    "raised-area-out-of-view": "対象が段差・高所にあり、撮影位置から見えない",
    "occluded": "壁・物体などで遮られている",
    "ai-confused-stage": "AIが舞台・スクリーン等を設備と誤認した可能性",
    "other-visibility-issue": "この映像だけでは対象の外観を確認できない",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class HumanReviewError(ValueError):
    pass


def _load_private_manifest(folder: Path) -> dict:
    if folder.is_symlink() or folder.is_relative_to(ROOT):
        raise HumanReviewError("Review must remain in an ordinary private folder outside the repository")
    manifest_file = folder / "frames.json"
    index_file = folder / "index.html"
    if manifest_file.is_symlink() or not manifest_file.is_file() or not index_file.is_file():
        raise HumanReviewError("Missing complete private keyframe evidence")
    if manifest_file.stat().st_size > 1024 * 1024:
        raise HumanReviewError("Frame manifest is too large")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise HumanReviewError("Invalid evidence manifest")
    wid, digest = manifest.get("worldId"), manifest.get("mediaSha256")
    if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid):
        raise HumanReviewError("Invalid World ID")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise HumanReviewError("Invalid video provenance hash")
    if folder.name != f"{wid}_{digest}":
        raise HumanReviewError("Folder does not match source video identity")
    if (manifest.get("status") != "local-private-unreviewed" or
        manifest.get("publiclyShareable") is not False or
        manifest.get("equipmentFunctionalityVerified") is not False):
        raise HumanReviewError("Only unranked, private, unreviewed keyframes can be reviewed")
    items = manifest.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 6:
        raise HumanReviewError("Expected 1-6 local evidence images")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise HumanReviewError("Malformed image record")
        kind, image = item.get("kind"), item.get("file")
        if kind not in FACILITIES or kind in seen:
            raise HumanReviewError("Unknown or duplicate facility image")
        if (not isinstance(image, str) or image != Path(image).name or
                not re.fullmatch(r"[a-z_]+_[0-9]{6}ms\.jpg", image)):
            raise HumanReviewError("Invalid image filename")
        if (not isinstance(item.get("humanReviewed"), bool) or
                item["humanReviewed"] is not False or
                item.get("equipmentFunctionalityVerified") is not False):
            raise HumanReviewError("Unexpected existing review or functionality status")
        timestamp, confidence = item.get("timestampSeconds"), item.get("confidence")
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or
            not math.isfinite(timestamp) or not 0 <= timestamp <= 125.25 or
            isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or
            not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise HumanReviewError("Invalid evidence time or confidence")
        image_path = folder / image
        if image_path.is_symlink() or not image_path.is_file() or image_path.stat().st_size < 300:
            raise HumanReviewError("Missing local source image")
        seen.add(kind)
    return manifest


def _render_review_index(manifest: dict, reviews: list[dict]) -> str:
    by_kind = {review["kind"]: review for review in reviews}
    cards = []
    for item in manifest["items"]:
        kind = item["kind"]
        review = by_kind.get(kind)
        label = "未確認（AIによる外観候補のみ）"
        reason = ""
        if review:
            label = VERDICTS[review["verdict"]]
            reason = REASONS[review["reason"]]
        cards.append(
            "<article><h2>" + html.escape(LABELS_JA[kind]) + "</h2>" +
            '<img src="' + html.escape(item["file"], quote=True) +
            '" loading="lazy" alt="対象の根拠とされたフレーム">' +
            "<p>AI候補時刻: " + f'{item["timestampSeconds"]:.2f}' +
            "秒／AI自己申告の信頼度: " + f'{item["confidence"]:.0%}' +
            "</p><p>人手確認: " + html.escape(label) + "</p>" +
            ("<p>補足: " + html.escape(reason) + "</p>" if reason else "") +
            "</article>"
        )
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>非公開・設備の人手確認結果</title>'
        '<style>body{background:#17181a;color:#f3f3f3;font:16px system-ui,sans-serif;'
        'max-width:1000px;margin:2rem auto;padding:0 1rem}article{padding:1rem;'
        'border:1px solid #666;border-radius:12px;margin:1rem 0}'
        'img{max-width:100%;height:auto}p{line-height:1.5}</style></head><body>'
        '<h1>非公開・DJ設備の人手確認</h1><p>'
        'この撮影位置で見えなかったことはWorldに設備が存在しない証明ではありません。'
        '表示画像と人手判定は外観のみを対象とし、DJ配信・再生・操作・音質は未検証です。'
        '動画・画像・レビューは公開せずローカルで管理してください。</p>'
        + "".join(cards) + "</body></html>"
    )


def record_review(folder: Path, *, facility: str, verdict: str,
                  reason: str) -> dict:
    """Explicit human attestation about THIS camera vantage, not whole World."""
    folder = folder.expanduser().resolve(strict=True)
    if facility not in FACILITIES or verdict not in VERDICTS or reason not in REASONS:
        raise HumanReviewError("Unknown facility/verdict/reason")
    manifest = _load_private_manifest(folder)
    if not any(x["kind"] == facility for x in manifest["items"]):
        raise HumanReviewError("Facility is not among the extracted AI candidate images")
    review_path = folder / "human-review.json"
    reviews = []
    if review_path.exists():
        if review_path.is_symlink() or review_path.stat().st_size > 1024 * 1024:
            raise HumanReviewError("Unsafe existing review file")
        previous = json.loads(review_path.read_text(encoding="utf-8"))
        if (not isinstance(previous, dict) or previous.get("schemaVersion") != 1 or
            previous.get("status") != "private-human-appearance-review" or
            previous.get("worldId") != manifest["worldId"] or
            previous.get("mediaSha256") != manifest["mediaSha256"] or
            previous.get("publiclyShareable") is not False or
            previous.get("equipmentFunctionalityVerified") is not False or
            not isinstance(previous.get("reviews"), list)):
            raise HumanReviewError("Existing review provenance mismatch")
        reviews = previous["reviews"]
        kinds = [row.get("kind") for row in reviews if isinstance(row, dict)]
        if (len(kinds) != len(reviews) or len(set(kinds)) != len(kinds) or
            any(row.get("kind") not in FACILITIES or
                row.get("verdict") not in VERDICTS or
                row.get("reason") not in REASONS or
                row.get("humanReviewed") is not True
                for row in reviews)):
            raise HumanReviewError("Invalid existing review records")
    new_entry = {"kind": facility, "verdict": verdict, "reason": reason,
                 "humanReviewed": True, "equipmentFunctionalityVerified": False}
    old = next((row for row in reviews if row["kind"] == facility), None)
    if old is not None and old != new_entry:
        raise HumanReviewError("Conflicting review exists; refusing to overwrite")
    if old is None:
        reviews = [*reviews, new_entry]
    reviewed_index = folder / "reviewed-index.html"
    if reviewed_index.is_symlink():
        raise HumanReviewError("Unsafe output HTML symlink")
    # Review metadata is separate: original evidence and model draft stay intact.
    atomic_json(review_path, {
        "schemaVersion": 1, "status": "private-human-appearance-review",
        "worldId": manifest["worldId"], "mediaSha256": manifest["mediaSha256"],
        "reviews": reviews, "publiclyShareable": False,
        "equipmentFunctionalityVerified": False,
    })
    reviewed_index.write_text(_render_review_index(manifest, reviews), encoding="utf-8")
    return {"status": "private-human-appearance-review",
            "worldId": manifest["worldId"], "facility": facility, "verdict": verdict,
            "reviewedIndex": str(reviewed_index),
            "publiclyShareable": False, "equipmentFunctionalityVerified": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--facility", choices=FACILITIES, required=True)
    parser.add_argument("--verdict", choices=tuple(VERDICTS), required=True)
    parser.add_argument("--reason", choices=tuple(REASONS), required=True)
    parser.add_argument("--confirm-visual-review", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.confirm_visual_review:
            raise HumanReviewError("Explicit human visual review must be confirmed")
        result = record_review(args.frames_dir, facility=args.facility,
                               verdict=args.verdict, reason=args.reason)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
