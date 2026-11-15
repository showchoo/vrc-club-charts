# 掲載クラブの100MB以下除外ルール

## 目的

VRC Club Chartsに掲載するDJクラブWorldのうち、**公開のファイルサイズが100MB以下と確認できたWorldだけ**を、公開一覧・ランキング・World詳細ページ・検索インデックス対象から外します。ちょうど100MBも除外対象です。100MB超は残します。容量不明のWorldは誤削除を避けるために残します。

### 重要：このサイトから非掲載にするだけ

- VRChat本体のWorldや作者のデータを消去する処理ではありません。
- data/worlds.json、ユーザーのお気に入り確認、レビュー、Supabaseの審査・調査履歴は削除しません。
- 公開処理の共通入口 published_worlds() で除外するため、将来Supabaseから同期されても確認済みの小容量Worldが掲載され直さないようにします。
- 容量データが変わり100MB超となった場合、次の確認で再掲載可能です。
- 公開一覧を絞り込む条件であり、イベントやDJ情報の履歴を削除する条件ではありません。

## どの容量を測定するのか

現行のGitHubカタログ200件・Supabaseの公開承認テーブルには、**Worldのサイズ値がありません**。

ファイルサイズの補助情報源として、第三者の公開サイト [Worlds on VRChat (VRCW)](https://en.vrcw.net/) の各World詳細ページにある File size を参照します。これは**公式VRChat APIの当日実測ではありません**。また、そのページでは「どのプラットフォームのビルドか」が明記されない場合があります。そのため、証拠ファイルに platformInterpretation: unspecified-single-reported-build としてその不確実性を残します。

**VRChatのPC版とQuest版の容量を混同しないこと。** VRChat公式はAndroid/Quest Worldの100MB制限を説明していますが、これは「PC版が100MB以下である」証明にはなりません。PC版のサイズが必要なら、対象WorldのWindows用パッケージという区別ができる別データで確認してください。

当サイトの100MBルールは、現段階では**第三者サイトの単一の公開ファイルサイズ表記に基づく暫定的な非掲載**です。誤判定が発見されたら証拠を修正・削除して復帰できます。

## 自動更新と保護条件

- scripts/update_world_sizes.py は data/worlds.json にあるWorld IDだけを、第三者サイトの公開HTMLから収集します。
- 1回最大200 World、約0.7秒以上の間隔で確認し、最大10分で停止します。元のWorldデータ/ファイルのダウンロードやVRChatへのログインは行いません。
- **単一で曖昧さのない数値**（例：File size 82.84MB）だけを採用し、ダウンロードエラー・ID不一致・サイズなし・重複したサイズ表記では除外しません。
- data/world-size-evidence.json にWorld ID、数値、取得日、根拠のURL、プラットフォーム未確定の明示を記録します。
- 取得から45日を超えた容量はサイトからの自動除外に使いません（古いデータだけで無期限に隠さない）。
- ワールドの作成者、スクリーンショット、DJ配信設備の動作を容量から推測しません。
- GitHub Actionsの Refresh public World file sizes を初回は main への実装反映時、以後は毎週実行します。第三者サイトに接続できない場合は未確認のWorldを残します。

## 動作確認

データなしの初期状態では除外対象0件です。最新データが登録されると、scripts/dj_stream_policy.py の共通掲載判定が更新されます。

公開サイトをビルドすると、該当Worldのランキング、クラブ一覧、詳細ページ、サイトマップから除外されます。一方、ソースのWorldカタログとユーザー承認履歴は保持されます。

ローカルでテストする場合：

~~~powershell
py -3 -m unittest discover -s tests -p test_world_size_policy.py -v
py -3 scripts/build_rankings.py
py -3 scripts/validate_catalog.py
~~~

world-size-evidence.json を消すと非掲載になっていたWorldが再び掲載され得るため、通常は削除せずGitで版管理してください。
