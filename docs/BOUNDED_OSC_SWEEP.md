# VRChat公式クライアント：短時間のOSC視点スイープ検査

**用途：** 自分で入室した1つのワールドを、一定の位置から短く見回し、Windowsローカルに無音MP4と検査監査JSONを保存する試作機能です。Gemini不要、VRChatのAPIや非公式クライアントは使いません。

VRChat公式ドキュメント： [OSC Input Controller](https://docs.vrchat.com/docs/osc-as-input-controller) / [OSC Overview](https://docs.vrchat.com/docs/osc-overview)。OSCが公式に存在することと、**無人で公開ワールドを巡回するための運営許可があることは別**です。2026年11月10日にGmailで確認できた運営メールは受付・規約案内で、正式な許諾本文は見つかっていません。別経路で許可を得ている場合、許可の保存と使用範囲の確認を行ってください。下記の `-ConfirmPlatformAuthorization` は**利用者自身の確認**であり、サーバー側の許可判定ではありません。

## 開発・試験の段階

- 単独・非公開で、ユーザー本人またはワールド制作者の許可がある環境に限定する初期試験を想定しています。
- 公式VRChatクライアントは**人間が起動し、対象のWorldに手動で入室**してください。
- 他の参加者が写り込まず、録画に必要な権利があることを確かめてください。音声は保存しません。
- これは**ワールドを順次巡回する機能ではありません**。ワールド変更、アカウントのログイン、パブリックインスタンスへの自動入室、DJ機材のクリック・実動作検証、ランキングの自動公開は行いません。
- 本機能はGitHubで実装・オフライン検証されますが、**実際のWindows VRChatクライアントでの動作確認は未実施**です。

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
