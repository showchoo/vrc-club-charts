# 制作者専用：DJ動画プレイヤーの音声テスト（ローカル）

この機能は、自分が管理するVRChatテストワールドで**実際に音声が出力されたか調べるための材料**を作ります。任意の公開ワールドに自動で入室したり、勝手に機材を操作したりする仕組みではありません。

## 1. オリジナルのテスト動画を生成する

FFmpegが必要です。Windowsのリポジトリ作業フォルダで実行します。

```powershell
git pull
py -3 scripts/dj_audio_playback_test.py create --out "$env:USERPROFILE\Videos\VRCClubCharts\dj-calibration-8s.mp4"
```

640×360の動くテスト画面に、**523→659→784→1046 Hz**の音を各2秒ずつ収録した、**オリジナルの8秒間のH.264/AAC動画**を作ります。既存の楽曲は使用しません。

テスト動画は自身が許可を持つ場所にアップロードして、VRChatの動画プレイヤーに**人間が手動で**設定します。VRChatには動画URLの条件やUntrusted URLsの設定があります。無断アップロード、他者の音源使用はしないでください。動画を自動的に公開・アップロードする機能はありません。

## 2. 許可を得た1人だけのテストで再生して録画する

対象ワールドは自分が管理できるもの、または制作者から改変・検査を明示的に許可されたものに限ります。

1. VRChatでテストワールドの動画プレイヤーに上記のテスト動画を読み込み、音声付きで再生します。
2. **録音について同意があるプライベートテスト環境**で、VRChatの出力音声をローカル録画・録音ツールで記録します。
3. 音声付きMP4をPCに保存します。**既存のWindowsインスペクターは無音MP4を録画するため、このテストには使えません。** OBSなどでローカル録音し、動画と録音内容を自身で確認してください。
4. パスワードや個人情報、第三者の会話が混ざっていないことを確認します。

## 3. 録音したMP4とオリジナル音声を照合

```powershell
py -3 scripts/dj_audio_playback_test.py verify `
  --original "$env:USERPROFILE\Videos\VRCClubCharts\dj-calibration-8s.mp4" `
  --recording "$env:USERPROFILE\Videos\VRCClubCharts\captured-test.mp4" `
  --out "$env:USERPROFILE\Videos\VRCClubCharts\private-dj-audio-result.json" `
  --confirm-private-recording
```

FFmpegでローカルの録画から音声だけを一時的に復号し、元動画と同じ4トーンが順番どおり検出できるか確認します。録音内容そのものはGitHubや外部サービスに送信しません。

**判定結果**は `test_audio_sequence_detected` または `inconclusive` です。合致しない場合でもプレイヤー故障とは限りません（音量・録音設定・同期ずれなどで検出できない場合があります）。

結果JSONには元動画と録画のSHA-256、音の検出結果のみを記録します。2つの動画が完全同一ファイルの場合は「独立した録画ではない」として拒否します。

## 判定に関する重要な注意点

- 4トーンが録音で見つかったとしても、その音がVRChatから出力されたことを**スクリプトだけで独立認証することはできません**。テストした人が録音経路を確認する必要があります。
- この検証で分かるのは、既知の短い動画の音声信号が別の録音に入ったかどうかです。**ライブDJ配信の成功、スクリーン映像の表示、全来場者への音声出力、配信同期、操作ボタン**はまだ未検証です。
- `equipmentFunctionalityVerified`、`liveDjStreamVerified`、`actualSpeakerOrHeadsetOutputVerified`、`rankingEligible` は**常にfalse**です。
- ローカルテストではなくサイトのCraftsmanship Rankingに実測値を掲載する場合、複数回の独立した検査、権利確認と別の公開承認が必要です。

関連： [UdonSharpプレイヤー内部イベント検査](CREATOR_DJ_VIDEO_PROBE.md) ｜ [VRChat動画プレイヤー公式資料](https://creators.vrchat.com/worlds/udon/video-players/)

## オフラインでのコード検証

`python -m unittest discover` では音声パターン検出の単体テストを実行します。`python scripts/inspection_pipeline_smoketest.py` は**FFmpegで生成した合成動画**を再エンコードしただけの比較テストであり、VRChat実機で録音できたという意味にはなりません。

## プレイヤー内部イベントとの組み合わせ

同じプライベートな検査について、Udonのイベントログも残っている場合は、[COMBINED_DJ_INSPECTION_EVIDENCE.md](COMBINED_DJ_INSPECTION_EVIDENCE.md) の一括照合を使えます。ログと録音が同じセッションに由来するかは利用者が確認します。検査の陽性結果はライブDJ配信の機能証明ではありません。
