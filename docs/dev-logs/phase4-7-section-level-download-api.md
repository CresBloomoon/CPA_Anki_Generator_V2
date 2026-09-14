# Phase4-7: セクション単位ダウンロードAPI

## 背景

Phase5-17〜5-20（生成進捗の表形式化＋セクション単位ダウンロード）の一部として、
完了・一部完了したセクション単体を`.apkg`としてダウンロードできるAPIを追加する。
現状把握の結果、`AnkiPackageRepository.build_package(cards)`が既にセクションと
いう概念を知らない汎用実装（渡されたカードを`deck_path`でグルーピングして
パッケージ化するだけ）であることを確認し、無改修で流用できる見込みが立った。
実際のUI（ダウンロードボタンの表示等）はPhase5-26で別途実装するため、
本Phaseはバックエンドのみのスコープとする。

## 何を実装したか

- `backend/app/usecases/build_anki_package_usecase.py`（修正）
  - `SectionIndexNotFoundError`／`SectionNotDownloadableError`の2例外を新設
  - `execute_for_section(job, section_index) -> AnkiPackageResult`を追加。
    `section_index`が範囲外（負の値含む）なら`SectionIndexNotFoundError`、
    対象セクションが`DONE`／`PARTIALLY_DONE`以外なら
    `SectionNotDownloadableError`を送出する。それ以外は、そのセクションの
    `cards`のみを`AnkiPackageRepository.build_package()`に渡す
- `backend/app/routes/generation_routes.py`（修正）
  - `_build_apkg_response()`ヘルパーを新設し、`Response`組み立て
    （`Content-Disposition`ヘッダー付与等）を既存の`download_generation_
    job_package`と共通化
  - 新規ルート`GET /generation-jobs/{job_id}/sections/{section_index}/
    download`を追加。`JobNotFoundError`／`SectionIndexNotFoundError`を
    404、`SectionNotDownloadableError`を409にマッピング。ファイル名は
    `generated_section.apkg`／`generated_section_partial.apkg`（汎用名）
- テスト
  - `tests/usecases/test_build_anki_package_usecase.py`（修正）：
    `TestExecuteForSection`クラスを追加。`DONE`／`PARTIALLY_DONE`での
    正常系（他セクションのカードが混ざらないことの確認込み）、
    `PENDING`／`RUNNING`／カード0件の`FAILED`での
    `SectionNotDownloadableError`、範囲外（正の値・負の値）での
    `SectionIndexNotFoundError`を検証
  - `tests/routes/test_generation_routes.py`（修正）：
    `TestDownloadGenerationJobSectionPackage`クラスを追加。正常系、
    未知の`job_id`（404）、範囲外の`section_index`（404）、未完了
    セクションへのアクセス（409、`_FakeAiRepository`の`release_event`
    でジョブを意図的に`RUNNING`のまま保持して検証）を確認

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **`section_index`は配列インデックスのまま採用し、`section_id`は新設し
  なかった**：`GenerationJob`の既存のミューテーションメソッド
  （`mark_running`等）がすべて配列インデックスでセクションを指定する
  設計に既に統一されており、フロントエンドも配列インデックスをReactの
  keyの一部として使っている。ここだけ`section_id`を新設すると、
  `SectionJob`へのフィールド追加からフロントエンドでの追跡方法の変更
  まで波及し、今回のスコープに対して不釣り合いに大きくなるため見送った
- **`section_index`の範囲チェックを明示的に行った**：Pythonのリストは
  負のインデックスを許容する（`-1`は最後の要素）ため、`job.section_
  jobs[section_index]`を無防備に呼ぶと、範囲外のはずの負の値が
  エラーにならず、意図しない別のセクションを黙って返してしまう。
  `section_index < 0`を明示的に弾く実装とした
- **`SectionNotDownloadableError`を409にマッピングした**：Phase4-9で
  `DuplicateGenerationJobError`／`PdfContentMismatchError`を409に
  マッピングした前例と語彙を揃え、「現在の状態が要求された操作と
  競合する」という意味で一貫させた
- **ファイル名は節タイトルを埋め込まず、汎用名にした**：節タイトルには
  ファイル名として安全でない文字（`::`等）が含まれうるため、
  サニタイズが必要になる。これはPhase5-26（実際のUI/UX）側の関心事に
  近いと判断し、今回は`generated_section.apkg`等の汎用名で済ませた

## ADR

今回はADRを書くレベルの設計判断はなし。
