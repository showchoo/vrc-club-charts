/*
 * VRC Club Charts / shared public language control.
 * Japanese and English are presentation languages, never separate ranking data:
 * URLs, scores, World IDs, user-submitted text and moderation rules stay unchanged.
 */
(() => {
  'use strict';
  const STORE = 'vcc-site-language';
  const translations = {
    // Public page titles and browser search descriptions
    'VRC Club Charts — CLUB DISCOVERY | VRChatクラブを発見': 'VRC Club Charts — CLUB DISCOVERY | Discover VRChat Clubs',
    '体験レビュー — VRC Club Charts': 'Field Notes & Reviews — VRC Club Charts',
    'プライバシーポリシー — VRC Club Charts': 'Privacy Policy — VRC Club Charts',
    'VRChatで個性が光るクラブを探す。ビジュアル評価と訪問者の体験レビューで、次のフロアを見つけよう。': 'Explore standout VRChat clubs through visual impressions and visitor field notes.',
    'VRChatのクラブを探し、その魅力を深く知る。VRC Club Chartsのコンセプト、ビジュアル評価の方法、訪問者レビューの掲載方針。': 'Discover VRChat clubs and how they are evaluated, reviewed and presented.',
    'VRChatのクラブWorldを訪れた感想を、承認申請なしで投稿。AIによる外観スコアとは別の現地レポートです。': 'Share VRChat club experiences openly as moderated field notes, separate from AI visual impressions.',
    'VRChatクラブ／DJ／音楽イベントの予定を探すVRC Club Chartsイベントカレンダー。': 'Find upcoming VRChat club events, DJ sets and music-community nights.',
    'VRChatクラブ／音楽コミュニティで活動するDJのディレクトリ。ランキングではなく、ジャンルと所属から探せます。': 'Browse VRChat DJs, their genres and crews in a non-ranked directory.',
    'VRC Club Chartsの情報の取得・利用・公開範囲、アクセス解析、レビュー投稿とブラウザ保存について。': 'How VRC Club Charts collects, uses and publishes data, including reviews and browser storage.',
    '表示言語（英語／日本語）の選択は、このブラウザのlocalStorageに保存され、サイト内でのみ利用します。': 'Your English/Japanese language preference is stored only in this browser’s localStorage and is used only on this site.',
    // Home / discovery
    '個性が光る、クラブを探す。': 'Discover clubs with character.',
    '話題性だけでは見つからない、個性的なVRChatクラブへ。': 'Beyond the popular picks: discover distinctive VRChat clubs.',
    'ビジュアルの魅力': 'Visual creativity',
    'を手がかりに、次のフロアを見つけよう。': ' is your guide to the next floor.',
    '評価方法を見る ↗': 'How we evaluate ↗',
    'ビジュアル評価ランキング': 'Visual Impression Chart',
    'クラブの世界観や照明、空間デザインの印象を比較。評価前のWorldも発見候補として紹介します。': 'Compare visual atmosphere, lighting and spatial design. Worlds awaiting assessment also appear as discovery leads.',
    'Worldを読み込み中…': 'Loading Worlds…',
    '※ビジュアル評価は公開サムネイル1枚をAIで分析した参考スコアです。実地調査ではなく、音響・ギミック・動作性能は含みません。': 'Visual scores are AI estimates based on a single public thumbnail, not in-world visits. Sound, interactions and performance are not assessed.',
    '評価方法と限界 ↗': 'Method and limitations ↗',
    '掲載されていないクラブを、教えてください。': 'Know a club we missed?',
    'VRChatのWorld URLを貼るだけ。公開情報を確認したうえでAIがクラブ用途を判定し、条件に合えば自動掲載します。': 'Paste a VRChat World URL. We verify its public information and use AI to check club relevance before eligible Worlds are listed automatically.',
    'Worldを投稿する →': 'Submit a World →',
    '公開Worldのみ／同じWorldは重複登録しません。1日3件まで。AI判定が曖昧なものは確認待ちとなり、ランキングの点数は自動生成しません。': 'Public Worlds only. Duplicates are ignored; maximum three submissions per day. Uncertain AI decisions require review. Ranking scores are never fabricated.',
    '編集部が注目するクラブ。': "Editor's picks.",
    '運営者による独立した評価です。ビジュアル評価や訪問者レビューの点数とは合算しません。': 'Independent editorial selections. Their scores are not combined with AI visuals or visitor reviews.',
    '画像の先にある、体験。': 'Beyond the image: the experience.',
    '音・光・ギミック・居心地。写真には写らない魅力を、訪問者の感想から知る。誰でも投稿でき、掲載前に内容を確認します。': "Sound, lights, interaction and atmosphere: hear what photos cannot show through visitors' own reports. Anyone can contribute; submissions are moderated.",
    'レビューを投稿 ↗': 'Write a review ↗',
    '現地レポートを読み込み中…': 'Loading field notes…',
    '訪問・本人情報は自己申告です。個人の評価点はビジュアル評価に加算しません。': 'Visits and identities are self-reported. Individual review scores do not affect the visual chart.',
    'まだ知らないフロアへ。': 'Find your next floor.',
    '次の夜を、見つける。': 'Find your next night.',
    'ワールド情報を表示できません。': 'World information is unavailable.',
    'Upcoming events are being collected.': 'Upcoming events are being collected.',
    'ワールド情報を表示できません。': 'World information is unavailable.',
    'クラブWorldを探しています。画像の分析ができたWorldからビジュアル評価を紹介します。': 'Discovering new club Worlds. Visual impressions will appear as thumbnails are assessed.',
    'ビジュアル評価': 'Visual impression',
    '評価前': 'Not yet assessed',
    '公開画像の印象から推定した参考評価です。': 'A reference score estimated from public imagery.',
    '発見の手がかり ·': 'Discovery clues ·',
    '内部の音響・操作性・動作性能は未評価です。': 'Sound, interactions and performance remain unassessed.',
    '探索中のWorldです。公式ディレクトリへの掲載は未確定です。': 'A World being explored; it has not been verified for the directory.',
    '画像評価前のWorldです。表示タグは発見の手がかりです。': 'Awaiting visual assessment; tags are discovery clues.',
    'クラブ探索データを読み込めませんでした。しばらくしてからお試しください。': 'Could not load club discovery data. Please try again later.',
    '編集部が注目するクラブ': "Editor's picks",
    // World directory and profiles (generated)
    'まだ知らない、次のフロアへ。': 'Discover your next floor.',
    'World名・制作者・ジャンル': 'World name, creator or genre',
    '評価範囲': 'Scope of assessment',
    'ビジュアル評価について': 'About visual impressions',
    '評価の根拠': 'Evaluation basis',
    'このWorldに関連する今後のイベントは、まだ登録されていません。': 'No upcoming events have been listed for this World.',
    '関連するDJの情報は、まだ登録されていません。': 'No associated DJs have been listed yet.',
    'ビジュアル評価は公開サムネイル1枚をAIで分析した参考値です。音響・ギミック・動作性能は未確認です。': 'Visual impressions are AI estimates from one public thumbnail. Sound, interactions and performance are not verified.',
    '評価方法を見る ↗': 'How we evaluate ↗',
    '訪問レビューを投稿する ↗': 'Share your field note ↗',
    '体験レビューを投稿 ↗': 'Write a field note ↗',
    // About / methodology
    'クラブの魅力を、': 'Discover what makes',
    'もっと深く知る。': 'a club exceptional.',
    'VRChatのクラブカルチャーを、見つけるだけでなく、その表現と完成度まで伝える。VRC Club Chartsは、クラブWorldの探索と、訪れた人の体験をつなぐ独立したガイドです。': 'Explore VRChat club culture beyond discovery—its design, expression and craftsmanship. VRC Club Charts connects World discovery with the experiences of people who have visited.',
    '人気より、体験。': 'Experience over popularity.',
    '訪問数やお気に入り数は、Worldを知るきっかけにはなります。しかし、照明の演出、空間の設計、音響、ギミックの完成度までは測れません。': 'Visits and favorites can help you find a World, but they do not measure lighting, spatial design, sound or interactions.',
    'VRC Club Chartsは、話題性と作り込みを分けて紹介します。': 'We keep popularity and craftsmanship separate.',
    'DISCOVER / Worlds・Events・DJs': 'DISCOVER / Worlds, Events & DJs',
    '気になるクラブを探し、イベントの予定をチェックし、出演するアーティストに出会う。シーンを横断して楽しめるよう、情報を整理しています。': 'Discover clubs, explore event schedules and meet the artists behind the scene.',
    'クラブ収集の進捗': 'World discovery coverage',
    '直近の収集結果を確認中…': 'Loading the latest discovery report…',
    '複数の公開情報源からWorld IDを収集し、発見元と確認履歴を保存しています。この数字はVRChat全クラブに対する網羅率ではありません。非公開Worldや外部サイトに掲載されないクラブは発見できない場合があります。': 'We collect World IDs from several public sources and preserve source and verification history. These figures do not represent complete coverage of all VRChat clubs; private and unlisted Worlds may be missed.',
    '情報源別の収集状況を見る ↗': 'View discovery sources ↗',
    'CLUB DISCOVERYは公開されているクラブWorld情報をもとに候補を発見します。ビジュアル評価にはGoogle Geminiの画像解析AIを使用し、公開サムネイルのデザイン・照明の見え方・構図・独創性から0〜100点の参考スコアを推定しています。': 'CLUB DISCOVERY finds candidates using public World information. Google Gemini analyzes public thumbnails to estimate a 0–100 reference score for design, lighting, composition and originality.',
    'この数値は静止画1枚をもとにした推定で、ワールド内の実地評価ではありません。音響・ギミック・実際の照明演出・操作性・動作性能は確認できません。画像や撮影方法による偏りもあるため、点数を作り込み全体の優劣と解釈しないでください。訪問者レビューの点数はビジュアル評価に加算しません。': 'These are estimates from a single image, not on-site evaluations. Sound, interactive features, dynamic lighting, usability and performance cannot be verified. Photo selection can bias the score, which should not be read as an overall craftsmanship ranking. Visitor review scores are not added to the visual chart.',
    'CLUB DISCOVERYを見る ↗': 'Explore CLUB DISCOVERY ↗',
    'CRAFTSMANSHIP / 体験から評価する': 'CRAFTSMANSHIP / Real experiences',
    '実際にWorldを訪れた人なら、審査や専用コードなしで体験レビューを投稿できます。Visual・Lighting & VJ・Sound・Spatial・Interaction・VR Originality・Optimizationの7基準とコメントで、画像からは分からない魅力を伝えます。': 'Anyone who has visited a World can share a field note without applying for reviewer status. Seven criteria and written comments capture what thumbnails cannot.',
    '一般レビューは本人確認や訪問確認を行わない自己申告の感想です。内容を確認して掲載しますが、ビジュアル評価の点数や並び順には加算しません。': 'Community reviews are self-reported and visits or identities are not independently verified. Submissions are moderated and do not affect visual scores or ordering.',
    '掲載情報と編集方針': 'Listings and editorial policy',
    'イベント情報は手動確認した「CURATED」と、公開フィードから条件に沿って抽出した「PUBLIC FEED」を区別します。自動掲載は推薦や品質保証を意味しません。': 'We distinguish manually checked CURATED events from PUBLIC FEED imports. Automated inclusion is neither endorsement nor a guarantee of quality.',
    '広告費やスポンサー契約によってビジュアル評価の点数・並び順を変更することはありません。制作者など関係者による体験レビューは、その関係を明示し、個人の参考評価として掲載します。': 'Advertising and sponsorship do not alter visual scores or ranking order. Reviews from creators or other affiliated parties disclose that relationship.',
    '非公開化・削除されたWorldや、掲載情報に重大な問題がある項目は、必要に応じて公開対象から外します。': 'Private, deleted or materially problematic World listings may be removed.',
    '集計データを現在取得できません。': 'Discovery statistics are currently unavailable.',
    // Reviews and submissions
    'クラブの本当の魅力は、': "A club's real magic",
    '中に入るとわかる。': 'is on the inside.',
    '画像だけでは伝わらない音響・ギミック・空間の使いやすさ。訪問した人の体験を、クラブ選びに役立つ現地レポートとして集めています。': 'Sound, interaction and use of space cannot be captured in a picture. Field notes from real visits help others choose where to go.',
    'レビュワー登録・承認・専用コードは不要です': 'No registration, approval or special code is required',
    '訪れた人の、リアルな声。': 'Voices from the dance floor.',
    '一般の投稿者による感想です。本人確認や訪問の事実確認が完了しているわけではなく、ビジュアル評価には加算されません。': 'These are self-reported visitor impressions. Identity and visits are not independently verified, and scores do not affect the visual chart.',
    '体験を、7つの視点で。': 'Seven ways to describe the experience.',
    'より具体的なレビューにするための共通項目です。スコアは投稿者個人の参考値であり、総合ランキングには使われません。': 'Seven shared criteria help visitors write more specific reviews. Scores represent personal impressions and do not determine an overall ranking.',
    'モデリング、素材、空間のデザイン。': 'Modeling, textures and spatial design.',
    '照明、レーザー、映像演出、曲との連動。': 'Lighting, lasers, visual effects and music sync.',
    '音響の聴こえ方、DJ用途での使いやすさ。': 'Sound quality and suitability for DJ performances.',
    'フロア、DJブース、動線、空間の広がり。': 'Dance floor, DJ booth, circulation and scale.',
    '操作できる演出、ギミック、参加体験。': 'Interactive effects, mechanics and participation.',
    'VRならではの表現や独自性。': 'Distinctive features made possible by VR.',
    '動作の軽さ、安定性、視認性。': 'Performance, stability and legibility.',
    '訪問レビューを投稿する。': 'Share your World experience.',
    'アカウントや審査は不要です。スパム対策のため、同じブラウザから同一Worldへの投稿は30日に1回、投稿数は1日最大3件を目安に制限しています。内容は掲載前に確認します。': 'No account or application is required. To limit spam, a browser may submit to the same World once every 30 days and roughly three reviews a day. All submissions are checked before publication.',
    '表示名': 'Display name',
    '公開されます／本人確認なし': 'Public / not identity-verified',
    'VRChat名やニックネーム': 'VRChat name or nickname',
    '訪問日': 'Date visited',
    '訪問したWorld': 'Visited World',
    'Worldを選択': 'Select a World',
    '合計100点／個人の参考評価': 'Total 100 points / personal reference',
    '具体的な感想': 'Your experience',
    '30〜1800文字': '30–1800 characters',
    '良かった演出や、気になった点など。訪問して感じたことを具体的に教えてください。': 'Describe lighting, sound, interactions, highlights and anything you would change.',
    'このWorldの制作者・スタッフなど、直接の利害関係があります。': 'I am a creator, staff member or otherwise affiliated with this World.',
    '実際にWorldへ訪問して評価しました。投稿は内容確認後に掲載されることに同意します。': 'I visited this World and understand that my review will be checked before publication.',
    'プライバシーポリシー': 'Privacy Policy',
    'を確認しました。': ' reviewed and understood.',
    '訪問レビューを送信 →': 'Submit field note →',
    '掲載後もビジュアル評価には影響しません。': 'Your review will not affect the visual chart.',
    '表示名は自己申告であり、Worldへの訪問や利害関係の申告を独立に検証したものではありません。誹謗中傷・宣伝・重複投稿などは掲載しません。': 'Names, visits and affiliations are self-reported and not independently verified. Abusive, promotional or duplicate posts will not be published.',
    // Events & DJs
    'クラブイベント、DJセット、音楽コミュニティの予定をひとつに。気になる夜から、次の体験を見つけよう。': 'Browse club nights, DJ sets and music-community events in one place.',
    'イベントを登録 ↗': 'Submit an event ↗',
    'ICSカレンダー ↓': 'ICS calendar ↓',
    'イベント名・主催・ジャンル': 'Event, organizer or genre',
    '開催予定': 'Upcoming events',
    '該当するイベントがありません。': 'No matching events.',
    '検索条件を変えるか、イベント情報を登録してください。': 'Try another search or submit an event.',
    '音をつくる人、夜をつなぐ人。VRChatで活動するDJやアーティストを、ジャンルと所属から探せます。': 'Meet the DJs and artists shaping VRChat nightlife. Browse by genre and crew.',
    'DJを登録 ↗': 'Submit a DJ ↗',
    'DJ名・所属・ジャンル': 'DJ name, crew or genre',
    // Review feed and World submission states
    'vrchat.com/home/world/… のWorld URLを入力してください。': 'Enter a VRChat World URL from vrchat.com/home/world/…',
    '公式情報を確認中…': 'Checking official World information…',
    'VRChatの公開状態と登録状況を確認しています。': 'Checking public visibility and listing status.',
    '受付に失敗しました。': 'Your submission could not be processed.',
    'すでに掲載されています。Worlds一覧からご覧ください。': 'This World is already listed. Find it in the Worlds directory.',
    '登録済みのWorldです。掲載ページへの反映をご確認ください。': 'This World has already been registered.',
    '投稿済みです。クラブ判定の証拠が不足しているため確認待ちです。': 'Your submission is pending because there is not enough evidence to confirm it is a club.',
    'このWorldはすでに投稿されています。判定・掲載結果をお待ちください。': 'This World has already been submitted and is awaiting a decision.',
    '投稿を受け付けました。公開情報をAIが判定し、条件を満たせば自動掲載されます。': 'World submitted. AI will review public information and list it if the requirements are met.',
    '送信できませんでした。': 'Could not submit your request.',
    '関係者による投稿': 'Affiliated contributor',
    '掲載中の体験レビューはまだありません。最初の現地レポートをお待ちしています。': 'No field notes have been published yet. Be the first to share a visit.',
    '体験レビューを読み込めませんでした。': 'Could not load field notes.',
    'World一覧を読み込めませんでした。再読み込みしてください。': 'Could not load Worlds. Please refresh the page.',
    'レビューを送信しています…': 'Submitting your field note…',
    'レビューを受け付けました。内容確認後に掲載されます。ご投稿ありがとうございます。': 'Thanks! Your field note was received and will be published after moderation.',
    '出演DJの情報は、まだ登録されていません。': 'No performing DJs are listed yet.',
    'ビジュアル評価は公開画像のみを参考にした推定値です。現地体験レビューは投稿者の自己申告であり、ビジュアル評価の点数・順位に合算されません。': 'Visual scores are estimated only from public images. Field notes are self-reported and do not change visual rankings.',
    // Privacy policy
    'VRC Club Chartsは、VRChatのクラブWorldやイベントを探し、訪問者の感想を共有する独立したサイトです。サイト運営・レビュー投稿・不正利用防止に必要な情報と、その取り扱いについて説明します。': 'VRC Club Charts is an independent site for discovering VRChat clubs and events and sharing visitor experiences. This policy describes the information needed to run the site, process reviews and prevent abuse.',
    '1. 取得する情報': '1. Information we collect',
    'サイト閲覧時：': 'When you browse:',
    '閲覧ページのパス、閲覧日時、外部からの参照元ドメイン、UTMパラメータ（source・medium・campaign）を記録します。推定ユニーク訪問ブラウザ数の集計のため、ブラウザ内で作成したランダムな識別子を送信し、サーバーでは秘密鍵を使ってハッシュ化した値と訪問日だけを別テーブルに保存します。実際の人数や個人を特定するものではありません。': 'We record the page path, time of visit, referring domain and UTM parameters (source, medium and campaign). To estimate unique visiting browsers, a random browser-generated identifier is sent to the server, which stores only a secret-keyed hash and visit date in a separate table. This does not identify actual individuals or the number of people.',
    '掲載漏れのWorld投稿時：': 'When you submit an unlisted World:',
    'VRChatのWorld URLから、公開されているWorld名、制作者、説明、タグ、サムネイルを取得して保存します。投稿頻度制限に、接続元情報とブラウザのランダム識別子から作る非公開のハッシュ値を使用します。生のIPアドレスはWorld投稿用データベースに保存しません。': 'We collect and store public World name, creator, description, tags and thumbnail using the submitted VRChat URL. Private hashes derived from connection information and a random browser identifier enforce rate limits. Raw IP addresses are not stored in the World submission database.',
    '体験レビュー投稿時：': 'When you submit a field note:',
    '投稿者が入力した表示名、対象World、訪問日、7項目の評価、コメント、制作・運営への関係の有無を保存します。投稿にアカウント登録や事前承認は必要ありません。': 'We store your display name, World, visit date, seven criteria scores, comment and declared affiliations with the creator or operator. No account or prior reviewer approval is required.',
    '迷惑投稿防止：': 'Abuse prevention:',
    'ブラウザで作成したランダムな投稿識別子と、接続元IPアドレス等からサーバー側で生成したハッシュ値を利用します。レビュー用データベースには生のIPアドレスを保存せず、ハッシュ値は一般公開しません。ただし、利用するホスティング・API基盤が接続に伴う技術情報を処理する場合があります。': 'We use a random browser-generated submission identifier and hashes generated server-side from connection information, including the IP address. The review database does not store raw IP addresses or expose these hashes publicly. Hosting and API providers may still process technical connection information.',
    '過去の申請：': 'Legacy applications:',
    '旧レビュワー承認制度で受け付けた表示名、連絡先、活動経験等は、既存の非公開データとして管理しています。現在の一般レビュー投稿にレビュワー申請は不要です。': 'Display names, contact details and experience information submitted under the previous reviewer approval program remain managed as private legacy records. Applications are no longer required to submit community reviews.',
    '2. 利用目的': '2. How we use information',
    '収集した情報は、サイト利用状況の把握、情報掲載・サイト改善、体験レビューの受付と表示、重複・迷惑投稿の抑制、セキュリティ確保、不具合対応、お問い合わせへの対応に利用します。': 'We use collected information to understand site usage, publish and improve listings, receive and display field notes, prevent duplicate or abusive submissions, maintain security, resolve issues and respond to inquiries.',
    'World掲載漏れの投稿は、公開情報の照合とGeminiによるクラブ用途判定に使用します。判定結果が高確度で根拠条件を満たす場合は自動掲載し、曖昧な場合は確認待ちとします。Worldの公開情報はAI判定の処理先へ送信される場合がありますが、投稿識別子や接続元ハッシュは送信しません。': 'Submissions of unlisted Worlds are checked against public records and classified for club relevance using Gemini. High-confidence cases meeting evidence requirements may be listed automatically; uncertain cases are held for review. Public World information may be sent to the AI service, but submission identifiers and connection hashes are not.',
    'CLUB DISCOVERYのビジュアル評価では、公開されているWorld名やサムネイル画像等を画像解析サービス（Google Gemini）で処理します。一般利用者の体験レビューや投稿識別子をGeminiの採点用入力として送信する設計ではありません。': 'For visual impressions, Google Gemini processes public World names, thumbnails and similar public information. Community field notes and submission identifiers are not designed to be sent as inputs for Gemini scoring.',
    '評価方法について ↗': 'About our evaluation method ↗',
    '3. レビューの公開範囲': '3. Publication of field notes',
    '投稿されたレビューは、内容を確認したうえで掲載します。公開時は表示名、World、訪問日、評価点、コメント、関係者である旨の申告をサイト上に表示します。本人確認やWorldへの訪問確認を行ったことを意味するものではありません。': 'Field notes are published after review. Published entries show the display name, World, visit date, scores, comment and any declared affiliation. Publication does not mean that we verified identity or the visit.',
    '審査待ち・不掲載のレビューや、投稿識別子・ハッシュ値は一般公開しません。公開後のレビューは検索エンジン等に記録・転載される可能性があり、サイト上で削除しても外部の記録が直ちに消えるとは限りません。表示名やコメントに、第三者の個人情報を入力しないでください。': 'Pending or rejected field notes and submission identifiers/hashes are not made public. Published reviews may be indexed or copied elsewhere, and external copies may persist after deletion from this site. Do not include anyone else’s personal information in names or comments.',
    '4. ブラウザ保存とCookie': '4. Browser storage and cookies',
    'World投稿機能でも、迷惑投稿防止のためランダムなブラウザ識別子を': 'The World submission feature stores a random browser identifier in',
    'に保存します。': 'to prevent abuse.',
    '体験レビュー機能では、投稿頻度の制限に用いるランダムなブラウザ識別子と、表示名の入力補助用データをブラウザの': 'The field note feature stores a random browser identifier for rate limits and a display name helper in',
    'ブラウザ側の保存データは、ブラウザのサイトデータ削除機能から消去できます。ただし、ブラウザの保存データを消しても、すでに送信・公開されたレビューは削除されません。': 'You can clear locally stored data through your browser. This does not delete reviews that have already been submitted or published.',
    'アクセス解析ではCookie・端末指紋（フィンガープリンティング）を使いません。推定ユニーク訪問ブラウザ数のため、ランダム生成したブラウザ識別子を': 'Our first-party analytics do not use cookies or device fingerprinting. To estimate unique visiting browsers, a randomly generated browser identifier is kept in',
    '同一ブラウザからの複数閲覧を数え直さない目的に限り使用し、サーバーは識別子の元データを保存せず、秘密鍵でハッシュ化した値を保存します。管理者向けの解析除外設定も': 'It is used solely to deduplicate visits from the same browser. The server stores only a secret-keyed hash, not the original identifier. The administrator analytics opt-out is also stored in',
    '外部サービス側のCookie・技術的な保存処理については、各サービスの方針が適用される場合があります。': 'Third-party services may have their own cookie and technical storage policies.',
    '5. アクセス解析': '5. Analytics',
    '独自アクセス解析では、閲覧ページのパス・閲覧時刻・外部参照元ドメイン・指定されたUTMパラメータからPVを集計します。さらにブラウザ内で作成したランダムなIDのハッシュ値から、今日・直近7日・直近30日の推定ユニーク訪問ブラウザ数を集計します。生のIPアドレス、User-Agent、ブラウザ識別子の元データ、VRChatのアカウント情報は記録しません。ハッシュは最大40日程度を目安に、次の閲覧計測時に期限切れレコードを削除します。': 'First-party page views use page path, timestamp, referring domain and specified UTM parameters. Hashes of random browser IDs also provide estimated unique browsers today and over the previous 7 and 30 days. We do not store raw IP addresses, User-Agent strings, original browser IDs or VRChat account data. Expired hashes are removed during subsequent analytics events, with a retention target of roughly 40 days.',
    'ブラウザで': 'When',
    'が有効な場合や管理者用のアクセス解析除外を有効にした場合、独自のアクセス解析は送信せず、推定訪問者用の識別子も新規作成しません。解析除外やDo Not Trackが有効な閲覧はPV・推定訪問数ともに集計しません。ブラウザ保存が無効な場合でもPVは記録されますが、推定ユニーク訪問数には含めません。ブラウザ・端末・旧新URLが異なる場合は同じ人でも別々に数えることがあり、過去のPVから人数は復元できません。ホスティング等の外部基盤によるセキュリティ目的の記録には、この設定は影響しません。': 'is enabled in the browser, or the administrator analytics opt-out is on, first-party analytics are not sent and no new estimated-visitor identifier is created. Those visits are excluded from page views and estimated visitor counts. If browser storage is blocked, page views may still be logged but do not count toward estimated unique visits. Different browsers, devices and domains may count the same person separately. Historical person counts cannot be reconstructed from page views. These preferences do not override hosting providers’ security logs.',
    '6. 外部サービス・投稿窓口': '6. Third-party services and submissions',
    'サイトの公開、データ保存、画像やWorld情報の取得等に、Vercel、GitHub、Supabase、VRChat関連サービスを利用しています。World画像の表示時や外部リンクを開く際には、接続先へIPアドレス等の技術的情報が送信される場合があります。': 'We use Vercel, GitHub, Supabase and VRChat-related services for hosting, storage, images and World information. Loading a World image or opening an external link may transmit technical connection data, including IP addresses, to that service.',
    'World・イベント・DJの推薦はGitHubのIssueフォームから受け付ける場合があります。その場合、送信した内容やGitHubアカウント名は公開され得ます。GitHubのフォームにパスワード、非公開の連絡先、本人確認書類などを入力しないでください。': 'World, event and DJ recommendations may be submitted via GitHub Issues. Submitted information and your GitHub username may become public. Do not submit passwords, private contact details or identity documents.',
    '7. 保存・管理・削除': '7. Retention and deletion',
    'データは利用目的に必要な範囲で管理し、一般利用者からレビュー投稿データや旧申請情報を直接閲覧できないよう、アクセス権限を制限しています。現状、すべての情報に共通する一律の自動削除期限は設定していません。': 'Data is managed as needed for the purposes described above. Access restrictions prevent general users from directly reading submitted reviews and legacy application data. We do not currently apply one universal automatic deletion deadline to every category.',
    'ご自身に関する情報の確認・訂正・削除、公開レビューの取り下げについては、下記窓口にお問い合わせください。対象情報と申出内容を確認し、対応可能な範囲で個別にご案内します。': 'To request access, correction, deletion of your information or withdrawal of a published review, use the contact method below. We assess requests individually and respond where possible.',
    '8. お問い合わせ・改定': '8. Contact and updates',
    'サイト運営や情報の取り扱いに関するお問い合わせは、': 'For questions about the site or its use of information, contact us through',
    'VRC Club ChartsのGitHub Issues ↗': 'VRC Club Charts GitHub Issues ↗',
    'から受け付けています。Issuesは公開されるため、個人情報や秘密情報は記入せず、非公開の連絡方法が必要な場合はその旨のみをお知らせください。': '. Issues are public, so do not include personal or confidential information; if private contact is needed, only state that requirement.',
    '機能や外部サービスの変更に合わせて、本ポリシーを更新することがあります。広告・計測サービス等を追加する場合も、実際の取り扱いに応じて説明を更新します。': 'This policy may be updated as features or providers change, including new advertising or analytics services. Changes will reflect actual data practices.',
    '最終更新：2026年10月6日 / VRC Club Charts（独立運営サイト）': 'Last updated: October 6, 2026 / VRC Club Charts (independent project)',
    // Live UI and form feedback
    'Worldを投稿中…': 'Submitting World…',
    '送信しています…': 'Submitting…',
    '送信しました。': 'Submitted.',
    'レビューを読み込み中…': 'Loading reviews…',
    'レビューがまだありません。': 'No reviews yet.',
    'すべて': 'All',
    'すべてのジャンル': 'All genres',
    '件': 'items',
  };

  const patterns = [
    {
      re: /^(\d[\d,]*)のWorldを収録。クラブ・DJ・レイヴなど、まだ知らないWorldを探せます。ビジュアルの参考スコアと、訪問した人の体験レビューを分けて紹介します。$/,
      en: m => `Discover ${m[1]} Worlds across clubs, DJs and raves. Visual reference scores and visitor field notes are presented separately.`
    },
    {
      re: /^掲載\s*([\d,]+)件\s*\/\s*確認待ち\s*([\d,]+)件\s*\/\s*履歴保存\s*([\d,]+)件（最終集計\s*(.*?)）$/,
      en: m => `Listed ${m[1]} / Pending ${m[2]} / Tracked ${m[3]} (last update: ${m[4]})`
    },
    {
      re: /^ビジュアル評価 (\d+)件 · 画像ベースの参考値$/,
      en: m => `Visual assessments: ${m[1]} · Image-based estimates`
    },
    {
      re: /^(\d+) WORLDS DISCOVERED \//,
      en: m => m[0] // Existing discovery fallback is already in English.
    },
  ];

  const originals = new WeakMap();
  const attributeOriginals = new WeakMap();
  let language = 'ja';
  let button;
  let scheduled = false;
  let originalTitle = '';
  let originalMetaDescription = '';

  function translate(original, lang) {
    if (lang === 'ja') return original;
    const key = original.trim();
    if (!key) return original;
    let replacement = translations[key];
    if (replacement === undefined) {
      for (const pattern of patterns) {
        const match = key.match(pattern.re);
        if (match) {
          replacement = pattern.en(match);
          break;
        }
      }
    }
    if (replacement === undefined || replacement === key) return original;
    const start = original.match(/^\s*/)[0];
    const end = original.match(/\s*$/)[0];
    return start + replacement + end;
  }

  function visitText(textNode) {
    const parent = textNode.parentElement;
    if (!parent || /^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA|CODE|PRE)$/i.test(parent.tagName)) return;
    if (parent.closest('[data-vcc-no-translate]')) return;
    const previous = originals.get(textNode);
    const current = textNode.nodeValue;
    const source = previous && current === previous.rendered ? previous.source : current;
    const rendered = translate(source, language);
    originals.set(textNode, {source, rendered});
    if (rendered !== current) textNode.nodeValue = rendered;
  }

  function visitAttributes(node) {
    if (!node || node.nodeType !== 1 || node.hasAttribute('data-vcc-no-translate')) return;
    const original = attributeOriginals.get(node) || {};
    const next = {};
    for (const name of ['placeholder', 'aria-label']) {
      if (!node.hasAttribute(name)) continue;
      const now = node.getAttribute(name);
      const source = original[name] && now === original[name].rendered ? original[name].source : now;
      const rendered = translate(source, language);
      next[name] = {source, rendered};
      if (now !== rendered) node.setAttribute(name, rendered);
    }
    attributeOriginals.set(node, next);
  }

  function update() {
    if (!document.body) return;
    document.documentElement.lang = language;
    document.documentElement.dataset.vccLang = language;
    if (originalTitle) {
      const title = translate(originalTitle, language);
      if (document.title !== title) document.title = title;
    }
    const description = document.querySelector('meta[name="description"]');
    if (description && originalMetaDescription) {
      const value = translate(originalMetaDescription, language);
      if (description.getAttribute('content') !== value) description.setAttribute('content', value);
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) visitText(walker.currentNode);
    document.body.querySelectorAll('[placeholder], [aria-label]').forEach(visitAttributes);
    if (button) {
      const label = language === 'ja' ? 'EN' : '日本語';
      if (button.textContent !== label) button.textContent = label;
      const aria = language === 'ja' ? 'Switch to English' : '日本語に切り替える';
      if (button.getAttribute('aria-label') !== aria) button.setAttribute('aria-label', aria);
      const title = language === 'ja' ? 'English' : '日本語';
      if (button.getAttribute('title') !== title) button.setAttribute('title', title);
    }
  }

  function queueUpdate() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      update();
    });
  }

  function setLanguage(next) {
    if (next !== 'en' && next !== 'ja') return;
    language = next;
    try { localStorage.setItem(STORE, next); } catch (_) {}
    update();
    window.dispatchEvent(new CustomEvent('vcc:language-change', {detail: {language: next}}));
  }

  function init() {
    originalTitle = document.title;
    originalMetaDescription = document.querySelector('meta[name="description"]')?.getAttribute('content') || '';
    const header = document.querySelector('.site-header');
    if (header && !document.getElementById('vccLanguageToggle')) {
      button = document.createElement('button');
      button.id = 'vccLanguageToggle';
      button.type = 'button';
      button.className = 'vcc-language-toggle';
      button.setAttribute('data-vcc-no-translate', 'true');
      button.addEventListener('click', () => setLanguage(language === 'ja' ? 'en' : 'ja'));
      header.appendChild(button);
    }
    try {
      const saved = localStorage.getItem(STORE);
      language = saved === 'ja' || saved === 'en' ? saved
        : navigator.language.toLowerCase().startsWith('ja') ? 'ja' : 'en';
    } catch (_) {
      language = navigator.language.toLowerCase().startsWith('ja') ? 'ja' : 'en';
    }
    update();
    new MutationObserver(queueUpdate).observe(document.body, {
      childList: true, subtree: true, characterData: true
    });
  }

  window.VCCLanguage = {get: () => language, set: setLanguage, translate};
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once: true});
  } else {
    init();
  }
})();
