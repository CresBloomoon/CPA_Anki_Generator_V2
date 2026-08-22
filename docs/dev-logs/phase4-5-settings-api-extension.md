# Phase4-5: 設定APIの拡張（プロバイダー検証＋利用可能モデル一覧）

## 何を実装したか

- `backend/app/repositories/settings/available_models.py`（新規）
  - `AVAILABLE_MODELS_BY_PROVIDER: dict[str, list[str]]`。プロバイダー
    ごとの選択可能なモデル一覧をハードコードした定数（案A採用）：
    `gemini`（`gemini-2.5-flash`／`gemini-2.5-pro`）、`claude`
    （`claude-opus-5`／`claude-sonnet-5`／`claude-haiku-4-5`）、`openai`
    （`gpt-5.5`／`gpt-5-mini`）。このdictのキー一覧が、`AiProviderSettings`
    が受け付ける「既知のプロバイダー」の一次情報を兼ねる。
- `backend/app/repositories/settings/settings_repository.py`（修正）
  - `AiProviderSettings.__post_init__`に、`provider`が
    `AVAILABLE_MODELS_BY_PROVIDER`の既知の3プロバイダーのいずれかである
    ことを検証する処理を追加。空文字チェックに続けて行い、不一致の場合は
    対応プロバイダー一覧を含めた`ValueError`を送出する。`model_name`
    自体が一覧に含まれるかどうかまでは検証しない（今回確定した方針の
    スコープ外）。
- `backend/app/routes/schemas/settings.py`（修正）：`AvailableModelsResponse`
  （`models: dict[str, list[str]]`）を追加。
- `backend/app/routes/settings_routes.py`（修正）：`GET
  /settings/available-models`を新設。`AVAILABLE_MODELS_BY_PROVIDER`を
  そのままレスポンスに変換するだけの薄いルートで、状態を持たない純粋な
  定数の公開のため、`SettingsRepository`のような`Depends()`によるDIは
  行っていない。
- `backend/app/dependencies.py`（修正）：`get_ai_card_generator_repository()`
  が`SettingsRepository().load()`を呼ぶ箇所を`try/except ValueError`で
  囲み、`HTTPException(500)`に変換するようにした（詳細は下記「実装中に
  発見したバグ・問題点」を参照）。
- テスト
  - `tests/repositories/settings/test_available_models.py`（新規）：
    定数が既知の3プロバイダーちょうどを含むこと、各プロバイダーに
    最低1つ以上モデルがあることを確認。
  - `tests/repositories/settings/test_settings_repository.py`（修正）：
    `test_unknown_provider_raises`を追加（`"chatgpt"`という消費者向け
    製品名は内部識別子ではなく`ValueError`になることを確認）。既存の
    `test_load_reads_existing_file_written_by_something_else`が使っていた
    フィクスチャ（`provider: "chatgpt", model_name: "gpt-5"`）は、この
    検証追加によりもう構築できなくなるため、`provider: "openai",
    model_name: "gpt-5.5"`という実在する組み合わせに差し替えた。
  - `tests/routes/test_settings_routes.py`（修正）：`PUT /settings`に
    未知のプロバイダーを渡すと422になることを確認するテスト、`GET
    /settings/available-models`が3プロバイダー分のモデル一覧を返すことを
    確認するテストを追加。
  - `tests/repositories/ai/test_factory.py`（修正）：`test_unsupported_
    provider_raises`を削除（理由は下記）。

## 実装中に発見したバグ・問題点

- **`SettingsRepository.load()`が未知プロバイダーで`ValueError`を送出する
  ようになったことで、`get_ai_card_generator_repository()`の中で
  ハンドリング漏れが生じていた**：実機（Docker）でのpytest実行で
  `tests/test_dependencies.py::TestBuildAiRepository::
  test_unsupported_provider_raises_500`が失敗して発覚した。このテストは
  もともと`AiProviderSettings(provider="unknown-provider", ...)`を直接
  構築してから`_build_ai_repository()`に渡し、`HTTPException(500)`に
  変換されることを確認していた。しかし今回の検証追加により、この行自体が
  `_build_ai_repository()`に到達する前に`ValueError`を送出するように
  なり、テストの前提が成立しなくなった。
  - 単にテストを削除するだけでは済まない問題だと判断した。
    `_build_ai_repository()`は既に検証済みの`AiProviderSettings`を
    受け取る前提の関数なので、「未知プロバイダー」は確かにもう
    ここには到達し得ない。しかし**`get_ai_card_generator_repository()`
    が`SettingsRepository().load()`で`settings.json`を直接パースする
    箇所は依然として実在するパス**であり、もし`settings.json`に
    このバリデーション追加前の古いプロバイダー名や、手動編集による
    不正な値が残っていた場合、`load()`内の`AiProviderSettings`構築で
    `ValueError`が送出される。この呼び出しは`_build_ai_repository()`の
    `try/except`の外側にあったため、素の`ValueError`がFastAPIまで
    伝播し、意図しない生の500（詳細メッセージのない一般的なエラー）に
    なってしまう回帰を生んでいた。
  - `get_ai_card_generator_repository()`内で`SettingsRepository().load()`
    呼び出しを`try/except ValueError`で囲み、`_build_ai_repository()`と
    同じ形の`HTTPException(status_code=500, detail=str(exc))`に変換する
    よう修正した。
  - `tests/test_dependencies.py`のテストは、もう再現できなくなった
    「`_build_ai_repository()`に未知プロバイダーを直接渡す」パターンを
    削除し、代わりに`get_ai_card_generator_repository()`を対象に
    「`settings.json`に未知プロバイダーが残っている」という実際に
    起こり得るシナリオでテストし直した（`monkeypatch`で
    `app.dependencies.SettingsRepository`を`tmp_path`ベースの
    インスタンスに差し替え、本物の`settings.json`には触れない）。

## 大きな判断とその理由

- **`AiCardGeneratorFactory`の`UnsupportedProviderError`を検証していた
  既存テストを削除した**：このテストは`AiProviderSettings(provider=
  "chatgpt", ...)`を構築してから`factory.create()`に渡し、
  `UnsupportedProviderError`が送出されることを確認していた。今回
  `AiProviderSettings`自体が未知のプロバイダーを拒否するようになった
  ため、この行は`factory.create()`に到達する前に`ValueError`を送出する
  ようになり、テストの前提が成立しなくなった。この検証の実質的な内容
  （`"chatgpt"`が内部識別子として認識されないこと）は
  `test_settings_repository.py`の`test_unknown_provider_raises`に
  引き継いだ。
  - `factory.py`の`UnsupportedProviderError`自体は削除していない。
    `AiProviderSettings`が受け付ける既知プロバイダー一覧
    （`AVAILABLE_MODELS_BY_PROVIDER`のキー）と、`Factory.create()`が
    実際に分岐を持つプロバイダーは、現状は完全に一致しているが、
    将来どちらか一方だけが更新されて食い違うことは起こり得る
    （例：`available_models.py`に新プロバイダーを追加したが
    `factory.py`に分岐を足し忘れる）。そのための防御的なフォール
    バックとして`UnsupportedProviderError`自体は残したが、現状の
    構成ではこの分岐へ到達する現実的なテストシナリオを作れない
    （`AiProviderSettings`を経由する限り到達しない）ため、専用の
    テストは追加しなかった。
- **モデル一覧の一次情報を`available_models.py`の1箇所に集約した**：
  「既知のプロバイダー」という概念は、`AiProviderSettings`の検証と
  `GET /settings/available-models`のレスポンスの両方で必要になる。
  この2箇所が別々に「gemini/claude/openai」というリストを持つと
  いずれ食い違うリスクがあるため、`AVAILABLE_MODELS_BY_PROVIDER`の
  キー一覧を両方から参照する単一の一次情報にした。
- **`GET /settings/available-models`は`Depends()`によるDIを使わない
  薄いルートにした**：この定数はリクエストごとに変化せず、テスト時に
  差し替える必要もない（`SettingsRepository`のようにファイルI/Oを
  持たない、コード内に直接定義された値のため）。DIを導入する意味が
  ないため、モジュールレベルの定数を直接importして返すだけの実装に
  した。

## ADR

今回はADRを書くレベルの設計判断はなし。
