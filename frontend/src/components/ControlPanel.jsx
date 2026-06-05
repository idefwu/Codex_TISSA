import { ChevronLeft, ChevronRight, Database, KeyRound, RefreshCw, SlidersHorizontal, X } from 'lucide-react'

const modelOptions = ['gpt-4o', 'gpt-5.5', 'gpt-5.4']

const moneyFormatter = new Intl.NumberFormat('zh-TW', {
  maximumFractionDigits: 0,
})

function ToggleControl({ checked, label, name, onChange }) {
  return (
    <label className="toggle-row">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(name, event.target.checked)}
      />
      <span className="toggle-track" aria-hidden="true" />
    </label>
  )
}

function SummaryCard({ label, value }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export function ControlPanel({
  collapsed,
  controls,
  dbSummary,
  llmHealth,
  mobileOpen,
  onCloseMobile,
  onRefreshDbSummary,
  onRefreshLlmHealth,
  onToggleCollapsed,
  onUpdateControl,
}) {
  const isCompact = collapsed && !mobileOpen
  const summary = dbSummary.data

  return (
    <aside className={`control-panel ${isCompact ? 'control-panel--collapsed' : ''} ${mobileOpen ? 'control-panel--mobile-open' : ''}`}>
      <div className="control-header">
        {!isCompact ? (
          <>
            <div>
              <p className="panel-kicker">Controls</p>
              <h2>Agent 設定</h2>
            </div>
            <button
              type="button"
              className="icon-button mobile-only"
              onClick={onCloseMobile}
              aria-label="關閉控制面板"
              title="關閉控制面板"
            >
              <X size={18} />
            </button>
          </>
        ) : null}
        <button
          type="button"
          className="icon-button desktop-only"
          onClick={onToggleCollapsed}
          aria-label={isCompact ? '展開控制面板' : '收合控制面板'}
          title={isCompact ? '展開控制面板' : '收合控制面板'}
        >
          {isCompact ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
      </div>

      {isCompact ? (
        <div className="collapsed-panel-icon" aria-hidden="true">
          <SlidersHorizontal size={18} />
        </div>
      ) : (
        <div className="control-content">
          <section className="db-summary-panel">
            <div className="db-summary-header">
              <div>
                <p className="panel-kicker">Database</p>
                <h3>DB 概況</h3>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={onRefreshDbSummary}
                aria-label="重新整理 DB 概況"
                title="重新整理 DB 概況"
              >
                <RefreshCw size={16} />
              </button>
            </div>

            {dbSummary.state === 'loading' ? (
              <div className="summary-state">
                <Database size={16} />
                載入中
              </div>
            ) : null}

            {dbSummary.state === 'error' ? (
              <div className="summary-state summary-state--error">
                <Database size={16} />
                {dbSummary.error}
              </div>
            ) : null}

            {summary ? (
              <div className="summary-grid">
                <SummaryCard label="員工" value={summary.employee_count} />
                <SummaryCard label="廠商" value={summary.vendor_count} />
                <SummaryCard label="費用筆數" value={summary.expense_count} />
                <SummaryCard label="發票" value={summary.invoice_count} />
                <SummaryCard label="費用總額" value={`${moneyFormatter.format(summary.expense_total)} ${summary.currency}`} />
                <SummaryCard label="發票總額" value={`${moneyFormatter.format(summary.invoice_total)} ${summary.currency}`} />
              </div>
            ) : null}
          </section>

          <section className="db-summary-panel">
            <div className="db-summary-header">
              <div>
                <p className="panel-kicker">OpenAI</p>
                <h3>LLM Health</h3>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={onRefreshLlmHealth}
                aria-label="重新檢查 LLM 狀態"
                title="重新檢查 LLM 狀態"
              >
                <RefreshCw size={16} />
              </button>
            </div>

            {llmHealth.state === 'checking' ? (
              <div className="summary-state">
                <KeyRound size={16} />
                檢查中
              </div>
            ) : null}

            {llmHealth.state === 'ready' ? (
              <div className="summary-state summary-state--success">
                <KeyRound size={16} />
                <span>API Key 已設定：{llmHealth.data?.masked_key ?? '已遮罩'}</span>
              </div>
            ) : null}

            {llmHealth.state === 'error' ? (
              <div className="summary-state summary-state--error">
                <KeyRound size={16} />
                <span>
                  {llmHealth.data?.masked_key ? `Key：${llmHealth.data.masked_key}，` : ''}
                  {llmHealth.error}
                </span>
              </div>
            ) : null}
          </section>

          <label className="field">
            <span>模型選擇或輸入</span>
            <input
              type="text"
              list="model-options"
              value={controls.model}
              onChange={(event) => onUpdateControl('model', event.target.value)}
            />
            <datalist id="model-options">
              {modelOptions.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
          </label>

          <label className="field">
            <span>Temperature：{Number(controls.temperature).toFixed(1)}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={controls.temperature}
              onChange={(event) => onUpdateControl('temperature', Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span>System Prompt</span>
            <textarea
              value={controls.systemPrompt}
              onChange={(event) => onUpdateControl('systemPrompt', event.target.value)}
              rows={4}
            />
          </label>

          <label className="field">
            <span>Memory 輪數：{controls.memoryRounds}</span>
            <input
              type="range"
              min="1"
              max="10"
              step="1"
              value={controls.memoryRounds}
              onChange={(event) => onUpdateControl('memoryRounds', Number(event.target.value))}
            />
          </label>

          <div className="toggle-group" aria-label="Agent 功能切換">
            <ToggleControl
              checked={controls.contextRouter}
              label="Enable Context Router"
              name="contextRouter"
              onChange={onUpdateControl}
            />
            <ToggleControl
              checked={controls.dbQuery}
              label="Enable DB Query"
              name="dbQuery"
              onChange={onUpdateControl}
            />
            <ToggleControl checked={controls.rag} label="Enable RAG" name="rag" onChange={onUpdateControl} />
            <ToggleControl
              checked={controls.imageSkill}
              label="Enable Image Skill"
              name="imageSkill"
              onChange={onUpdateControl}
            />
            <ToggleControl
              checked={controls.auditLog}
              label="Enable Audit Log"
              name="auditLog"
              onChange={onUpdateControl}
            />
          </div>
        </div>
      )}
    </aside>
  )
}
