# Phase5-14: セクションテーブルの全選択/全解除チェックボックス

## 何を実装したか

- `frontend/src/components/SectionTable.tsx`（修正）
  - チェックボックス列ヘッダー（`<th>`）に、行の選択状態と連動する全選択/全解除チェックボックスを追加。
  - 3状態（未選択／中間／全選択）は`rows`から毎レンダリング時に導出する（新規stateは持たない）：`allSelected = rows.length > 0 && rows.every(r => r.selected)`、`someSelected = rows.some(r => r.selected)`。
  - 中間状態（`indeterminate`）はHTMLのチェックボックスにおいてDOMプロパティであり、ReactのJSX propとしては直接指定できないため、`useRef`でヘッダーのチェックボックス要素を参照し、`useEffect`で`someSelected && !allSelected`を命令的に設定する。
  - クリック時の挙動：`allSelected`が`false`（未選択または一部選択）のときは全選択、`true`（全選択済み）のときは全解除に切り替える。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **Phase5-7（列幅調整）とは別Phaseとして切り出した**：見た目のレイアウト調整（Phase5-7）と選択ロジックの変更（本Phase）は関心事が異なるため。まーくんとの合意により、既存のPhase番号はスライドさせず末尾（Phase5-14）に追加した。
- **新規stateを持たず`rows`から導出する設計にした**：選択状態の唯一の情報源は各行の`SectionRow.selected`であり、ヘッダーチェックボックスの見た目はそこから計算できる派生値にすぎない。別のstateとして持たせると、行の選択操作とヘッダーの表示が食い違うバグの温床になるため、導出値のみで完結させた。

## ADR

今回はADRを書くレベルの設計判断はなし。
