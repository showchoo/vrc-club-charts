# 暗いVRChat DJクラブの撮影画像をローカルで比較する

実機のPrivate Worldで撮影できた画像では、画面全体の輝度中央値は低いものの、DJステージのスクリーン・スピーカー・床や壁の構造は写っていました。明暗の強いクラブを、単純な「画像の中央輝度が45未満だから何も見えない」と判断してはいけません。

このツールは既存の**非公開・実画像**を元に、暗部を少し明るくした参考画像と原画を1画面で比較する機能です。再度VRChatを起動・撮影する必要はありません。

## 実行（Windows）

1. 以下をPowerShellで実行します。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/private_low_light_review.py --open
~~~

2. ツールが自動でローカルフォルダ
   %USERPROFILE%\Videos\VRCClubCharts\private-light-recovery から、最新の
   low-light-visibility-needs-review の撮影結果を探します。
3. ファイルを検証できれば、Windowsで**非公開の比較ページが開きます**。
   原画と、暗い部分だけを持ち上げた参考画像を横並びで確認できます。

**Pillowが必要**です。従来の10秒撮影で Pillow が動作していればそのまま使用できます。ライブラリが足りない環境だけ py -3 -m pip install pillow を実行してください。

最新のものではなく特定の保存結果を使いたい場合は --report で指定できます。

~~~powershell
py -3 scripts/private_low_light_review.py --report "C:\Users\showchoo_main\Videos\VRCClubCharts\private-light-recovery\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T082523Z_82d546cee3\lighting-cycle.json" --open
~~~

コマンド実行中にVRChatへ操作を送ることはありません。**現在のローカルPCが勤務日かどうかも無関係**です。これは過去の私的画像を整理・検証する処理であり、巡回スケジューラではありません。

## 保存するもの

元の撮影フォルダの中に、最大1つの private-visibility-review/ を作成します。

| ファイル | 内容 |
|---|---|
| original.png | SHA-256検証後の元画像の同一コピー |
| shadow-lift.png | 暗い画素の輝度だけを持ち上げた参考画像 |
| index.html | 2枚を並べる**ローカル専用**比較ページ |
| review.json | 変換方式・元画像/補正版SHA-256・数値統計・未確認フラグ |

画像の自動アップロードはありません。GitHub、Gemini、Vercel、Supabaseへの通信は行いません。既存の元PNGやレポートを変更しません。再実行ではハッシュ確認済みの既存結果を再利用し、異常時には上書きせず停止します。

変換は画像の**Y（輝度）成分のみ**に単調なシャドウ補正をかけます。輝度112以上は変更せず、黒は黒のままです。存在しない物体をAIで補完したり、新しい映像を生成する処理ではありませんが、色やノイズは現実の見た目と異なって見える場合があります。

## 検証項目と限界

- 元の lighting-cycle.json を読み、既存の診断コードでワールドID、Private撮影由来、撮影ステータス、選択されたフレームの情報を検証します。
- 元PNGのSHA-256と、記録されたキャプチャ画面サイズが一致しなければ中止します。
- シンボリックリンク、サイズ超過、途中まで書かれたファイルや改ざんされたレビュー結果は拒否します。
- **明るくなった画像を「ワールドが実際に明るい」「設備の存在・正常動作を確認した」「AI認識精度が向上した」とはみなしません。**
- equipmentFunctionalityVerified, lightingCycleVerified, navigationSafe, rankingEligible, publiclyShareable は全て false です。
- この画面は人が確認するためのものです。DJ配信機能を確認するには、対象World内での別の認可済み検証とその記録が必要です。

## 次段階

暗部補正した画像は、今後の**DJブース/デッキ/スクリーン/照明などの外観判定**を検証する入力候補です。まず元画像と補正画像の両方を人が見比べ、誤認識・誤検出の有無を調べます。モデルへ送る場合は、撮影の権利とAIアップロードの同意を別に確認し、推定結果を未確認のままランキングに反映しない方針です。

自動テスト：

~~~powershell
py -3 -m unittest discover -s tests -p test_private_low_light_review.py -v
~~~
