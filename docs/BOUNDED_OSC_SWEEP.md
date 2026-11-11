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
