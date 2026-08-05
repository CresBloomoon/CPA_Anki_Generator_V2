# Phase2-2: AI抽象化の骨組み

## 実装したもの

- `backend/app/repositories/ai/dto.py`：`PromptContext`（`section_title`／`additional_prompt`）。
  依頼書の`generate_cards(section_text, prompt_context) -> CardContent`という抽象インター
  フェースの第2引数に相当する、プロバイダー非依存の文脈値オブジェクト。
- `backend/app/repositories/ai/base.py`：`AiCardGeneratorRepository`抽象基底クラス
  （`abc.ABC`）。`generate_cards`のみを抽象メソッドとして定義し、各プロバイダー固有の
  構造化出力強制方式（Geminiの`response_mime_type`等）はPhase2-3以降の具象実装に委ねる。
- `backend/app/repositories/ai/prompt_builder.py`：`PromptBuilder`。旧`ai_client.
  get_base_prompt`と同じ構成順序（project_constitution.md → HTMLテンプレート説明 →
  Front/Backテンプレート → anki_generation.md本文（`${text_chunk}`を`string.Template`で
  置換）→ 任意の追加指示）を踏襲。ファイルパスはコンストラクタ引数で差し替え可能にして
  おり、テストではデフォルトの実ファイルを読ませて検証している。
- `backend/app/prompts/project_constitution.md`・`anki_generation.md`、
  `backend/app/card_templates/anki_front_card_template.html`・
  `anki_back_card_template.html`・`anki_card_style.css`：旧リポジトリから`diff`で
  完全一致を確認した上でそのままコピー（内容の変更は一切なし）。
- `backend/tests/repositories/ai/test_base.py`・`test_prompt_builder.py`：抽象クラスが
  直接インスタンス化できないこと、具象サブクラスが正しく動作すること、`PromptBuilder`の
  出力に憲法・Front・Back・出力フォーマット指示・本文テキストが期待順序で含まれること、
  追加指示の有無で出力が切り替わることを検証。

## 設計判断

- `PromptContext`は現時点で`section_title`を保持しているが、`PromptBuilder`自体は
  まだこれをプロンプト本文に使っていない（旧実装が使っていなかったため、忠実な移植を
  優先し、プロンプト内容自体は変更しなかった）。カードへの`section_title`付与は
  usecase層（Phase3-2）が`Section`から直接行う設計であり、`PromptContext`の
  `section_title`は将来のプロンプト改善に備えたプレースホルダという位置づけ。

## 実装中に発見した設計上の課題

`PromptContext.section_title`が、実際にAIへ渡されるプロンプト（`PromptBuilder.build()`の
出力）に一切反映されていないことが判明した。旧`ai_client.py`も同様に節タイトルをAIへ
渡していなかったため、Phase2-2では忠実な移植を優先し、プロンプト内容自体は変更していない。

しかし、AIが「どの節の話をしているか」を知らないまま本文だけでカードを生成している状態は、
正確性（依頼書の要件）の観点で改善余地がある可能性が高いと判断した。この対応は
Phase3-2（セクション単位カード生成Usecase、`Section`から`PromptContext`を組み立てる工程）
で改めて検討・実装することとする。この決定は
`docs/specs/cpa-anki-generator-v2-phase-plan.md`のPhase3-2項目に追記済み。

## 動作確認

- サンドボックス内で`PromptBuilder`と`AiCardGeneratorRepository`のテストと同一の
  ロジックを直接実行し、全ケースを確認済み。
- 開発者側の実機で`docker compose run --rm backend sh -c "pip install -e .[dev] &&
  pytest"`を実行し、`59 passed`を確認済み（Phase2-1完了時点の54件＋今回の5件）。

## ADR

今回の判断（`PromptContext.section_title`を現時点で未使用のまま保持する判断）は
小規模なものであり、ADRを起票するほどの分岐ではないと判断した。対応の要否・方針は
上記の通りPhase3-2着手時に検討する。
