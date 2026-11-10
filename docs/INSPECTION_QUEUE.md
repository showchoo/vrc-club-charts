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

毎回Worldを探す手間を減らすため、**任意で公式World起動ページをブラウザーに開く**オプションも追加しました。VRChat以外のドメインは開かず、World IDを検証したうえで以下の公式サイトのページだけを使います。

~~~powershell
py -3 scripts/inspection_queue.py --run --open-world-page --seconds 45
~~~

**これはブラウザーでページを開く機能です。** VRChatクライアントへの自動ログイン、インスタンス作成、参加者不在の確認、Worldへの自動入室を行うものではありません。ページで適切な非公開インスタンスを選び、クライアントで入室を確認したうえで、コンソールに正しいWorld IDを入力してください。ページの起動に失敗したときは録画せず停止します。


許可のある環境でOSCによる短いカメラスイープも使う場合は、以下を明示指定します。**OSCの公式サポート自体は無人エージェント運用の許可を意味しません。** 当該使用方法について運営の許諾を確認してから実行してください。

~~~powershell
py -3 scripts/inspection_queue.py --run --seconds 45 --sweep --confirm-platform-authorization --acknowledge-automation-risk
~~~

動画をGeminiで処理する場合（クラウド送信、利用料の可能性あり）は、撮影・分析権利を確認したうえで次のように指定します。

~~~powershell
py -3 scripts/inspection_queue.py --run --analyze-video --confirm-recording-rights --confirm-gemini-upload
~~~

スイープと動画分析は各条件が揃えば組み合わせ可能です。**公開プレビュー・ランキングの自動更新はこのキューでは常に無効**です。

## オプション：VRChatクライアントのローカルログによるWorld照合

公式クライアントの出力ログから直近の入室イベントと「入室成功」を読み、対象のWorld IDと一致するか保守的に照合します。--verify-local-log を有効にすると録画の前後で検査し、不一致・過去の入室・非公開ではないインスタンス・途中退室の記録を検出した場合は停止します。

~~~powershell
py -3 scripts/inspection_queue.py --run --open-world-page --verify-local-log --seconds 45
~~~

- Windows標準の出力ログ保存場所（AppData/LocalLow/VRChat/VRChat）の最新 output_log_*.txt の末尾最大1MBのみ読みます。ログは変更しません。
- Worldへの手動入室から約3分以内にIDを入力してください。録画終了後にも同じ入室イベントか確認します。
- これは実機でのWorld ID確認を補助するのみです。他参加者の不在、録画権利、現在も正しいWorldにいること、VRChat運営の無人アクセス許可を独立して証明するものではありません。
- ログにはユーザーIDやIPアドレスなど個人情報が含まれます。ログ全文をGitHub、Gemini、Supabaseやチャットに共有しないでください。照合機能はログ全文を外部送信せず、ID以外のプライベートな入室情報を状態ファイルへ保存しません。
- 保守的な初期実装のため、ログに ~private( と記録されているインスタンスのみ受け付けます。参加者の人数までは判定しません。
- 明示的に指定しない限り、従来の手動録画挙動のままです。

VRChat公式：[出力ログの場所](https://help.vrchat.com/hc/en-us/articles/9521522810899-Where-do-I-find-my-Output-Logs-and-Crash-Dumps)、[Udonデバッグログ](https://creators.vrchat.com/worlds/udon/debugging-udon-projects/)。

## 停止・再開と個人情報保護

- 1回の計画は最大25World。公開状態かつランキング候補になっているIDのみ選択し、無効ID・重複を除外します。候補であっても実際のアクセス可否は保証しません。
- World IDを入力しない・qを入力する・Ctrl+Cで止めた場合、次のWorldへ進みません。
- 各成功はVideos/VRCClubCharts/inspection-queue-state.json に記録され、同じ計画で次回開始すると完了分をスキップします。
- 録画・解析に失敗したWorldで停止します。再起動時はそのWorldから再試行でき、再度手動確認が必要です。
- **Ctrl+C、フォーカス喪失、ナビゲーション安全停止、正常完了記録の欠落**があった録画は、たとえMP4に多数のフレームが残っていても検査成功と扱いません。Gemini解析と公開への連携は中止します。
- 計画のWorld構成・順序が変わると、古い検査記録を誤用しないようエラーで停止します。別の検査バッチでは --capture-dir を別フォルダに指定してください。重要な動画や監査JSONは削除しないでください。
- 計画、状態JSON、MP4、AIレポートはローカルに保存し、GitHub/Vercelへ自動アップロードしません。必要な場合のみ既存の別ツールで明示的にプレビュー公開してください。

## 開発者向けオフラインテスト

~~~powershell
py -3 -m unittest tests.test_inspection_queue
~~~

静的なカタログフィルタ、重複排除、別計画への誤った再開防止、手動確認、途中失敗停止、クラウドとOSCの同意条件をモックで確認します。これはVRChatでの実機動作確認の代わりにはなりません。

## 次の開発ゲート

**実機で1ワールドを録画し、フォーカス/OSC/MP4/動画解析の動作を確認すること。** その後、World IDと入室済みインスタンスの一致を確実に検証できる手段、インスタンスの権利・参加者の扱い、衝突や人物の検出、緊急停止、VRChatの具体的な許可範囲を確認してから、無人でのWorld切替を設計します。
