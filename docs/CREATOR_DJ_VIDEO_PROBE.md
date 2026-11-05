# DJ動画プレイヤーの動作検証 — ワールド制作者用プローブ

この機能は、**自分が制作・管理するワールド、または制作者から検査・改変の許可を受けたワールド**向けの実験的なUdonSharpコンポーネントです。一般公開ワールドに無断導入したり、VRChatアカウントを無人操作したりする仕組みではありません。

## 実装

- ソース: [VCCDJVideoProbe.cs](../unity/CreatorOwnedDJProbe/VCCDJVideoProbe.cs)
- 対象: 公式VRChat Worlds SDK/UdonSharpのVideo Player
- 取得予定: `OnVideoReady`、`OnVideoStart`、`OnVideoPlay`、`OnVideoPause`、`OnVideoError`、動画再生位置(`GetTime`)の定期サンプル
- テスト範囲: **そのワールドの、そのコンポーネントの、その動画を実行した1セッションのみ**
- 記録: ローカルのVRChat出力ログ。ユーザー名、URL、音声、映像、チャット本文は意図的に記録しません。
- 参加者: 1人のプライベートなテストを想定。人数が増えた場合、検査を止めます。

## 導入と動作確認（Unity／Windowsが必要）

1. 自分が管理するWorldのUnityプロジェクトを開き、公式VRChat Worlds SDKとUdonSharpを導入します。
2. `unity/CreatorOwnedDJProbe/VCCDJVideoProbe.cs` をAssetsへコピーします。
3. **実際にイベントが発生するVideo Playerと同じGameObject**にUdonSharpコンポーネントとして追加し、`targetPlayer` に正しいVideo Playerを割り当てます。
4. `worldId` に対象のWorld ID、`sessionToken` に英数字8〜32文字の一意のトークン、`componentId` に例えば `screen01` を設定します。
5. Creator CompanionのBuild & Testで、**参加者が1人**の検査環境を起動します。実装やイベントがUnity/UdonSharpでコンパイルできるかも、ここで実機確認が必要です。
6. Interactまたは自作のローカルUIから `BeginProbe()` を呼び出し、**権利がある既知のテスト動画**をプレイヤー本来の操作で読み込み・再生します。
7. 動画の再生位置が進んでいることを目視で確認した後、`EndProbe()` で終了します。
8. Windowsの `%USERPROFILE%\AppData\LocalLow\VRChat\VRChat\` にある最新 `output_log_*.txt` 内の `VCCDJPROBE|` から始まる検査記録を確認します。ログ本体は個人情報を含み得るため、**このまま公開・共有しないでください**。

## 判定の限界

`OnVideoStart` 等が発生し、`GetTime()` が増加しても、それはプレイヤー内部の再生状態に関する証拠でしかありません。特にライブ配信では再生位置が取得できないことがあります。

次の事項は本プローブ単独では**未検証**です。

- YouTube LiveやTwitch等のライブDJ配信が実際に映像・音声を出力できること
- スクリーンへのテクスチャ描画、空間音響、音量、遅延、同期
- URL入力、再生制御、ミキサー等が来場者の操作で機能すること
- 他のVRChatワールドに同種の設備が存在・動作すること
- 完全無人巡回やランキング評価に利用してよい法的／プラットフォーム上の許可

本コードは**UnityのビルドテストとVRChat実機テストが未完了**です。映像解析のみの暫定スコア、検査用ログ、検証済みCraftsmanshipは明確に分離してください。今回の機能はランキングの点数・順位を自動変更しません。

公式資料:

- [VRChat Video Players](https://creators.vrchat.com/worlds/udon/video-players/)
- [VRChat Udon video events](https://creators.vrchat.com/worlds/udon/graph/event-nodes/)
- [VRChat Udon debugging](https://creators.vrchat.com/worlds/udon/debugging-udon-projects/)
- [VRChat Terms of Service](https://hello.vrchat.com/legal)

## Windowsのローカルログ自動判定（新機能）

Unityでの実行と動画の再生が完了したら、**撮影・ログ閲覧権限がある実機のPowerShell**で以下を実行します。※「World ID」「session token」はUnity内で設定した**実際の値**に置き換えてください。

```powershell
git pull
py -3 scripts/analyze_creator_dj_probe.py `
  --log "$env:USERPROFILE\AppData\LocalLow\VRChat\VRChat\output_log_実際の名前.txt" `
  --session CreatorTest01 `
  --world wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05 `
  --component screen01 `
  --out "$env:USERPROFILE\Videos\VRCClubCharts\private-player-check.json"
```

このスクリプトはログ全体を公開したり送信したりせず、指定したセッションのイベントのみを読み取ります。元ログのSHA-256と、個人情報を含まない判定結果だけを**GitHubリポジトリ外**のJSONに保存します。既存の結果ファイルを勝手に上書きしません。

次の条件がすべて満たされたときだけ、`local_player_clock_observed` と判定します。

- 開始イベントが1回あり、ready → start → play のイベントが録画中に記録された
- 3点以上の再生位置サンプルから約2秒以上の進行を認め、実時間と概ね整合する
- エラー、停止前のpause、他参加者の出入り、検査途中の終了がない
- 指定したsession、World ID、component IDが一致し、イベント時刻が逆行していない

その他は `inconclusive`（判定不能）です。ライブストリームでは再生位置 `GetTime()` が取得できない場合があり、判定不能でもプレイヤーが故障しているとは限りません。

**重要：** `local_player_clock_observed` は内部イベントと再生位置を観測したという意味のみです。音声・映像が来場者に実際に再生されたこと、操作が可能なこと、ライブDJ配信に対応すること、第三者が検証したことは示しません。JSONの `equipmentFunctionalityVerified` と `rankingEligible` は常に `false` で、ランキングを更新しません。

Unity/VRChat実機でのコンパイル・再生実行は未検証です。オフライン単体テストは次のコマンドで確認できます。

```powershell
py -3 -m unittest tests.test_analyze_creator_dj_probe tests.test_creator_dj_video_probe_contract
```
