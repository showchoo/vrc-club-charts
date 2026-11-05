# DJ設備の検査証拠をまとめる（オフライン・制作者管理の環境専用）

このツールは **Udon動画プレイヤーのログ** と **8秒間のオリジナル4音テスト動画を再生した際の録音** を、1つの非公開レポートにまとめます。

**AIがVRChatへ入室する機能ではありません。** 自分が管理するワールド、または明確な許可を得たテストワールドで、人間が検査した記録だけを扱います。対象ワールド・録画・録音に必要な権利と同意を確保してください。

## 必要なもの

1. [制作者向けUdon動画プレイヤーのプローブ](CREATOR_DJ_VIDEO_PROBE.md)を導入したテストワールドのローカルVRChat出力ログ（`output_log_*.txt`）。
2. [オリジナルの音声テスト動画](CREATOR_DJ_AUDIO_TEST.md)（`dj-calibration-8s.mp4`）。
3. そのテストの**実際の録画**（音声入りの別MP4）。録画には権利と参加者の同意が必要です。現在のWindowsインスペクターが生成する無音MP4は使用できません。
4. 実際の `worldId`、Udonの `sessionToken`、`componentId`。ログと録画が**同一の検査セッションに由来すること**を人間が確認します。

## Windowsでの検査

リポジトリから `git pull` した後、PowerShellで実行します。パスやWorld IDは例示であり、実際のファイルと識別子に置き換えてください。

```powershell
py -3 scripts/verify_dj_inspection_session.py `
  --log "$env:USERPROFILE\AppData\LocalLow\VRChat\VRChat\output_log_実際の名前.txt" `
  --session CreatorTest01 `
  --world wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 `
  --component screen01 `
  --reference "$env:USERPROFILE\Videos\VRCClubCharts\dj-calibration-8s.mp4" `
  --recording "$env:USERPROFILE\Videos\VRCClubCharts\captured-test.mp4" `
  --out "$env:USERPROFILE\Videos\VRCClubCharts\private-combined-test.json" `
  --confirm-private-recording-rights `
  --attest-recording-from-session
```

`--confirm-private-recording-rights` は録音・撮影の権利と参加者同意を確認した場合のみ、`--attest-recording-from-session` はログと録音が同じ実験を示していると実際に確認した場合のみ指定します。

プログラムはローカルで次を検査します。

- ログに指定セッション・World ID・設備IDの `ready` → `start` → `play`、3点以上の再生位置の進行、終了イベントが正しい順番であること。エラー・一時停止・ほかの参加者の入室を検出した場合は失敗扱い。
- オリジナルに4トーン（523→659→784→1046 Hz）が含まれていること。
- 別の録音に同じ順序・概ね同じ間隔で4トーンが含まれること。参照MP4とバイト一致する「録音」は拒否します。
- ログ、オリジナル動画、録音のSHA-256を保存し、ファイルとセッションを間違えにくくします。

### 判定結果

| `status` | 意味 |
|---|---|
| `operator_linked_local_observations` | 指定ログの内部再生イベントと、別録音のテスト音声信号を両方検出できた。ただし同一セッションとの対応は人間の申告による |
| `inconclusive` | 少なくとも一方の条件を満たさず、検証できない。故障と断定しない |

データが無効、同意がない、オリジナルと録画が同一、既存出力を上書きしようとした場合はエラーで停止します。ログ本文や録音内容は**外部送信せず**、出力JSONにもユーザー名、チャット、音声データ、ファイルのフルパスを入れません。レポートはGitHubリポジトリ外に保存します。

### 完全な機能証明ではない理由

この仕組みだけでは、録音がVRChatの出力に由来することや、ログと録音の時間的な一致を**機械的に証明できません**。意図的にテスト音声を録音ファイルへ混ぜた場合も区別できません。したがって両方検出できても、音声出力の独立検証・映像表示・ライブDJ配信・操作ボタン動作の証明にはなりません。

JSONの `audioOutputIndependentlyVerified`、`videoPixelsVerified`、`liveDjStreamingVerified`、`controlsVerified`、`equipmentFunctionalityVerified`、`rankingEligible` は常に `false` です。Craftsmanship Rankingへの自動反映は行いません。

## 開発者テスト

```powershell
py -3 -m unittest tests.test_verify_dj_inspection_session tests.test_analyze_creator_dj_probe
py -3 scripts/inspection_pipeline_smoketest.py
```

GitHub CIでは、**合成したUdonログとFFmpegで生成・再エンコードした動画**から上記の処理を通すテストを実行します。合成テストが成功しても、VRChat実機での再生成功を意味しません。
