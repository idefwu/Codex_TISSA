import { ChevronLeft, ChevronRight, SlidersHorizontal, X } from 'lucide-react'

const modelOptions = ['gpt-4o', 'gpt-5.5', 'gpt-5.4']

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

export function ControlPanel({
  collapsed,
  controls,
  mobileOpen,
  onCloseMobile,
  onToggleCollapsed,
  onUpdateControl,
}) {
  const isCompact = collapsed && !mobileOpen

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
          <label className="field">
            <span>模型選擇</span>
            <select value={controls.model} onChange={(event) => onUpdateControl('model', event.target.value)}>
              {modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
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
