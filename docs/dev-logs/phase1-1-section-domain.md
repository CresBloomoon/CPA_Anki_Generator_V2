# Phase1-1: ドメイン層 Section

## 実装したもの

- `backend/app/domain/section.py`
  - `PageRange`：`start_page`／任意の`end_page`を持つ値オブジェクト。`start_page >= 1`を検証。
    `end_page`は「次の節の開始ページ」に相当する排他的な上限として扱い（旧`pdf_parser.
    extract_text_from_range`の1始まり・終了排他の仕様を踏襲）、`start_page`以下の値は拒否する。
    `page_count()`は`end_page`が不明な場合は計算不能として`ValueError`を送出する（総ページ数を
    使ったフォールバック計算はPhase3-2のサブシュレッディングUsecase側の関心事であり、ドメインの
    純粋な値オブジェクトには持たせない）。
  - `DeckPath`：`"::"`区切りの値オブジェクト。空セグメントに加え、セグメント内に`"::"`が
    混入するケースも拒否する（`from_string()`で再分割した際に壊れるのを防ぐ）。
    `from_string()`／`child()`／`joined()`を持ち、`root_path.child(chapter_title).
    child(section_title)`のように連鎖させて使う。
  - `Section`：`title`（節タイトル）／`chapter_title`（章タイトル）／`page_range`／`deck_path`／
    `min_card_count`／`source_file`。空文字列・負のカード数を拒否する。「選択」チェックボックスは
    UI都合でありドメイン不変条件ではないため、エンティティ自体には持たせていない。
- `backend/tests/domain/test_section.py`：`PageRange`／`DeckPath`／`Section`それぞれの不正値
  拒否、`DeckPath`の連結、`PageRange.page_count()`の計算を網羅するpytestテスト（13ケース）。
- `backend/pyproject.toml`：`dev` extra（`pytest>=8.3`）と`[tool.pytest.ini_options]`
  （`pythonpath=["."]`）を追加し、パッケージを`pip install -e .[dev]`した状態でも
  `import app...`が通るようにした。

## 設計判断

- `PageRange.page_count()`は`end_page`不明時にフォールバック値（旧実装の`start_page+5`相当）を
  computeしない。そのフォールバックはPDF全体のページ数や分割ルールに依存するUsecase層の判断で
  あり、ドメインの値オブジェクトに持たせると責務が混ざるため。
- `DeckPath`のセグメントに`"::"`自体を含めることを禁止した。旧実装には無かったチェックだが、
  `child()`で組み立てたパスを`from_string()`で読み戻す場面（設定の保存・復元等）で
  セグメント数がずれる不具合を未然に防ぐための追加バリデーション。

## 発見した問題点

- `backend/Dockerfile`に`tests/`ディレクトリをコピーする行が漏れており、
  `docker compose run --rm backend pytest`が0件しかテストを検出できない不具合があった。
  - 原因：Phase0-1でDockerfileを書いた時点では`backend/tests/`自体が存在せず、
    `COPY pyproject.toml ./` と `COPY app ./app` のみで正しく完結していた。Phase1-1で
    `backend/tests/`を新規追加した際にDockerfileの見直しを行わなかったため発生した。
  - より根本的な原因：実装時のサンドボックス環境にDockerが無く、テストロジック自体の正しさは
    `app.domain.section`をサンドボックス内で直接importする手動検証で確認していたが、それは
    「実際のDockerイメージにテストファイルが含まれているか」を検証するものではなかった。
  - 対処：`backend/Dockerfile`に`COPY tests ./tests`を追加。開発者側で
    `docker compose run --rm backend sh -c "pip install -e .[dev] && pytest"`を実行し、
    `13 passed`を確認済み。
  - 教訓：新しいトップレベルディレクトリを追加した際は、Dockerfileの`COPY`一覧も併せて
    見直す。

## 動作確認

- 開発者側の実機で`docker compose run --rm backend sh -c "pip install -e .[dev] && pytest"`を
  実行し、`13 passed in 0.09s`を確認済み。

## ADR

`DeckPath`のセパレータ混入禁止、`PageRange.page_count()`のフォールバック非対応はいずれも
小規模な設計判断であり、ADRを起票するほどの分岐ではないと判断した。
