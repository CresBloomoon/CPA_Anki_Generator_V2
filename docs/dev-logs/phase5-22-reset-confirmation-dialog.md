# Phase5-22: リセット時の未ダウンロード確認ダイアログ（C-2）

## 背景

APIコスト損失調査で洗い出したC-2（リセットボタンが未ダウンロードの完了・一部完了
ジョブを警告なしで破棄してしまう）への対応。B-1（Phase4-8／Phase5-21）と合わせて、
今回対応する2件のうちの2件目にあたる。

## 何を実装したか

- `frontend/src/components/DownloadButton.tsx`（修正）
  - `onDownloaded: () => void`propを追加。ダウンロードが実際に成功した
    直後（クリック時点ではない）に呼び出す。
- `frontend/src/App.tsx`（修正）
  - `hasDownloaded: boolean`（初期値`false`）のstateを追加。
  - 確認ダイアログの表示要否を判定する`doneCount`を、`generationStatus`
    の`section_jobs`から`'DONE'`または`'PARTIALLY_DONE'`でフィルタして
    算出。
  - 従来の`handleReset()`を実際のリセット処理のみを行う`performReset()`
    に切り出し、`hasDownloaded`のリセットも追加。
  - リセットボタンのクリックハンドラを`handleResetClick()`に変更。
    `doneCount > 0 && !hasDownloaded`のときのみ確認ダイアログ
    （`isResetConfirmOpen`）を開き、それ以外は従来通り即座に
    `performReset()`を実行する。
  - `Modal.tsx`を再利用した確認ダイアログを追加。タイトル「リセットの
    確認」、本文で完了件数と失われる旨を明示し、「キャンセル」
    （`secondaryButtonClasses`）／「リセットする」（`primaryButtonClasses`
    + `bg-red-600`）の2ボタンを配置。オーバーレイクリック・×ボタンは
    `Modal`の既存動作のまま「キャンセル」として機能する。
  - `<DownloadButton>`に`onDownloaded={() => setHasDownloaded(true)}`を
    配線。

## 実装中に発見したバグ・問題点

Todoリスト作成時点（実装前）で発見・報告済みの内容：まーくんから提示された
検出条件は`doneCount`を`'DONE'`のみでフィルタする内容だったが、
`DownloadButton.tsx`側の`doneCount`（Phase5-21で`'PARTIALLY_DONE'`を
含むよう拡張済み）とズレていた。このままだと、唯一のセクションが
`PARTIALLY_DONE`のケースでダウンロードボタンは表示されるにもかかわらず、
確認ダイアログは出ないまま即リセットされてしまい、C-2が防ごうとしている
シナリオそのものが再現してしまう。まーくんと相談の上、App.tsx側の
`doneCount`にも`'PARTIALLY_DONE'`を含める形で実装した。

## 大きな判断とその理由

- **`handleReset()`を`performReset()`（実処理）と`handleResetClick()`
  （確認要否の判定）に分離した**：ボタンのクリックハンドラが直接リセット
  処理を行う構造のままだと、確認ダイアログの分岐を挟む余地がなくなる。
  実処理と「実行するかどうかの判定」を分けることで、確認ダイアログの
  「リセットする」ボタン（`handleConfirmReset`）からも同じ`performReset()`
  を呼べるようにした。
- **`hasDownloaded`の差分追跡はしない（まーくんとの合意事項）**：一度
  ダウンロード済みの後にさらにセクションが完了しても、`hasDownloaded`は
  `true`のまま据え置く単純なフラグとした。より厳密には「ダウンロード後に
  追加で完了したセクションがあるか」を追跡する余地もあるが、リセット
  頻度・実運用上のリスクを踏まえてスコープ外とした。
- **オーバーレイクリック・×ボタンに専用の実装を追加しなかった**：
  `Modal.tsx`は元々`onClose`のみを呼ぶ設計であり、これは確認ダイアログの
  文脈では「キャンセル」（安全側のデフォルト動作）としてそのまま機能する。
  破壊的操作である「リセットする」は明示的なボタンクリックでしか
  発火しないため、追加の実装は不要と判断した。

## ADR

今回はADRを書くレベルの設計判断はなし。
