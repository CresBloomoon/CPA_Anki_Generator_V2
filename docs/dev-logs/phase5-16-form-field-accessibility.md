# Phase5-16: フォーム要素のアクセシビリティ対応（id/name＋sr-onlyラベル）

## 何を実装したか

- `frontend/src/components/SectionTable.tsx`（修正）
  - `fieldId(rowId: string, field: string): string`ヘルパーを新設。`row.id`
    （`createId()`由来、既存のReact keyと同じ発生源）とフィールド名から
    `section-${rowId}-${field}`という一意なidを生成する。配列indexではなく
    `row.id`を使うのは、行の削除・並べ替えでindexがずれても、既存の行に対応する
    idが安定して同じ値を指し続けるようにするため。
  - 各行の6要素（選択チェックボックス／節タイトル／開始ページ／終了ページ／
    出力デッキ名／ソースファイル）に`fieldId()`で生成したidを付与し、それぞれに
    視覚的には非表示（`sr-only`）の`<label htmlFor>`を紐付けた。列見出し
    （`<th>`）が既に視覚的に存在するため、セルごとに同じ文言を視覚的にも
    重複表示することはしていない。
- `frontend/src/components/UploadPanel.tsx`（修正）
  - 隠しファイル`<input type="file">`に`id="upload-panel-file-input"`を付与し、
    既存の（`htmlFor`未指定だった）「PDFファイル（複数選択可）」の`<label>`と
    紐付けた。
  - ルートパス`<input type="text">`に`id="upload-panel-root-path-input"`を付与し、
    既存の「ルートパス（例:...）」の`<label>`と紐付けた。
  - いずれも新規のラベル増設ではなく、既存の`<label>`テキストへの`htmlFor`追加
    のみ。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **id生成のキーに`row.id`を採用した**：`SectionTable`はPhase5-2の時点から
  行の識別に`row.id`（`createId()`由来）を使っており、Reactの`key`にも
  同じ値を使っている。配列indexを使う案も検討したが、行削除や並べ替えの
  たびにindexが別の行に「使い回される」ことになり、フォーカス位置の保持や
  DOM要素の同一性という観点で不安定になる。既に存在する安定したキーを
  そのまま流用するのが最も筋が良いと判断した。
- **ラベルはsr-onlyの`<label htmlFor>`で対応し、`aria-label`は採用しなかった**：
  `aria-label`の方が実装コストは若干低いが、`<label>`要素を使う方が支援技術との
  親和性が高い「王道」の実装であり、既存の列見出し（`<th>`）と組み合わせても
  破綻しない。まーくんとの相談の結果、SectionTable側はsr-onlyラベル方式で
  統一することにした。
- **列見出しと同じ文言を視覚的にも重複表示する案は採用しなかった**：
  `<th>`が既に列名を表示しているため、各セルに同じ文言を視覚的にも表示すると
  二重表示になりレイアウトが崩れる。視覚的には非表示（`sr-only`）のラベルで
  対応することで、見た目を変えずにアクセシビリティ上の関連付けだけを追加した。

## ADR

今回はADRを書くレベルの設計判断はなし。
