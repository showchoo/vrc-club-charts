# VRChatの暗いクラブの写真からDJ設備の外観をAIで候補抽出する

この機能は、すでにローカルPCで取得したPrivate Worldの低照度スクリーンショットを利用して、**DJ設備の外観候補**を確認する実験です。現在の照明判定から切り離しており、VRChatの起動・自動移動・自動ログインはしません。完全自動巡回の完成を意味しません。

## 対象設備（6種類）

- DJブース（dj_booth）
- DJデッキ／ミキサーらしい機器（dj_decks）
- 映像スクリーン（video_screen）
- 照明設備（lighting_rig）
- ステージ（stage）
- 操作パネル（interactive_control）

**大きなスクリーン、スピーカー、照明やステージがあるだけでは「DJ配信できるブース」を確認したことにはなりません。** DJブースは実物が画面内にはっきり認識できる場合に限ります。外観候補が見つかっても、ライブ配信や動画/音声再生が使えるかどうかは未確認です。

## まず安全な確認（ネットワーク送信なし）

Windows PowerShell:

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/private_low_light_review.py --open
py -3 scripts/analyze_private_scene_still.py
~~~

最初のコマンドは最新の低照度キャプチャからローカル比較画面を開きます。2つめは、対象画像の記録を読み取り専用で検証するだけで、Geminiに画像を送信しません。個別のレポートを指定する場合は --report と、前回出力された lighting-cycle.json のフルパスを指定できます。

## AIに画像を送る場合（個別に明示的な同意が必要）

**自分の権利を有する、参加者が写っていないPrivate Worldの撮影画像のみ**を対象とし、Geminiへの送信を認める場合にだけ以下を実行します。

~~~powershell
py -3 -m pip install google-genai
py -3 scripts/analyze_private_scene_still.py --analyze --confirm-recording-rights --confirm-gemini-upload
~~~

あらかじめGEMINI_API_KEY環境変数が必要です。キーはチャットやGitHubに貼らないでください。

このコマンドを実行すると、元のPNGと暗部補正したPNGを**最大1280ピクセルのJPEGに変換し、2枚ともGeminiに送信**します（Exifなどは引き継がず再エンコード）。Googleへ送信されるので完全なローカル処理ではなくなります。モデルからの自由記述やユーザー名は保存せず、設備の許可済み6項目について見える/見えない/不明と数値信頼度だけをローカルに保存します。上位モデルの推論利用は契約・料金条件を確認してください。モデル名の指定は --model オプションが使えます。

**モデルの結果は未実測**です。ユーザーが確認できたPNGをモデルが認識できるかどうかは、この実際のAPI実行まではわかりません。

### 保存先とセキュリティ

既存の private-visibility-review/ に、モデル名ごとの非公開JSONを保存します。

- still-facilities-gemini-3.5-flash-lite.json（デフォルトモデル例）
- 内部に originalSha256、enhancedSha256、元画像と補正画像の各6カテゴリの視覚結果、候補一覧を記録
- 原画・補正版は**同じフレーム**なので、両方に写っていても独立した二重の証拠ではありません
- どちらか片方だけに写ったとされた設備や、信頼度が0.80未満の設備は候補に採用しません
- どちらも「visible」であっても未確認の**外観候補**にとどめます
- 既存の結果と画像ハッシュが一致したら再送信せず再利用し、改ざん・不一致時は停止
- VRChatのアカウント名、自由記述、チャット、画像そのものをサイトに掲載しません

Geminiへ実際に送信したケースでは、JSONの externalUploads と sourceMediaUploadedToGemini は true です。**未確認のDJ配信機能、動画再生、音声再生、進路安全性を認定するものではありません。** ランキングは変更せず、equipmentFunctionalityVerified・liveDJStreamingVerified・rankingEligible・publiclyShareable は false のままです。

## 自動テスト

GitHub Actionsでは、**実際の画像をGoogleへ送信しない**モック解析で、権利確認の必須性、外観の誤認防止、自由記述の拒否、画像SHA、キャッシュ再利用、機密を含むエラーのマスキングを検査します。

~~~powershell
py -3 -m unittest discover -s tests -p test_analyze_private_scene_still.py -v
~~~

AIモデルが本当に正しく認識できるかは、実画像を使った追加の評価が必要です。実画像・正解ラベルのない段階では精度を捏造せず、誤検出率・再現率を主張しません。
