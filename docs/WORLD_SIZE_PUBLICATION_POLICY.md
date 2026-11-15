# 掲載クラブの100MB以下除外ルール（PC版パッケージ）

## 対象と判定基準

VRC Club ChartsのDJクラブWorldで、**Windows PC版の最新UnityPackageが100MiB（104,857,600バイト）以下**と最近のメタデータで確認できたものだけ、公開一覧・ランキング・World詳細ページ・検索インデックスから除外します。**100MiBちょうども除外**です。容量が100MiBを超えるWorld、Quest版しか分からないWorld、古い情報しかないWorld、容量不明のWorldは掲載を維持します。

100MBという運用基準をファイル容量の2進単位（100MiB）で定義します。報告では正確なバイト数も保存するため、しきい値付近の丸め誤差で誤判定しません。

### 削除するのは「公開掲載」だけ

- VRChat本体のWorldを削除しません。
- GitHubの data/worlds.json やユーザーのお気に入り確認、レビュー、Supabaseの管理・調査履歴は削除しません。
- これらの記録を保存したまま、中央の published_worlds() 掲載判定で表示対象から除きます。
- 最新のPC版が100MiB超になった場合は再掲載可能です。
- イベントやDJ出演履歴を一括削除しません。

## ファイルサイズの取得元

[hiinaspace/vrcwscrape](https://github.com/hiinaspace/vrcwscrape) が、VRChatの公開Worldとバージョン別ファイル情報（ShowFile API）をミラーした、[DoltHub公開データベース](https://www.dolthub.com/repositories/hiinaspace/vrcwscrape)を使用します。**第三者によるミラーであり、当日現在の公式サイズを保証するものではありません。**

- public DoltHub SQLから World ID、UnityPackageファイルID、ファイル名、最新版のversion、sizeInBytes、メタデータの取得日時を取得します。
- ファイル名に standalonewindows が含まれるPCパッケージのみ採用。Quest/Android版は決して代用しません。
- 同じWorldにWindows版の複数パッケージがあり、サイズが一致していることを確認できない場合は「容量不明」として扱います。
- **ミラーのファイルメタデータ取得日が90日より古いと除外不可**。今日のGitHub取得日が新しくても、2026年5月取得など古いVRChatデータは使いません。
- 実際のWorldパッケージをダウンロードしたり、VRChatへログインしたりしません。明示的な元データの数値だけを使います。

先行実装はVRCWページの単一「File size」を利用しようとしましたが、GitHub Actionsから5回の取得がすべて失敗しました。容量を0件しか確認できず、PC/Questの区別も曖昧だったため、上記の**Windows版メタデータ限定方式**に切り替えています。

## サイトへの適用

GitHubの data/world-size-evidence.json に、正確なバイト数、PCというプラットフォーム、元パッケージID/バージョン、参照元URL、ミラーの最終取得日とGitHubの確認日を記録します。サイズの根拠が不明ならWorldは掲載されたままです。データは版管理し、表示の除外だけを復旧可能にします。

scripts/update_world_sizes.py がGitHub Actionsで最大200のカタログWorldを3IDずつまとめて、週1回、公開SQLの読み取りで確認します。検証結果は scripts/world_size_policy.py により、公開ランキングと個別ページの両方へ適用されます。取得不能になった場合も掲載データを破棄しません。

## ローカルでの検証

~~~powershell
py -3 -m unittest discover -s tests -p test_world_size_policy.py -v
py -3 scripts/update_world_sizes.py --max-requests 10
py -3 scripts/build_rankings.py
py -3 scripts/validate_catalog.py
~~~

ネットワークやミラーの都合により、**容量不明のWorldは残ります**。削除件数については実際のデータ取得を確認するまでは断定できません。発見数・除外数・取得不能数をGitHub Actionsログで確認してください。
