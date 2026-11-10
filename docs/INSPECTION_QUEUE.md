# 複数World検査キュー（Windowsローカル・試験段階）

この機能は、既存の「1ワールド録画 → 任意のGemini分析」パイプラインを**複数Worldの順番管理**につなげます。対象リストは既存の公開Worldカタログから自動作成します。**VRChatへのログイン、World自動入室、無人巡回、DJプレイヤー実動作テスト、ランキング自動公開はしません。** 人間が各Worldへ入室し、画面のWorld IDを確認して入力してから録画します。実機テストは未実施です。

既存の[Windows単一World試験](ONE_WORLD_INSPECTION.md)、[OSCスイープ](BOUNDED_OSC_SWEEP.md)、[動画解析](AUTOMATED_INSPECTION_PIPELINE.md)も確認してください。

## 使い方

PowerShellをリポジトリのルートで開き、必要なPython/FFmpeg/mssなどを既存ガイドに従って準備します。まず**録画・入室・課金API呼び出しを一切しない**計画表示を試します。

~~~powershell
py -3 scripts/inspection_queue.py --limit 5
~~~

実行用のプライベートな計画を、WindowsのVideos/VRCClubCharts/inspection-queue-plan.json に保存します（Gitには保存しません）。

~~~powershell
py -3 scripts/inspection_queue.py --prepare --limit 5
~~~

起動前に単一Worldランチャーの -Diagnose で実機前提条件を確認できます。録画のみの複数World試験を開始する場合：

~~~powershell
py -3 scripts/inspection_queue.py --run --seconds 45
~~~

ツールは各World名とIDを表示し、**公式VRChatクライアントで、そのWorldの人がいない非公開インスタンスへ手動入室**するよう要求します。録画権利と参加者不在を確認したら表示されたWorld ID全体を入力します。録画開始時は案内に従ってVRChat画面へフォーカスを戻してください。

許可のある環境でOSCによる短いカメラスイープも使う場合は、以下を明示指定します。**OSCの公式サポート自体は無人エージェント運用の許可を意味しません。** 当該使用方法について運営の許諾を確認してから実行してください。

~~~powershell
py -3 scripts/inspection_queue.py --run --seconds 45 --sweep --confirm-platform-authorization --acknowledge-automation-risk
~~~

動画をGeminiで処理する場合（クラウド送信、利用料の可能性あり）は、撮影・分析権利を確認したうえで次のように指定します。

~~~powershell
py -3 scripts/inspection_queue.py --run --analyze-video --confirm-recording-rights --confirm-gemini-upload
~~~

スイープと動画分析は各条件が揃えば組み合わせ可能です。**公開プレビュー・ランキングの自動更新はこのキューでは常に無効**です。

## 停止・再開と個人情報保護

- 1回の計画は最大25World。公開状態かつランキング候補になっているIDのみ選択し、無効ID・重複を除外します。候補であっても実際のアクセス可否は保証しません。
- World IDを入力しない・qを入力する・Ctrl+Cで止めた場合、次のWorldへ進みません。
- 各成功はVideos/VRCClubCharts/inspection-queue-state.json に記録され、同じ計画で次回開始すると完了分をスキップします。
- 録画・解析に失敗したWorldで停止します。再起動時はそのWorldから再試行でき、再度手動確認が必要です。
- 計画のWorld構成・順序が変わると、古い検査記録を誤用しないようエラーで停止します。別の検査バッチでは --capture-dir を別フォルダに指定してください。重要な動画や監査JSONは削除しないでください。
- 計画、状態JSON、MP4、AIレポートはローカルに保存し、GitHub/Vercelへ自動アップロードしません。必要な場合のみ既存の別ツールで明示的にプレビュー公開してください。

## 開発者向けオフラインテスト

~~~powershell
py -3 -m unittest tests.test_inspection_queue
~~~

静的なカタログフィルタ、重複排除、別計画への誤った再開防止、手動確認、途中失敗停止、クラウドとOSCの同意条件をモックで確認します。これはVRChatでの実機動作確認の代わりにはなりません。

## 次の開発ゲート

**実機で1ワールドを録画し、フォーカス/OSC/MP4/動画解析の動作を確認すること。** その後、World IDと入室済みインスタンスの一致を確実に検証できる手段、インスタンスの権利・参加者の扱い、衝突や人物の検出、緊急停止、VRChatの具体的な許可範囲を確認してから、無人でのWorld切替を設計します。
