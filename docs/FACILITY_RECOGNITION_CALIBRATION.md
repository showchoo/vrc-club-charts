# DJ設備のAI検出精度を測る（ローカル専用）

この手順は **映像にDJブース・スクリーンなどが見えるか** をAIが
どの程度正しく判定するかを測るためのものです。DJ配信、動画再生、
ボタン操作、音質、FPSなどの**動作確認にはなりません**。

完全自動巡回やVRChatへのログインは行いません。既存の録画の
作成・許可確認・Gemini解析は
[ONE_WORLD_INSPECTION.md](ONE_WORLD_INSPECTION.md) を参照してください。

## この機能でできること

- Geminiの認識結果と、動画を全編確認して付けた正解ラベルを比較。
- DJブース、DJデッキらしき機材、スクリーン、照明、ステージ、操作パネルを別々に評価。
- **TP**（正検出）、**FP**（誤検出）、**FN**（見逃し）、**TN**（正しく未検出）、
  適合率・再現率・F1を自動集計。
- データ不足なら精度を断定しない。未評価・判別不能のラベルは集計から除外。
- 動画と元レポートのSHA-256およびFFprobeの動画長を検査。
- データはすべてローカルに保存。Gemini、VRChat、GitHub、Vercelへの通信や
  Craftsmanship Rankingの変更はありません。

## 実際の動画から正解ラベルの入力画面を作る

まず、動画本体、Geminiによる同動画の \`*.draft.json\`、
対応する撮影・分析の許可が必要です。
**画面に他ユーザー、チャット、個人情報が映る場合は第三者に共有しないでください。**

PowerShellで、GitHubから最新のソースを取得したあと、
次を実行します（各ファイル名は手元の実物に変更）。

```powershell
git pull
py -3 scripts/calibrate_facility_recognition.py make-template --draft "D:\VRC-Captures\sample.draft.json" --video "D:\VRC-Captures\sample.mp4" --out "$env:USERPROFILE\Videos\VRCClubCharts\calibration\labels-template.json"
```

同じフォルダに \`labels-template.review.html\` が生成されます。
このHTMLをWindowsのブラウザーで開き、**元の動画を最初から最後まで**
再生してください。各設備について、次のいずれかをクリックします。

- 映っている
- 動画内で見つからない
- 判別できない

6項目の入力と「動画全体を確認した」チェックが完了すると、
\`facility-labels-xxxxxxxxxxxxxxxx.json\` をローカルダウンロードできます。
**この操作でAIの判定や公開サイトは変更されません。**

*「映っていない」は、その録画映像では観察されなかったという意味であり、
VRChatワールド全体に設備が存在しないという意味ではありません。*
同じ映像の設備の外観だけを判断し、稼働可能性は判断しないでください。

## 複数の録画から誤認識率を集計する

\`calibration.json\` を次のように、GitHubリポジトリの**外側**で作成します。
各ペアの動画、解析レポート、ブラウザーから保存したラベルJSONは、
必ず同じ録画を指している必要があります。

```json
{
  "schemaVersion": 1,
  "cases": [
    {
      "video": "D:\\VRC-Captures\\sample.mp4",
      "draft": "D:\\VRC-Captures\\sample.draft.json",
      "labels": "D:\\VRC-Captures\\facility-labels.json"
    }
  ]
}
```

※この例の各ファイルは実在を意味しません。利用前に保存場所を変更してください。

```powershell
py -3 scripts/calibrate_facility_recognition.py score --manifest "D:\VRC-Captures\calibration.json" --out "$env:USERPROFILE\Videos\VRCClubCharts\calibration\metrics.json"
```

出力は6種類の \`tp\`, \`fp\`, \`fn\`, \`tn\`,
\`precision\`, \`recall\`, \`f1\` と全クラス合計（micro）です。

- **適合率** = TP ÷ (TP + FP)：検出した設備が本当に映っていた割合。
- **再現率** = TP ÷ (TP + FN)：動画内で見えた設備を検出できた割合。
- **F1** = 適合率と再現率の調和平均。
- ゼロ除算の場合、値を 0 と断定せず \`null\` を返します。
- \`uncertain\` は正誤集計に含めません。
- モデルの「見えた」という推定信頼度は現行の表示基準
  **0.80以上**で正検出の候補として扱います。
- 同じワールドの同じ動画を重複登録すると中止します。
- **異なるGeminiモデル名の評価を混ぜるとエラー**になります。精度はモデル別に測定してください。

\`enoughSamplesForPreliminaryReview\` が \`true\` になるには
**30録画以上**で、各設備について正例10件・負例10件以上のラベルが必要です。
これは大まかな最低サンプル目安であり、
\`true\` でも十分な精度や一般化性能を保証しません。
独立した評価用の動画群で別途検証する必要があります。

\`readyForUnattendedDeployment\` と
\`equipmentFunctionalityVerified\` は**常に false**です。
この計測結果からサイト掲載判定、DJ配信機能の認定、
自動操作の有効化を行う仕組みはありません。

## 開発者向けの自動テスト

GitHub CIには単体テストのほか、合成MP4を生成し、
ローカルラベル画面、正解データ形式、誤認識集計を通すテストを追加しています。
**合成データでF1が高くても、実映像のモデル精度を測ったことにはなりません。**

```powershell
py -3 -m unittest tests.test_calibrate_facility_recognition
py -3 scripts/inspection_pipeline_smoketest.py
```
