# Windows VRChat inspector — local pilot

## Current status

`scripts/windows_vrchat_inspector.py` is a **local Windows prototype**. It can
record the visible VRChat window of a manually entered world, optionally call
Gemini for a bounded set of OSC movement commands, and optionally produce an
AI video evaluation with the existing `scripts/evaluate_interior_video.py`.
**It has not yet been run on the user's PC or against the actual VRChat client.**
There is no automatic login, world hopping, API scraping, or automatic public ranking.

### Platform policy

VRChat's Terms of Service (effective October 23, 2026, Section 13.2(i/j))
restrict external automated agents and access inconsistent with individual
human use: https://hello.vrchat.com/legal .
The OSC input controls are officially documented at
https://docs.vrchat.com/docs/osc-as-input-controller .
VRChat support's refusal to interpret the rules for individual users is NOT
permission to run an unattended inspection bot. `--ai-explore` is a
technically supported, **explicit opt-in** integration that may breach these
rules; use it only where the platform has authorized the intended activity.

## Stationary OSC camera sweep (new opt-in pilot)

The [bounded sweep guide](BOUNDED_OSC_SWEEP.md) explains the new
`-Sweep` PowerShell mode. It makes up to four short rightward view
rotations while recording a manually opened, private, empty World in the
official Windows VRChat client. **No Gemini API key is needed** for this
mode. However, the operator must independently confirm platform
authorization (`-ConfirmPlatformAuthorization`), instance/privacy rights,
and the automation risk. It never auto-joins Worlds, validates equipment
functions, or publishes a ranking. Actual Windows testing is still pending.

## Windows prerequisites

- Windows 10/11, a visible official VRChat desktop client, already manually
  inside a private instance, no other participants visible.
- Python 3.10+; FFmpeg in PATH (with libx264 encoder).
- `py -m pip install mss google-genai`
- For Gemini, set your own `GEMINI_API_KEY` in local PowerShell only.
- For AI movement, enable VRChat OSC Input in the in-game Action Menu.
- Have any needed recording permissions from creators/participants.

The program does not store account credentials, alter the VRChat client,
automatically log in or join a world, or use unofficial VRChat APIs.

## Recording a manually selected world without AI control

Open PowerShell in your local VRC Club Charts repository folder. Start
VRChat, enter a private instance, and bring the VRChat window to the foreground.
Replace the sample World ID with the actual world you have opened.

```powershell
py scripts/windows_vrchat_inspector.py --world-id wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 --seconds 45 --private-instance-confirmed
```

Produces a local MP4 (video only, no audio) and JSON audit under your Windows
Videos/VRCClubCharts folder. It records the client rectangle, not your whole
desktop. When you launch it from PowerShell, switch back to VRChat within 15 seconds.
The client must remain visible and focused. Stop via Ctrl+C or change
window focus. This is still awaiting real Windows smoke testing.

## 2026年のGemini新型AuthキーとHTML 400について

2026-11-11の実機診断で、動画なしの `GET /v1beta/models` すら `HTTP 400` / `responseKind: "html"` で失敗しました。`google-genai` SDKでも同じHTML 400が発生するため、動画サイズ・動画フォーマット・SDKのみの不具合とは断定できません。**動画を再撮影・再圧縮せず、認証キーとプロジェクトの設定を優先して調べます。**

Googleは2026-05-28からGoogle AI Studio新規作成キーをAuthキーへ移行しています。新型キーは通常 `AQ.`、旧Standardキーは `AIza` という形式です。旧診断の `keyLooksLikeStandardGoogleKey: false` は新型キーにも当てはまるため、**無効キーの根拠ではありません**。現行診断は機密値を表示しない `keyFamily`（`authorization` / `legacy-standard` / `unrecognized` / `missing`）へ変更しました。この分類は文字列パターンだけであり、キーの有効性の証明ではありません。

- 公式ドキュメント: https://ai.google.dev/gemini-api/docs/api-key
- 同一エラーの開発者報告（2026-10-26）: https://discuss.ai.google.dev/t/aq-authorization-key-returns-generic-html-400-for-get-v1beta-models-on-windows-11/195158
- 上記フォーラムで2026-10-29にGoogle担当者は、**新しいGoogle AI Studioプロジェクトに新しいAuthキーを作り、最小限のAPIリクエストで検証する**ことを提案しています。ただし、解決を保証する回答ではありません。

対処はGoogle AI StudioのAPI Keys画面でキーの種類と対象プロジェクト、Gemini APIへの割当を確認し、必要なら新しいプロジェクトに新しいキーを作って、現在のPowerShellの `$env:GEMINI_API_KEY` を差し替えて専用診断を再実行することです。既存のVercel用シークレットや稼働中サイトの設定は**変更しない**でください。キーそのものはGitHub/チャット/ログに投稿しないでください。

## 動画・SDKを使わずにGeminiの400エラーを診断（2026-11-11）

有効な `gemini-3.5-flash-lite` モデルに、`google-genai` SDKからたった一文を送ってもHTML形式の `400 Bad Request` が返る場合、動画を何度圧縮しても原因は分かりません。先に**公式REST APIへPython標準ライブラリ（urllib）で直接通信**する診断を追加しました。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/diagnose_gemini_connection.py --run
~~~

この診断は、環境変数 `GEMINI_API_KEY` をHTTPヘッダーに載せ、モデル一覧GETを送ります。**GETが成功したときだけ**、固定文字列 `Reply with OK only` の小さな生成POSTを1回送ります。VRChatや動画には触れません。GitHubへも送信しません。API利用料が発生する可能性はあります。APIキー本体、リクエスト本文、API応答本文、プロキシURLは画面に出しません。

見方：
- `status: "rest-text-ok"`：APIキーと基本的な生成REST通信は成功。SDKの`httpx2`通信・環境設定の差を優先調査
- `status: "rest-list-failed"`：SDK以外でもモデル一覧取得に失敗。HTTPコード・`responseKind`・`apiErrorStatus`・プロキシ環境の有無を確認
- `modelList.responseKind: "html"`：Google公式の構造化JSONエラーでない応答。キー・プロキシ・ネットワーク・Googleのフロントエンドなどを切り分ける
- `keyHasOuterWhitespace` / `keyHasQuoteCharacters` がtrue：誤って空白や引用符をキーに含めた可能性。**実際のキーは表示・共有しない**
- `status: "rest-generate-failed"`：モデル一覧GETは成功したが生成POSTが失敗

Python標準ライブラリのみで動き、Windows PowerShellの`py -c`の複雑な引用符も不要です。診断結果だけを開発相談へ渡せます。

## Gemini動画の送信途中で切断された場合（2026-11-11）

実機で10.74 MiBの30秒MP4は直接送信経路に進みましたが、`httpx2.RemoteProtocolError: Server disconnected without sending a response` で応答前に通信断となりました。原因は未確定であり、動画不良・モデル名の誤りを示すものではありません。長いトレースに代えて、現行コードでは `Gemini model-request transport failed` と安全な診断案内を表示します。

**1. APIの基本通信（テキストのみ、小さなリクエスト）を先に確認する。** APIキーは現在のPowerShell内に `GEMINI_API_KEY` として設定済みであること。値を貼り付けたり表示したりしないこと。

~~~powershell
py -3 -c "import os; from google import genai; client=genai.Client(api_key=os.environ['GEMINI_API_KEY']); print(client.models.generate_content(model='gemini-3.5-flash-lite', contents='Reply OK only').text)"
~~~

PowerShellでは外側をダブルクォート、Python内の文字列をシングルクォートにする（逆にするとWindowsでPythonへの引用符が失われ、SyntaxErrorになる場合がある）。ここでも通信が切れるなら、動画の圧縮より先にインターネット接続、プロキシ/VPN、ローカルファイアウォール、Google APIへのアクセスを確認する。入力やAPIキーをこのチャットに貼らないこと。

**2. テキスト通信が成功した場合、元動画を変更せずに別ファイルへ軽量化する。** VRChatで録画し直す必要はなく、30秒のまま2fps・横960px・映像600kbps程度（おおむね2～3MiB以下）へ変換できる。映像のサンプル密度は下がるため、細かな機材・文字の確認精度は低下し得る。

~~~powershell
$video = "$HOME\Videos\VRCClubCharts\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T034002Z.mp4"
$small = "$HOME\Videos\VRCClubCharts\dj_floor_20261111T034002Z_small.mp4"
ffmpeg -hide_banner -loglevel error -n -i "$video" -vf "fps=2,scale=960:-2" -an -c:v libx264 -preset veryfast -b:v 600k -maxrate 700k -bufsize 1400k -movflags +faststart "$small"
(Get-Item "$small").Length / 1MB
~~~

**3.** 動画内の人の撮影・分析・クラウド送信に必要な権利と同意がある場合だけ、軽量版を**別名の非公開ドラフト**に解析する。

~~~powershell
py -3 scripts/evaluate_interior_video.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --video "$small" --source owner-recorded --out "$HOME\Videos\VRCClubCharts\private-evaluations\dj_floor_20261111T034002Z_small.draft.json" --analyze --confirm-sharing
~~~

軽量版は元動画とは異なるハッシュを持つため、ドラフトの出典はこの軽量版になる。公開ランキングへは反映されない。**通信断はプロキシやネットワーク要因の可能性もあり、圧縮すれば必ず直るわけではない。**

## Gemini動画アップロードでHTTP 400になる場合（2026-11-11）

実機で30秒のH.264/MP4自動撮影（120フレーム、映像品質ok）に成功しましたが、旧コードでは `client.files.upload(file=...)` が `400 Bad Request` を返す事例がありました。原因は未確定です。Gemini公式仕様では短い動画をモデル入力に直接含める方式があるため、現行の `evaluate_interior_video.py` は **12MiB以下ならinline video**、それより大きい動画は **MIMEタイプを明示したFiles API** を利用します。別方式による自動再送はしません。

既存動画は再撮影不要。必要な撮影/参加者の権利とGeminiクラウド転送同意を確認してから、使用中のPowerShellで以下を実行します（APIキーを画面やログに表示しないこと）。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$video = "$HOME\Videos\VRCClubCharts\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T034002Z.mp4"
Get-Item "$video" | Select-Object Name, Length
py -3 scripts/evaluate_interior_video.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --video "$video" --source owner-recorded --out "$HOME\Videos\VRCClubCharts\private-evaluations\dj_floor_20261111T034002Z.draft.json" --analyze --confirm-sharing
~~~

`Length` が12,582,912バイト以下であればFiles APIを使わない経路に切り替わります。容量がそれより大きい場合は引き続きFiles APIを使うため、同じ400が発生したら、まずサイズ・利用可能モデル・Google側のキー権限とネットワーク条件を調べます。例外時は処理段階とHTTPコードのみを表示し、HTMLエラーやトークンをログに出しません。結果は非公開ドラフトのみで、公開ランキングへ反映しません。

## Optional video AI assessment

```powershell
$env:GEMINI_API_KEY="your-local-key"
py scripts/windows_vrchat_inspector.py --world-id wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 --seconds 45 --private-instance-confirmed --evaluate --confirm-gemini-upload
```

The video is uploaded to Gemini only with these explicit switches; a
`*.evaluation-draft.json` is saved locally and is NEVER auto-published.
Provider costs, limits, and privacy policies apply. Avoid recording any
other users, personal identifiers, unauthorized music or private content.

## Opt-in AI-guided movement (authorized environments only)

The code supports up to 12 Gemini screenshot decisions and sends only
brief forward/back/strafe/turn OSC inputs. It is NOT enabled by default.

```powershell
py scripts/windows_vrchat_inspector.py --world-id <your-world-id> --seconds 45 --private-instance-confirmed --ai-explore --acknowledge-automation-risk --confirm-gemini-upload
```

Use this mode only with permission for the automated activity. Each movement
lasts at most 0.65 seconds; commands are allowlisted. The system resets OSC
movement axes after each action, on errors, and at exit. No click, jump, grab
or interactive equipment testing is implemented. Screenshot content is sent
to Gemini during AI mode; no direct VRChat API calls occur.

## Limits, safety, and remaining work

- Maximum 120 seconds, at most 12 AI actions and no scheduled batch scanning.
- No audio recording; the script cannot judge sound quality.
- No reliable detection of other users or obstacles. Private-instance
  confirmation is the user's responsibility. The program stops on focus loss.
- The script only accepts a manually specified World ID; it cannot verify that
  it matches the open world. It does not navigate to other worlds automatically.
- Videos and JSON stay locally in Windows. No GitHub, Supabase or Vercel upload.
- No claims of verified DJ livestream operation or optimized FPS.
- No change to the production Craftsmanship Ranking.
- Windows client screenshot capture, MP4 encoding, Gemini and OSC need
  end-to-end tests on the user's own PC; CI tests use mocked components.

Next: verify the local recording pipeline, evaluate image-based action safety
in a consented test environment, add route memory and obstacle recovery, then
develop a real equipment-testing protocol where platform use is authorized.

## Automated local video evaluation and safe public visual previews

See [Automated Inspection Pipeline](AUTOMATED_INSPECTION_PIPELINE.md) for
consent-gated batch processing, numeric visual preview scores, Git deployment
and provenance/revocation rules. The batch analysis is independent of
unattended VRChat access and cannot claim verified DJ equipment function.
