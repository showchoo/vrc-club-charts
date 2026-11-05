#!/usr/bin/env python3
"""One local command to prepare and score a private DJ recognition review queue.

Discovers already-consented draft reports and exact matching local MP4 bytes.
Creates offline browser review pages, then automatically scores any fully
reviewed downloaded JSON labels. Does NOT call Gemini, VRChat or the network;
does NOT publish or change Craftsmanship/DJ functional verification.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

try:
    from scripts import calibrate_facility_recognition as cal
    from scripts.auto_process_interior_queue import atomic_json, ROOT
    from scripts.calibration_report_registry import archive_inactive_reports, model_key
    from scripts.inspection_facility_inventory import FACILITIES, LABELS_JA
except ModuleNotFoundError:
    import calibrate_facility_recognition as cal
    from auto_process_interior_queue import atomic_json, ROOT
    from calibration_report_registry import archive_inactive_reports, model_key
    from inspection_facility_inventory import FACILITIES, LABELS_JA

MAX_VIDEO_FILES = 500
MAX_DRAFT_FILES = 200


def _outside_repo(path: Path, *, must_exist: bool) -> Path:
    p = Path(path).expanduser().resolve(strict=must_exist)
    if p.is_relative_to(ROOT):
        raise cal.FacilityCalibrationError("Videos, labels and workspace must stay outside git")
    if must_exist and not p.is_dir():
        raise cal.FacilityCalibrationError("Requested input folder is not a directory")
    return p


def _video_hash(path: Path) -> str:
    return cal.media_sha256(path)


def _percentage(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "算出不可"
    return f"{100 * value:.1f}%"


def _metric_sections(metrics: list[dict]) -> str:
    if not metrics:
        return ('<section><h2>認識精度の集計</h2><p>確認済みの動画がないため'
                '実測値はありません。未確認の動画を正解データには使いません。</p></section>')
    blocks = ['<section><h2>モデル別・設備別の認識精度</h2>'
              '<p>動画全編を確認した回答との一致率です。'
              'DJ配信の動作やワールド全体の設備を確認したものではありません。'
              '少数例の数値は一般的な認識精度を保証しません。</p>']
    for item in metrics:
        blocks.append('<h3>' + html.escape(item["model"]) + '</h3>')
        blocks.append('<p>確認済み録画：' + str(item["reviewedClips"]) +
                      '件／暫定評価の必要件数：' +
                      ('最低条件を満たす' if item["enoughSamplesForPreliminaryReview"]
                       else '不足') + '</p>')
        blocks.append('<table><thead><tr><th>設備</th><th>対象数</th>'
                      '<th>適合率</th><th>再現率</th><th>F1</th>'
                      '<th>誤検出 FP</th><th>見逃し FN</th></tr></thead><tbody>')
        for kind in FACILITIES:
            score = item["classes"][kind]
            blocks.append('<tr><td>' + html.escape(LABELS_JA[kind]) +
                          '</td><td>' + str(score["evaluated"]) +
                          '</td><td>' + _percentage(score["precision"]) +
                          '</td><td>' + _percentage(score["recall"]) +
                          '</td><td>' + _percentage(score["f1"]) +
                          '</td><td>' + str(score["fp"]) +
                          '</td><td>' + str(score["fn"]) + '</td></tr>')
        blocks.append('</tbody></table><p>全設備の集計F1：' +
                      _percentage(item["microF1"]) +
                      '。判別不能の回答は除外しています。</p>')
    blocks.append('</section>')
    return "".join(blocks)


def _render_index(items: list[dict], label_dir: Path,
                  metrics: list[dict] | None = None) -> str:
    rows = []
    for row in items:
        status = "確認済み" if row["status"] == "reviewed" else "未確認"
        if row["status"] == "invalid-label":
            status = "ラベル不一致・要確認"
        uri = html.escape("review/" + row["reviewName"], quote=True)
        wid = html.escape(row["worldId"])
        sha = html.escape(row["digestPrefix"])
        rows.append(
            f'<tr><td><a href="{uri}">{wid}</a></td>'
            f'<td><code>{sha}</code></td><td>{status}</td></tr>'
        )
    location = html.escape(str(label_dir))
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        '<title>DJ設備認識・ローカル確認キュー</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:1000px;'
        'margin:2rem auto;padding:0 1rem;background:#161719;color:#f2f2f3}'
        'a{color:#b4dfff}table{width:100%;border-collapse:collapse}'
        'td,th{border:1px solid #555;padding:.6rem;text-align:left}'
        'code{overflow-wrap:anywhere}h2{margin-top:2rem}' 
        'h3{margin-top:1.5rem;color:#b4dfff}p{line-height:1.6}</style></head><body>'
        '<h1>ローカル設備認識の確認キュー</h1>'
        '<p>各ワールドを開いて録画を全編確認し、6種類の設備を判定してください。'
        '各ページでJSONを保存した後、下記の保存先を指定してこの処理を再実行すると、'
        '確認済みデータのみ自動集計します。</p>'
        f'<p>回答ラベルの検索先: <code>{location}</code></p>'
        '<p>この一覧と録画は非公開です。ワールド内のDJ設備の動作、'
        '音響や配信機能を確認したものではありません。</p>'
        '<table><thead><tr><th>World ID／確認ページ</th><th>動画識別子</th>'
        '<th>入力状況</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table>' +
        _metric_sections(metrics or []) + '</body></html>'
    )


def prepare_and_score(*, video_dir: Path, draft_dir: Path, work_dir: Path,
                      label_dir: Path) -> dict:
    video_dir = _outside_repo(video_dir, must_exist=True)
    draft_dir = _outside_repo(draft_dir, must_exist=True)
    work_dir = _outside_repo(work_dir, must_exist=False)
    label_dir = _outside_repo(label_dir, must_exist=True)

    videos = sorted(video_dir.glob("*.mp4"))
    drafts = sorted(draft_dir.glob("*.draft.json"))
    if len(videos) > MAX_VIDEO_FILES or len(drafts) > MAX_DRAFT_FILES:
        raise cal.FacilityCalibrationError("Too many local videos/drafts; split into batches")

    # Compute source hashes once. Never inspect unrelated file types.
    by_digest = {}
    for video in videos:
        if not video.is_file() or video.is_symlink():
            continue
        digest = _video_hash(video)
        if digest in by_digest:
            # Equivalent byte streams are one source; do not double count.
            continue
        by_digest[digest] = video

    validated = []
    ignored = 0
    encountered = set()
    for draft_file in drafts:
        try:
            draft = cal.read_small_json(draft_file)
            evidence = draft.get("evidence")
            if not isinstance(evidence, dict):
                ignored += 1
                continue
            digest = evidence.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                ignored += 1
                continue
            video = by_digest.get(digest)
            if video is None:
                ignored += 1
                continue
            world_id, confirmed_digest, model, _ = cal.validate_draft(draft, video)
            identity = (world_id, confirmed_digest)
            if identity in encountered:
                raise cal.FacilityCalibrationError("Duplicate draft for the same video and World")
            if any(existing["digest"] == confirmed_digest for existing in validated):
                raise cal.FacilityCalibrationError("Same video cannot be assigned to multiple Worlds")
            encountered.add(identity)
            validated.append({
                "worldId": world_id, "digest": confirmed_digest, "model": model,
                "video": video, "draft": draft_file,
            })
        except (OSError, ValueError, json.JSONDecodeError):
            ignored += 1
            continue
    if not validated:
        # The owner might revoke the last label or remove the last video.
        # Previously generated metrics are now stale and must not remain
        # in the ACTIVE workspace with apparently current accuracy figures.
        retired = archive_inactive_reports(work_dir, set())
        if work_dir.is_dir():
            (work_dir / "review-queue.html").write_text(
                _render_index([], label_dir), encoding="utf-8")
            atomic_json(work_dir / "calibration-current.json", {
                "schemaVersion": 1, "status": "no-current-reviewed-videos",
                "activeModels": [], "reviewedClips": 0,
                "readyForUnattendedDeployment": False,
                "equipmentFunctionalityVerified": False,
            })
        return {
            "status": "no-matching-consented-analysis",
            "foundVideos": len(videos), "foundDrafts": len(drafts),
            "matched": 0, "ignoredDrafts": ignored,
            "archivedOldReports": retired["archived"],
            "unknownFilesPreserved": retired["ignoredUnknown"],
            "networkUsed": False, "publicSiteChanged": False,
        }

    review_dir = work_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    grouped = {}
    queue = []
    generated = reused = invalid = reviewed = 0
    for record in validated:
        digest, world_id = record["digest"], record["worldId"]
        prefix = digest[:16]
        template = review_dir / f"labels-template-{world_id}_{prefix}.json"
        review_name = f"labels-template-{world_id}_{prefix}.review.html"
        # The source is hashed and immutable; do not regenerate existing reviews.
        if template.exists() != (review_dir / review_name).exists():
            raise cal.FacilityCalibrationError("Incomplete prior local review UI")
        if not template.exists():
            cal.create_label_template(record["draft"], record["video"], template)
            generated += 1
        else:
            saved_template = cal.read_small_json(template)
            if (saved_template.get("worldId") != world_id or
                saved_template.get("mediaSha256") != digest or
                saved_template.get("reviewedEntireRecording") is not False):
                raise cal.FacilityCalibrationError("Prior unreviewed template provenance mismatch")
            reused += 1

        label_file = label_dir / f"facility-labels-{prefix}.json"
        status = "pending"
        if label_file.is_file() and not label_file.is_symlink():
            try:
                labels = cal._check_label(cal.read_small_json(label_file),
                                          world_id=world_id, digest=digest)
                if labels:
                    reviewed += 1
                    status = "reviewed"
                    grouped.setdefault(record["model"], []).append({
                        "draft": str(record["draft"]),
                        "video": str(record["video"]),
                        "labels": str(label_file),
                    })
            except (OSError, ValueError, json.JSONDecodeError):
                status = "invalid-label"
                invalid += 1
        queue.append({
            "worldId": world_id, "digestPrefix": prefix,
            "reviewName": review_name, "status": status,
        })

    # One dataset/metrics file per Gemini model, so model versions never mix.
    metrics = []
    active_keys = set()
    for model, cases in sorted(grouped.items()):
        key = model_key(model)
        active_keys.add(key)
        manifest_path = work_dir / f"reviewed-dataset-{key}.json"
        atomic_json(manifest_path, {"schemaVersion": 1, "cases": cases})
        measured = cal.score_dataset(manifest_path)
        metrics_path = work_dir / f"calibration-metrics-{key}.json"
        atomic_json(metrics_path, measured)
        metrics.append({
            "model": model, "reviewedClips": len(cases),
            "microF1": measured["micro"]["f1"],
            "enoughSamplesForPreliminaryReview":
                measured["enoughSamplesForPreliminaryReview"],
            "classes": measured["classes"],
            "report": str(metrics_path),
        })

    retired = archive_inactive_reports(work_dir, active_keys)
    atomic_json(work_dir / "calibration-current.json", {
        "schemaVersion": 1,
        "status": "current-operator-reviewed-calibration",
        "activeModels": [
            {"model": metric["model"], "reviewedClips": metric["reviewedClips"],
             "metricsFile": Path(metric["report"]).name,
             "microF1": metric["microF1"],
             "enoughSamplesForPreliminaryReview":
                 metric["enoughSamplesForPreliminaryReview"]}
            for metric in metrics
        ],
        "reviewedClips": reviewed, "pendingClips": len(validated) - reviewed - invalid,
        "invalidLabels": invalid,
        "readyForUnattendedDeployment": False,
        "equipmentFunctionalityVerified": False,
    })
    index_file = work_dir / "review-queue.html"
    index_file.write_text(_render_index(queue, label_dir, metrics), encoding="utf-8")
    return {
        "status": "review-queue-ready",
        "foundVideos": len(videos), "foundDrafts": len(drafts),
        "matched": len(validated), "ignoredDrafts": ignored,
        "newReviewPages": generated, "reusedReviewPages": reused,
        "reviewed": reviewed, "pending": len(validated) - reviewed - invalid,
        "invalidLabels": invalid, "metricsByModel": metrics,
        "archivedOldReports": retired["archived"],
        "unknownFilesPreserved": retired["ignoredUnknown"],
        "reviewIndex": str(index_file),
        "currentIndex": str(work_dir / "calibration-current.json"),
        "networkUsed": False, "publicSiteChanged": False,
        "equipmentFunctionalityVerified": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Videos" / "VRCClubCharts"
    parser.add_argument("--video-dir", type=Path, default=base)
    parser.add_argument("--draft-dir", type=Path, default=base / "private-evaluations")
    parser.add_argument("--work-dir", type=Path, default=base / "private-calibration")
    parser.add_argument("--labels-dir", type=Path, default=Path.home() / "Downloads")
    args = parser.parse_args(argv)
    try:
        summary = prepare_and_score(video_dir=args.video_dir, draft_dir=args.draft_dir,
                                    work_dir=args.work_dir, label_dir=args.labels_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
