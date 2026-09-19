# Phase7-2-6: root_pathのフロントエンド配線

## 背景

Step7-2（履歴機能）の最後のPhase。バックエンド側は既にPhase7-2-1で
`GenerationJob`/`StartGenerationRequest`に`root_path`フィールドを受け
入れる準備が完了していたが、フロントエンドが一度もこの値を送信しておらず、
`UploadPanel`のローカルstateに閉じ込められたままだった。そのため、
Phase7-2-5で作った履歴タブの見出しは常に「ジョブ{job_id先頭8文字}」という
フォールバック表示のままになっていた。

現状把握の結果、`root_path`は`UploadPanel`→`App.tsx`→`GenerationProgress`
→`startGenerationJob()`というバケツリレーが必要であることを確認し、
まーくんとA案（既存の`onScanComplete`コールバックの引数に`rootPath`も
含めて渡す）で合意した上で実装した。

## 何を実装したか

- `frontend/src/components/UploadPanel.tsx`（修正）
  - `UploadPanelProps.onScanComplete`のシグネチャを`(result: ScanResponse)
    => void`から`(result: ScanResponse, rootPath: string) => void`に拡張。
    `ScanResponse`自体はバックエンドの`/scan`レスポンスを1:1で鏡写しした
    型のため、`rootPath`をそこに混ぜず別引数として渡す設計にした
  - `handleScan()`内で`onScanComplete(scanResult, rootPath.trim())`を呼ぶ
    よう変更
- `frontend/src/App.tsx`（修正）
  - 新規state`rootPath: string`（初期値`''`）を追加
  - `handleScanComplete(result, scannedRootPath)`で`setRootPath(scanned
    RootPath)`を呼ぶよう拡張
  - `performReset()`に`setRootPath('')`を追加
  - `<GenerationProgress>`に`rootPath={rootPath}`propを追加
- `frontend/src/components/GenerationProgress.tsx`（修正）
  - `GenerationProgressProps`に`rootPath: string`を追加
  - `startGenerationJob()`呼び出しに`rootPath`を渡すよう変更
- `frontend/src/api/client.ts`（修正）
  - `startGenerationJob(sections, additionalPrompt)`を`startGeneration
    Job(sections, additionalPrompt, rootPath)`に拡張し、リクエストボディに
    `root_path: rootPath`を追加
- `frontend/src/api/types.ts`（修正）
  - `StartGenerationRequest`インターフェースに`root_path: string`を追加
    （バックエンドの同名Pydanticモデルには既にあったが、フロント側の
    ミラー型に漏れていたことを現状把握で発見・修正）
- `frontend/src/components/HistoryPanel.tsx`：無改修。`jobHeading()`の
  `job.root_path || \`ジョブ ${job.job_id.slice(0, 8)}\``というロジックが
  既に非空の`root_path`を正しく扱える作りだったため、変更不要だった

## 実装中に発見したバグ・問題点

### `StartGenerationRequest`（フロント側の型）に`root_path`が欠落していた

現状把握の過程で、バックエンドの`StartGenerationRequest`Pydanticモデルには
Phase7-2-1で`root_path: str = ""`が既に追加されていたにもかかわらず、
フロント側の同名インターフェース（`api/types.ts`）には追加されていな
かったことが判明した。これまで`root_path`を送信する経路自体が無かったため
実害は顕在化していなかったが、本Phaseで追加した。

### タブ切り替えによる生成中状態の消失（Phase7-2-6の修正対象外）

まーくんの実機確認で、生成中に「履歴」タブへ切り替えてから「メイン」タブ
に戻ると、バックエンドでは生成が継続している（履歴タブでは正しく「生成中」
と表示される）にもかかわらず、メイン画面が「生成開始前」の見た目に戻って
しまう不具合が発見された。

調査の結果、原因は`App.tsx`のタブ切り替えロジックにあることを確認した。
`{activeTab === 'main' && (<>...<GenerationProgress /></>)}`という条件付き
レンダリングのため、`activeTab`が`'main'`以外になると`GenerationProgress`
はReactツリーから完全に取り除かれてアンマウントされる。`jobId`・`status`
等はいずれも`GenerationProgress`内部の`useState`であり、`App.tsx`側は
`jobId`自体を一切保持していない（`generationStatus`はコピーを保持している
が、`GenerationProgress`へprops経由で戻す仕組みが無い）ため、`'main'`タブ
に戻ると`GenerationProgress`は新規インスタンスとして`jobId: null`から再
マウントされ、ポーリングも再開されない。

この条件付きレンダリングの構造自体は**Phase5-25**（2026-09-09、タブ化を
導入したPhase）で導入されて以来、一度も変更されていないことを`git show`
で確認した。Phase7-2-5・Phase7-2-6のどちらも、この構造自体には手を入れて
いない。Phase5-25時点から論理的には存在し得たバグだが、当時は「履歴」
タブが「準備中です」という固定テキストのみで、生成中にわざわざ他タブを
覗く理由が実用上無かったため表面化しなかった。Phase7-2-5で履歴タブに
「自分のジョブが今どうなっているか確認する」という、まさに生成中に見に
行きたくなる実用的な機能が入ったことで、初めて「生成中にタブを行き来する」
という操作が現実的に発生するようになり、今回顕在化したものと判断した。

このバグはPhase7-2-6の変更（`root_path`の配線）とは無関係であることを
確認済みのため、本Phaseの修正対象には含めない。別タスクとして切り分けて
対応する。

## 大きな判断とその理由

- **`rootPath`を`ScanResponse`に含めず、`onScanComplete`の第2引数として
  別出しした**：`ScanResponse`はバックエンドの`/scan`レスポンスを1:1で
  鏡写しした型という既存の原則（`api/types.ts`のコメント参照）があり、
  フロント内部だけで完結する値をそこに混ぜると、その原則が崩れるため
- **スキャン後にルートパス入力欄を編集しても、生成開始時の値には反映
  されない仕様を許容した**：`root_path`は生成そのものには使われず、履歴
  一覧の見出し表示専用の値であるため、既存の`deck_path`（スキャン時に
  自動生成され、その後行ごとに編集可能だが、編集してもルートパス自体の
  再計算はされない）と同種の性質として扱って問題ないと判断した
  （まーくんとの合意事項）
- **複数回スキャンした場合、`rootPath`は直近のスキャン値で上書き（後勝ち）
  にした**：`warnings`が既に同じ「直近のみ表示」という扱いになっており、
  一貫させた。表示専用の値のため実害が無いこともまーくんと確認済み

## ADR

今回はADRを書くレベルの設計判断はなし。
