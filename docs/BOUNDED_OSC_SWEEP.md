# VRChat公式クライアント：短時間のOSC視点スイープ検査

**用途：** 自分で入室した1つのワールドを、一定の位置から短く見回し、Windowsローカルに無音MP4と検査監査JSONを保存する試作機能です。Gemini不要、VRChatのAPIや非公式クライアントは使いません。

VRChat公式ドキュメント： [OSC Input Controller](https://docs.vrchat.com/docs/osc-as-input-controller) / [OSC Overview](https://docs.vrchat.com/docs/osc-overview)。OSCが公式に存在することと、**無人で公開ワールドを巡回するための運営許可があることは別**です。2026年11月10日にGmailで確認できた運営メールは受付・規約案内で、正式な許諾本文は見つかっていません。別経路で許可を得ている場合、許可の保存と使用範囲の確認を行ってください。下記の `-ConfirmPlatformAuthorization` は**利用者自身の確認**であり、サーバー側の許可判定ではありません。

## 開発・試験の段階

- 単独・非公開で、ユーザー本人またはワールド制作者の許可がある環境に限定する初期試験を想定しています。
- 公式VRChatクライアントは**人間が起動し、対象のWorldに手動で入室**してください。
- 他の参加者が写り込まず、録画に必要な権利があることを確かめてください。音声は保存しません。
- これは**ワールドを順次巡回する機能ではありません**。ワールド変更、アカウントのログイン、パブリックインスタンスへの自動入室、DJ機材のクリック・実動作検証、ランキングの自動公開は行いません。
- 本機能はGitHubで実装・オフライン検証されますが、**実際のWindows VRChatクライアントでの動作確認は未実施**です。

## 同じPrivate Worldなら再入室は不要（2026-11-11）

毎回Privateインスタンスへ入り直す必要はありません。従来のローカルログ確認は「入室から180秒以内」という制限がありましたが、現行の検査は**最新の成功したPrivate入室から最大24時間**、同じWorldの同じ入室ログが残っていれば再利用します。

- Windows公式クライアントが起動しており、対象WorldのPrivateインスタンスに現在滞在していることをオペレーターが確認
- VRChatの最新output_logの末尾（最大1MiB）に、同じPrivate入室・入室成功の記録が残り、その後に別World/インスタンスへの入室、離室、切断の記録がないこと
- 録画・OSC操作中に1秒間隔で同じログと入室フィンガープリントを検証し、録画後にも再確認すること
- ログが古すぎる（24時間以上）、必要な入室行が末尾から消えている、ログを読めない、Worldが変わった等の場合は停止。確認できないときだけ再入室が必要
- ログはオンライン接続や他の参加者不在を完全には証明しないため、確認フラグはこれまでどおり必要。自動でPublic Worldに入室したり、他の参加者を追いかけたりしない

**通常の手順**：Private Worldにそのまま滞在し、下記コマンドを再実行するだけです。入室直後の3分以内に急ぐ必要はありません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/run_one_world_inspection.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 30 --sweep --private-instance-confirmed --verify-local-log --confirm-platform-authorization --acknowledge-automation-risk
~~~

動画解析を有効にしない限り、録画ファイル・入室ログはローカルに留まり、Geminiやランキングには送信しません。

## 実機成功：0.80のOSC右回転を通常スイープへ採用（2026-11-11）

VRChatの完全再起動とOSC再有効化の後、Windowsデスクトップ実機で以下を目視確認しました。

- Quick Menu：OSCのQuickMenuToggleRight入力で自動的に開いた
- 視点の右回転：OSCのLookHorizontal=0.80を2回送信し、マウス・ゲームパッドに触れずに実際に回転した
- 正確な原因（再起動の効果、デッドゾーンのしきい値）は未確定。以前の0.35の失敗が再起動前の状態によるものだった可能性もある
- 左回転 -0.35、歩行、4回連続スイープによる部屋全体のカバー率は実機で未確認

この観測を受け、通常の短時間OSCスイープで使う turn_right の入力を0.35から**0.80**へ更新しました。1操作あたり最大0.48秒、最大4回、各操作終了時に0へ戻し、フォーカス喪失・World変更・Ctrl+Shift+F12で停止する既存制限は維持します。**0.80で右回転することと、正確な角度や安全な全域観測ができることは別です。**

ローカルPCで最新版に更新して短時間のスイープを再確認：

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 -m unittest tests.test_windows_vrchat_inspector tests.test_inspection_sweep
~~~

対象WorldのPrivateインスタンスに手動入室し、参加者不在・撮影の権利・OSCが有効であることを確認してから、同じPrivate Worldに滞在していることを確認してから以下を実行します。

~~~powershell
py -3 scripts/run_one_world_inspection.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 30 --sweep --private-instance-confirmed --verify-local-log --confirm-platform-authorization --acknowledge-automation-risk
~~~

30秒の無音MP4と非公開の監査JSONをローカルへ保存します。Geminiアップロード・DJ設備の機能確認・公開ランキング更新は行いません。実機スイープの正常動作はこの更新を適用した後に別途確認が必要です。

## Windows 64-bit HWNDエラーとOSCボタン式の診断

2026-11-11の実機テストでは、PowerShell経由のWindowsウィンドウ検出が OverflowError: int too long to convert となる場合がありました。Windowsのウィンドウハンドル（HWND）に対応するctypesのポインター幅の型宣言を修正しました。更新とオフライン回帰試験：

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 -m unittest tests.test_windows_window_handle_ctypes tests.test_inspection_osc_button_probe
~~~

長い日本語入りPythonコードをPowerShellからパイプすると文字化けする場合があるので、専用のファイルを実行します。まず送信しないdry-run：

~~~powershell
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79
~~~

対象のWorldに手動でPrivate入室し、参加者不在・OSC操作許可を確認した上で、同じPrivate Worldに滞在していることを確認してから下記の実機試験を実施してください。

~~~powershell
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --live --confirm-private-instance --confirm-platform-authorization --acknowledge-automation-risk
~~~

VRChatのOSCを有効にし、Action Menu / OSC Debug画面を閉じます。実行後8秒以内にVRChatを最前面に戻し、マウスやゲームパッドを動かさず観察します。ボタン式の /input/LookRight に整数1（押下）を0.65秒ずつ3回送信し、毎回0（解除）を送ります。移動・長時間保持・録画・Geminiへの送信はしません。フォーカス喪失、Worldログ変更、Ctrl+Shift+F12で停止します。

結果の status: sent-unverified はコマンド送信完了のみを示します。**実際に視点が動いたかは目視確認が必要**です。UDP/OSCの送信成功だけで視点移動が成功したとは判定できません。

## アナログ入力のデッドゾーン切り分け（2026-11-11）

Windows実機ではOSC Debugで受信が見えるものの、アナログ0.35とボタン式LookRightの双方で右回転を目視確認できませんでした。VRChat公式フィードバックには、2024年の更新でLookHorizontalのデッドゾーンがおよそ50%になったという利用者報告があります（https://feedback.vrchat.com/open-beta/p/1489-vive-controllers-default-wand-binding-has-analog-locomotion-rotation-speed）。現在も同じ挙動とは限らないため、**通常巡回コードの入力値は変更せず**診断専用モードを追加しました。

最新版を取得後、まずdry-run:

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --mode analog
~~~

同じWorldのPrivateインスタンスに滞在していることを確認し、他の参加者がいないこと、録画・操作の権利を確認してください。VRChatのOSCを有効にし、Action MenuとOSC Debugを閉じてください。同じPrivate Worldに滞在していることを確認してから次を実行します。

~~~powershell
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --mode analog --live --confirm-private-instance --confirm-platform-authorization --acknowledge-automation-risk
~~~

実行後8秒以内にVRChatを最前面へ戻し、マウス・キーボード・ゲームパッドから手を離してください。0.80（-1～1の範囲）のアナログ右回転を0.4秒ずつ2回だけ送信し、それぞれ最後に0.0へ戻します。歩行・録画・Geminiへの送信はしません。Ctrl+Shift+F12で停止できます。

sent-unverified は送信完了だけを示し、実際に回転したことの証明ではありません。**目視で右回転したか**の結果をもとに、入力値の較正か、VRChat側の入力競合・デスクトップ設定の調査を次に行います。

## OSCの受信とゲーム入力の切り分け：Quick Menu（2026-11-11）

実機では、0.35/0.80のアナログ視点回転とボタン式LookRightは、送信完了でも視点が動きません。OSC Debugに受信が表示されることは、VRChatのゲーム入力まで適用された証拠ではありません。VRChatの公式入力仕様では、アナログ値は明示的に0へ戻すまで維持されるため、連続送信が必須という結論にもなりません。

そこで通常スイープには手を加えず、**キャラクターを移動させない**Quick Menu操作を1回だけ行う診断モードを追加しました。実行前はVRChatのQuick MenuとAction Menuを閉じてください。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --mode ui
~~~

同じPrivate Worldへの入室ログが確認できる状態で、許可・参加者不在を確認してから次を実行してください。

~~~powershell
py -3 scripts/inspection_osc_button_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --mode ui --live --confirm-private-instance --confirm-platform-authorization --acknowledge-automation-risk
~~~

8秒以内にVRChatのウィンドウを前面に戻し、必要なら一度ウィンドウ内部をクリックしてから手を離してください。/input/QuickMenuToggleRight の整数1（押下）と0（解除）を1回だけ送ります。メニューが開けばOSC入力の少なくとも一部は動いています。開かなければ入力処理の問題、別の入力デバイス・デスクトップ設定・キャプチャしたウィンドウの状態などを優先して調査します。ただし一つのUI操作だけで入力系全体の成功・失敗を断定しません。

メニューを開くだけで録画・歩行・視点回転・クラウド送信はしません。結果の sent-unverified は送信完了のみです。開いたメニューは必要に応じて本人が閉じてください。異常時にはCtrl+Shift+F12で操作停止できます。

## 1. Windows上で準備

PowerShellをVRC Club ChartsのローカルGitチェックアウトで開きます。

```powershell
git pull
py -3 -m pip install mss pillow
.\scripts\launch_one_world_inspection.ps1 -Diagnose -Sweep
```

FFmpegとFFprobe（libx264付き）が必要です。VRChatのAction MenuでOSCを有効化します。診断はウィンドウ確認のみで、入室・録画・OSC送信は行いません。

## 2. 人間が許可範囲を確かめた後で試験

公式クライアントで対象Worldを手動で開き、ほかの参加者がいないこと、録画権利があることを確認します。**ワールドIDは必ず実際に開いているIDに置き換えます。** プログラムは現在のWorld IDを自動検証できません。

```powershell
.\scripts\launch_one_world_inspection.ps1 `
  -WorldId wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 `
  -Seconds 30 `
  -Sweep `
  -ConfirmPrivateInstance `
  -ConfirmPlatformAuthorization `
  -AcknowledgeAutomationRisk
```

上記スイープは、向きを変えずに観察→右へ最大0.48秒の短い回転を4回繰り返して観察します。**角度は較正されていません。360度スキャンや部屋全体の観測を保証しません。** 画像が2回続けてほぼ変わらなければ早期停止します。AIの撮影画像アップロードはありません。

作業フォルダ外の `%USERPROFILE%\Videos\VRCClubCharts` にMP4と `*.inspection.json` を保存します。各アクション・観察回数・変化の有無・中止理由を記録します。人物識別、機材の実動作、ワールド到達率を示す値は**常に未検証**です。

## 3. 緊急停止

- **Ctrl+C** で実行を中断、またはVRChatウィンドウからフォーカスを外します。
- OSC操作は最大0.48秒ずつに制限され、アクション終了・異常・クリーンアップ時に移動3軸へゼロを送ります。
- 表示対象が変わらない場合、時間が足りない場合、ウィンドウがアクティブでない場合、続行しません。
- ユーザーが直接クライアントを終了することでも操作は中断されますが、UDP通信だけでは送信先の実状態を確認できません。

なお、VRChatの動作状態や音声が本当に適切かを判定する計測器はありません。現段階では**運用・公開ランキングの根拠には使用しないでください**。

## 4. オフラインテスト

```powershell
py -3 -m unittest tests.test_inspection_sweep tests.test_windows_vrchat_inspector tests.test_one_world_inspection
```

モックのウィンドウ・OSC送信器で試験します。実クライアントの起動、VRChatアクセス、課金APIへのアクセスはありません。
