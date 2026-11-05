"""Generate a PRIVATE offline HTML label-review screen for full video inspection.

No server, remote scripts, cookies, analytics, API requests or auto-labeling.
A browser can open the reviewed video from its local file:// URL; the operator
must review the FULL recording and explicitly classify all six categories.
The completed JSON is downloaded to a user-chosen local path.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

try:
    from scripts.inspection_facility_inventory import FACILITIES, LABELS_JA
except ModuleNotFoundError:
    from inspection_facility_inventory import FACILITIES, LABELS_JA


def render_review_screen(*, template: dict, video: Path) -> str:
    if template.get("schemaVersion") != 1 or set(template.get("labels", {})) != set(FACILITIES):
        raise ValueError("Unexpected video label template")
    sha = template.get("mediaSha256", "")
    wid = template.get("worldId", "")
    if not isinstance(sha, str) or len(sha) != 64 or not isinstance(wid, str) or not wid.startswith("wrld_"):
        raise ValueError("Invalid review screen provenance")
    video = Path(video).expanduser().resolve(strict=True)
    video_url = html.escape(video.as_uri(), quote=True)
    seed = {
        "schemaVersion": 1, "worldId": wid,
        "mediaSha256": sha,
        "reviewedEntireRecording": False,
        "scope": "appearance_only_within_this_video_not_entire_vrchat_world",
        "labels": {name: "unreviewed" for name in FACILITIES},
        "notEquipmentFunctionalityVerification": True,
    }
    # Only fixed category labels, UUID-like World ID and SHA-256 enter JS.
    seed_json = json.dumps(seed, ensure_ascii=True).replace("<", "\\u003c")
    categories = json.dumps(
        [{"kind": kind, "label": LABELS_JA[kind]} for kind in FACILITIES],
        ensure_ascii=True,
    ).replace("<", "\\u003c")
    output_name = f"facility-labels-{sha[:16]}.json"
    page = r'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; media-src 'self' file:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>ローカルDJ設備認識の正解ラベル作成</title>
<style>body{font:16px system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#141518;color:#f0f0f2}
h1{font-size:1.5rem}h2{font-size:1.05rem}p{line-height:1.65}
video{width:100%;max-height:480px;background:#000;border-radius:8px}
fieldset{border:1px solid #555;border-radius:10px;margin:1rem 0;padding:1rem}
legend{font-weight:650}button{cursor:pointer;background:#303642;color:white;border:1px solid #86868a;border-radius:8px;padding:.5rem .8rem;margin:.25rem}
button[aria-pressed="true"]{background:#205f4d;border-color:#7ee0bc}
button:disabled{opacity:.45;cursor:not-allowed}small{color:#b1b1b8}
#download{background:#18624d;font-size:1.05rem;padding:.8rem}code{overflow-wrap:anywhere}
</style></head><body>
<h1>DJ設備の認識精度を確認（非公開・ローカル）</h1>
<p>映像を最初から最後まで確認し、各設備が<strong>この動画のどこかに映ったか</strong>を記録してください。
これはワールド全体に設備が存在するか、DJ配信が動作するかの判定ではありません。</p>
<p><small>World ID: <code id="world-id"></code> ｜ 動画SHA-256先頭: <code id="digest"></code></small></p>
<video id="clip" controls preload="metadata" src="__VIDEO_URL__"></video>
<p><small>再生できない場合は元のMP4を別のプレイヤーで開いて全編を確認してください。
個人情報・他ユーザーが映る動画や画像を公開・共有しないでください。外部送信は行いません。</small></p>
<form id="review" autocomplete="off"><div id="classes"></div>
<label><input type="checkbox" id="full"> この録画を最後まで確認し、判定が動画全体に対するものであることを確認しました。</label>
<p><button id="download" type="submit" disabled>正解ラベルJSONを保存</button></p>
<p id="state" role="status">6項目すべてを選択してください。</p></form>
<script>
"use strict";
const seed = __SEED_JSON__;
const categories = __CATEGORIES__;
const options = [
  {value:"visible", label:"映っている"},
  {value:"not_visible", label:"動画内で見つからない"},
  {value:"uncertain", label:"判別できない"}
];
const labels = {...seed.labels};
const container = document.getElementById("classes");
const confirm = document.getElementById("full");
const download = document.getElementById("download");
const state = document.getElementById("state");
document.getElementById("world-id").textContent = seed.worldId;
document.getElementById("digest").textContent = seed.mediaSha256.slice(0,16);
function refresh() {
  const filled = categories.filter(x => labels[x.kind] !== "unreviewed").length;
  download.disabled = !confirm.checked || filled !== categories.length;
  state.textContent = filled + "/" + categories.length
    + "項目回答済み。機能の動作確認を意味しません。";
}
for (const category of categories) {
  const field = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = category.label;
  field.appendChild(legend);
  for (const choice of options) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = choice.label;
    button.setAttribute("aria-pressed","false");
    button.addEventListener("click", () => {
      labels[category.kind] = choice.value;
      for (const peer of field.querySelectorAll("button")) {
        peer.setAttribute("aria-pressed", String(peer === button));
      }
      refresh();
    });
    field.appendChild(button);
  }
  container.appendChild(field);
}
confirm.addEventListener("change", refresh);
document.getElementById("review").addEventListener("submit", event => {
  event.preventDefault();
  refresh();
  if (download.disabled) return;
  const completed = {...seed, reviewedEntireRecording:true, labels:{...labels}};
  const data = new Blob([JSON.stringify(completed,null,2)+"\n"], {type:"application/json"});
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "__OUTPUT_NAME__";
  a.click();
  // Give the browser time to begin the download before revoking the blob.
  setTimeout(() => URL.revokeObjectURL(url), 30000);
  state.textContent = "正解ラベルをローカル保存しました。動画はアップロードされません。";
});
refresh();
</script></body></html>'''
    return page.replace("__VIDEO_URL__", video_url).replace("__SEED_JSON__", seed_json).replace(
        "__CATEGORIES__", categories).replace("__OUTPUT_NAME__", output_name)
