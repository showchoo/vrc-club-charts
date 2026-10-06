/*
 * VRC Club Charts / shared public language control.
 * Japanese and English are presentation languages, never separate ranking data:
 * URLs, scores, World IDs, user-submitted text and moderation rules stay unchanged.
 */
(() => {
  'use strict';
  const STORE = 'vcc-site-language';
  const translations = {
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
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) visitText(walker.currentNode);
    document.body.querySelectorAll('[placeholder], [aria-label]').forEach(visitAttributes);
    if (button) {
      button.textContent = language === 'ja' ? 'EN' : '日本語';
      button.setAttribute('aria-label', language === 'ja' ? 'Switch to English' : '日本語に切り替える');
      button.setAttribute('title', language === 'ja' ? 'English' : '日本語');
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
