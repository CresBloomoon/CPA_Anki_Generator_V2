# CPA Anki Generator V2 — Step → Phase 実装計画

（Claude Code が /home/node/.claude/plans/precious-splashing-quill.md に生成し、承認済みの計画のバックアップ。全34Phase。Phase5-3〜5-11はPhase5-1・5-2の実機検証を踏まえて後日追加。）

## Context

CPA_Anki_Generator_V2 は実装着手前（コードなし、依頼書のみ）。依頼書の実装順序（domain →
repositories → usecases → routes → frontend）を、レビュー・実装可能な小さいPhase単位まで分解した。
根拠は依頼書本文と、参照専用の旧リポジトリ（/workspace/CPA_Anki_Generator）の
main.py/pdf_parser.py/ai_client.py/anki_creator.py/config_manager.pyの詳細調査。
旧リポジトリは「参照専用・反面教師込み」として扱い、良い部分は移植し、既知のバグ（後述）は
V2で明示的に直す。

計画提示後にユーザーから受けた回答により、以下の4点は確定事項として反映済み：
- 画像コピー機能（html2canvas）はちゃんと直す（メディアファイルを実際に同梱する）
- 進捗取得はポーリング
- 生成ジョブの永続化はインメモリのみ
- 科目リストのUI（人間が選択する設定機能）は不要。代わりに「章タイトル自動検出」＋
「本1冊分の共通ルートパスを1回だけ入力」という新しいフローをスコープに追加

## 全体方針

- 各PhaseはPR1つ分の粒度。前Phaseへの依存を明示。
- レイヤー別テスト方針：domain＝純粋ユニットテスト／repositories＝薄いフィクスチャでのI/Oテスト／
usecases＝repositoryをフェイクにしたテスト（C#/DDD経験が最も活きる層）／routes＝FastAPI
TestClient／frontend＝最初は手動確認。
- 旧アプリは全状態をst.session_state（サーバメモリ、単一ブラウザセッション）に依存していたが、
V2はHTTPなので「アップロード済みPDF」「生成ジョブ状態」をサーバ側に保持する場所が新規に必要
（旧アプリには存在しない概念）。これがStep0〜Step3を通じて一番の設計上の分岐点。

---
## Step 0: 環境構築

### Phase0-1: バックエンド最小骨格
- 実装物：backend/app/{routes,usecases,repositories/{ai,pdf,anki,jobs,settings},domain} の空パッケージ、
FastAPI main.py（/healthのみ）、依存管理（pyproject.toml推奨）、Dockerfile
- 依存：なし
- Done when：docker buildが通り、コンテナ起動後/healthが200を返す

### Phase0-2: フロントエンド最小骨格
- 実装物：frontend/（Vite+TS+Tailwind雛形）、src/App.tsxプレースホルダ、Dockerfile
- 依存：なし（0-1と並行可）
- Done when：コンテナ内でnpm run dev相当が動き、白紙ページが表示される

### Phase0-3: Docker Compose結線 + .env.example
- 実装物：ルートdocker-compose.yml（frontend/backend分離、env_fileでbackendに読込）、
ルート直下.env.example（GEMINI_API_KEY=／CLAUDE_API_KEY=／OPENAI_API_KEY=のみ）
- 決定事項：.envはリポジトリルート直下に置く（旧repoはapp/.envだったが、V2はcompose起点で
管理する方がシンプルなため）
- 依存：0-1, 0-2
- Done when：docker compose upで両コンテナが立ち上がる

### Phase0-4（任意・後回し可）: Lint/Format
- 実装物：backend側ruff/black、frontend側eslint/prettier
- 依存：0-1, 0-2

---
## Step 1: ドメイン層

### Phase1-1: Section（章タイトルを含む）
- 実装物：domain/section.py
  - PageRange（開始ページ・任意の終了ページ、start >= 1検証、ページ数計算）
  - DeckPath（"::"区切りの値オブジェクト。空セグメント禁止、joined()、child(title)で
子パス生成——root_path.child(chapter_title).child(section_title)のように連鎖させて使う）
  - Sectionエンティティ：title（節タイトル）, chapter_title（章タイトル、新規）, page_range,
deck_path, min_card_count: int >= 0, source_file: str
  - 「選択」チェックボックスの真偽値はUI都合でありドメイン不変条件ではないためSection自体には
持たせない（route/usecase層のDTOで扱う）
- 依存：なし
- Done when：不正値（開始ページ0、空タイトル等）で例外が出るユニットテストが揃う

### Phase1-2: CardContent と Card
- 実装物：domain/card.py
  - CardContent：AIリポジトリの戻り値契約。1回のgenerate_cards呼び出し（＝1テキストチャンク）が
生成する複数カードのコンテナ（TITLE/QUESTION/RONSHO_BODY/KAISETSU_BODY/YO_SURUNI_BODY/
RYUI_BODY/RANK_TANTO/RANK_RONBUN/PAGE_CODE/TAGSの10フィールドを持つCardContentItemのリスト）。
PAGE_CODE非空を必須バリデーション
  - Card：CardContentItem + メタデータ（section_title, deck_path）を合成したエンティティ。
identity_key()が「TITLE＋明示的な区切り文字＋section_title」を返す（旧anki_creator.pyの
GUID衝突バグ＝区切りなし連結、をここで明示的に修正）
- 依存：Phase1-1
- Done when：PAGE_CODE空文字が拒否される／identity_key()が区切りありで衝突しないことを確認

### Phase1-3: Deck
- 実装物：domain/deck.py
  - Deckアグリゲート：deck_path + cards: list[Card]、add_card(card)（deck_path不一致は
エラー）
  - deterministic_deck_id(deck_path) -> int：Python組込みhash()（プロセスごとに非決定的＝旧
repoの既知バグ）ではなくhashlib.md5等の決定的ハッシュを使う純粋関数
- 依存：Phase1-2
- Done when：同じdeck_pathから常に同じdeck_idが返ることをテストで保証

### Phase1-4: GenerationJob
- 実装物：domain/generation_job.py
  - SectionJobStatus（PENDING/RUNNING/DONE/FAILED）
  - SectionJob：section, status, cards, error_message
  - GenerationJob：job_id, section_jobs、状態遷移メソッド（mark_running/mark_done/
mark_failed）、is_complete(), collect_generated_cards()（完了済みのみ集約）
  - 「1セクション失敗で残りは中断するが完了済みは保持する」という旧UX契約を、位置インデックス
ではなく状態機械として表現する
- 依存：Phase1-2
- Done when：一部FAILED・残りPENDINGでもcollect_generated_cards()が完了済み分だけ返す

---
## Step 2: Repositories層

### Phase2-1: PDF構造解析リポジトリ（章・節の2階層検出）
- 実装物：repositories/pdf/pdf_structure_repository.py
  - 移植：ページ上部30%以内の視覚的見出し検出（正規表現第...[節章項]）、TOC/outlineとの
突合、format_section_titleの正規化（全角→半角、漢数字→算用数字、2桁ゼロ埋め）、
count_ranks_in_textのランクカウント経験則（50文字以内は同一論点）、
extract_text_from_rangeのページ区切りマーカー付き抽出
  - 新規（章タイトル自動検出）：正規表現の末尾文字（章／節／項）で見出しレベルを判定し、
ページを先頭から走査しながら「現在の章タイトル」を状態として保持、以降に検出される節見出しに
その章タイトルを付与する。TOCフォールバックで拾った節にも、直前の章の開始ページから
ブラケティングして章タイトルを推定して付与する
  - 明示的に修正：全例外をswallowして空/部分結果を返す旧仕様をやめ、型付き例外または
ScanResult(sections, warnings)のような結果型で「一部失敗」を明示的に表現する
  - 出力はPhase1-1のSectionの材料（title, chapter_title, page_range, min_card_count,
source_file）——deck_pathの組み立て（root_pathとの連結）はここでは行わず、usecase層に
委ねる（root_pathはリクエスト時の入力でありPDF解析の関心事ではないため）
- 依存：Phase1-1
- ⚠前提・要確認：「項」（第3階層）は旧仕様同様、節と同じ階層として扱う（章→節の2階層のみを
新設し、項を独立階層として扱う要望がなければこのまま進める）
- Done when：2章×複数節を含むサンプルPDFフィクスチャで、各節に正しい章タイトルが付与される

### Phase2-2: AI抽象化の骨組み（AiCardGeneratorRepository）
- 実装物：repositories/ai/base.py（抽象基底、generate_cards(section_text, prompt_context)
-> CardContent）、repositories/ai/dto.py（PromptContext）、repositories/ai/prompt_builder.py
（project_constitution.md＋Front/Back HTMLテンプレート＋anki_generation.mdを結合、旧
get_base_promptの構成順序を踏襲）、prompts/・card_templates/をbackend配下に移植
- 依存：Phase1-2
- Done when：PromptBuilderの出力に3ファイルの内容とsection_textが期待順序で含まれることを確認

### Phase2-3: Gemini具象実装
- 実装物：repositories/ai/gemini_repository.py（temperature=0.0,
response_mime_type="application/json"）、repositories/ai/json_repair.py（旧
_extract_cards_from_jsonの多段階JSON修復ロジック移植——実運用で発生する打ち切りJSON対策として
必要）
- 依存：Phase2-2
- 明示的に修正：3キーローテーションは廃止（単一GEMINI_API_KEY）。レート制限時の指数バックオフ
リトライは単一キー内でも有用なので残す
- Done when：正常JSON／わざと壊したJSONの両方でCardContentが正しく得られる

### Phase2-4: 設定リポジトリ（プロバイダー／モデル選択）
- 実装物：repositories/settings/settings_repository.py（現在のprovider・model_nameの読み書き）
- 依存：なし
- Done when：設定値の読み込み・保存の往復テストが通る
- 備考：科目リストUIは不要と決定済み。ここは依頼書のFactory要件を満たす最小スコープのみ

### Phase2-5: AI Repository Factory
- 実装物：repositories/ai/factory.py（AiCardGeneratorFactory.create(settings) ->
AiCardGeneratorRepository。現時点ではGeminiのみ分岐）
- 依存：Phase2-3, Phase2-4
- Done when：provider="gemini"設定からGeminiRepositoryが正しく構築される

### Phase2-6: Ankiパッケージングリポジトリ（画像コピー機能を正しく機能させる）
- 実装物：repositories/anki/anki_package_repository.py
  - 移植：genankiモデル定義（TAGS以外の9フィールド）、テンプレート／CSSのファイルロード、
deck_pathごとのグルーピング、一時ファイル経由の.apkgバイト列取得
  - 明示的に修正：deck_id = abs(hash(...))（非決定的）→ Phase1-3のdeterministic_deck_id。
GUID＝genanki.guid_for(TITLE + section_title)（区切りなし衝突）→ Phase1-2の
Card.identity_key()
  - 画像コピー機能（必須維持・削除/簡略化しない）：旧anki_back_card_template.html／
anki_card_style.cssのソースコードを実際に読んで確認した、正確な仕組みは以下の通り：
    1. 回答面の4ボックス（論証／解説／要するに？／留意点）はonclick="copyBox(this)"を持つ
    2. copyBox(el)は、ClipboardItemとnavigator.clipboard.writeが使える環境では：
html2canvas(el, {scale:3, backgroundColor:"#ffffff", onclone: .copy-overlayを非表示})
でそのボックスをDOMごと（枠線・背景色・パディング等のスタイル込みで）ラスタライズして
canvas化→canvas.toBlob(..., "image/png")でPNG Blob化→
new ClipboardItem({"image/png": blobPromise})をnavigator.clipboard.write([...])で
システムクリップボードに画像として書き込む（GoodNotes等、画像貼り付けに対応した
アプリへそのままペースト可能になるのはこのため）
    3. ClipboardItem非対応環境（Clipboard画像書き込み非対応のwebview等）では
navigator.clipboard.writeText(...)によるプレーンテキストコピーに自動フォールバックする
    4. 成功時は.copy-overlayに_success_icon.pngを背景画像としたsuccess-pop-fade
アニメーション（1秒間のチェックマーク演出）を発火する
  - このcopyBoxのJS/CSSロジック自体は正しく設計されているためそのまま移植する（書き直さない）。
旧実装の不具合は「ロジックが動いていない」ことではなく、参照している_html2canvas.jsと
_success_icon.pngの2ファイルがgenankiパッケージのmedia_filesに一度も同梱されていなかったこと。
V2ではこの2点を実際に用意し同梱することで、既存の仕組みをそのまま機能させる：
_html2canvas.js（MITライセンスの配布物をバージョン固定でリポジトリにベンダリング）と
_success_icon.png（チェックマーク等のシンプルなアイコンを新規作成/調達）を
backend/app/card_templates/assets/に配置し、genanki.Package(decks, media_files=[...])で
同梱する
- 依存：Phase1-2, Phase1-3
- Done when：生成した.apkgをAnki Desktopに実インポートし、回答カードをクリックするとそのボックス
のスクリーンショット（PNG画像）が実際にクリップボードにコピーされ、他アプリ（画像貼り付け対応、
例：GoodNotes）にペーストできることを確認（Step6のE2Eで実施）

### Phase2-7（任意・後回し）: 科目自動推定リポジトリ
- 実装物：repositories/pdf/subject_inference_repository.py（PDFファイル名・本文のキーワード
出現頻度によるスコアリングで科目候補を推定する軽量な文字列マッチング。AI呼び出し不要）
- 依存：Phase2-1
- 位置づけ：ユーザー要望では「必須ではなく、コストが見合わなければ後回しでよい」と明言されている
ため、Step6でE2Eが通った後に着手するかどうかを判断する任意Phaseとする
- Done when：サンプルPDF名・本文で妥当な科目候補が返る

### Phase2-8／2-9（後続・依頼書で明示的に後回しと指定）: Claude／ChatGPT具象実装
- 実装物：repositories/ai/claude_repository.py（tool use）／repositories/ai/chatgpt_repository.py
（response_format）
- 依存：Phase2-2のみ（Gemini実装と独立に着手可能）
- Done when：各プロバイダー固有の構造化出力機構が吸収され、同じCardContentが得られる

---
## Step 3: UseCases層

### Phase3-1: 構造スキャンUsecase（ルートパス入力を反映）
- 実装物：usecases/scan_pdf_structure_usecase.py
  - 入力：複数PDF＋ユーザーが1冊につき1回だけ入力するroot_path（例:
公認会計士試験::財務会計::理論）
  - 処理：Phase2-1で章・節を検出→各Sectionのdeck_pathを
DeckPath(root_path).child(chapter_title).child(section_title)として初期値組み立て
（以後テーブル上で行ごとに編集可能）
  - 複数PDFをまとめてスキャンしsource_fileを付与するロジック（旧main.py相当）もここに集約
- 依存：Phase1-1, Phase2-1
- Done when：root_path="X::Y"で2章×複数節のフィクスチャを流すと、各Section.deck_pathが
X::Y::章タイトル::節タイトルになる

### Phase3-2: セクション単位カード生成Usecase（サブシュレッディング含む）
- 実装物：usecases/generate_cards_for_section_usecase.py
  - 移植：ブロック分割ルール（total_pages > 5 OR min_goal > 20なら4ページ単位に分割、
block_goal = max(1, min_goal // ブロック数)、最終ブロックは残り全部を割当）
  - Phase2-1のテキスト抽出＋Phase2-5のFactory経由AIリポジトリ呼び出し、CardContentをCardに
変換
  - セクション失敗時は例外を送出（swallowしない。中断判断はPhase3-3が行う）
- 依存：Phase1-2, Phase2-1, Phase2-5
- Done when：フェイクAIリポジトリで「6ページ・最低枚数25」入力がブロック3つに分割され、
各ブロックの目標枚数が期待通りになる
- ⚠着手時に検討：Phase2-2で判明した通り、`PromptContext.section_title`は現時点で
  `PromptBuilder.build()`の出力（実際にAIへ渡されるプロンプト）に一切反映されていない
  （旧`ai_client.py`も節タイトルをAIへ渡していなかったための忠実な移植）。AIが「どの節の
  話をしているか」を知らないまま本文だけでカードを生成している状態であり、正確性の観点で
  改善余地がある可能性が高い。本Phaseで`Section`から`PromptContext`を組み立てる際、
  `section_title`を実際にAIへ渡す設計にするかどうかを検討し、対応すること。

### Phase3-3: 生成ジョブオーケストレーションUsecase（非同期、インメモリ、ポーリング前提）
- 実装物：
  - repositories/jobs/job_store.py：インメモリのGenerationJob保存（プロセス内dict＋
asyncio.Lock）。永続化なし（バックエンド再起動でジョブは消える——決定事項）
  - usecases/start_generation_job_usecase.py：選択済みSectionリストからGenerationJobを
作成しジョブストアに登録、バックグラウンド実行を開始（FastAPI BackgroundTasks）
  - ジョブ実行本体：Phase3-2をセクションごとに順次呼び出し、SectionJobの状態を
RUNNING→DONE/FAILEDに更新。1セクション失敗で残りはPENDINGのまま中断するが完了済みは保持
  - usecases/get_generation_job_status_usecase.py：ジョブIDから各セクションの状態を返す
（クライアントはこれをポーリングする——決定事項）
  - アップロード済みPDFバイト列はサーバ側インメモリストア（repositories/pdf/pdf_store.py）に
IDで保持し、スキャン・生成の両方から同じIDで参照する（旧st.session_state.pdf_info相当。
毎回再アップロードさせない）
- 依存：Phase1-4, Phase3-2
- Done when：3セクション中2番目が失敗するシナリオで、1番目DONE・2番目FAILED・3番目PENDING
で停止し、collect_generated_cards()が1番目の分だけ返す

### Phase3-4: パッケージングUsecase
- 実装物：usecases/build_anki_package_usecase.py（ジョブのcollect_generated_cards()から
Phase2-6を呼び出し.apkg生成。完了済み全部か一部かで「final」「partial」を切り替える旧UXを踏襲）
- 依存：Phase1-4, Phase2-6, Phase3-3
- Done when：一部完了状態のジョブから「partial」ラベル付き.apkgが生成できる

---
## Step 4: Routes層

### Phase4-1: PDFアップロード／スキャンAPI
- 実装物：routes/pdf_routes.py
  - POST /pdfs：ファイルを受け取りPDFストアに保存、pdf_idを返す
  - POST /scan：pdf_idのリスト＋root_pathを受けPhase3-1を呼び出し、章タイトル込みの
Section一覧をJSONで返す
- 依存：Phase3-1、Phase3-3のPDFストア
- Done when：TestClientで実PDFをアップロード→スキャンし、章タイトル付き節一覧が返る

### Phase4-2: 生成リクエストのスキーマ定義
- 実装物：routes/schemas/generation.py（Pydantic）：SectionInput（selected, title,
chapter_title（新規）, start_page, deck_path, min_card_count, source_file）、
StartGenerationRequest（sections: list[SectionInput], additional_prompt: str | None）
- 依存：Phase1-1
- Done when：不正入力（開始ページ負数など）でバリデーションエラーが返る
- 備考：セクション編集はクライアント側React stateで完結するため独立の「編集API」は不要。
このスキーマが実質的な編集契約になる

### Phase4-3: 生成ジョブAPI（開始／進捗ポーリング／ダウンロード）
- 実装物：routes/generation_routes.py
  - POST /generation-jobs（Phase4-2のリクエストを受けPhase3-3で開始、job_idを返す）
  - GET /generation-jobs/{job_id}（各セクションの状態・進捗を返す。フロントはこれを一定間隔で
ポーリング）
  - GET /generation-jobs/{job_id}/download（Phase3-4を呼び出し.apkgをストリーム返却）
- 依存：Phase3-3, Phase3-4, Phase4-2
- Done when：ジョブ開始→ポーリングでDONE確認→ダウンロードでvalidな.apkgが返る一連の流れが通る

### Phase4-4: 設定API（プロバイダー／モデルのみ）
- 実装物：routes/settings_routes.py（GET/PUT /settings＝provider・model_name）
- 依存：Phase2-4
- Done when：設定の読み書きがAPI経由で往復できる

---
## Step 5: フロントエンド

### Phase5-1: アップロード＋ルートパス入力UI
- 実装物：components/UploadPanel.tsx（複数PDF選択→POST /pdfs→pdf_id保持、本1冊分の
共通ルートパス（例:公認会計士試験::財務会計::理論）を1回入力するテキスト欄、スキャン開始
ボタン→POST /scan）
- 依存：Phase4-1
- Done when：実PDFを選択しルートパスを入力してスキャンし、章タイトル込みの結果が確認できる

### Phase5-2: セクションテーブルUI（章タイトル列を追加）
- 実装物：components/SectionTable.tsx（<table>＋React state。列：チェックボックス／
章タイトル（新規・編集可）／節タイトル（編集可）／開始ページ（編集可）／
出力デッキ名（root_path::章::節で初期表示、編集可）／最低枚数（編集可）／ソースファイル。
行の追加削除も可能）
- 依存：Phase5-1
- 明示的に反面教師として避けるもの：旧sections_df/sections_df_latestの二重ステート管理は
行わない。単一のsections: SectionRow[]ステートとimmutableな更新関数で完結させる
- Done when：セルを1回編集しただけで即座に反映される（旧アプリの「1回目の編集がリバートする」
バグが再現しないことを確認）
- 備考（実装詳細・低リスクなのでデフォルト採用）：出力デッキ名の自動補完は、同一テーブル内の
既出デッキパスからの<datalist>程度の簡易版で開始する

### Phase5-3〜5-11 追加の経緯

Phase5-1・5-2をまーくんが実際にブラウザで操作して見つかった8件のUI/UX改善要望を、
新規Phaseとして追加した。実装順序は、生成トリガー／ダウンロードUI（旧Phase5-3/5-4）を
Phase5-4/5-5へ先に繰り上げ、残り6項目をPhase5-6〜5-11へ回す構成とする（理由：
生成トリガー〜ダウンロードは一度もブラウザで手動検証されていない未知数の大きい領域であり、
早期に検証してこのツール本来の価値（実際にAnkiデッキが作れること）に到達することを優先した。
残り6項目は、生成トリガーUIまで実際に使ってみた後にまとめて対応した方が、他に見つかる
改善点と合わせて手戻りなく実施できると判断した）。任意項目（旧5-5/5-6）はPhase5-12/5-13へ
繰り下げる。

### Phase5-3: セクションテーブルの操作ボタンをアイコン化＋ルートパスのデフォルト値
- 実装物：
  - SectionTable.tsxの削除ボタンをゴミ箱アイコンに、「行を追加」ボタンを＋アイコン付きに
変更（外部アイコンライブラリは追加せず、インラインSVGの自作アイコンで対応）
  - UploadPanel.tsxのルートパス入力欄の初期値を「公認会計士試験::」に変更
- 依存：Phase5-2
- Done when：見た目が変わり、削除・追加・スキャンの機能自体は従来通り動作する
- 備考：3点とも設計判断を要さない軽微な変更のため1Phaseにまとめる

### Phase5-4（旧Phase5-3）: 生成トリガー＋進捗UI（ポーリング）
- 実装物：components/GenerationProgress.tsx（生成開始→POST /generation-jobs→一定間隔で
GET /generation-jobs/{id}をポーリング→セクションごとの状態と全体進捗バーを表示）
- 依存：Phase4-3, Phase5-2
- Done when：実行中に各セクションの状態がポーリング間隔分の遅延ありで切り替わって見える

### Phase5-5（旧Phase5-4）: ダウンロードUI
- 実装物：components/DownloadButton.tsx（完了/一部完了に応じてラベル・ファイル名を切り替え、
GET /generation-jobs/{id}/downloadをトリガー）
- 依存：Phase4-3, Phase5-4
- Done when：一部完了時点でも「途中経過をダウンロード」から有効な.apkgが落とせる

### Phase5-6: リセットボタンの追加
- 実装物：App.tsxにリセットボタンを追加。押下でrows／warnings／uploadedSourceFiles／
hasScanned、およびPhase5-4で追加される生成ジョブ関連state（job_id・ポーリング状態等）を
すべて初期値に戻し、UploadPanelはkeyを変更して強制的に再マウントすることで、ファイル選択・
ルートパス入力・エラー表示などの内部stateも合わせてリセットする
- 依存：Phase5-5
- Done when：PDF選択・ルートパス・テーブル内容・生成ジョブの状態がすべて空の初期表示に戻る
- 備考：「テーブルだけ空にする」個別リセットは不要（行数が少なく個別削除で十分）という
まーくんの判断により、アプリ全体を白紙に戻す1ボタンのみとする。生成トリガーUI実装後に
着手するため、ジョブ状態も最初からリセット対象に含めて設計する

### Phase5-7: セクションテーブルの列幅調整
- 実装物：SectionTable.tsxに列境界のドラッグハンドルを追加し、<colgroup>＋
table-layout: fixedで列幅を可変にする。列幅はcolumnWidths: Record<列キー, number>という
単一state管理にし、将来バックエンドへの永続化に差し替えやすい形にしておく（今回は永続化しない）
- 依存：Phase5-2
- Done when：列境界をドラッグして幅を変更でき、セル編集など他の操作に影響しない
（リロードで初期幅に戻ってよい）

### Phase5-8: 入力値の視覚的バリデーション
- 実装物：SectionTable.tsxの各セルへの妥当性チェックと、赤枠・警告アイコン等の視覚的
フィードバック。対象は横断的に洗い出した以下の項目：
  - 終了ページ ＜ 開始ページ（今回の発端）
  - 節タイトルが空欄
  - 出力デッキ名が空欄、または空セグメントを含む（例："A::::B"、末尾が"::"で終わる等）
  - ソースファイル未選択
- 依存：Phase5-2
- Done when：上記いずれかに該当するセルが視覚的に警告表示される。バリデーションはあくまで
視覚的フィードバックであり、送信自体はブロックしない（生成開始時の最終防波堤はPhase4-3で
実装済みのサーバー側422のまま）

### Phase5-9: PDFドラッグ&ドロップアップロードエリア
- 実装物：UploadPanel.tsxのファイル選択部分を、角丸点線枠のドロップゾーンUIに置き換え
（ドラッグ&ドロップ・クリックでのファイル選択の両方に対応）
- 依存：Phase5-2
- Done when：PDFをドラッグ&ドロップでファイル選択でき、クリックでの選択も引き続き可能

### Phase5-10: ルートパス履歴機能（バックエンド）
- 実装物：
  - repositories/settings/root_path_history_repository.py（新規、SettingsRepositoryと
同じ構造のJSON永続化：backend/root_path_history.json）
  - GET /root-path-history
  - /scan成功時（ステータス200、sectionsが0件でも）に、使われたroot_pathを自動的に
履歴へ記録。直近5件、MRU順（既存の値が再度使われたら先頭に移動）、重複除外
- 依存：Phase4-1
- Done when：同じroot_pathで複数回スキャンしても履歴が重複せず先頭に移動し、直近5件を
超えた分は古い順に切り捨てられることをテストで確認
- 決定事項：インメモリのみ（JobStore/PdfStoreと同じ割り切り）ではなく、ファイル永続化を
採用する。理由：ルートパス履歴の主目的が「Windows PCと外出先のMacBook Air、どちらから
アクセスしても同じ履歴が見える」「日をまたいだデッキ表記の記憶補助」であり、Docker再起動を
またいで消えると本来の目的（過去のデッキ表記を確認しに行く手間を省く）を果たせないため
（まーくんとの合意事項）

### Phase5-11: ルートパス履歴機能（フロントエンド）
- 実装物：UploadPanel.tsx起動時にGET /root-path-historyを呼び、履歴一覧をルートパス
入力欄の<datalist>として選択可能にする
- 依存：Phase5-10
- Done when：異なる端末（別ブラウザ/シークレットウィンドウ等でシミュレート）からアクセス
しても同じ履歴が見える

### Phase5-12（旧Phase5-5、任意・小規模）: 設定UI（プロバイダー／モデルのみ）
- 実装物：components/SettingsPanel.tsx（provider/model選択のみ。科目リストUIは無し）
- 依存：Phase4-4

### Phase5-13（旧Phase5-6、任意・後回し、Phase2-7に連動）: ルートパス欄への科目自動サジェスト
- 実装物：Phase2-7が実装された場合に、スキャン結果から推定科目をルートパス欄にプリフィル表示

---
## Step 6: 結合＆実PDF検証

### Phase6-1: Docker Compose全体起動＋CORS配線
- 実装物：backend側CORSMiddleware設定、compose上でのポート・ネットワーク疎通確認
- 依存：Step0〜5すべて
- Done when：docker compose upのみでフロントエンドからバックエンドAPIに疎通する

### Phase6-2: サンプル実PDFでのE2E手動検証
- 実施内容：実際のCPAテキストPDF1冊分（複数章・各章複数節を含むもの）で、アップロード→
ルートパス入力→スキャン（章タイトルの検出精度を確認）→テーブル編集→生成（実Gemini APIキー
使用）→ダウンロード→Anki Desktopにインポートし、以下を目視確認：
  - 4段構成の見た目、PAGE_CODEでのソート/検索、タグ
  - デッキ階層がroot_path::章::節の3階層で正しく表示される
  - 再インポート時にデッキ・ノートが重複せず更新される（Phase1-3/1-2のバグ修正の実地確認）
  - 回答カードのクリックで、そのボックスのPNGスクリーンショットが実際にクリップボードへ
コピーされ、他アプリ（例：GoodNotes）に画像としてペーストできること、および
Clipboard画像非対応環境ではテキストコピーにフォールバックすること（Phase2-6のメディア
同梱の実地確認。ロジック自体は旧実装を移植したものなのでここでは主に「動くかどうか」を
確認する）
- 依存：Phase6-1
- Done when：手動チェックリストが全項目パスする（この時点でPhase2-7〜2-9、5-12、5-13などの
任意Phaseに着手してよい）

---
## 残る軽微な確認事項（ブロッキングではない前提で進める）

1. 「項」（第3階層の見出し）は章→節の2階層構造には含めず、旧仕様通り節と同レベル扱いとする
（Phase2-1）——階層を増やす要望があれば教えてほしい
2. CardContentは「1チャンクから複数カードを返すコンテナ」という解釈で進める（Phase1-2）
3. html2canvas.jsのベンダリング元・バージョン、成功アイコンのデザインは実装時に確定する
（Phase2-6）

---
（全34Phaseがタスクとして登録済み。任意Phase 2-7/2-8/2-9/5-12/5-13は除外、必要になった時点で追加）
