# Phase2-6: Ankiパッケージングリポジトリ

## 実装したもの

- `backend/app/repositories/anki/note_builder.py`：genankiに依存しない純粋ロジック。
  - `FIELD_NAMES`：genankiモデルの9フィールド（`TAGS`を除く）を、カードテンプレートの
    `{{FIELD}}`プレースホルダと同じ順序で定義。
  - `sanitize_tag`：タグ内の半角・全角スペースを`_`に置換。
  - `build_note_tags`：`Card.content.tags`をサニタイズし、`section_title`をサニタイズして
    追加タグとして常に付与。
  - `build_note_fields`：`Card.content`から`FIELD_NAMES`順のフィールド値リストを組み立て。
  - `group_cards_into_decks`：`Card`のリストを`deck_path`ごとにグルーピングし、Phase1-3の
    `Deck`集約（`add_card()`）を使って組み立てる。
  - genankiに一切依存しないため、サンドボックス内で直接実行して全13ケースを検証できた。
- `backend/app/repositories/anki/anki_package_repository.py`：`AnkiPackageRepository.
  build_package(cards: list[Card]) -> bytes`。`note_builder`の純粋ロジックを使い、
  genankiのModel/Note/Deck/Packageを組み立てて`.apkg`バイト列を返す薄い連携層。
  カードテンプレート（Front/Back HTML・CSS）はファイルから読み込み、一時ファイル経由で
  `.apkg`バイト列を取得する（genankiに`write_to_file`しか無いため）。
- `backend/app/card_templates/assets/`：
  - `_html2canvas.js`：npm経由でhtml2canvas 1.4.1（MITライセンス）を正規取得し
    バージョン固定でベンダリング。ライセンス全文を`_html2canvas.LICENSE.txt`として同梱。
  - `_success_icon.png`：外部素材のライセンス不明瞭さを避けるため、純粋Pythonで
    チェックマークアイコンを新規生成（64x64のRGBA PNG）。
- `backend/pyproject.toml`：`genanki>=0.13`を追加。
- テスト：`test_note_builder.py`（13ケース）、`test_anki_package_repository.py`
  （6ケース、`.apkg`をzip+sqlite3で実際に開いてフィールド・タグ・GUID・デッキID・
  メディア同梱を検証）。

## 修正した旧実装のバグ

1. **デッキIDの非決定性**：旧`anki_creator.py`の`deck_id = abs(hash(full_deck_name)) %
   10**10`はPython組込み`hash()`に依存しており、`PYTHONHASHSEED`次第でプロセスごとに
   異なる値になっていた。Phase1-3の`deterministic_deck_id`（MD5ベース）を採用し、
   同じ`deck_path`から常に同じデッキIDが得られるようにした。
2. **GUID衝突**：旧実装の`genanki.guid_for(TITLE + section_title)`は区切り文字なしの
   単純連結で、`TITLE="AB"+section="C"`と`TITLE="A"+section="BC"`が衝突し得た。
   Phase1-2の`Card.identity_key()`（制御文字`\x1f`区切り）を`genanki.guid_for()`の
   入力とすることで解消した。
3. **画像コピー機能のメディア未同梱**：旧実装は`anki_back_card_template.html`／
   `anki_card_style.css`が`_html2canvas.js`・`_success_icon.png`を参照していたにも
   関わらず、`genanki.Package`の`media_files`に一切追加しておらず、クリックで
   スクリーンショットをコピーする機能が実際には動作していなかった。V2ではこの2ファイルを
   実際に用意し、`package.media_files`に設定することで機能させた（`copyBox()`のJS/CSS
   ロジック自体は変更せずそのまま移植）。

## サンドボックスでは検証できなかった点とDocker実機での確認

`genanki`は依存関係が多く（`cached-property`／`frozendict`／`chevron`／`pyyaml`）、
このサンドボックスにインストールする現実的な手段が無かったため、以下2点は推測せず
Docker実機で確認してもらった（CLAUDE.mdの新ルールに基づく調査スクリプトを
`backend/tmp_samples/`に作成→実行依頼→結果確認→スクリプト削除、という手順を踏んだ）。

1. **`genanki.Package([])`（デッキ0件）の挙動**：例外を送出せず、`write_to_file()`も
   成功し、有効な`.apkg`（zip、`collection.anki2`＋`media`のみを含む）が生成されることを
   確認した。V2はセクション単位で失敗して中断する設計であり、将来0件のカードで
   ダウンロードが行われる可能性はゼロではないため、この結果を受けて
   `test_empty_card_list_still_produces_a_valid_apkg`は削除せずそのまま維持した。
2. **`.apkg`内のデッキ情報のスキーマ構造**：当初`test_deck_id_is_deterministic_not_
   process_random`は独立した`decks`テーブルを`SELECT id FROM decks WHERE name = ?`で
   問い合わせる想定で書いていたが、Docker実行で`no such table: decks`エラーとなった。
   調査の結果、デッキ情報は独立テーブルではなく、`col`テーブルの`decks`カラムに
   デッキIDをキーとしたJSON文字列として格納されていることが判明した。
   `AnkiPackageRepository`・`deterministic_deck_id`自体の実装は正しく
   （`expected deterministic_deck_id(Root::A) = 7426908785`と実際に格納されたIDが
   完全一致）、不具合はテストのSQLクエリ側にあったため、`col.decks`を読んで
   `json.loads()`でパースし、`name`が一致するエントリの`id`を検証する形に
   テストコードのみを修正した。

## 動作確認

- `note_builder.py`はgenankiに依存しないため、サンドボックス内で直接実行し全13ケースを
  確認済み。
- `anki_package_repository.py`とそのテストはDocker実機での確認が必要だった。
  開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、当初`test_deck_id_is_deterministic_
  not_process_random`が`no such table: decks`で1件失敗したが、上記の調査・修正を経て
  再実行し、`100 passed in 7.51s`を確認済み（Phase2-5完了時点の84件＋今回の16件）。

## ADR

デッキID・GUIDの決定的化はPhase1-2/1-3で既に決定済みの方針を適用したものであり、
モデルIDの新規採番（旧`1598273645`を再利用しない判断）を含め、ADRを起票するほどの
新たな分岐ではないと判断した。
