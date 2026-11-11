# ローカルPC巡回：Googleカレンダーの「仕事」の日だけ起動するゲート

## 方針

自宅Windows PCでの将来の巡回は、**Googleカレンダーのメインカレンダーに勤務予定が確認できた日だけ**実行します。日付は日本時間（JST、UTC+09:00）です。勤務日以外、Google API停止、認証期限切れ、予定の判別不能時は必ず巡回をスキップします。

現在の仕組みは**実際のSteam/VRChat起動やワールド間自動移動を実装したものではありません**。Googleカレンダーから勤務日を安全に読み取る判定ゲートを追加し、既存の**手動入室が必要な**一ワールド調査ランチャーから `-WorkdayOnly` で利用できるようにしたものです。これをスケジュール実行する設定は、無人巡回の認可・画面取得・Windowsセッション・実行時刻等が整うまで作成しません。

### タイトル判定

- **勤務日**：状態 `confirmed` で、タイトルが完全一致の `仕事` または `仕事` に続いて通常スペース・全角スペース・タブの付く予定。例：`仕事　会計なし`、`仕事　明けで滝田バスケ`、`仕事　締め`。予定の開始～終了と当該JST日付の時間帯が重なっている必要があります。
- **対象外**：`仕事なし`、`仕事ズボン縫う`、`仕事の準備`、`NBA` 等。キャンセル・仮予定も対象外。
- 日付はイベント開始時刻のタイムゾーンをJSTに直して判定。終日予定にも対応。
- Googleカレンダーを読むだけです。予定を書き換えたり、仕事日の一覧をGitHubに保存したりしません。

## 初回だけ行うローカルOAuth設定

ChatGPTで接続したGoogleカレンダーは、そのままローカルWindowsプログラムの認証情報にはなりません。Windows側でGoogle Calendar APIの**読み取り専用OAuth認証**を一度行う必要があります。

1. Google Cloud Consoleでプロジェクトを用意し、**Google Calendar API**を有効にします。
2. Google Auth PlatformのOAuth同意画面を設定し、OAuth 2.0の**デスクトップアプリ**用クライアントを作成してJSONをダウンロードします。ログインするアカウントは、勤務予定を登録しているメインカレンダーのGoogleアカウントです。テスト公開設定や再認証要求の詳細はGoogleの管理画面で確認してください。
3. クライアントJSONを**GitHub管理外の** `$env:LOCALAPPDATA\VRCClubCharts\calendar-auth\oauth-client.json` に保存します。**JSONの中身、トークン、パスワードはチャットにも貼らない**でください。
4. Windows PowerShellで次を実行します。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
py -3 scripts/workday_patrol_gate.py --authorize
~~~

初回はブラウザでGoogleの認証画面が開きます。許可は `calendar.events.readonly`（予定の読み取りのみ）。以後、ローカル `%LOCALAPPDATA%\VRCClubCharts\calendar-auth\token.json` の認証情報を利用します。期限切れでも更新トークンが有効なら自動更新します。失効時にブラウザを勝手に開かず、**巡回をスキップ**します。

Google公式：[Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)／[events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)

## 判定のみの実行（VRChatは起動しない）

~~~powershell
py -3 scripts/workday_patrol_gate.py
~~~

- **終了コード0**：`workday-eligible`、勤務日なので巡回対象としてよい（ただし自動巡回の実行は未実装）。
- **終了コード3**：`non-workday-skip`、勤務予定がなく巡回を行わない。
- **終了コード2**：`calendar-unavailable-skip`、認証/API/取得データに問題があるため巡回禁止。

開発用に特定の日付を調べることもできます。

~~~powershell
py -3 scripts/workday_patrol_gate.py --date 2026-11-12
~~~

返すJSONは勤務日の可否と該当件数だけであり、個人の勤務予定タイトル・イベントID・トークンは表示しません。

## 既存の手動調査ランチャーの勤務日限定モード

従来の手動入室済みPrivate World調査コマンドに `-WorkdayOnly` を加えると、**カメラ/Steam/VRChat等の処理の前**に勤務日を確認します。

~~~powershell
.\scripts\launch_one_world_inspection.ps1 -WorldId "<手動入室済みWorldのID>" -ConfirmPrivateInstance -WorkdayOnly
~~~

勤務日でも、既存の権利確認・手動入室・実機安全停止がすべて必要です。手動の診断や合成テストは勤務日以外でも実行できます。

### 将来の自動化に向けた注意

- 現在は**無人ログイン、自動World入室、巡回スケジューラ、PC電源ON/OFFは未実装**です。Googleカレンダーの勤務日判定だけでは無人巡回は成立しません。
- ローカルPCが起動・起床していない日は、スケジューラからも実行できません。Windowsのロック画面や省電力状態では、現在の最前面VRChat画面キャプチャ方式は使えません。
- 今後、巡回を実装するときは**実行直前に最新の勤務日を再照会し、不明なら停止**すること。勤務日を固定日付リストにしないこと。
- 無人操作・撮影・クラブ内入室は、VRChat運営からその運用形態について明確な許可が得られてから有効化すること。現時点のコードはその承認を代用しません。
- Googleの認証ファイルはローカルに保持し、公開GitHub・Vercel・GitHub Actions・Supabaseに保存しません。
