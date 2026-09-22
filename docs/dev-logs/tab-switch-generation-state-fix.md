# タブ切替時の生成進捗状態消失バグ修正

## 背景

Phase7-2-6の実機確認中に発見されたバグへの対応。Step7-2の各Phase自体には
紐づかない、単独のバグ修正のため、通常のPhase番号を冠したdev-logとは別
ファイルとして記録する。

## バグの内容

生成を開始した状態のまま「履歴」タブに切り替え、その後「メイン」タブに
戻ると、バックエンド側では生成が継続している（履歴タブでは正しく「生成中」
と表示される）にもかかわらず、メイン画面の進捗表示が「生成開始前」の見た目
に巻き戻ってしまう不具合。

## 原因

`App.tsx`は`{activeTab === 'main' && (...)}`という条件付きレンダリングで
タブの中身を出し分けている。`activeTab`が`'main'`以外になると、この中身
（`GenerationProgress`を含む）はReactツリーから完全に取り除かれ、コンポー
ネントごとアンマウントされる。

`jobId`・`status`・`isStarting`・`error`・`pollError`はいずれも
`GenerationProgress`内部の`useState`であり、ポーリング用の`useEffect`も
同コンポーネント内にあった。`App.tsx`側は`jobId`自体を一切保持しておらず、
ポーリング結果のコピー（`generationStatus`、`onStatusChange`コールバック
経由）を持っているのみで、これを`GenerationProgress`へpropsとして戻す
仕組みも無かった。そのため、`'main'`タブに戻ると`GenerationProgress`は
新規インスタンスとして`jobId: null`から再マウントされ、ポーリングも
再開されず、「生成開始前」の見た目になっていた。

この条件付きレンダリングの構造自体はPhase5-25（タブ化を導入したPhase）で
導入されて以来変更されておらず、Phase7-2-5で履歴タブに実用的な内容が入り
「生成中に他タブを見に行く」という操作が現実的になったことで、初めて
表面化したものと考えられる（詳細はPhase7-2-6のdev-log参照）。

## 対応方針（案2）

ポーリング処理・関連state・開始処理一式を`GenerationProgress`から
`App.tsx`へ丸ごと移設した。`GenerationProgress`は移設後、これらをpropsで
受け取って表示するだけの、表示専任のコンポーネントになった。

- `App.tsx`
  - 新規state：`jobId`・`isStartingGeneration`・`generationError`・
    `pollError`（`status`は既存の`generationStatus`をそのまま流用）
  - ポーリング用`useEffect`（`jobId`依存）を新設。`GenerationProgress`から
    移設した内容そのまま
  - `handleStartGeneration(sections, additionalPrompt)`を新設。
    `startGenerationJob()`を呼び、`jobId`/`isStartingGeneration`/
    `generationError`を更新
  - `performReset()`に`setJobId(null)`・`setGenerationError(null)`・
    `setPollError(null)`を追加（`resetKey`による強制再マウントに頼らず、
    明示的にクリアする必要が生じたため）
  - `<GenerationProgress>`へのprops：`jobId`・`status`・`isStarting`・
    `error`・`pollError`・`onStart`を渡す。`onStatusChange`propは廃止
- `frontend/src/components/GenerationProgress.tsx`
  - `jobId`/`status`/`isStarting`/`error`/`pollError`の`useState`と、
    ポーリング用`useEffect`、`handleStart()`本体を削除
  - `GenerationProgressProps`を新propsに合わせて変更
  - ボタンクリック時は`onStart(selectedRows.map(toSectionInput),
    additionalPrompt)`を呼ぶだけに変更
  - `additionalPrompt`のローカルstateはそのまま残した（`jobId`確定前のみ
    意味を持つ下書き入力であり、ポーリング等との結合が無いため）

これにより、`GenerationProgress`が（タブ切替で）アンマウントされても、
状態そのものは`App.tsx`側に残り続け、`'main'`に戻った際は現在の状態を
props経由でそのまま表示できるようになった。

## 副次的に解消された関連バグ

調査の過程で、同根の副次的な不具合が2件存在することが判明し、今回の対応で
あわせて解消された。

1. **リセットボタンの活性状態が他タブ閲覧中は更新されない**：リセット
   ボタンは`activeTab`に関わらず常にヘッダーに表示されており
   （`disabled={isGenerating(generationStatus)}`）、`generationStatus`に
   依存している。修正前はポーリングが`main`タブにいる間しか動かず、他の
   タブを見ている間は`generationStatus`が更新されないままだったため、
   実際にはジョブが完了していてもリセットボタンが「生成中」のまま無効化
   され続ける（またはその逆）ことがあった。ポーリングが常時動作する
   ようになったことで解消。
2. **ファビコン表示が他タブ閲覧中は更新されない**：Phase5-27で実装した
   タブファビコンの状態表示（`isCurrentlyGenerating`/
   `hasUndownloadedCompletion`）も`generationStatus`に依存しているため、
   同じ理由で他タブ閲覧中は更新が止まっていた。同様に解消。

## 変更ファイル

- `frontend/src/App.tsx`
- `frontend/src/components/GenerationProgress.tsx`

## ADR

今回はADRを書くレベルの設計判断はなし。
