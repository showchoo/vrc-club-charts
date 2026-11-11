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

## Gemini動画アップロードでHTTP 400になる場合（2026-11-11）

実機で30秒のH.264/MP4自動撮影（120フレーム、映像品質ok）に成功しましたが、旧コードでは \`client.files.upload(file=...)\` が \`400 Bad Request\` を返す事例がありました。原因は未確定です。Gemini公式仕様では短い動画をモデル入力に直接含める方式があるため、現行の \`evaluate_interior_video.py\` は **12MiB以下ならinline video**、それより大きい動画は **MIMEタイプを明示したFiles API** を利用します。別方式による自動再送はしません。

既存動画は再撮影不要。必要な撮影/参加者の権利とGeminiクラウド転送同意を確認してから、使用中のPowerShellで以下を実行します（APIキーを画面やログに表示しないこと）。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$video = "$HOME\Videos\VRCClubCharts\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T034002Z.mp4"
Get-Item "$video" | Select-Object Name, Length
py -3 scripts/evaluate_interior_video.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --video "$video" --source owner-recorded --out "$HOME\Videos\VRCClubCharts\private-evaluations\dj_floor_20261111T034002Z.draft.json" --analyze --confirm-sharing
~~~

\`Length\` が12,582,912バイト以下であればFiles APIを使わない経路に切り替わります。容量がそれより大きい場合は引き続きFiles APIを使うため、同じ400が発生したら、まずサイズ・利用可能モデル・Google側のキー権限とネットワーク条件を調べます。例外時は処理段階とHTTPコードのみを表示し、HTMLエラーやトークンをログに出しません。結果は非公開ドラフトのみで、公開ランキングへ反映しません。

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
