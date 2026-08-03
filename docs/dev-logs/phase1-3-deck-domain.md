# Phase1-3: ドメイン層 Deck

## 実装したもの

- `backend/app/domain/deck.py`
  - `deterministic_deck_id(deck_path)`：`deck_path.joined()`をMD5でハッシュ化し先頭を
    10桁の整数に変換する純粋関数。旧`anki_creator.py`の`abs(hash(full_deck_name)) %
    10**10`（Python組込み`hash()`はプロセスごとに`PYTHONHASHSEED`でランダム化される）を、
    同じ`deck_path`なら常に同じIDを返す実装に置き換えた。
  - `Deck`：可変アグリゲート（`deck_path` + `cards: list[Card]`）。`add_card(card)`は
    `card.deck_path`が自分の`deck_path`と一致しない場合`ValueError`を送出する。
- `backend/tests/domain/test_deck.py`：5ケース。特に`test_stable_across_python_hash_seeds`は、
  `PYTHONHASHSEED`を`0`/`1`/`12345`と変えたsubprocessを3回起動し、`deterministic_deck_id`が
  常に同じ値を返すことを検証する——旧バグ（`hash()`の非決定性）そのものをピンポイントで
  再現・防止する回帰テスト。

## 設計判断

- `Deck`は`Section`/`Card`とは異なり`frozen`にしていない。カードが順次追加されていく
  ライフサイクルを持つアグリゲートルートとして扱い、状態変更は`add_card()`という振る舞い
  メソッド経由のみに限定する方針とした（値オブジェクトは不変、識別・ライフサイクルを持つ
  アグリゲートは可変、という役割分担）。この方針はPhase1-4の`GenerationJob`（状態遷移
  メソッドを持つ）でも踏襲する。
- `deterministic_deck_id`はMD5を採用。暗号学的な安全性は不要で、単に「同じ入力から常に
  同じ出力」という決定性のみが目的のため、標準ライブラリで手軽に使えるMD5で十分と判断した。

## 動作確認

- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend sh -c
  "pip install -e .[dev] && pytest"`を実行し、`25 passed in 0.67s`を確認済み
  （Phase1-1〜1-2の20件＋今回の5件）。

## 発見した問題点

特になし。

## ADR

MD5採用、`Deck`を可変アグリゲートとする判断はいずれも小規模な設計判断であり、ADRを
起票するほどの分岐ではないと判断した。
