# Phase1-2: ドメイン層 CardContentとCard

## 実装したもの

- `backend/app/domain/card.py`
  - `CardContentItem`：AIが1件のカードとして返す10フィールド
    （`title`/`question`/`ronsho_body`/`kaisetsu_body`/`yo_suruni_body`/`ryui_body`/
    `rank_tanto`/`rank_ronbun`/`page_code`/`tags`）を持つ値オブジェクト。フィールド名は
    旧実装のJSONキー（`TITLE`等の大文字）ではなくPythonらしいsnake_caseにした——大文字キーとの
    対応付けはAIリポジトリ実装（Phase2-3）側の責務であり、ドメイン層に外部API/JSON契約の命名を
    持ち込まないため。`page_code`が空文字なら`ValueError`。
  - `CardContent`：1回の`generate_cards`呼び出し（＝1テキストチャンク）が生成する複数
    `CardContentItem`のコンテナ。`AiCardGeneratorRepository.generate_cards`の戻り値契約として
    使う（依頼書の型名は単数形だが、実際は1回のAI呼び出しから複数カードが返るため、コンテナ型
    として設計した）。
  - `Card`：`CardContentItem` + `section_title` + `deck_path`（Phase1-1の`DeckPath`）を合成した
    エンティティ。`identity_key()`は`TITLE`と`section_title`を非表示制御文字`\x1f`
    （Unit Separator）で結合する——旧`anki_creator.py`の`genanki.guid_for(TITLE + section_title)`
    （区切りなし連結）によるGUID衝突バグをここで明示的に修正した。
- `backend/tests/domain/test_card.py`：不正値の拒否、`identity_key()`の非衝突性・安定性を
  検証するpytestテスト（7ケース）。

## 設計判断

- `identity_key()`の区切り文字には`\x1f`（ASCII Unit Separator）を採用した。人間が読む
  ログ等ではなくgenanki GUID生成の入力にのみ使う値であるため、可読性より「実際のカード本文に
  絶対に出現しない」ことを優先した。
- `CardContentItem`のフィールド名をsnake_caseにしたことで、AI応答JSON（`TITLE`等の大文字
  キー）からこのドメインオブジェクトへの変換処理が必要になる。この変換はPhase2-2/2-3の
  AIリポジトリ実装側に置く。

## 動作確認

- 開発者側の実機で`docker compose run --rm backend sh -c "pip install -e .[dev] && pytest"`を
  実行し、`20 passed in 0.14s`を確認済み（Phase1-1の13件＋今回の7件で計20件、内訳と一致）。

## 発見した問題点

特になし（Phase1-1で発見したDockerfileのCOPY漏れは今回のテストファイル追加には影響しなかった
——`tests/`ディレクトリ自体は既にCOPY対象になっているため）。

## ADR

`identity_key()`の区切り文字選定、フィールド名のsnake_case化はいずれも小規模な設計判断であり、
ADRを起票するほどの分岐ではないと判断した。
