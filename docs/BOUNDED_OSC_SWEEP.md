# VRChat公式クライアント：短時間のOSC視点スイープ検査

**用途：** 自分で入室した1つのワールドを、一定の位置から短く見回し、Windowsローカルに無音MP4と検査監査JSONを保存する試作機能です。Gemini不要、VRChatのAPIや非公式クライアントは使いません。

VRChat公式ドキュメント： [OSC Input Controller](https://docs.vrchat.com/docs/osc-as-input-controller) / [OSC Overview](https://docs.vrchat.com/docs/osc-overview)。OSCが公式に存在することと、**無人で公開ワールドを巡回するための運営許可があることは別**です。2026年11月10日にGmailで確認できた運営メールは受付・規約案内で、正式な許諾本文は見つかっていません。別経路で許可を得ている場合、許可の保存と使用範囲の確認を行ってください。下記の `-ConfirmPlatformAuthorization` は**利用者自身の確認**であり、サーバー側の許可判定ではありません。

## 実機校正：前進を目視確認、旧画像比較では見逃し（2026-11-11）

`inspection_position_step_probe.py` のWindows実機で `--direction forward` の0.20秒前進を実行しました。出力は `status: sent-unverified`、`visualChangeDetected: false`、`visualDifferenceScore: 0.00038`（旧しきい値 `0.018`）でしたが、**操作者が前進したことを目視で確認**しました。したがってOSC前進は実機で反応したと判断できますが、16×9縮小グレースケールによる旧画面比較には**偽陰性**があります。前進距離・階段・衝突安全性の独立検証にはまだ到達していません。

これを記録・調査するため、`scripts/inspection_position_feedback.py` を追加しました。元の2枚のPNGのSHA-256を元レポートと照合し、192×108ピクセルでの細かな輝度差・変化画素率・16区画の最大変化を数値化します。利用可能ならPillowで**差分強調画像**も生成し、ブラウザで移動前後の画像と並べて表示します。これらは**視点の変化の診断値**であって、前進・障害物回避を機械的に確認した結果ではありません。今のところ旧NavigationGuardの閾値を安易に下げたり、移動時間を延ばしたりはしません。

既に実行した動画や操作を撮り直さず、**人間が確かに前進を見た場合だけ**、以下のコマンドを実行します。クラウド送信もOSC送信もありません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$report = "$HOME\Videos\VRCClubCharts\private-position-probes\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T053943Z_0d74d0c97d\position-step.json"
$result = py -3 scripts/inspection_position_feedback.py --report "$report" --observed moved --confirm-human-observation | ConvertFrom-Json
if ($LASTEXITCODE -eq 0 -and $result.index) { Start-Process $result.index }
~~~

`position-step-feedback.json` と `position-step-feedback.html` を元データと**別ファイル**としてローカル保存します。Pillowが未導入の場合、画像差分の追加計測はできませんが、人手の確認は保存できます。元の `position-step.json`、`before.png`、`after.png` は変更せず、`independentPositionVerified: false` を維持します。後から矛盾する目視評価で上書きすることはできません。

## 監督付き・撮影位置の短距離移動パイロット（2026-11-11）

GeminiがDJブースを見たと誤判定した理由は、フロアから高い位置のDJブースが見えないという**視点の制約**でした。固定位置でのOSCスイープだけでは解決しないため、**ローカルでの移動1回と移動前後の視点記録**を切り分けた `scripts/inspection_position_step_probe.py` を実装しました。

**現在できること**：手動で入室した1つのPrivate World内で、許可・録画権利・安全な平坦な進路を確認したうえで、OSCの `/input/Vertical` または `/input/Horizontal` を**最大1回、0.20秒だけ**操作して必ずゼロへ戻します。前後のVRChat画面を2枚のPNGとして `Videos/VRCClubCharts/private-position-probes` に保存し、差分と安全確認の状態を非公開JSONに残します。変更差分は「画面が変わった」ことの指標にすぎず、実際に歩けた距離や衝突・階段の安全性の証拠にはなりません。**Geminiクラウド、公開サイト、ランキングへの送信は一切行いません**。OSCのUDP送信先はローカル `127.0.0.1:9000` のみです。

**できないこと**：階段や段差を認識して自律的に上ること、壁を避けて自律経路を計画すること、プレイヤーの位置や移動距離を確認すること、視界外のDJブース到達を宣言すること。将来の目標と、今回の初期試験を混同しないでください。OSCの `/input/Vertical` と `/input/Horizontal` はVRChat公式が案内する入力軸ですが、World設定や端末のデッドゾーンにより想定どおり動くとは限りません。参考: https://docs.vrchat.com/docs/osc-as-input-controller

まず**dry-run**（VRChat操作・録画・UDPパケット送信を一切行わない）：

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_position_step_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79
~~~

実機試験は、公式VRChatクライアントを起動して**本人が当該WorldのPrivateインスタンスへ入室**し、別の参加者が映らず、フラットな空きスペースで前方の進路が明確に安全だと確認できたときだけ実施してください。**階段・高台・崖・ワールドの境界付近・障害物のある場所では実行しないこと。** 試験前にOSCを有効にして、OSC DebugやQuick Menuを閉じてください。オペレーターが必要な許可を確保し、実行時には一時的にVRChatを前面へ戻す必要があります。

~~~powershell
py -3 scripts/inspection_position_step_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --direction forward --live --confirm-private-instance --confirm-recording-rights --confirm-flat-clear-path --confirm-platform-authorization --acknowledge-automation-risk
~~~

表示後8秒以内にVRChatを前面へ戻し、マウスやWASD・ゲームパッドから手を離します。**Ctrl+Shift+F12**の非常停止、フォーカス喪失、現在Worldの入室ログ変更を監視し、OSCの各軸は初期化時・操作後・終了時に必ずゼロを送る設計です。ただしOS/プロセスの強制終了やネットワーク障害があるとゼロ送信も保証できないので、VRChat側で操作を停止できるよう手動監督してください。

結果の `status: "sent-unverified"` は**OSC入力を送っただけ**であり、歩行したことの証明ではありません。出力 `position-step.json` には `positionVerified: false`、`collisionSafetyVerified: false`、`stairsTraversed: false`、`djBoothLocated: false` が保持されます。動いていなければ自動再試行はしません。スクリーンショットに他のプレイヤーや個人情報が入っている可能性があるため、公開しないでください。

次の段階は、今回の実機で動作を確認した後、複数の撮影位置を撮り分けるプランナーを別機能として開発することです。階段検出・移動経路の正確な安全確認ができるまでは、無監督での段差移動は解禁しません。

## 90秒の暗いクラブ観測が「calibrating」のままだった場合（2026-11-11）

実機World `wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79` にて90秒の監督付き観測が完了しましたが、`lighting-cycle-not-confirmed`、`lightCycle.status=calibrating`、`referenceMedianLuma=null` となりました。OSC移動は0回で、安全上の異常停止はありません。

**まだ理由は断定できません。** 既存コードでは画面輝度中央値45以上、ほぼ黒い画素比率92%未満、3フレーム連続で明るさの差が6以内という基準が必要です。暗いWorldでは「45」を超えられない可能性がありますが、照明変化が速くて連続フレームが安定しなかった可能性もあります。

今回は**再観測せず**、既存の90個の`luminanceSamples`を使って校正が失敗した理由を切り分ける`scripts/diagnose_light_cycle_report.py`を追加しました。以下はVRChatを起動せずに実行できる**完全ローカル・読み取り専用**のコマンドです。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$report = "$HOME\Videos\VRCClubCharts\private-light-recovery\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T062458Z_0f2ebe8795\lighting-cycle.json"
py -3 scripts/diagnose_light_cycle_report.py --report "$report"
~~~

出力の `primaryDiagnostic` は原因の候補（`no-samples-above-minimum-luminance`／`all-samples-near-black`／`bright-frames-excluded-by-near-black-fraction`／`no-three-consecutive-eligible-stable-frames` など）です。`medianLumaMin/Max/Typical`、`framesAboveCurrentLumaThreshold`、`framesPassingNearBlackLimit`、`stableVisibleWindowsEntirelyBelowLumaThreshold` も表示します。画面そのものや個人情報は送信・出力せず、元のJSONも変更しません。

今後の`inspection_light_cycle_probe.py`の実行結果には `calibrationDiagnostics` が加わります。ただしこの診断は**元の輝度基準を勝手に下げません**。照明が変化したのか、暗いままなのか、映像として何が見えるかは数値だけでは確定できず、Worldの設備の有無・衝突安全性・自律移動の許可を与えるものではありません。診断結果を基に、次の校正方法を検討します。

## 実画像で確認：暗いクラブと見えるステージを区別する補助指標

2026-11-11のPrivate World検証では、保存した `low-light-review.png` のユーザー確認画像から、暗い客席と、白く明るいスクリーン・ステージ・スピーカー・VRChat UIが同じ画面に写っていることを確認できました。これは**画面取得そのものが正常であり、画面全体の中央値だけではステージの視認性を説明できない**実例です。DJ配信機能の検証ではありません。

既存の照明状態機械は、明るい基準画面（中央値45以上）の安定した「明 → 暗 → 明」の周期を検出する別目的の診断です。**しきい値45は緩めず、照明回復未確認のまま移動・巡回を開始しない**ことを維持します。

新規観測の `luminanceSamples` と `calibrationDiagnostics.sceneContrastDiagnostic` には、以下の数値のみを追加しました。

- `lumaP90`: グレースケール輝度の90パーセンタイル。暗い床が多くても明るいステージがあれば高くなる場合がある
- `tonalRangeP10P90`: 10～90パーセンタイルの幅（画像内の明暗差の参考値）
- `highlightPixelFraction`: 輝度96以上の画素割合
- `highlightTiles`/`highlightTilesTotal`: 192×108画像を4×3分割し、各区画の5%以上に輝度96以上の画素が存在する区画数

これは**画面内に光る部分があることの数値的な手掛かり**であって、物体認識・ステージ可視性・進路の安全・VRChatウィンドウとの一致・DJ設備機能の保証ではありません。発光UIや一瞬の光でも数値は高くなる可能性があります。人の目によるPNG確認の代替にはせず、Gemini、OSC、ランキングの合格条件には使いません。

手元で受領した画像（1578×865 JPG）を192×108のグレースケールに縮小して検査した参考値は、中央値約9、90パーセンタイル約126、輝度96以上の割合約14%です。Windows側の元PNGでは画像圧縮差があるため数値が少し異なる可能性があります。

## 輝度がしきい値未満でも1枚だけ視覚確認する（2026-11-11）

実機の10秒観測で、VRChatは最前面、撮影範囲 `left:230, top:-970, width:1578, height:865`、中央値輝度は2〜44で変動し、9/10フレームが「ほぼ黒い画素が多すぎる」基準を下回りました。暗すぎて `45` の安定照明基準に達しず、完全真っ黒継続でもないため、従来の `--capture-dark-diagnostic` だけではPNGを保存しませんでした。負の `top` 座標は上方配置のサブモニターなら正当な座標で、座標のみで異常判定しません。

この中間状態を切り分けるため、明示的な `--capture-visibility-sample` を追加しました。**すべて45未満でも、ほぼ黒い画素割合が92%未満のフレーム**について、最も黒い面積が少ないフレームを1枚選び、同率なら中央値が高い方を優先します。ローカルに `low-light-review.png` を**最大1枚だけ**保存し、`lowLightSample` に元のフレーム番号と数値を記録します。これは**照明回復の認定や視認性保証ではなく、画面キャプチャがVRChatの実表示と一致しているかを人間が比較する証拠**です。

下記は**手動で入室した、参加者が写らず録画の権利があるPrivate World**に限ります。開始後20秒以内にVRChatを最前面に戻し、ほかのウィンドウを操作しないでください。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 10 --focus-seconds 20 --live --capture-visibility-sample --capture-dark-diagnostic --confirm-private-instance --confirm-recording-rights --confirm-platform-authorization --acknowledge-automation-risk
~~~

`status: low-light-visibility-needs-review` なら `lowLightImage` に画像パスが表示されます。まずローカルPCで画像を開き、VRChatの画面と一致するか比較します。

優先順位は**厳密な照明回復PNG → 継続した明るい候補PNG → 全フレーム真っ黒診断PNG → 低照明レビューPNG**です。同一実行で保存するPNGは最大1枚。権利・フォーカス・Worldセッション・緊急停止の条件は一切緩めず、OSC移動・Geminiアップロード・ランキング反映はありません。

## 画面フォーカスによる事前停止の切り分け

`world-focus-or-emergency-stop` は従来、VRChatが最前面にないケースと安全停止イベントの両方を表していました。真っ黒なキャプチャの診断前に停止した場合、画像は取得・保存されていません。事前停止理由を `vrchat-not-foreground-after-focus-delay`（待機時間終了時にVRChatが最前面ではない）と `safety-stop-during-focus-wait`（待機中に安全停止）に分けています。観測途中のフォーカス喪失とWorldログ/非常停止の安全停止判定は従来どおりです。

画面切り替えに余裕が必要なら `--focus-seconds 20` を追加できます。**実行後は、PowerShellを前面に残さず、VRChat本体のウィンドウをクリックして前面にしてください**。他のアプリを操作するとキャプチャは停止します。自動でウィンドウを前面化する、エラーを無視して撮影する、といった操作はしません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 10 --focus-seconds 20 --live --capture-dark-diagnostic --confirm-private-instance --confirm-recording-rights --confirm-platform-authorization --acknowledge-automation-risk
~~~

## 真っ黒な撮影が続く場合の10秒診断（2026-11-11）

同じWorldで前回90秒の輝度中央値は2～186と変動したのに、次の120秒間は**全サンプルが輝度1・ほぼ黒い画素比率約96%**になりました。画像が真っ黒な実Worldか、mss画面キャプチャが黒画面や別の領域を取っているか、数値だけでは決められません。判定条件を安易に下げず、画像取得そのものを検査します。

`diagnose_light_cycle_report.py` は既存ログの再解析だけで `captureVisibilityDiagnostic` を表示します。`near-black-throughout` は**画面の暗さと画像取得の不良を区別できない**という意味で、取得失敗を断定しません。画像を保存しない古い実行結果からPNGを復元することもできません。

今後の**監督付きPrivate World**の検査に、明示的な `--capture-dark-diagnostic` を追加しました。全部のフレームで中央値3以下かつほぼ黒い画素比率95%以上の場合に限り、**最後の撮影画像1枚**を `dark-capture-diagnostic.png` としてローカル非公開保存します。通常の照明回復画像や明るい撮影候補の条件を優先します。暗さが途中で回復した場合はこの黒画面診断画像は作りません。

VRChat公式クライアントを手動でPrivate Worldに入室させ、他人の写り込みがなく、録画・画面確認の権利があることを確認してください。PowerShellから次を実行すると、表示後8秒以内にVRChatを前面に戻して**10サンプルだけ観測**します。OSC移動は行いません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 10 --live --capture-dark-diagnostic --confirm-private-instance --confirm-recording-rights --confirm-platform-authorization --acknowledge-automation-risk
~~~

`status: capture-visibility-needs-review` なら `captureDiagnosticImage` にローカル画像のパスが出ます。PNGをPCで開き、**VRChatの実画面には明るい床やUIが見えていたか、保存画像には何が写っているか**を比較してください。

- VRChat実画面は見えるのに保存PNGだけ黒い → キャプチャ方式・GPU／フルスクリーン・ウィンドウ座標等を優先調査
- VRChat実画面もPNGも黒い → Worldが暗い／ロード途中／画面演出の可能性。証拠画像だけで原因断定不可
- 別の場所や画面が写る → 対象範囲・座標・モニター構成を優先調査

観測前にVRChatウィンドウ領域を取得し直して座標・サイズを `captureRegion` に記録します。視点の操作、Gemini送信、ランキング変更はしません。参加者・個人情報が写る可能性があるPNGは公開しないでください。失敗理由を切り分けるための試験であり、`capture-visibility-needs-review` 自体は映像取得の失敗を確定するものではありません。

## 短い最大輝度より、長く明るい撮影候補を優先（2026-11-11）

初回の実機ログには、輝度186の83番目サンプル（82–83番目の連続2フレーム）を最も明るい候補とする旧結果がありました。ただし、**これは画面が最も見やすいことの証明ではありません**。同じ90サンプルには明るい条件を最大4フレーム連続して満たした区間もあります。そこで補助選択ロジックを修正しました。

新しい候補順位は **(1) 条件を満たした明るい状態の連続サンプル数が長い、(2) 同数なら区間内の明るさ変動幅が小さい、(3) 同じなら区間の中央値が高い** の順です。画像は区間の明るさ中央値に最も近いフレームを代表として最大1枚だけ保存します（選択対象は保持している直近最大6フレーム）。全ログの画像をメモリに溜めないため、視認性の高い画像を必ず選ぶわけではありません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$report = "$HOME\Videos\VRCClubCharts\private-light-recovery\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T062458Z_0f2ebe8795\lighting-cycle.json"
py -3 scripts/diagnose_light_cycle_report.py --report "$report"
~~~

`briefBrightWindow.candidate` に `brightRunSamples`、`brightRunLength`、`brightRunMedianLuma`、`brightRunLumaSpread`、`selectionPolicy` を追加。**既存JSONを読み取るだけで再判定でき、過去の画像は復元できません**。これまでの照明安定校正、OSC停止条件、同意確認、ランキングへの非反映は変更しません。最大4連続は今回のユーザー提示済みログの要約値であり、次の再解析で選ばれる正確なサンプル番号は未確認です。ストロボなどの演出が続いているだけの可能性があるため、人間の画像確認なしに「見える」「安全」「設備あり」と判定しません。

## 暗いクラブの「一瞬だけ明るい」撮影候補（2026-11-11、試験機能）

90秒の実機観測を既存ログから診断したところ、輝度中央値は最低2／最高186／代表値11でした。輝度45以上は15フレームあり最大4フレーム連続しましたが、**3フレームの輝度差が6以内の校正窓はゼロ**でした。つまり暗いまま固定ではなく、**照明が大きく変わるため従来の安定校正が始まらなかった**状態です。

再撮影せずに、最新の詳細診断で「暗いフレームの後に、2フレーム連続して明るい時間帯があったか」を調べます。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$report = "$HOME\Videos\VRCClubCharts\private-light-recovery\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_20261111T062458Z_0f2ebe8795\lighting-cycle.json"
py -3 scripts/diagnose_light_cycle_report.py --report "$report"
~~~

新しい `briefBrightWindow` には、輝度30以下の暗いフレームが先行し、その後に輝度45以上・ほぼ黒い画素比率92%未満の**2連続フレーム**があるか、候補フレーム番号と明るさを表示します。光量変化だけを調べるもので、画像を復元したり、DJ設備や明暗周期の完了を主張したりしません。

将来の実機観測で、**手動で確認するための1枚だけ**の候補画像を保存したい場合は、従来の監督付きコマンドに `--capture-bright-window` を追加できます。これは**明示的に指定したときだけ有効**です。

~~~powershell
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 90 --live --capture-bright-window --confirm-private-instance --confirm-recording-rights --confirm-platform-authorization --acknowledge-automation-risk
~~~

保存する条件は「一度暗いフレームを観測し、その後に明るいフレームが2回連続したこと」です。従来の厳格な「明るい基準→暗転→安定した回復」検出に成功した場合は、今まで通り `recovery.png` を優先します。厳格な検出に失敗して上の条件だけ満たした場合は `brief-brightness-opportunity-observed` と表示し、`bright-window-candidate.png` を最大1枚だけ非公開保存します。どちらの状態でもOSC移動は0回です。候補画像は**画面が十分見えている証明ではなく、ストロボ・白飛びを除外できません**。必ず人間が視覚確認してください。

権利確認済み・他者不在のPrivate Worldに手動入室している場合に限定し、実行後8秒以内にVRChatを前面に戻してください。出力は従来と同じローカル非公開フォルダに保存され、Geminiやランキングへ送信しません。Worldログ変更、フォーカス喪失、非常停止時には候補画像を保存しません。これを根拠に**自律歩行・自動再開・DJ配信機器の動作判定・ランキング公開**を行うことは禁止のままです。安定周期を確かめる基準値は変更していません。

## 照明回復を自動観測し、安定したフレームを記録する（2026-11-11）

**新しい試験機能：** `scripts/inspection_light_cycle_probe.py`。今のWorldは時間経過でフロアが暗くなるため、OSC移動をさせずに**照明の周期を非公開で観測**できる専用モードを追加しました。

**検出の流れ：** (1) 最初の連続3フレームで明るく安定した基準を測る → (2) 基準から十分暗くなった状態を連続2フレームで確認 → (3) 元の明るさの86%以上に戻り、連続3フレームの明るさが安定したら「照明回復候補」と判定します。観測は1秒間隔、初期設定60秒・最大120秒。明るさの閾値は実機未校正で、ストロボや局所的な演出を完全に判別できません。最初から暗いときには、いったん安定した明るい基準が見つかるまで待ちます。

**回復候補が見つかった場合：** その瞬間のVRChatクライアント画面だけをローカルPNG 1枚とし、光量変化の数値ログを `%USERPROFILE%\Videos\VRCClubCharts\private-light-recovery` に保存します。これにより「照明が回復した瞬間の再観察」を自動化できます。**回復したからといって、勝手に前進・回転・階段移動を再開することはありません。** 撮影権利があるPrivate Worldのみ。Gemini・GitHub・公開サイトへの画像転送はなし。Worldログが変わる、VRChatのフォーカスを失う、Ctrl+Shift+F12を押すと停止します。

まず、**VRChatに触らないDry-run**：

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 90
~~~

実Worldに入室し、OSCの自動移動なしで照明の暗転→回復を観測したい場合は、録画・参加者の権利と運営許可がある**人のいないPrivateインスタンス**に限定して、次を手動実行します。コマンド実行後8秒以内にVRChatを最前面に戻し、観察中はフォーカスを保持してください。

~~~powershell
py -3 scripts/inspection_light_cycle_probe.py --world-id wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79 --seconds 90 --live --confirm-private-instance --confirm-recording-rights --confirm-platform-authorization --acknowledge-automation-risk
~~~

終了後に `status: recovered-stable-light-observed` が出れば、定義した明暗の回復条件を観測でき、`recoveryImage` にローカル証拠画像が保存されています。出力 `lighting-cycle-not-confirmed` は基準・暗転・回復の一部を確認できなかった状態であり、プログラムの通信失敗ではありません。どちらも衝突安全性、World内移動、DJブース・配信動作の証明ではありません。

**次の開発段階：** 複数の光量周期を比較し、回復した瞬間の安全なカメラ撮影を通常の設備調査と連携します。自動歩行を再開するには、前方の安全、Worldの衝突判定、未知の階段・段差、本人または第三者の在室状況などを別に検証する必要があります。

## 暗転・照明フェードを伴うクラブ（2026-11-11）

今回の実機Worldは、時間経過とともに室内照明が落ちて暗くなります。従来の16×9や192×108のスクリーンショット差分のみでは、**暗転をキャラクター移動と誤認する偽陽性**と、**暗くて微小移動を検出できない偽陰性**の両方が起き得ます。GeminiのDJ設備「見えない」判定も、単に暗転していたか、撮影位置が低くて隠れていた可能性を残します。

\`scripts/inspection_lighting_guard.py\` はローカル画像だけから明度を縮小計測し、2枚の画像の大部分が同じ方向に暗く／明るくなる**大きな照明変化の疑い**、ほぼ黒くなったフレームの**低視認性**を判定します。これは小規模な保守的ヒューリスティックで、VRChat内の照明状態・移動・通行可能性を計測した証明ではありません。スポットライトやストロボなど部分的な照明の変化は見逃す場合があり、カメラ回転による明度変化で安全側に誤停止する場合もあります。

実装上の扱い：
- \`scripts/inspection_sweep.py\` の実画面PNGを観察する際、ほぼ黒いフレームや明度全体の急変が起きたら**それ以降のOSC回転を中止**し、\`lighting_transition_or_low_visibility\` または \`low_visibility_or_invalid_image\` を記録。環境変化を部屋の見回し成功の証拠にしません。
- \`scripts/windows_vrchat_inspector.py\` のAI操作モードは、暗転や大きな照明変化を検出すると、**Geminiへ次の移動提案を求めずに停止**。安全な経路や移動距離を決めて歩き続けることはしません。
- \`scripts/inspection_position_feedback.py\` のローカル差分レポートに \`lightingDiagnostics\` と \`frameComparisonConfoundedByLighting\` を追加。動画の再撮影・Gemini再送信なしに、撮影済み2枚の画像から照明変化が疑われるかを調査できます。
- 暗転中にDJブースが写らなくても、World内に存在しないとは判断しないこと。再確認は視界が確保できる状態、または安全な別の撮影位置から行い、人手レビューが完了するまで未確認扱いとします。

実機のこのWorldについて、**いつ照明が暗転するか、どの程度暗くなるか、ストロボのタイミング**は未計測です。今回のしきい値は安全側の初期値であり、正答率の実証は未完了です。現在の実装は「暗いとき停止」が中心で、照明の明るいタイミングを待って自動再開するものではありません。

最新コードをローカルで取得：

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
py -3 -m unittest tests.test_inspection_lighting_guard tests.test_inspection_sweep tests.test_inspection_position_feedback
~~~

\`position-step-feedback.json\` が既に存在している場合、再作成コマンドは既存結果をそのまま返し、後から照明診断を勝手に上書きしません。追加のローカル照明診断を別の成果物として行う場合は、改めてスコープを指定して実施してください。

## 開発・試験の段階

- 単独・非公開で、ユーザー本人またはワールド制作者の許可がある環境に限定する初期試験を想定しています。
- 公式VRChatクライアントは**人間が起動し、対象のWorldに手動で入室**してください。
- 他の参加者が写り込まず、録画に必要な権利があることを確かめてください。音声は保存しません。
- これは**ワールドを順次巡回する機能ではありません**。ワールド変更、アカウントのログイン、パブリックインスタンスへの自動入室、DJ機材のクリック・実動作検証、ランキングの自動公開は行いません。
- 本機能はGitHubで実装・オフライン検証されますが、**実際のWindows VRChatクライアントでの動作確認は未実施**です。

## DJブースが高い位置にあり、撮影地点から見えない場合（2026-11-11）

本番環境で30秒のOSCスイープからGeminiが **DJブース visible / 自己申告信頼度90%** と判定しました。しかし利用者の実視認では、**DJブースは一段高い位置にあり、フロアからは見えず**、抽出画像にもブースが見当たりませんでした。今回のAI判定は、撮影地点での**未確認／誤検出候補**として扱います。映像に見えないことはWorld内にDJブースが無いという意味ではありません。Geminiの自己申告信頼度を実測の検出精度と取り違えないでください。

### 人手レビューを非公開で記録

`scripts/review_facility_keyframes.py` は、抽出済みの `frames.json` と画像をチェックし、元動画ハッシュに結び付けた `human-review.json` と `reviewed-index.html` を**ローカルにだけ**追加します。元の動画・Geminiドラフト・証拠画像・`frames.json`・`index.html` は書き換えません。明示的な `--confirm-visual-review` が必要で、Worldの外観／DJ配信機材の動作を確定しません。

~~~powershell
cd C:\Users\showchoo_main\vrc-club-charts
git pull --ff-only
$frames = "$HOME\Videos\VRCClubCharts\private-keyframes\wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79_efce59d31eab0fb6759f69dc9b7de43d3e5ec72bcd6b4673cc487117812a9320"
$review = py -3 scripts/review_facility_keyframes.py --frames-dir "$frames" --facility dj_booth --verdict not-visible-from-vantage --reason raised-area-out-of-view --confirm-visual-review | ConvertFrom-Json
if ($LASTEXITCODE -eq 0 -and $review.reviewedIndex) { Start-Process $review.reviewedIndex }
~~~

「高い位置で撮影すれば見える可能性がある」という**撮影位置の制約**を記録するもので、AI判定の真偽を再生成するものではありません。他の設備は未確認のまま残ります。判定を変更したくなった場合は、暗黙の上書きをせず個別に見直します。現状は公開サイトやランキングに自動同期しません。

### 次の自律巡回開発の要件

今の `--sweep` は**同じ地点での視点回転**であり、階段・段差・隣の部屋への移動を行いません。次に開発すべきなのは、画角にブースがない場合に「視点不十分」と判断し、異なる視点から再検査する方式です。移動は障害物衝突・落下・World固有の仕組みを考慮する必要があり、現在は動作未検証です。十分な安全確認なしに階段等へ自動移動して「設備あり」と確定しないでください。

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
