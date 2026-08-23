import { useEffect, useState } from 'react'
import { getAvailableModels, getSettings, updateSettings } from '../api/client'
import { primaryButtonClasses, textInputClasses } from '../styles'

const PROVIDER_LABELS: Record<string, string> = {
  gemini: 'Gemini',
  claude: 'Claude',
  openai: 'OpenAI',
}

interface SettingsPanelProps {
  // Called only after a successful save. The caller (App.tsx) closes the
  // modal and shows a toast; on failure this is not called, and the error
  // stays visible inline below (modal stays open).
  onSaved: () => void
}

export function SettingsPanel({ onSaved }: SettingsPanelProps) {
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>(
    {},
  )
  const [provider, setProvider] = useState('')
  const [modelName, setModelName] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getSettings(), getAvailableModels()])
      .then(([settings, models]) => {
        setAvailableModels(models.models)
        setProvider(settings.provider)
        setModelName(settings.model_name)
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setIsLoading(false))
  }, [])

  function handleProviderChange(nextProvider: string) {
    setProvider(nextProvider)
    // プロバイダーを切り替えたら、そのプロバイダーの先頭モデルに合わせる。
    // 前のプロバイダーのモデル名をそのまま残すと、存在しない組み合わせ
    // （例: provider=claude, model_name=gpt-5.5）になってしまうため。
    const nextModels = availableModels[nextProvider] ?? []
    setModelName(nextModels[0] ?? '')
  }

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      await updateSettings(provider, modelName)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return <p className="text-sm text-gray-500">設定を読み込み中...</p>
  }

  const modelOptions = availableModels[provider] ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="settings-provider"
            className="block text-sm text-gray-600"
          >
            プロバイダー
          </label>
          <select
            id="settings-provider"
            value={provider}
            onChange={(event) => handleProviderChange(event.target.value)}
            className={`mt-1 ${textInputClasses}`}
          >
            {Object.keys(availableModels).map((key) => (
              <option key={key} value={key}>
                {PROVIDER_LABELS[key] ?? key}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="settings-model" className="block text-sm text-gray-600">
            モデル
          </label>
          <select
            id="settings-model"
            value={modelName}
            onChange={(event) => setModelName(event.target.value)}
            className={`mt-1 ${textInputClasses}`}
          >
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className={`bg-blue-600 ${primaryButtonClasses}`}
        >
          {isSaving ? '保存中...' : '保存'}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
