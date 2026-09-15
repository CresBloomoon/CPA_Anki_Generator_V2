import { useEffect, useState } from 'react'
import { UploadPanel } from './components/UploadPanel'
import { SectionTable, type SectionRow } from './components/SectionTable'
import { GenerationProgress } from './components/GenerationProgress'
import { SettingsPanel } from './components/SettingsPanel'
import { Toast } from './components/Toast'
import type {
  GenerationJobStatusResponse,
  ScanResponse,
  SectionScanResult,
} from './api/types'
import { createId } from './utils/id'
import { setFaviconIcon } from './utils/favicon'
import { secondaryButtonClasses } from './styles'

function toSectionRow(section: SectionScanResult): SectionRow {
  return {
    id: createId(),
    selected: true,
    title: section.title,
    start_page: section.start_page,
    end_page: section.end_page,
    deck_path: section.deck_path,
    source_file: section.source_file,
  }
}

// "生成中" = まだ完了しておらず、かつ1件も停止していない状態。
// 一部のセクションが失敗する(FAILED)、あるいは途中のブロックまでは
// 成功したが完走できなかった(PARTIALLY_DONE)と、
// StartGenerationJobUsecase.run() がそこで処理を打ち切り、残りは永遠に
// PENDINGのまま止まる(Phase3-3の設計)。この状態は「未完了」ではあるが
// 実質的には停止済みなので、生成中とは扱わない(扱うとリセット手段が
// 無くなり、ページリロードしか復帰方法が無くなってしまう)。
function isGenerating(status: GenerationJobStatusResponse | null): boolean {
  if (!status) return false
  if (status.is_complete) return false
  const hasStopped = status.section_jobs.some(
    (sectionJob) =>
      sectionJob.status === 'FAILED' ||
      sectionJob.status === 'PARTIALLY_DONE',
  )
  return !hasStopped
}

function App() {
  const [rows, setRows] = useState<SectionRow[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [uploadedSourceFiles, setUploadedSourceFiles] = useState<string[]>([])
  const [hasScanned, setHasScanned] = useState(false)
  const [generationStatus, setGenerationStatus] =
    useState<GenerationJobStatusResponse | null>(null)
  // Bumped on reset; used (with a distinct prefix per component -- see
  // below) as `key` for UploadPanel/GenerationProgress so React fully
  // remounts them, clearing their internal state (including
  // GenerationProgress's polling interval, via its effect cleanup) without
  // this component needing to know what's inside either of them. A shared
  // bare `resetKey` here previously caused two *sibling* elements to carry
  // the same key, which React silently mishandled (duplicated DOM instead
  // of cleanly remounting) -- hence the "upload-"/"progress-" prefixes.
  const [resetKey, setResetKey] = useState(0)
  const [activeTab, setActiveTab] = useState<'main' | 'settings' | 'history'>(
    'main',
  )
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  // Whether the current job's results have been downloaded at least once.
  // Reset to false on every performReset() -- see C-2's dev-log for why no
  // finer-grained "downloaded vs. newly completed since" tracking is done.
  const [hasDownloaded, setHasDownloaded] = useState(false)

  // Counts sections whose cards are actually downloadable (DONE or
  // PARTIALLY_DONE -- must match DownloadButton's own doneCount, otherwise
  // a job whose only section is PARTIALLY_DONE would show a download
  // button but skip the confirm-before-reset warning below).
  const doneCount =
    generationStatus?.section_jobs.filter(
      (sectionJob) =>
        sectionJob.status === 'DONE' || sectionJob.status === 'PARTIALLY_DONE',
    ).length ?? 0

  // Anything worth not losing to an accidental browser-level navigation
  // (back button, reload, closing the tab) -- scanned results exist from
  // here through generation and completion, until performReset() clears
  // rows again. See Phase5-24's dev-log for the incident this guards
  // against.
  const hasUnsavedProgress = rows.length > 0

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!hasUnsavedProgress) return
      // Both are set for cross-browser compatibility -- the exact
      // incantation browsers look for to trigger their own (non-
      // customizable) confirmation dialog has historically differed.
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedProgress])

  const isCurrentlyGenerating = isGenerating(generationStatus)

  // Phase5-27: drives the tab favicon (blue dot while generating, green dot
  // while there's downloadable output still sitting undownloaded). Neither
  // depends on tab visibility -- both are meant to be visible at a glance
  // regardless of whether the user is currently looking at the tab.
  const hasUndownloadedCompletion =
    !isCurrentlyGenerating && doneCount > 0 && !hasDownloaded

  const faviconIconKind = isCurrentlyGenerating
    ? 'generating'
    : hasUndownloadedCompletion
      ? 'completed'
      : null

  useEffect(() => {
    void setFaviconIcon(faviconIconKind)
  }, [faviconIconKind])

  function handleSettingsSaved() {
    // Phase5-25: settings moved from a modal to a tab -- stay on the
    // settings tab after saving (there's no "close" concept anymore) and
    // rely on the toast alone to confirm success.
    setToastMessage('保存しました')
  }

  function handleFilesUploaded(sourceFiles: string[]) {
    setUploadedSourceFiles((prev) =>
      Array.from(new Set([...prev, ...sourceFiles])),
    )
  }

  function performReset() {
    setRows([])
    setWarnings([])
    setUploadedSourceFiles([])
    setHasScanned(false)
    setGenerationStatus(null)
    setHasDownloaded(false)
    setResetKey((prev) => prev + 1)
  }

  function handleResetClick() {
    // Undownloaded completed cards would be discarded silently otherwise --
    // ask for confirmation first (see C-2's dev-log). Phase5-25: switched
    // from a custom Modal to the browser's own window.confirm() -- a
    // visually distinct (e.g. red) warning button was judged unnecessary
    // for this confirmation.
    if (doneCount > 0 && !hasDownloaded) {
      const confirmed = window.confirm(
        `完了したセクションが${doneCount}件ありますが、まだダウンロードしていません。このままリセットすると生成済みのカードは失われます。よろしいですか？`,
      )
      if (!confirmed) return
    }
    performReset()
  }

  function handleScanComplete(result: ScanResponse) {
    // 追記方式: 複数回に分けてアップロード・スキャンしても、既に手動編集・
    // 追加した行を消さない(まーくんとの合意事項)。warningsは直近の
    // スキャン結果のみを表示する(過去の警告を蓄積させると、既に対応済みの
    // 警告がいつまでも残ってしまうため)。
    setRows((prev) => [...prev, ...result.sections.map(toSectionRow)])
    setWarnings(result.warnings)
    setHasScanned(true)
  }

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: 'main', label: 'メイン' },
    { key: 'settings', label: '設定' },
    { key: 'history', label: '履歴' },
  ]

  return (
    <div className="min-h-screen bg-white p-8 text-gray-900">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">CPA Anki Generator V2</h1>
        <button
          type="button"
          onClick={handleResetClick}
          disabled={isGenerating(generationStatus)}
          title={
            isGenerating(generationStatus)
              ? '生成が完了するまでリセットできません'
              : undefined
          }
          className={secondaryButtonClasses}
        >
          リセット
        </button>
      </div>

      <div className="mb-6 flex gap-4 border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`-mb-px border-b-2 px-1 pb-2 text-sm font-medium ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {toastMessage && (
        <Toast message={toastMessage} onDismiss={() => setToastMessage(null)} />
      )}

      {activeTab === 'main' && (
        <>
          <UploadPanel
            key={`upload-${resetKey}`}
            onFilesUploaded={handleFilesUploaded}
            onScanComplete={handleScanComplete}
          />

          {warnings.length > 0 && (
            <ul className="mt-4 text-sm text-amber-700">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          {/*
            エラー(UploadPanel側のerrorステート)ともwarningsとも別枠の、
            あくまで情報提供のための空状態メッセージ。操作を妨げるもの
            ではないため、ボタンの無効化などは一切行わない。テーブルの
            「行を追加」から手動でセクションを積み上げられることも案内する。
          */}
          {hasScanned && rows.length === 0 && (
            <p className="mt-4 text-sm text-gray-500">
              セクションが見つかりませんでした。下の「行を追加」から手動で入力できます。
            </p>
          )}

          <SectionTable
            rows={rows}
            onRowsChange={setRows}
            sourceFileOptions={uploadedSourceFiles}
          />

          <GenerationProgress
            key={`progress-${resetKey}`}
            rows={rows}
            onStatusChange={setGenerationStatus}
            onDownloaded={() => setHasDownloaded(true)}
          />
        </>
      )}

      {activeTab === 'settings' && (
        <SettingsPanel onSaved={handleSettingsSaved} />
      )}

      {activeTab === 'history' && (
        <p className="text-sm text-gray-500">準備中です。</p>
      )}
    </div>
  )
}

export default App
